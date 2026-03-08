from itertools import combinations

from music21 import chord as m21chord, pitch as m21pitch

from jackbutler.analysis.base import BaseAnalyzer
from jackbutler.analysis.models import ChordInfo
from jackbutler.parsing.models import ParsedMeasure

# Map music21 quality strings to conventional suffixes
_QUALITY_SUFFIX = {
    "major": "",
    "minor": "m",
    "diminished": "dim",
    "augmented": "aug",
    "dominant": "7",
    "major-seventh": "maj7",
    "minor-seventh": "m7",
    "half-diminished": "m7b5",
    "diminished-seventh": "dim7",
    "suspended-second": "sus2",
    "suspended-fourth": "sus4",
}

# Standard qualities that get a bonus in scoring
_STANDARD_QUALITIES = {
    "major", "minor", "diminished", "augmented",
    "dominant", "major-seventh", "minor-seventh",
    "half-diminished", "diminished-seventh",
    "suspended-second", "suspended-fourth",
}

# A valid chord name is a root (A-G with optional #/b/-) followed by an
# optional suffix of known quality tokens.  Anything else is nonsense.
import re

_VALID_CHORD_NAME = re.compile(
    r"^[A-G][#\-b]?"                # root
    r"(m|min|dim|aug|sus[24]|maj|add)?"  # base quality
    r"(7|9|11|13|6)?"               # extension
    r"(b5|#5|b9|#9|#11|b13)?"       # alteration
    r"\??"                           # optional ? for unrecognized quality
    r"$"
)


def _short_chord_name(c: m21chord.Chord) -> str:
    """Build a concise chord name like 'Am', 'Bdim', 'Fmaj7'."""
    root = c.root().name
    cn = c.commonName.lower()

    # Check commonName first for compound qualities (e.g. "major seventh chord")
    if "major seventh" in cn:
        return root + "maj7"
    if "dominant seventh" in cn:
        return root + "7"
    if "minor seventh" in cn:
        return root + "m7"
    if "half-diminished" in cn:
        return root + "m7b5"
    if "diminished seventh" in cn:
        return root + "dim7"

    # Then use the quality property for triads
    quality = c.quality
    suffix = _QUALITY_SUFFIX.get(quality, "")
    if suffix or quality == "major":
        return root + suffix

    # Fallback keywords
    if "diminished" in cn:
        return root + "dim"
    if "augmented" in cn:
        return root + "aug"
    if "minor" in cn:
        return root + "m"
    if "suspended" in cn and "fourth" in cn:
        return root + "sus4"
    if "suspended" in cn and "second" in cn:
        return root + "sus2"

    # Last resort: try root alone (unrecognized quality)
    return root + "?"


def _identify_chord(midi_values: list[int], beat_position: float) -> ChordInfo | None:
    """Try to identify a chord from a list of MIDI values."""
    unique = sorted(set(midi_values))
    if len(unique) < 2:
        return None
    try:
        c = m21chord.Chord(unique)
        return ChordInfo(
            name=_short_chord_name(c),
            root=c.root().name,
            midi_pitches=unique,
            beat_position=beat_position,
        )
    except Exception:
        return None


def _chord_tone_set(c: m21chord.Chord) -> set[str]:
    """Get the set of pitch class names that are chord tones (root, 3rd, 5th, 7th)."""
    tones: set[str] = set()
    try:
        tones.add(c.root().name)
    except Exception:
        pass
    if c.third:
        tones.add(c.third.name)
    if c.fifth:
        tones.add(c.fifth.name)
    if c.seventh:
        tones.add(c.seventh.name)
    return tones


def _score_candidate(
    c: m21chord.Chord,
    all_pitch_classes: list[str],
    strong_beat_pcs: set[str],
) -> float:
    """Score a chord candidate against the measure's pitches.

    confidence = chord_tone_coverage * 0.7 + quality_bonus + strong_beat_bonus
    """
    ct = _chord_tone_set(c)
    if not ct or not all_pitch_classes:
        return 0.0

    # How many of the measure's pitch classes are chord tones
    chord_tone_count = sum(1 for pc in all_pitch_classes if pc in ct)
    coverage = chord_tone_count / len(all_pitch_classes)

    # Standard quality bonus
    quality = c.quality
    cn = c.commonName.lower()
    is_standard = quality in _STANDARD_QUALITIES or any(
        kw in cn for kw in ("seventh", "diminished", "augmented", "suspended")
    )
    quality_bonus = 0.1 if is_standard else 0.0

    # Root on strong beat bonus
    try:
        root_name = c.root().name
        strong_beat_bonus = 0.1 if root_name in strong_beat_pcs else 0.0
    except Exception:
        strong_beat_bonus = 0.0

    return coverage * 0.7 + quality_bonus + strong_beat_bonus


def _score_chord_interpretations(
    measure: ParsedMeasure,
) -> list[ChordInfo]:
    """Generate multiple chord interpretations with confidence scores."""
    # Collect all non-tied pitch classes and their MIDI values
    all_midi: list[int] = []
    for beat in measure.beats:
        for n in beat.notes:
            if not n.is_tied:
                all_midi.append(n.midi)

    # Reduce to unique pitch classes (use lowest octave instance)
    pc_to_midi: dict[str, int] = {}
    for m in all_midi:
        pc = m21pitch.Pitch(midi=m).name
        if pc not in pc_to_midi or m < pc_to_midi[pc]:
            pc_to_midi[pc] = m

    if len(pc_to_midi) < 3:
        return []

    # All pitch classes in the measure (with duplicates for coverage calc)
    all_pcs = [m21pitch.Pitch(midi=m).name for m in all_midi]

    # Pitch classes on strong beats
    strong_beat_pcs: set[str] = set()
    for beat in measure.beats:
        if beat.start in (1.0, 2.0, 3.0):
            for n in beat.notes:
                if not n.is_tied:
                    strong_beat_pcs.add(m21pitch.Pitch(midi=n.midi).name)

    unique_midis = list(pc_to_midi.values())

    # Generate candidate pitch subsets
    midi_subsets: list[list[int]] = []

    # Full set
    if len(unique_midis) >= 3:
        midi_subsets.append(unique_midis)

    # 3-note subsets
    if len(unique_midis) >= 3:
        for combo in combinations(unique_midis, 3):
            midi_subsets.append(list(combo))

    # 4-note subsets
    if len(unique_midis) > 4:
        for combo in combinations(unique_midis, 4):
            midi_subsets.append(list(combo))

    # Score each candidate, deduplicate by root+name
    seen: dict[str, ChordInfo] = {}  # key: "root:name"
    for subset in midi_subsets:
        try:
            c = m21chord.Chord(sorted(subset))
            name = _short_chord_name(c)
            root = c.root().name
            dedup_key = f"{root}:{name}"
            if dedup_key in seen:
                continue
            score = _score_candidate(c, all_pcs, strong_beat_pcs)
            seen[dedup_key] = ChordInfo(
                name=name,
                root=root,
                midi_pitches=sorted(subset),
                beat_position=0.0,
                confidence=round(score, 3),
            )
        except Exception:
            continue

    # Sort by confidence descending, keep top 5
    candidates = sorted(seen.values(), key=lambda ci: ci.confidence, reverse=True)
    return candidates[:5]


def _identify_implied_chord(measure: ParsedMeasure) -> ChordInfo | None:
    """Identify the implied chord from all non-tied pitches in a measure.

    For arpeggiated passages where each beat has only one note,
    the measure as a whole often outlines a single chord.
    """
    all_midi: list[int] = []
    for beat in measure.beats:
        for n in beat.notes:
            if not n.is_tied:
                all_midi.append(n.midi)

    # Reduce to unique pitch classes (use lowest octave instance)
    pc_to_midi: dict[str, int] = {}
    for m in all_midi:
        pc = m21pitch.Pitch(midi=m).name
        if pc not in pc_to_midi or m < pc_to_midi[pc]:
            pc_to_midi[pc] = m

    unique_pcs = list(pc_to_midi.values())
    if len(unique_pcs) < 3:
        return None

    # Try the full set of pitch classes as a chord
    chord_info = _identify_chord(unique_pcs, beat_position=1.0)
    if chord_info:
        return chord_info

    # If that fails (too many notes), try subsets of 3-4 notes
    # prioritizing notes that appear on strong beats (positions 1.0, 2.0, 3.0)
    strong_midi: list[int] = []
    for beat in measure.beats:
        if beat.start in (1.0, 2.0, 3.0):
            for n in beat.notes:
                if not n.is_tied:
                    strong_midi.append(n.midi)

    if len(set(strong_midi)) >= 3:
        return _identify_chord(sorted(set(strong_midi)), beat_position=1.0)

    return None


class ChordAnalyzer(BaseAnalyzer):
    """Identify chords from simultaneous notes or arpeggiated patterns."""

    def analyze_measure(self, measure: ParsedMeasure, context: dict) -> dict:
        chords: list[ChordInfo] = []

        # 1. Check for simultaneous chords (multiple notes per beat)
        for beat in measure.beats:
            midi_values = [n.midi for n in beat.notes if not n.is_tied]
            chord_info = _identify_chord(midi_values, beat.start)
            if chord_info:
                chords.append(chord_info)

        # 2. If no simultaneous chords found, look for implied/arpeggiated chord
        if not chords:
            implied = _identify_implied_chord(measure)
            if implied:
                implied.beat_position = 0.0  # mark as measure-level, not beat-level
                chords.append(implied)

        # 3. Generate alternative interpretations with confidence scores
        alternatives = _score_chord_interpretations(measure)

        # If we have a primary chord, set its confidence from scored alternatives
        if chords and alternatives:
            primary_key = f"{chords[0].root}:{chords[0].name}"
            for alt in alternatives:
                if f"{alt.root}:{alt.name}" == primary_key:
                    chords[0].confidence = alt.confidence
                    break
            # Alternatives = everything except the primary chord
            chord_alternatives = [
                a for a in alternatives
                if f"{a.root}:{a.name}" != primary_key
            ]
        elif alternatives:
            # No chord was identified by original logic; use top scored as primary
            chords = [alternatives[0]]
            chord_alternatives = alternatives[1:]
        else:
            chord_alternatives = []

        context["chords"] = chords
        context["chord_alternatives"] = chord_alternatives
        return {"chords": chords, "chord_alternatives": chord_alternatives}
