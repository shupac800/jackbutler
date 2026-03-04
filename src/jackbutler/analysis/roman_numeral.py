import re

from music21 import chord as m21chord, roman

from jackbutler.analysis.base import BaseAnalyzer
from jackbutler.analysis.models import ChordInfo
from jackbutler.parsing.models import ParsedMeasure

# Strip inversion figures (trailing digits) from roman numeral, keep quality symbols
_STRIP_FIGURES = re.compile(r"[0-9]+$")


class RomanNumeralAnalyzer(BaseAnalyzer):
    """Label chords as Roman numerals relative to the detected key."""

    def analyze_measure(self, measure: ParsedMeasure, context: dict) -> dict:
        key_result = context.get("key_result")
        chords: list[ChordInfo] = context.get("chords", [])

        if not key_result or not chords:
            return {"roman_numerals": []}

        numerals: list[str] = []
        for chord_info in chords:
            try:
                c = m21chord.Chord(chord_info.midi_pitches)
                rn = roman.romanNumeralFromChord(c, key_result)
                numerals.append(_STRIP_FIGURES.sub("", rn.figure))
            except Exception:
                numerals.append("?")

        return {"roman_numerals": numerals}
