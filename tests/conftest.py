import tempfile
from pathlib import Path

import guitarpro
import pytest


@pytest.fixture
def c_major_gp5(tmp_path: Path) -> Path:
    """Generate a GP5 file with one measure containing a C major chord (C4-E4-G4)."""
    song = guitarpro.Song()
    song.title = "Test Song"
    song.artist = "Test Artist"

    track = song.tracks[0]
    track.name = "Lead Guitar"

    # Standard tuning: E4=64, B3=59, G3=55, D3=50, A2=45, E2=40
    track.strings = [
        guitarpro.GuitarString(number=1, value=64),
        guitarpro.GuitarString(number=2, value=59),
        guitarpro.GuitarString(number=3, value=55),
        guitarpro.GuitarString(number=4, value=50),
        guitarpro.GuitarString(number=5, value=45),
        guitarpro.GuitarString(number=6, value=40),
    ]

    measure = track.measures[0]
    voice = measure.voices[0]

    # Clear default beats
    voice.beats.clear()

    # Beat 1: C major chord — C4(60), E4(64), G4(67)
    beat = guitarpro.Beat(voice)
    beat.duration = guitarpro.Duration(value=2)  # half note

    # String 2, fret 1 → 59+1=60 (C4)
    n1 = guitarpro.Note(beat)
    n1.string = 2
    n1.value = 1
    n1.velocity = 95
    beat.notes.append(n1)

    # String 1, fret 0 → 64+0=64 (E4)
    n2 = guitarpro.Note(beat)
    n2.string = 1
    n2.value = 0
    n2.velocity = 95
    beat.notes.append(n2)

    # String 2, fret 8 → 59+8=67 (G4)  — actually let's use string 1 fret 3 = 67
    # Wait, string 1 already used. Use a separate beat for G.
    # Actually GP allows multiple notes on different strings in one beat.
    # String 3, fret 12 → 55+12=67 (G4)
    n3 = guitarpro.Note(beat)
    n3.string = 3
    n3.value = 12
    n3.velocity = 95
    beat.notes.append(n3)

    voice.beats.append(beat)

    # Beat 2: same chord, half note
    beat2 = guitarpro.Beat(voice)
    beat2.duration = guitarpro.Duration(value=2)

    n4 = guitarpro.Note(beat2)
    n4.string = 2
    n4.value = 1
    n4.velocity = 95
    beat2.notes.append(n4)

    n5 = guitarpro.Note(beat2)
    n5.string = 1
    n5.value = 0
    n5.velocity = 95
    beat2.notes.append(n5)

    n6 = guitarpro.Note(beat2)
    n6.string = 3
    n6.value = 12
    n6.velocity = 95
    beat2.notes.append(n6)

    voice.beats.append(beat2)

    filepath = tmp_path / "test_c_major.gp5"
    guitarpro.write(song, str(filepath))
    return filepath
