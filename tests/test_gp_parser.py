from pathlib import Path

from jackbutler.parsing.gp_parser import GPParser


def test_parse_c_major_file(c_major_gp5: Path):
    data = c_major_gp5.read_bytes()
    song = GPParser.parse(data, "test.gp5")

    assert song.title == "Test Song"
    assert song.artist == "Test Artist"
    assert len(song.tracks) >= 1

    track = song.tracks[0]
    assert track.is_percussion is False
    assert len(track.measures) >= 1

    measure = track.measures[0]
    assert measure.number == 1
    assert measure.time_sig == "4/4"
    assert len(measure.beats) >= 1

    # Check that C, E, G pitches are present
    all_midi = measure.all_pitches_midi
    assert 60 in all_midi  # C4
    assert 64 in all_midi  # E4
    assert 67 in all_midi  # G4


def test_parse_tracks_have_tuning(c_major_gp5: Path):
    data = c_major_gp5.read_bytes()
    song = GPParser.parse(data, "test.gp5")
    track = song.tracks[0]
    # Standard tuning
    assert track.tuning == [64, 59, 55, 50, 45, 40]
