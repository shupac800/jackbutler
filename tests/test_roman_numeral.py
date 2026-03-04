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
