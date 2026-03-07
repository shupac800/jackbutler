from music21 import key as m21key

from jackbutler.analysis.models import ChordInfo
from jackbutler.analysis.roman_numeral import RomanNumeralAnalyzer
from jackbutler.parsing.models import ParsedBeat, ParsedMeasure, ParsedNote


def _empty_measure() -> ParsedMeasure:
    return ParsedMeasure(number=1, time_sig="4/4", beats=[])


def test_c_major_in_c():
    analyzer = RomanNumeralAnalyzer()
    context = {
        "key_result": m21key.Key("C"),
        "chords": [
            ChordInfo(name="C major triad", root="C", midi_pitches=[60, 64, 67], beat_position=1.0),
        ],
    }
    result = analyzer.analyze_measure(_empty_measure(), context)
    assert len(result["roman_numerals"]) == 1
    assert "I" in result["roman_numerals"][0]


def test_no_key_returns_empty():
    analyzer = RomanNumeralAnalyzer()
    result = analyzer.analyze_measure(_empty_measure(), {})
    assert result["roman_numerals"] == []


def test_a_chord_in_b_minor_is_bvii():
    """A major chord should be bVII in B minor, not I.

    Regression: when the per-measure key was A major but the global key was
    B minor, the numeral was computed against A major (giving I) but displayed
    as 'I in B minor', which is wrong.
    """
    analyzer = RomanNumeralAnalyzer()
    # A major triad built from notes that might appear in a guitar measure
    a_chord = ChordInfo(
        name="A", root="A", midi_pitches=[57, 61, 64], beat_position=1.0
    )
    context = {
        "key_result": m21key.Key("A"),        # per-measure key
        "global_key": m21key.Key("B", "minor"),  # track-level key
        "chords": [a_chord],
        "chord_alternatives": [],
    }
    result = analyzer.analyze_measure(_empty_measure(), context)
    rn = result["roman_numerals"][0]
    assert "I" not in rn or "bVII" in rn, (
        f"A in B minor should be bVII, got '{rn}'"
    )
