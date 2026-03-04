from jackbutler.parsing.pitch import fret_to_midi, midi_to_pitch


def test_fret_to_midi_open_string():
    # Open high E string (MIDI 64) → E4
    assert fret_to_midi(0, 64) == 64


def test_fret_to_midi_fretted():
    # 5th fret on B string (MIDI 59) → 59+5=64 → E4
    assert fret_to_midi(5, 59) == 64


def test_fret_to_midi_low_e():
    # 3rd fret on low E (MIDI 40) → 43 → G2
    assert fret_to_midi(3, 40) == 43


def test_midi_to_pitch_middle_c():
    assert midi_to_pitch(60) == "C4"


def test_midi_to_pitch_e4():
    assert midi_to_pitch(64) == "E4"


def test_midi_to_pitch_a440():
    assert midi_to_pitch(69) == "A4"
