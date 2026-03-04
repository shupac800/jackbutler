from music21 import chord as m21chord, key as m21key, pitch as m21pitch

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


def _chord_tone_label(pc: str, chord: m21chord.Chord) -> str | None:
    """Return a chord-tone label like 'root', 'b3', '5th' for a pitch class."""
    try:
        root_name = chord.root().name
    except Exception:
        return None
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
    return None


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
    tone_parts = []
    for pc in pcs:
        label = _chord_tone_label(pc, c)
        if label:
            tone_parts.append(f"{pc}={label}")
        else:
            tone_parts.append(f"{pc}=passing")
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
            return {"commentary": "Rest measure."}

        # When chords are detected, lead with chord-based commentary
        if chords:
            for i, chord_info in enumerate(chords):
                numeral = numerals[i] if i < len(numerals) else None
                parts.extend(_chord_commentary(chord_info, numeral, pcs, global_key))
            return {"commentary": " ".join(parts)}

        # No chords detected — fall back to key-based analysis
        ref_key = global_key or measure_key
        if ref_key is None:
            return {"commentary": f"Notes: {', '.join(pcs)}."}

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

        return {"commentary": " ".join(parts)}
