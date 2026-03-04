from pathlib import Path

from jackbutler.analysis.engine import AnalysisEngine
from jackbutler.parsing.gp_parser import GPParser


def test_full_pipeline(c_major_gp5: Path):
    data = c_major_gp5.read_bytes()
    song = GPParser.parse(data, "test.gp5")
    engine = AnalysisEngine()
    analysis = engine.analyze(song)

    assert analysis.title == "Test Song"
    assert len(analysis.tracks) >= 1

    track = analysis.tracks[0]
    assert not track.is_percussion
    assert len(track.measures) >= 1

    m = track.measures[0]
    assert m.measure_number == 1
    assert m.detected_key is not None
    assert len(m.chords) > 0
    assert m.commentary != ""
