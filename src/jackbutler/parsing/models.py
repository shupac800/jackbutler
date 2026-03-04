from pydantic import BaseModel


class ParsedNote(BaseModel):
    midi: int
    pitch_name: str
    string: int  # 1-indexed string number
    fret: int
    is_tied: bool = False
    degree: int | None = None  # scale degree (1=root, 3=third, 5=fifth, etc.)


class ParsedBeat(BaseModel):
    notes: list[ParsedNote]
    start: float  # beat position within the measure (1-based)
    duration: float  # in quarter-note lengths


class ParsedMeasure(BaseModel):
    number: int  # 1-indexed
    time_sig: str  # e.g. "4/4"
    beats: list[ParsedBeat]

    @property
    def all_pitches_midi(self) -> list[int]:
        """All unique non-tied MIDI pitches in this measure."""
        seen: set[int] = set()
        result: list[int] = []
        for beat in self.beats:
            for n in beat.notes:
                if not n.is_tied and n.midi not in seen:
                    seen.add(n.midi)
                    result.append(n.midi)
        return result


class ParsedTrack(BaseModel):
    name: str
    index: int
    is_percussion: bool
    tuning: list[int]  # MIDI values per string, high to low
    measures: list[ParsedMeasure]


class ParsedSong(BaseModel):
    title: str
    artist: str
    tracks: list[ParsedTrack]
