from pydantic import BaseModel

from jackbutler.parsing.models import ParsedBeat


class ChordInfo(BaseModel):
    name: str
    root: str
    midi_pitches: list[int]
    beat_position: float
    confidence: float = 0.0
    roman_numeral: str = ""


class MeasureAnalysis(BaseModel):
    measure_number: int
    time_sig: str
    detected_key: str | None = None
    global_key: str | None = None
    mode: str | None = None
    key_confidence: float | None = None
    chords: list[ChordInfo] = []
    chord_alternatives: list[ChordInfo] = []
    roman_numerals: list[str] = []
    scale_degrees: list[str] = []  # e.g. ["A=i", "C=III", "D=iv"]
    commentary: str = ""
    harmonic_desc: str = ""
    melodic_desc: str = ""
    beats: list[ParsedBeat] = []
    note_names: list[str] = []


class TrackAnalysis(BaseModel):
    track_name: str
    track_index: int
    is_percussion: bool
    tuning: list[int] = []
    string_count: int = 6
    measures: list[MeasureAnalysis]


class SongAnalysis(BaseModel):
    title: str
    artist: str
    tracks: list[TrackAnalysis]
