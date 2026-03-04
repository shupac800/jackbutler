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

    # Last resort: root + abbreviated commonName
    return root + " " + c.commonName


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

        context["chords"] = chords
        return {"chords": chords}
