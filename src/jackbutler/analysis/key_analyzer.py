from music21 import key as m21key, note, pitch as m21pitch, stream

from jackbutler.analysis.base import BaseAnalyzer
from jackbutler.parsing.models import ParsedMeasure

# Standard Roman numeral labels for scale degrees in minor and major
_MAJOR_DEGREES = {1: "I", 2: "ii", 3: "iii", 4: "IV", 5: "V", 6: "vi", 7: "vii\u00b0"}
_MINOR_DEGREES = {1: "i", 2: "ii\u00b0", 3: "III", 4: "iv", 5: "v", 6: "VI", 7: "VII"}


def detect_key(midi_pitches: list[int]) -> m21key.Key | None:
    """Run KrumhanslSchmuckler on a list of MIDI pitches."""
    if not midi_pitches:
        return None
    s = stream.Stream()
    for m in midi_pitches:
        s.append(note.Note(midi=m))
    try:
        return s.analyze("key")
    except Exception:
        return None


def detect_key_alternatives(midi_pitches: list[int], max_alts: int = 4) -> list[m21key.Key]:
    """Return the top alternative key interpretations."""
    if not midi_pitches:
        return []
    s = stream.Stream()
    for m in midi_pitches:
        s.append(note.Note(midi=m))
    try:
        key_result = s.analyze("key")
        alts = key_result.alternateInterpretations[:max_alts]
        return [key_result] + alts
    except Exception:
        return []


def get_scale_degree_num(pitch_name: str, key_result: m21key.Key) -> int | None:
    """Return the scale degree number for a pitch class in the given key."""
    try:
        p = m21pitch.Pitch(pitch_name)
        return key_result.getScaleDegreeFromPitch(p)
    except Exception:
        return None


def get_scale_degree_label(pitch_name: str, key_result: m21key.Key) -> str | None:
    """Return the Roman numeral label for a pitch class in the given key."""
    degree = get_scale_degree_num(pitch_name, key_result)
    if degree is None:
        return None
    if key_result.mode == "minor":
        return _MINOR_DEGREES.get(degree, str(degree))
    return _MAJOR_DEGREES.get(degree, str(degree))


def pitch_classes_from_midi(midi_pitches: list[int]) -> list[str]:
    """Get unique pitch class names from MIDI values, preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for m in midi_pitches:
        pc = m21pitch.Pitch(midi=m).name
        if pc not in seen:
            seen.add(pc)
            result.append(pc)
    return result


def degree_analysis_for_key(
    pitch_classes: list[str], key_result: m21key.Key
) -> tuple[list[tuple[str, str | None, int | None]], int]:
    """Analyze how pitch classes fit a key.

    Returns (breakdown, diatonic_count) where breakdown is
    [(pitch_class, roman_label, degree_num), ...].
    """
    breakdown = []
    diatonic = 0
    for pc in pitch_classes:
        label = get_scale_degree_label(pc, key_result)
        degree_num = get_scale_degree_num(pc, key_result)
        breakdown.append((pc, label, degree_num))
        if label is not None:
            diatonic += 1
    return breakdown, diatonic


def _diatonic_fit(pitch_classes: list[str], key_result: m21key.Key) -> float:
    """Return fraction of pitch classes that are diatonic to the key (0.0-1.0)."""
    if not pitch_classes:
        return 0.0
    _, count = degree_analysis_for_key(pitch_classes, key_result)
    return count / len(pitch_classes)


def choose_best_key(
    midi_pitches: list[int],
    global_key: m21key.Key | None,
) -> tuple[m21key.Key | None, float, list[m21key.Key]]:
    """Choose the best key for a set of pitches, considering alternatives.

    Scoring: combines diatonic fit, KS correlation, and global key consistency.
    Returns (best_key, effective_confidence, all_alternatives).
    """
    if not midi_pitches:
        return None, 0.0, []

    alternatives = detect_key_alternatives(midi_pitches, max_alts=8)
    if not alternatives:
        return None, 0.0, []

    pcs = pitch_classes_from_midi(midi_pitches)

    # Also include the global key as a candidate if not already present
    if global_key:
        global_name = f"{global_key.tonic.name} {global_key.mode}"
        alt_names = {f"{k.tonic.name} {k.mode}" for k in alternatives}
        if global_name not in alt_names:
            alternatives.append(global_key)

    # Score each candidate
    scored: list[tuple[float, m21key.Key, float, float]] = []
    for candidate in alternatives:
        fit = _diatonic_fit(pcs, candidate)
        ks_corr = candidate.correlationCoefficient

        # Bonus for matching the global key (contextual consistency)
        global_bonus = 0.0
        if global_key:
            if (candidate.tonic.name == global_key.tonic.name
                    and candidate.mode == global_key.mode):
                global_bonus = 0.15
            elif candidate.tonic.name == global_key.tonic.name:
                # Same tonic, different mode (e.g. A major vs A minor) — small bonus
                global_bonus = 0.05

        # Composite score:
        # - Diatonic fit is most important (weight 0.50)
        # - KS correlation matters (weight 0.35)
        # - Global key consistency (weight 0.15, via bonus)
        score = (fit * 0.50) + (ks_corr * 0.35) + global_bonus
        scored.append((score, candidate, fit, ks_corr))

    scored.sort(key=lambda x: x[0], reverse=True)

    best_score, best_key, best_fit, best_ks = scored[0]

    # Effective confidence: blend of diatonic fit and KS correlation
    # If all notes are diatonic, we're confident even if KS is low
    effective_conf = (best_fit * 0.6) + (best_ks * 0.4)
    # Clamp to [0, 1]
    effective_conf = max(0.0, min(1.0, effective_conf))

    # Return all alternatives in scored order (for commentary)
    all_alts = [entry[1] for entry in scored]

    return best_key, round(effective_conf, 4), all_alts


class KeyAnalyzer(BaseAnalyzer):
    """Detect the key and mode of a measure, choosing the best fit."""

    def analyze_measure(self, measure: ParsedMeasure, context: dict) -> dict:
        pitches = measure.all_pitches_midi

        if len(pitches) < 2:
            adjacent = context.get("adjacent_pitches", [])
            pitches = pitches + adjacent

        if not pitches:
            return {}

        global_key = context.get("global_key")
        best_key, confidence, alternatives = choose_best_key(pitches, global_key)

        if best_key is None:
            return {}

        result = {
            "detected_key": f"{best_key.tonic.name} {best_key.mode}",
            "mode": best_key.mode,
            "key_confidence": confidence,
        }

        context["detected_key"] = result["detected_key"]
        context["key_result"] = best_key
        context["key_alternatives"] = alternatives
        context["key_confidence"] = confidence

        return result
