"""Tests for melodic pattern detection and split commentary."""

from jackbutler.analysis.commentary import (
    _detect_contour,
    _melodic_description,
    _pitch_sequence,
)
from jackbutler.analysis.models import ChordInfo
from jackbutler.parsing.models import ParsedBeat, ParsedMeasure, ParsedNote


def _make_measure(midi_values: list[int]) -> ParsedMeasure:
    """Create a measure with one note per beat from MIDI values."""
    beats = []
    for i, midi in enumerate(midi_values):
        beats.append(
            ParsedBeat(
                notes=[ParsedNote(midi=midi, pitch_name="", string=1, fret=0)],
                start=float(i + 1),
                duration=1.0,
            )
        )
    return ParsedMeasure(number=1, time_sig="4/4", beats=beats)


def _am_chord() -> ChordInfo:
    return ChordInfo(
        name="Am",
        root="A",
        midi_pitches=[57, 60, 64],  # A3, C4, E4
        beat_position=1.0,
    )


# --- _pitch_sequence ---


def test_pitch_sequence_basic():
    m = _make_measure([60, 64, 67, 72])
    assert _pitch_sequence(m) == [60, 64, 67, 72]


def test_pitch_sequence_skips_tied():
    beats = [
        ParsedBeat(
            notes=[ParsedNote(midi=60, pitch_name="C4", string=1, fret=0)],
            start=1.0,
            duration=1.0,
        ),
        ParsedBeat(
            notes=[ParsedNote(midi=60, pitch_name="C4", string=1, fret=0, is_tied=True)],
            start=2.0,
            duration=1.0,
        ),
        ParsedBeat(
            notes=[ParsedNote(midi=64, pitch_name="E4", string=1, fret=0)],
            start=3.0,
            duration=1.0,
        ),
    ]
    m = ParsedMeasure(number=1, time_sig="4/4", beats=beats)
    assert _pitch_sequence(m) == [60, 64]


def test_pitch_sequence_takes_highest():
    beats = [
        ParsedBeat(
            notes=[
                ParsedNote(midi=48, pitch_name="C3", string=2, fret=0),
                ParsedNote(midi=60, pitch_name="C4", string=1, fret=0),
            ],
            start=1.0,
            duration=1.0,
        ),
    ]
    m = ParsedMeasure(number=1, time_sig="4/4", beats=beats)
    assert _pitch_sequence(m) == [60]


# --- _detect_contour ---


def test_contour_ascending():
    assert _detect_contour([60, 62, 64, 67]) == "ascending"


def test_contour_descending():
    assert _detect_contour([67, 64, 62, 60]) == "descending"


def test_contour_static():
    assert _detect_contour([60, 60, 60]) == "static"


def test_contour_arch():
    assert _detect_contour([60, 64, 67, 64, 60]) == "ascending\u2013descending"


def test_contour_valley():
    assert _detect_contour([67, 64, 60, 64, 67]) == "descending\u2013ascending"


def test_contour_single():
    assert _detect_contour([60]) == "static"


# --- _melodic_description ---


def test_melodic_arpeggio_ascending():
    # A3=57, C4=60, E4=64 — all Am chord tones, ascending
    m = _make_measure([57, 60, 64])
    desc = _melodic_description(m, _am_chord())
    assert "Am arpeggio" in desc
    assert "ascending" in desc


def test_melodic_arpeggio_with_passing_tone():
    # A3, C4, D4, E4 — D is not an Am chord tone
    m = _make_measure([57, 60, 62, 64])
    desc = _melodic_description(m, _am_chord())
    assert "arpeggio" in desc
    assert "passing tone" in desc
    assert "D" in desc


def test_melodic_scale_run():
    # C4, D4, E4, F4 — all steps of 1-2 semitones
    m = _make_measure([60, 62, 64, 65])
    desc = _melodic_description(m, _am_chord())
    assert "scale run" in desc


def test_melodic_repeated_note():
    m = _make_measure([60, 60, 60, 60])
    desc = _melodic_description(m, _am_chord())
    assert "repeated" in desc


def test_melodic_single_note():
    m = _make_measure([60])
    desc = _melodic_description(m, _am_chord())
    assert "single note" in desc


def test_melodic_no_chord():
    m = _make_measure([60, 62, 64, 65])
    desc = _melodic_description(m, None)
    assert "scale run" in desc


def test_melodic_figuration_fallback():
    # Large leaps — not arpeggio, not scale run
    m = _make_measure([60, 72, 55, 67])
    desc = _melodic_description(m, _am_chord())
    assert "figuration" in desc or "melodic line" in desc
