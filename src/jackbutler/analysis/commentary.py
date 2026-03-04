from music21 import chord as m21chord, interval as m21interval, key as m21key, pitch as m21pitch

from jackbutler.analysis.base import BaseAnalyzer
from jackbutler.analysis.key_analyzer import (
    degree_analysis_for_key,
    get_scale_degree_label,
    pitch_classes_from_midi,
)
from jackbutler.analysis.models import ChordInfo
from jackbutler.parsing.models import ParsedMeasure


def _pitch_classes(measure: ParsedMeasure) -> list[str]:
    """Get unique pitch class names (no octave) in order of appearance."""
    seen: set[str] = set()
    result: list[str] = []
    for beat in measure.beats:
        for n in beat.notes:
            if not n.is_tied:
                pc = m21pitch.Pitch(midi=n.midi).name
                if pc not in seen:
                    seen.add(pc)
                    result.append(pc)
    return result


def _format_degrees(breakdown: list[tuple[str, str | None, int | None]]) -> str:
    """Format a degree breakdown as 'A=i, C=III, ...'."""
    parts = []
    for pc, label, _ in breakdown:
        parts.append(f"{pc}={label}" if label else f"{pc}=chromatic")
    return ", ".join(parts)


def _key_name(k: m21key.Key) -> str:
    return f"{k.tonic.name} {k.mode}"


def _interval_from_root(pc: str, root_name: str) -> str:
    """Return the interval name from the chord root to a pitch class (e.g. 'P4', 'm6')."""
    try:
        root = m21pitch.Pitch(root_name + "3")
        target = m21pitch.Pitch(pc + "3")
        # Ensure ascending
        if target.midi < root.midi:
            target.octave += 1
        iv = m21interval.Interval(root, target)
        return iv.semiSimpleName
    except Exception:
        return "?"


def _chord_tone_label(pc: str, chord: m21chord.Chord) -> str:
    """Return a chord-tone label like 'root', 'b3', '5th', or interval from root."""
    try:
        root_name = chord.root().name
    except Exception:
        return "?"
    if pc == root_name:
        return "root"
    third = chord.third
    if third and pc == third.name:
        return "b3" if chord.quality in ("diminished", "minor") else "3rd"
    fifth = chord.fifth
    if fifth and pc == fifth.name:
        return "b5" if chord.quality == "diminished" else "5th"
    seventh = chord.seventh
    if seventh and pc == seventh.name:
        return "7th"
    # Non-chord tone: label by interval from root
    return _interval_from_root(pc, root_name)


def _chord_commentary(
    chord_info: ChordInfo,
    numeral: str | None,
    pcs: list[str],
    global_key: m21key.Key | None,
) -> list[str]:
    """Generate commentary focused on the detected chord."""
    parts: list[str] = []
    c = m21chord.Chord(chord_info.midi_pitches)

    # Describe chord tones
    tone_parts = [f"{pc}={_chord_tone_label(pc, c)}" for pc in pcs]
    parts.append(f"{chord_info.name}: {', '.join(tone_parts)}.")

    # Explain relationship to global key
    if global_key and numeral:
        root_degree = get_scale_degree_label(chord_info.root, global_key)
        key_name = _key_name(global_key)
        if root_degree:
            parts.append(
                f"{numeral} in {key_name} \u2014 "
                f"{chord_info.root} is {root_degree}."
            )

    # Note quality
    quality = c.quality
    if quality == "diminished":
        parts.append("Diminished quality creates tension, typically resolving stepwise.")
    elif quality == "augmented":
        parts.append("Augmented quality creates instability, pulling toward resolution.")

    return parts


def _pitch_sequence(measure: ParsedMeasure) -> list[int]:
    """Get ordered MIDI values of non-tied notes (highest per beat)."""
    seq: list[int] = []
    for beat in measure.beats:
        candidates = [n.midi for n in beat.notes if not n.is_tied]
        if candidates:
            seq.append(max(candidates))
    return seq


def _detect_contour(midi_seq: list[int]) -> str:
    """Classify pitch contour as ascending, descending, arch, valley, or static."""
    if len(midi_seq) <= 1:
        return "static"
    if len(set(midi_seq)) == 1:
        return "static"

    diffs = [midi_seq[i + 1] - midi_seq[i] for i in range(len(midi_seq) - 1)]
    ups = sum(1 for d in diffs if d > 0)
    downs = sum(1 for d in diffs if d < 0)

    if downs == 0:
        return "ascending"
    if ups == 0:
        return "descending"

    # Check for arch (up then down) or valley (down then up)
    peak_idx = midi_seq.index(max(midi_seq))
    valley_idx = midi_seq.index(min(midi_seq))

    if 0 < peak_idx < len(midi_seq) - 1 and ups >= downs:
        return "ascending\u2013descending"
    if 0 < valley_idx < len(midi_seq) - 1 and downs >= ups:
        return "descending\u2013ascending"

    if ups > downs:
        return "ascending"
    if downs > ups:
        return "descending"
    return "undulating"


def _melodic_description(measure: ParsedMeasure, chord_info: ChordInfo | None) -> str:
    """Analyze the sequence of pitches to describe melodic motion."""
    midi_seq = _pitch_sequence(measure)
    if not midi_seq:
        return ""
    if len(midi_seq) == 1:
        note_name = m21pitch.Pitch(midi=midi_seq[0]).name
        return f"single note {note_name}"

    contour = _detect_contour(midi_seq)

    # Check for repeated notes
    if len(set(midi_seq)) == 1:
        note_name = m21pitch.Pitch(midi=midi_seq[0]).name
        return f"repeated {note_name}"

    chord_name = chord_info.name if chord_info else None
    chord_pcs: set[int] = set()
    if chord_info:
        chord_pcs = {p % 12 for p in chord_info.midi_pitches}

    seq_pcs = [m % 12 for m in midi_seq]

    # Detect arpeggio: ≥75% chord tones
    if chord_pcs and len(midi_seq) >= 2:
        ct_count = sum(1 for pc in seq_pcs if pc in chord_pcs)
        if ct_count / len(seq_pcs) >= 0.75:
            non_ct = [
                m21pitch.Pitch(midi=midi_seq[i]).name
                for i, pc in enumerate(seq_pcs)
                if pc not in chord_pcs
            ]
            label = f"{chord_name} arpeggio"
            if contour != "static":
                label += f" ({contour})"
            if non_ct:
                label += f" with passing tone{'s' if len(non_ct) > 1 else ''} {', '.join(non_ct)}"
            return label

    # Detect scale run: all consecutive intervals are 1-2 semitones
    if len(midi_seq) >= 3:
        intervals = [abs(midi_seq[i + 1] - midi_seq[i]) for i in range(len(midi_seq) - 1)]
        if all(1 <= iv <= 2 for iv in intervals):
            label = f"{contour} scale run" if contour not in ("static", "undulating") else "scale run"
            return label

    # Fallback
    if chord_name:
        return f"{chord_name} figuration ({contour})" if contour != "static" else f"{chord_name} figuration"
    return f"melodic line ({contour})" if contour != "static" else "melodic line"


def _harmonic_description(
    chord_info: ChordInfo,
    numeral: str | None,
    global_key: m21key.Key | None,
) -> str:
    """One-line harmonic summary: chord name + roman numeral in key."""
    parts = [chord_info.name]
    if numeral and global_key:
        parts.append(f"\u2014 {numeral} in {_key_name(global_key)}")
    return " ".join(parts)


class CommentaryGenerator(BaseAnalyzer):
    """Generate human-readable explanation of the harmonic content."""

    def analyze_measure(self, measure: ParsedMeasure, context: dict) -> dict:
        parts: list[str] = []
        pcs = _pitch_classes(measure)

        global_key: m21key.Key | None = context.get("global_key")
        measure_key: m21key.Key | None = context.get("key_result")
        chords: list[ChordInfo] = context.get("chords", [])
        numerals: list[str] = context.get("roman_numerals", [])
        confidence = context.get("key_confidence", 0) or 0

        if not pcs:
            return {
                "commentary": "Rest measure.",
                "harmonic_desc": "",
                "melodic_desc": "",
            }

        harmonic_desc = ""
        chord_for_melody = chords[0] if chords else None

        # When chords are detected, lead with chord-based commentary
        if chords:
            for i, chord_info in enumerate(chords):
                numeral = numerals[i] if i < len(numerals) else None
                parts.extend(_chord_commentary(chord_info, numeral, pcs, global_key))
            harmonic_desc = _harmonic_description(
                chords[0],
                numerals[0] if numerals else None,
                global_key,
            )
        else:
            # No chords detected — fall back to key-based analysis
            ref_key = global_key or measure_key
            if ref_key is None:
                melodic_desc = _melodic_description(measure, None)
                commentary = f"Notes: {', '.join(pcs)}."
                if melodic_desc:
                    commentary += f" {melodic_desc.capitalize()}."
                return {
                    "commentary": commentary,
                    "harmonic_desc": "",
                    "melodic_desc": melodic_desc,
                }

            ref_key_name = _key_name(ref_key)
            breakdown, in_key_count = degree_analysis_for_key(pcs, ref_key)
            out_of_key = [pc for pc, label, _ in breakdown if label is None]

            parts.append(f"In {ref_key_name}: {_format_degrees(breakdown)}.")

            if pcs:
                fit_pct = in_key_count / len(pcs)
                if fit_pct == 1.0:
                    parts.append(f"All {len(pcs)} pitches diatonic.")
                elif fit_pct >= 0.75:
                    parts.append(
                        f"{in_key_count}/{len(pcs)} diatonic; "
                        f"{', '.join(out_of_key)} chromatic."
                    )
                else:
                    parts.append(
                        f"Only {in_key_count}/{len(pcs)} diatonic. "
                        f"Chromatic tones ({', '.join(out_of_key)}) suggest "
                        f"borrowed chords or modulation."
                    )

            # Tonal anchors
            has_root = any(d == 1 for _, _, d in breakdown)
            has_fifth = any(d == 5 for _, _, d in breakdown)
            has_third = any(d == 3 for _, _, d in breakdown)
            if has_root and has_fifth and has_third:
                parts.append("Tonic triad present (root + 3rd + 5th).")
            elif has_root and has_fifth:
                parts.append("Root + 5th present.")

            harmonic_desc = f"In {ref_key_name}"

        melodic_desc = _melodic_description(measure, chord_for_melody)
        harmonic_text = " ".join(parts)
        if melodic_desc:
            commentary = f"{harmonic_text} {melodic_desc.capitalize()}."
        else:
            commentary = harmonic_text

        return {
            "commentary": commentary,
            "harmonic_desc": harmonic_desc,
            "melodic_desc": melodic_desc,
        }
