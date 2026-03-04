import re

from music21 import chord as m21chord, roman

from jackbutler.analysis.base import BaseAnalyzer
from jackbutler.analysis.models import ChordInfo
from jackbutler.parsing.models import ParsedMeasure

# Strip inversion figures (trailing digits) from roman numeral, keep quality symbols
_STRIP_FIGURES = re.compile(r"[0-9]+$")


def _compute_roman_numeral(chord_info: ChordInfo, key_result) -> str:
    """Compute a roman numeral for a single chord in the given key."""
    try:
        c = m21chord.Chord(chord_info.midi_pitches)
        rn = roman.romanNumeralFromChord(c, key_result)
        return _STRIP_FIGURES.sub("", rn.figure)
    except Exception:
        return "?"


class RomanNumeralAnalyzer(BaseAnalyzer):
    """Label chords as Roman numerals relative to the detected key."""

    def analyze_measure(self, measure: ParsedMeasure, context: dict) -> dict:
        key_result = context.get("key_result")
        chords: list[ChordInfo] = context.get("chords", [])
        chord_alternatives: list[ChordInfo] = context.get("chord_alternatives", [])

        if not key_result or not chords:
            return {"roman_numerals": [], "chord_alternatives": chord_alternatives}

        numerals: list[str] = []
        for chord_info in chords:
            rn_str = _compute_roman_numeral(chord_info, key_result)
            chord_info.roman_numeral = rn_str
            numerals.append(rn_str)

        # Compute roman numerals for alternatives too
        for alt in chord_alternatives:
            alt.roman_numeral = _compute_roman_numeral(alt, key_result)

        return {"roman_numerals": numerals, "chord_alternatives": chord_alternatives}
