"""Verify that all generated chord names and roman numerals are sensible."""

import re

import pytest
from music21 import chord as m21chord, key as m21key

from jackbutler.analysis.chord_analyzer import (
    ChordAnalyzer,
    _VALID_CHORD_NAME,
    _short_chord_name,
)
from jackbutler.analysis.roman_numeral import RomanNumeralAnalyzer, _RN_PREFIX
from jackbutler.analysis.models import ChordInfo
from jackbutler.parsing.models import ParsedBeat, ParsedMeasure, ParsedNote

# Valid roman numerals: optional accidental, I-VII (upper or lower),
# optional quality (o/°/ø/+/d), optional 7.
_VALID_RN = re.compile(
    r"^[#b]?(?:N|[iIvV]+)(?:o|°|ø|\+|d)?7?$"
)


# ---------- chord name tests ----------

@pytest.mark.parametrize(
    "name",
    ["C", "Am", "Bdim", "Fmaj7", "G7", "Dm7", "Em7b5", "Caug", "Dsus4",
     "Esus2", "F#m", "B-dim7", "A#", "Cmin7", "Gadd9"],
)
def test_valid_chord_names_accepted(name):
    assert _VALID_CHORD_NAME.match(name), f"{name!r} should be valid"


@pytest.mark.parametrize(
    "name",
    ["ivob86b", "C major chord", "incomplete minor-seventh", "X", "123", ""],
)
def test_invalid_chord_names_rejected(name):
    assert not _VALID_CHORD_NAME.match(name), f"{name!r} should be invalid"


# ---------- _short_chord_name produces valid names ----------

@pytest.mark.parametrize(
    "midi",
    [
        [60, 64, 67],          # C major
        [57, 60, 64],          # A minor
        [59, 62, 65],          # B diminished
        [65, 69, 72, 76],      # F major 7
        [55, 59, 62, 65],      # G7
        [62, 65, 69, 72],      # Dm7
        [60, 63, 66, 69],      # dim7 (symmetric)
        [60, 64, 68],          # C augmented
        [60, 65, 67],          # sus4 voicing
        [60, 62, 67],          # sus2 voicing
    ],
)
def test_short_chord_name_is_valid(midi):
    c = m21chord.Chord(midi)
    name = _short_chord_name(c)
    assert _VALID_CHORD_NAME.match(name), f"{name!r} is not a valid chord name"


def test_exotic_pitch_set_does_not_produce_garbage():
    """An unusual pitch set should produce root + '?' rather than a long nonsense string."""
    c = m21chord.Chord([60, 61, 63, 66, 70])
    name = _short_chord_name(c)
    # Must be short and start with a valid root
    assert len(name) <= 5, f"Name too long: {name!r}"
    assert name[0] in "ABCDEFG", f"Bad root in {name!r}"


# ---------- roman numeral tests ----------

@pytest.mark.parametrize(
    "figure, expected",
    [
        ("I", "I"),
        ("ii", "ii"),
        ("IV", "IV"),
        ("V7", "V7"),
        ("viio", "viio"),
        ("viio7", "viio7"),
        ("bVII", "bVII"),
        ("#iv", "#iv"),
        ("ivob86b", "ivo"),      # the bug case — figured bass stripped
        ("III+", "III+"),
        ("N", "N"),
        ("viid7", "viid7"),
    ],
)
def test_rn_prefix_extraction(figure, expected):
    m = _RN_PREFIX.match(figure)
    assert m, f"No match for {figure!r}"
    assert m.group(1) == expected


@pytest.mark.parametrize(
    "midi, key_str",
    [
        ([60, 64, 67], "C"),     # I in C
        ([57, 60, 64], "C"),     # vi in C
        ([59, 62, 65], "C"),     # viio in C
        ([65, 69, 72], "C"),     # IV in C
        ([55, 59, 62], "C"),     # V in C
        ([57, 60, 64], "A"),     # i in Am
        ([62, 66, 69], "B"),     # probably something in B minor
    ],
)
def test_computed_roman_numeral_is_valid(midi, key_str):
    """Every computed roman numeral must match the valid pattern."""
    analyzer = RomanNumeralAnalyzer()
    chord_info = ChordInfo(
        name="test", root="C", midi_pitches=midi, beat_position=1.0
    )
    context = {
        "key_result": m21key.Key(key_str),
        "chords": [chord_info],
    }
    result = analyzer.analyze_measure(
        ParsedMeasure(number=1, time_sig="4/4", beats=[]), context
    )
    for rn in result["roman_numerals"]:
        assert _VALID_RN.match(rn), f"Invalid roman numeral: {rn!r}"


# ---------- full pipeline: chord names from analyzer ----------

def _make_arpeggiated_measure(midi_sequence: list[int]) -> ParsedMeasure:
    """Build a measure with one note per beat (arpeggiated)."""
    beats = []
    for i, m in enumerate(midi_sequence):
        beats.append(ParsedBeat(
            notes=[ParsedNote(midi=m, pitch_name="", string=1, fret=0)],
            start=float(i + 1),
            duration=1.0,
        ))
    return ParsedMeasure(number=1, time_sig="4/4", beats=beats)


def test_arpeggiated_chord_name_is_valid():
    """An arpeggiated A-C-E pattern should produce a valid chord name."""
    measure = _make_arpeggiated_measure([57, 60, 64, 57])  # A C E A
    analyzer = ChordAnalyzer()
    result = analyzer.analyze_measure(measure, {})
    for chord in result["chords"]:
        assert _VALID_CHORD_NAME.match(chord.name), f"Invalid name: {chord.name!r}"
    for alt in result.get("chord_alternatives", []):
        assert _VALID_CHORD_NAME.match(alt.name), f"Invalid alt name: {alt.name!r}"
