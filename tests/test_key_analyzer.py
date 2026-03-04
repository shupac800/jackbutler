from jackbutler.analysis.key_analyzer import KeyAnalyzer
from jackbutler.parsing.models import ParsedBeat, ParsedMeasure, ParsedNote


def _make_measure(midi_values: list[int]) -> ParsedMeasure:
    notes = [
        ParsedNote(midi=m, pitch_name="", string=1, fret=0)
        for m in midi_values
    ]
    beats = [ParsedBeat(notes=notes, start=1.0, duration=1.0)]
    return ParsedMeasure(number=1, time_sig="4/4", beats=beats)


def test_c_major_detection():
    # C major scale pitches
    measure = _make_measure([60, 62, 64, 65, 67, 69, 71])
    analyzer = KeyAnalyzer()
    context: dict = {}
    result = analyzer.analyze_measure(measure, context)

    assert "detected_key" in result
    # C major and A minor are relative keys with identical pitches;
    # KrumhanslSchmuckler may return either
    assert result["detected_key"] in ("C major", "A minor")
    assert context["detected_key"] == result["detected_key"]


def test_empty_measure():
    measure = _make_measure([])
    analyzer = KeyAnalyzer()
    result = analyzer.analyze_measure(measure, {})
    assert result == {}
