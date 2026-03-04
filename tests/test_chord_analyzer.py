from jackbutler.analysis.chord_analyzer import ChordAnalyzer
from jackbutler.parsing.models import ParsedBeat, ParsedMeasure, ParsedNote


def _make_measure_with_chord(midi_values: list[int]) -> ParsedMeasure:
    notes = [
        ParsedNote(midi=m, pitch_name="", string=i + 1, fret=0)
        for i, m in enumerate(midi_values)
    ]
    beats = [ParsedBeat(notes=notes, start=1.0, duration=1.0)]
    return ParsedMeasure(number=1, time_sig="4/4", beats=beats)


def test_c_major_chord():
    measure = _make_measure_with_chord([60, 64, 67])  # C E G
    analyzer = ChordAnalyzer()
    context: dict = {}
    result = analyzer.analyze_measure(measure, context)

    assert len(result["chords"]) == 1
    chord = result["chords"][0]
    assert chord.root == "C"
    assert chord.name == "C"  # short name for C major triad


def test_single_note_no_chord():
    measure = _make_measure_with_chord([60])
    analyzer = ChordAnalyzer()
    context: dict = {}
    result = analyzer.analyze_measure(measure, context)
    assert result["chords"] == []
