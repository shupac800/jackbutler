import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import guitarpro

from jackbutler.parsing.models import (
    ParsedBeat,
    ParsedMeasure,
    ParsedNote,
    ParsedSong,
    ParsedTrack,
)
from jackbutler.parsing.pitch import fret_to_midi, midi_to_pitch


# Duration type value → quarter-note multiplier (pyguitarpro legacy format)
_DURATION_MAP = {
    -2: 16.0,   # longa
    -1: 8.0,    # whole × 2
    0: 4.0,     # whole
    1: 2.0,     # half
    2: 1.0,     # quarter
    4: 0.5,     # eighth
    8: 0.25,    # sixteenth
    16: 0.125,  # thirty-second
    32: 0.0625, # sixty-fourth
}

# GP7+ XML NoteValue name → quarter-note multiplier
_GP7_DURATION_MAP = {
    "Whole": 4.0,
    "Half": 2.0,
    "Quarter": 1.0,
    "Eighth": 0.5,
    "16th": 0.25,
    "32nd": 0.125,
    "64th": 0.0625,
}


def _quarter_length(duration: guitarpro.models.Duration) -> float:
    base = _DURATION_MAP.get(duration.value, 1.0)
    if duration.isDotted:
        base *= 1.5
    tuplet = duration.tuplet
    if tuplet.enters != 0 and tuplet.times != 0:
        base *= tuplet.times / tuplet.enters
    return base


def _is_gp7_zip(file_bytes: bytes) -> bool:
    """Check if the file is a GP7+ ZIP archive."""
    return file_bytes[:2] == b"PK"


class GPParser:
    """Parse Guitar Pro files into our domain models."""

    @staticmethod
    def parse(file_bytes: bytes, filename: str) -> ParsedSong:
        if _is_gp7_zip(file_bytes):
            return _parse_gp7(file_bytes)
        return _parse_legacy(file_bytes, filename)


def _parse_legacy(file_bytes: bytes, filename: str) -> ParsedSong:
    """Parse GP3/GP4/GP5 files via pyguitarpro."""
    suffix = Path(filename).suffix or ".gp5"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp.flush()
        song = guitarpro.parse(tmp.name)

    tracks: list[ParsedTrack] = []
    for track_idx, track in enumerate(song.tracks):
        if track.isPercussionTrack:
            tracks.append(ParsedTrack(
                name=track.name,
                index=track_idx,
                is_percussion=True,
                tuning=[],
                measures=[],
            ))
            continue

        tuning = [s.value for s in track.strings]

        measures: list[ParsedMeasure] = []
        for measure_idx, measure in enumerate(track.measures):
            header = measure.header
            time_sig = f"{header.timeSignature.numerator}/{header.timeSignature.denominator.value}"

            beats_out: list[ParsedBeat] = []

            for voice in measure.voices:
                pos = 1.0
                for beat in voice.beats:
                    ql = _quarter_length(beat.duration)
                    notes_out: list[ParsedNote] = []

                    for gp_note in beat.notes:
                        string_idx = gp_note.string  # 1-indexed
                        if string_idx < 1 or string_idx > len(tuning):
                            continue
                        string_midi = tuning[string_idx - 1]
                        midi = fret_to_midi(gp_note.value, string_midi)
                        is_tied = gp_note.type == guitarpro.NoteType.tie
                        notes_out.append(ParsedNote(
                            midi=midi,
                            pitch_name=midi_to_pitch(midi),
                            string=string_idx,
                            fret=gp_note.value,
                            is_tied=is_tied,
                        ))

                    if notes_out:
                        beats_out.append(ParsedBeat(
                            notes=notes_out,
                            start=pos,
                            duration=ql,
                        ))
                    pos += ql

            measures.append(ParsedMeasure(
                number=measure_idx + 1,
                time_sig=time_sig,
                beats=beats_out,
            ))

        tracks.append(ParsedTrack(
            name=track.name,
            index=track_idx,
            is_percussion=False,
            tuning=tuning,
            measures=measures,
        ))

    return ParsedSong(
        title=song.title or "Untitled",
        artist=song.artist or "Unknown",
        tracks=tracks,
    )


def _parse_gp7(file_bytes: bytes) -> ParsedSong:
    """Parse GP7/GP8 files (ZIP with GPIF XML)."""
    import io

    zf = zipfile.ZipFile(io.BytesIO(file_bytes))
    gpif_xml = zf.read("Content/score.gpif").decode("utf-8")
    root = ET.fromstring(gpif_xml)

    # --- Extract score metadata ---
    score = root.find("Score")
    title = _xml_text(score, "Title") or "Untitled"
    artist = _xml_text(score, "Artist") or "Unknown"

    # --- Build lookup tables ---
    # Rhythms: id → quarter-note length
    rhythm_map: dict[str, float] = {}
    for r in root.findall("Rhythms/Rhythm"):
        rid = r.get("id")
        nv = _xml_text(r, "NoteValue") or "Quarter"
        base = _GP7_DURATION_MAP.get(nv, 1.0)
        if r.find("AugmentationDot") is not None:
            dot_count = int(r.find("AugmentationDot").get("count", "1"))
            if dot_count == 1:
                base *= 1.5
            elif dot_count == 2:
                base *= 1.75
        tuplet = r.find("PrimaryTuplet")
        if tuplet is not None:
            enters = int(tuplet.get("num", "1"))
            den = int(tuplet.get("den", "1"))
            if enters and den:
                base *= den / enters
        rhythm_map[rid] = base

    # Notes: id → (midi, fret, string, is_tied)
    note_map: dict[str, tuple[int, int, int, bool]] = {}
    for n in root.findall("Notes/Note"):
        nid = n.get("id")
        midi_val = None
        fret = 0
        string = 1
        is_tied = n.find("Tie") is not None and n.find("Tie").get("origin") == "true"
        props = n.find("Properties")
        if props is not None:
            for p in props:
                pname = p.get("name")
                if pname == "Midi":
                    num = p.find("Number")
                    if num is not None:
                        midi_val = int(num.text)
                elif pname == "Fret":
                    fret_el = p.find("Fret")
                    if fret_el is not None:
                        fret = int(fret_el.text)
                elif pname == "String":
                    str_el = p.find("String")
                    if str_el is not None:
                        string = int(str_el.text)
        if midi_val is not None:
            note_map[nid] = (midi_val, fret, string, is_tied)

    # Beats: id → (rhythm_id, [note_ids])
    beat_map: dict[str, tuple[str, list[str]]] = {}
    for b in root.findall("Beats/Beat"):
        bid = b.get("id")
        rhythm_el = b.find("Rhythm")
        rid = rhythm_el.get("ref") if rhythm_el is not None else None
        notes_el = b.find("Notes")
        note_ids = notes_el.text.split() if notes_el is not None and notes_el.text else []
        beat_map[bid] = (rid, note_ids)

    # Voices: id → [beat_ids]
    voice_map: dict[str, list[str]] = {}
    for v in root.findall("Voices/Voice"):
        vid = v.get("id")
        beats_el = v.find("Beats")
        beat_ids = beats_el.text.split() if beats_el is not None and beats_el.text else []
        voice_map[vid] = beat_ids

    # Bars: id → [voice_ids]
    bar_map: dict[str, list[str]] = {}
    for bar in root.findall("Bars/Bar"):
        bid = bar.get("id")
        voices_el = bar.find("Voices")
        voice_ids = voices_el.text.split() if voices_el is not None and voices_el.text else []
        # Filter out -1 (empty voice slots)
        bar_map[bid] = [v for v in voice_ids if v != "-1"]

    # MasterBars: ordered list of (time_sig, [bar_ids])
    master_bars: list[tuple[str, list[str]]] = []
    for mb in root.findall("MasterBars/MasterBar"):
        time_el = mb.find("Time")
        time_sig = time_el.text if time_el is not None else "4/4"
        bars_el = mb.find("Bars")
        bar_ids = bars_el.text.split() if bars_el is not None and bars_el.text else []
        master_bars.append((time_sig, bar_ids))

    # Tracks: build ParsedTrack for each
    tracks: list[ParsedTrack] = []
    for track_idx, track_el in enumerate(root.findall("Tracks/Track")):
        track_name = (_xml_text(track_el, "Name") or f"Track {track_idx + 1}").strip()

        # Get tuning from Staves/Staff/Properties/Tuning
        tuning: list[int] = []
        for staff in track_el.findall("Staves/Staff"):
            staff_props = staff.find("Properties")
            if staff_props is None:
                continue
            for p in staff_props:
                if p.get("name") == "Tuning":
                    pitches_el = p.find("Pitches")
                    if pitches_el is not None and pitches_el.text:
                        tuning = [int(x) for x in pitches_el.text.split()]
                    break
            if tuning:
                break

        is_percussion = not tuning

        if is_percussion:
            tracks.append(ParsedTrack(
                name=track_name,
                index=track_idx,
                is_percussion=True,
                tuning=[],
                measures=[],
            ))
            continue

        # Reverse tuning to match high-to-low convention (GP7 stores low-to-high)
        tuning_high_to_low = list(reversed(tuning))

        measures: list[ParsedMeasure] = []
        for mb_idx, (time_sig, bar_ids) in enumerate(master_bars):
            if track_idx >= len(bar_ids):
                continue
            bar_id = bar_ids[track_idx]

            beats_out: list[ParsedBeat] = []
            voice_ids = bar_map.get(bar_id, [])

            for voice_id in voice_ids:
                beat_ids = voice_map.get(voice_id, [])
                pos = 1.0
                for beat_id in beat_ids:
                    rhythm_id, note_ids = beat_map.get(beat_id, (None, []))
                    ql = rhythm_map.get(rhythm_id, 1.0) if rhythm_id else 1.0

                    notes_out: list[ParsedNote] = []
                    for nid in note_ids:
                        if nid not in note_map:
                            continue
                        midi_val, fret, gp7_string, is_tied = note_map[nid]
                        # GP7 string is 0-indexed (0=lowest). Convert to 1-indexed high-to-low.
                        string_1idx = len(tuning) - gp7_string
                        notes_out.append(ParsedNote(
                            midi=midi_val,
                            pitch_name=midi_to_pitch(midi_val),
                            string=string_1idx,
                            fret=fret,
                            is_tied=is_tied,
                        ))

                    if notes_out:
                        beats_out.append(ParsedBeat(
                            notes=notes_out,
                            start=pos,
                            duration=ql,
                        ))
                    pos += ql

            measures.append(ParsedMeasure(
                number=mb_idx + 1,
                time_sig=time_sig,
                beats=beats_out,
            ))

        tracks.append(ParsedTrack(
            name=track_name,
            index=track_idx,
            is_percussion=False,
            tuning=tuning_high_to_low,
            measures=measures,
        ))

    return ParsedSong(title=title, artist=artist, tracks=tracks)


def _xml_text(parent: ET.Element | None, tag: str) -> str | None:
    """Get text content of a child element, or None."""
    if parent is None:
        return None
    el = parent.find(tag)
    if el is not None and el.text:
        return el.text.strip()
    return None
