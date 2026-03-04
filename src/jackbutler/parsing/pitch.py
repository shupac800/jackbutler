from music21 import pitch


def fret_to_midi(fret: int, string_tuning_midi: int) -> int:
    """Convert a fret number + open-string MIDI pitch to an absolute MIDI note."""
    return string_tuning_midi + fret


def midi_to_pitch(midi_value: int) -> str:
    """Convert a MIDI note number to a human-readable pitch name (e.g. 'C4')."""
    p = pitch.Pitch(midi=midi_value)
    return p.nameWithOctave
