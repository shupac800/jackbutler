from music21 import key as m21key, pitch as m21pitch

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


class CommentaryGenerator(BaseAnalyzer):
    """Generate human-readable explanation of why a key/mode was assigned."""

    def analyze_measure(self, measure: ParsedMeasure, context: dict) -> dict:
        parts: list[str] = []
        pcs = _pitch_classes(measure)

        global_key: m21key.Key | None = context.get("global_key")
        measure_key: m21key.Key | None = context.get("key_result")
        alternatives: list[m21key.Key] = context.get("key_alternatives", [])
        confidence = context.get("key_confidence", 0) or 0

        if not pcs:
            return {"commentary": "Rest measure."}

        ref_key = global_key or measure_key
        if ref_key is None:
            return {"commentary": f"Notes: {', '.join(pcs)}."}

        ref_key_name = _key_name(ref_key)
        breakdown, in_key_count = degree_analysis_for_key(pcs, ref_key)
        out_of_key = [pc for pc, label, _ in breakdown if label is None]

        # 1. Primary analysis in the global key
        parts.append(f"In {ref_key_name}: {_format_degrees(breakdown)}.")

        # 2. Fit quality
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

        # 3. Low-confidence alternative analysis
        #    When the per-measure detection is uncertain, show how the notes
        #    fit other plausible keys and explain why we still lean toward one.
        if confidence < 0.7 and alternatives:
            alt_analyses = []
            for alt_key in alternatives[:4]:
                alt_name = _key_name(alt_key)
                if alt_name == ref_key_name:
                    continue
                alt_bd, alt_diatonic = degree_analysis_for_key(pcs, alt_key)
                alt_conf = round(alt_key.correlationCoefficient, 2)
                alt_degs = _format_degrees(alt_bd)
                alt_analyses.append((alt_name, alt_diatonic, alt_degs, alt_conf))

            if alt_analyses:
                # Show alternatives that fit well
                parts.append(
                    f"Low confidence ({confidence:.0%}) \u2014 alternative readings:"
                )
                for alt_name, alt_dia, alt_degs, alt_conf in alt_analyses:
                    fit_note = (
                        f"all diatonic"
                        if alt_dia == len(pcs)
                        else f"{alt_dia}/{len(pcs)} diatonic"
                    )
                    parts.append(
                        f"  {alt_name} ({alt_conf:.0%}): {alt_degs} ({fit_note})."
                    )

                # Explain why we stick with the global key
                if global_key and measure_key:
                    measure_key_name = _key_name(measure_key)
                    if measure_key_name != ref_key_name:
                        tonic_degree = get_scale_degree_label(
                            measure_key.tonic.name, global_key
                        )
                        if tonic_degree:
                            parts.append(
                                f"Assigned {ref_key_name} based on surrounding context "
                                f"(local pull toward {measure_key_name} \u2014 "
                                f"{measure_key.tonic.name} is {tonic_degree})."
                            )
                        else:
                            parts.append(
                                f"Assigned {ref_key_name} based on surrounding context "
                                f"despite local pull toward {measure_key_name}."
                            )
                    else:
                        parts.append(
                            f"Context confirms {ref_key_name} despite ambiguity."
                        )

        # 4. High-confidence: simpler key-drift note
        elif measure_key and global_key and confidence >= 0.7:
            measure_key_name = _key_name(measure_key)
            if measure_key_name != ref_key_name:
                tonic_degree = get_scale_degree_label(
                    measure_key.tonic.name, global_key
                )
                if tonic_degree:
                    parts.append(
                        f"Local pull toward {measure_key_name} "
                        f"({measure_key.tonic.name} is {tonic_degree} in {ref_key_name})."
                    )

        # 5. Tonal anchors
        has_root = any(d == 1 for _, _, d in breakdown)
        has_fifth = any(d == 5 for _, _, d in breakdown)
        has_third = any(d == 3 for _, _, d in breakdown)
        if has_root and has_fifth and has_third:
            parts.append("Tonic triad present (root + 3rd + 5th).")
        elif has_root and has_fifth:
            parts.append("Root + 5th present.")

        # 6. Chords / Roman numerals if present
        chords: list[ChordInfo] = context.get("chords", [])
        numerals: list[str] = context.get("roman_numerals", [])
        if chords and numerals:
            chord_rn = [f"{c.name} ({rn})" for c, rn in zip(chords, numerals)]
            parts.append(f"Chords: {', '.join(chord_rn)}.")

        return {"commentary": " ".join(parts)}
