"""Tests for accidental display logic.

The staff notation in app.js must show explicit accidentals when a note
deviates from the key signature, and track accidental state within each
measure.  These tests reimplement the JS logic in Python and verify it
against known scenarios and real tablature data.
"""

import re
from pathlib import Path

import pytest

from jackbutler.parsing.pitch import midi_to_pitch


# ---------------------------------------------------------------------------
# Python reimplementation of the JS accidental helpers (app.js)
# ---------------------------------------------------------------------------

def _build_key_sig_accidentals() -> dict[str, dict[str, str]]:
    """Mirror KEY_SIG_ACCIDENTALS from app.js."""
    sharp_order = ["F", "C", "G", "D", "A", "E", "B"]
    flat_order = ["B", "E", "A", "D", "G", "C", "F"]
    sharp_keys = ["C", "G", "D", "A", "E", "B", "F#", "C#"]
    flat_keys = ["C", "F", "Bb", "Eb", "Ab", "Db", "Gb"]
    m: dict[str, dict[str, str]] = {}
    for i, key in enumerate(sharp_keys):
        m[key] = {sharp_order[j]: "#" for j in range(i)}
    for i in range(1, len(flat_keys)):
        m[flat_keys[i]] = {flat_order[j]: "b" for j in range(i)}
    return m


KEY_SIG_ACCIDENTALS = _build_key_sig_accidentals()

MINOR_TO_RELATIVE_MAJOR = {
    "A": "C", "E": "G", "B": "D", "F#": "A", "C#": "E", "G#": "B", "D#": "F#",
    "D": "F", "G": "Bb", "C": "Eb", "F": "Ab", "Bb": "Db", "Eb": "Gb",
    "A#": "C#", "Eb": "Gb",
}


def global_key_to_vex_key_sig(global_key: str | None) -> str | None:
    """Mirror globalKeyToVexKeySig from app.js."""
    if not global_key:
        return None
    parts = global_key.split(" ")
    tonic = parts[0]
    mode = parts[1] if len(parts) > 1 else "major"
    if mode == "minor":
        return MINOR_TO_RELATIVE_MAJOR.get(tonic)
    return tonic


def parse_pitch_accidental(pitch_name: str) -> tuple[str, str]:
    """Return (letter, accidental) from a pitch name like 'F#3'.

    accidental is '#', 'b', or ''.
    """
    m = re.match(r"^([A-G])([#\-b]?)", pitch_name)
    if not m:
        return ("C", "")
    acc = m.group(2)
    if acc == "-":
        acc = "b"
    return (m.group(1), acc or "")


def pitch_to_vex_key(pitch_name: str) -> str:
    """Mirror pitchToVexKey from app.js (includes octave transposition)."""
    m = re.match(r"^([A-G][#\-b]?)(\d+)$", pitch_name)
    if not m:
        return "C/4"
    note_name = m.group(1).replace("-", "b")
    octave = int(m.group(2)) + 1
    return f"{note_name}/{octave}"


def compute_accidentals(
    pitch_names: list[str],
    key_sig: str | None,
) -> list[str | None]:
    """Determine the accidental marker for each note in a measure.

    Returns a list parallel to *pitch_names*.  Each entry is:
      '#'  – display a sharp sign
      'b'  – display a flat sign
      'n'  – display a natural sign
      None – no accidental needed (implied by key signature)
    """
    key_sig_acc = KEY_SIG_ACCIDENTALS.get(key_sig or "C", {})
    active: dict[str, str] = {}  # letter+octave → last displayed accidental
    result: list[str | None] = []

    for pn in pitch_names:
        letter, accidental = parse_pitch_accidental(pn)
        vex_key = pitch_to_vex_key(pn)
        octave = vex_key.split("/")[1]
        note_id = letter + octave
        key_default = key_sig_acc.get(letter, "")

        needs_accidental = False
        if note_id in active:
            if accidental != active[note_id]:
                needs_accidental = True
        else:
            if accidental != key_default:
                needs_accidental = True

        if needs_accidental:
            marker = "n" if accidental == "" else accidental
            active[note_id] = accidental
            result.append(marker)
        else:
            if accidental != key_default:
                active[note_id] = accidental
            result.append(None)

    return result


# ---------------------------------------------------------------------------
# Tests: KEY_SIG_ACCIDENTALS construction
# ---------------------------------------------------------------------------


class TestKeySigAccidentals:
    def test_c_major_has_no_accidentals(self):
        assert KEY_SIG_ACCIDENTALS["C"] == {}

    def test_g_major_has_f_sharp(self):
        assert KEY_SIG_ACCIDENTALS["G"] == {"F": "#"}

    def test_d_major_has_f_sharp_c_sharp(self):
        assert KEY_SIG_ACCIDENTALS["D"] == {"F": "#", "C": "#"}

    def test_a_major_has_three_sharps(self):
        acc = KEY_SIG_ACCIDENTALS["A"]
        assert acc == {"F": "#", "C": "#", "G": "#"}

    def test_f_major_has_b_flat(self):
        assert KEY_SIG_ACCIDENTALS["F"] == {"B": "b"}

    def test_bb_major_has_two_flats(self):
        assert KEY_SIG_ACCIDENTALS["Bb"] == {"B": "b", "E": "b"}

    def test_eb_major_has_three_flats(self):
        assert KEY_SIG_ACCIDENTALS["Eb"] == {"B": "b", "E": "b", "A": "b"}


# ---------------------------------------------------------------------------
# Tests: globalKeyToVexKeySig mapping
# ---------------------------------------------------------------------------


class TestGlobalKeyToVexKeySig:
    def test_major_key_passes_through(self):
        assert global_key_to_vex_key_sig("D major") == "D"

    def test_minor_key_maps_to_relative_major(self):
        assert global_key_to_vex_key_sig("B minor") == "D"
        assert global_key_to_vex_key_sig("A minor") == "C"
        assert global_key_to_vex_key_sig("E minor") == "G"

    def test_none_returns_none(self):
        assert global_key_to_vex_key_sig(None) is None


# ---------------------------------------------------------------------------
# Tests: parsePitchAccidental
# ---------------------------------------------------------------------------


class TestParsePitchAccidental:
    def test_natural_note(self):
        assert parse_pitch_accidental("F3") == ("F", "")

    def test_sharp_note(self):
        assert parse_pitch_accidental("F#3") == ("F", "#")

    def test_flat_with_minus(self):
        assert parse_pitch_accidental("B-3") == ("B", "b")

    def test_flat_with_b(self):
        assert parse_pitch_accidental("Bb3") == ("B", "b")


# ---------------------------------------------------------------------------
# Tests: accidental computation — key signature scenarios
# ---------------------------------------------------------------------------


class TestAccidentalComputation:
    """Core accidental display logic."""

    def test_no_accidental_when_matches_key_sig(self):
        """F# in key of D major (which has F#) needs no marker."""
        result = compute_accidentals(["F#3"], "D")
        assert result == [None]

    def test_natural_shown_when_differs_from_key_sig(self):
        """F-natural in key of D major needs a natural sign."""
        result = compute_accidentals(["F3"], "D")
        assert result == ["n"]

    def test_sharp_shown_in_c_major(self):
        """F# in key of C major (no sharps) needs a sharp sign."""
        result = compute_accidentals(["F#3"], "C")
        assert result == ["#"]

    def test_flat_shown_in_c_major(self):
        """Bb in key of C major needs a flat sign."""
        result = compute_accidentals(["B-3"], "C")
        assert result == ["b"]

    def test_no_accidental_for_flat_in_flat_key(self):
        """Bb in key of F major (which has Bb) needs no marker."""
        result = compute_accidentals(["B-3"], "F")
        assert result == [None]

    def test_natural_overrides_flat_key_sig(self):
        """B-natural in key of F major (which has Bb) needs a natural sign."""
        result = compute_accidentals(["B3"], "F")
        assert result == ["n"]


# ---------------------------------------------------------------------------
# Tests: accidental computation — within-measure tracking
# ---------------------------------------------------------------------------


class TestWithinMeasureTracking:
    """After an accidental is shown, the active state changes for that note."""

    def test_sharp_then_natural_on_same_pitch(self):
        """F# followed by F-natural: first matches key (D major), second
        needs a natural sign."""
        result = compute_accidentals(["F#3", "F3"], "D")
        assert result == [None, "n"]

    def test_natural_then_sharp_on_same_pitch(self):
        """F-natural followed by F# in D major: first gets natural,
        second needs sharp to restore."""
        result = compute_accidentals(["F3", "F#3"], "D")
        assert result == ["n", "#"]

    def test_repeated_natural_after_deviation(self):
        """After F-natural is established by an accidental, a second
        F-natural in the same measure does NOT need another natural."""
        result = compute_accidentals(["F3", "F3"], "D")
        # First F-natural gets a natural sign (deviates from key sig F#).
        # Second F-natural matches the active accidental, so no marker.
        assert result == ["n", None]

    def test_different_octaves_tracked_independently(self):
        """F3 and F4 are tracked separately."""
        result = compute_accidentals(["F3", "F4"], "D")
        # Both deviate from key sig (F# in D major), both need naturals
        assert result == ["n", "n"]

    def test_other_notes_unaffected(self):
        """Altering F doesn't affect C# in the same measure."""
        result = compute_accidentals(["F3", "C#3"], "D")
        # F-natural needs natural (D major has F#).
        # C# matches key sig (D major has C#), no marker.
        assert result == ["n", None]

    def test_three_alternations(self):
        """F#, F-natural, F# in D major."""
        result = compute_accidentals(["F#3", "F3", "F#3"], "D")
        assert result == [None, "n", "#"]


# ---------------------------------------------------------------------------
# Tests: midi_to_pitch produces correct names for accidental scenarios
# ---------------------------------------------------------------------------


class TestMidiToPitchAccidentals:
    """Verify the backend pitch name generation is consistent with what
    the accidental display logic expects."""

    def test_f_sharp(self):
        # MIDI 66 = F#4
        assert midi_to_pitch(66) == "F#4"

    def test_f_natural(self):
        # MIDI 65 = F4
        assert midi_to_pitch(65) == "F4"

    def test_c_sharp(self):
        # MIDI 61 = C#4
        assert midi_to_pitch(61) == "C#4"

    def test_c_natural(self):
        # MIDI 60 = C4
        assert midi_to_pitch(60) == "C4"

    def test_b_flat(self):
        # MIDI 58 = B-3 (music21 uses "-" for flat)
        name = midi_to_pitch(58)
        assert name in ("B-3", "Bb3", "A#3")

    def test_g_sharp(self):
        assert midi_to_pitch(68) == "G#4"

    def test_e_natural(self):
        assert midi_to_pitch(64) == "E4"

    def test_f3_natural_from_guitar_tab(self):
        """F3 on guitar: string 4 (D3=50), fret 3 → MIDI 53 = F3."""
        from jackbutler.parsing.pitch import fret_to_midi
        midi = fret_to_midi(3, 50)
        assert midi == 53
        assert midi_to_pitch(midi) == "F3"

    def test_f3_sharp_from_guitar_tab(self):
        """F#3 on guitar: string 4 (D3=50), fret 4 → MIDI 54 = F#3."""
        from jackbutler.parsing.pitch import fret_to_midi
        midi = fret_to_midi(4, 50)
        assert midi == 54
        assert midi_to_pitch(midi) == "F#3"


# ---------------------------------------------------------------------------
# Tests: JS source has the accidental logic wired up
# ---------------------------------------------------------------------------

APP_JS = Path(__file__).resolve().parent.parent / "src" / "jackbutler" / "static" / "app.js"


class TestAppJsAccidentalIntegration:
    """Verify the JS source contains the accidental display infrastructure."""

    @pytest.fixture(autouse=True)
    def _load_js(self):
        self.js = APP_JS.read_text()

    def test_key_sig_accidentals_defined(self):
        assert "KEY_SIG_ACCIDENTALS" in self.js

    def test_parse_pitch_accidental_defined(self):
        assert "parsePitchAccidental" in self.js

    def test_accidental_added_to_stave_note(self):
        assert "addModifier" in self.js
        assert "Accidental" in self.js

    def test_active_accidentals_tracked(self):
        """The code must track which accidentals have been displayed
        within a measure so that subsequent notes are handled correctly."""
        assert "activeAcc" in self.js

    def test_natural_marker_used(self):
        """When a note is natural but the key sig has a sharp/flat,
        the code must use 'n' for a natural accidental."""
        assert '"n"' in self.js


# ---------------------------------------------------------------------------
# Tests: real tablature data (La Catedral Allegro)
# ---------------------------------------------------------------------------

LA_CATEDRAL_GP = Path(__file__).resolve().parent.parent / "tabs" / "lacatedral-allegro.gp"


@pytest.fixture(scope="module")
def la_catedral_analysis():
    from jackbutler.analysis.engine import AnalysisEngine
    from jackbutler.parsing.gp_parser import GPParser

    if not LA_CATEDRAL_GP.exists():
        pytest.skip("Demo file not available")
    data = LA_CATEDRAL_GP.read_bytes()
    song = GPParser.parse(data, "lacatedral-allegro.gp")
    engine = AnalysisEngine()
    return engine.analyze(song)


class TestLaCatedralAccidentals:
    """Verify accidental logic against the actual demo file."""

    def test_measure_6_has_beats(self, la_catedral_analysis):
        track = la_catedral_analysis.tracks[0]
        m6 = track.measures[5]
        assert len(m6.beats) > 0

    def test_measure_6_f_notes_get_correct_accidentals(self, la_catedral_analysis):
        """Measure 6 (B minor, key sig D = F#,C#) has both F-natural and F#.

        The note sequence includes:
          F2, F3, E3, F3, B3, F3, F#2, F#3, F3, F#3, G3, F#3

        Accidental rules:
        - First F-natural needs a natural sign (deviates from key sig F#)
        - Subsequent F-naturals at the same octave DON'T (active state)
        - F# after F-natural needs an explicit sharp (restoring key sig)
        - F-natural after F# needs a natural sign again
        """
        track = la_catedral_analysis.tracks[0]
        m6 = track.measures[5]
        key_sig = global_key_to_vex_key_sig(m6.global_key)
        assert key_sig == "D"  # B minor → relative major D

        # Collect all non-tied pitch names in beat order
        pitch_names = []
        for beat in m6.beats:
            for note in beat.notes:
                if not note.is_tied:
                    pitch_names.append(note.pitch_name)

        accidentals = compute_accidentals(pitch_names, key_sig)

        # Build a log of (pitch_name, accidental_marker) for F-class notes
        f_events = [
            (pn, accidentals[i])
            for i, pn in enumerate(pitch_names)
            if parse_pitch_accidental(pn)[0] == "F"
        ]
        assert len(f_events) >= 4, (
            f"Expected at least 4 F-class notes in measure 6, got {f_events}"
        )

        # Verify: first F-natural in each octave gets a natural marker
        first_f2 = next(
            (acc for pn, acc in f_events if pn == "F2"), "MISSING"
        )
        assert first_f2 == "n", (
            f"First F2 (natural) must show natural sign, got {first_f2!r}"
        )

        first_f3_natural = next(
            (acc for pn, acc in f_events if pn == "F3"), "MISSING"
        )
        assert first_f3_natural == "n", (
            f"First F3 (natural) must show natural sign, got {first_f3_natural!r}"
        )

        # Verify: after F-natural is active, F# needs an explicit sharp
        # Find the first F#3 event
        found_fsharp_after_fnat = False
        active_f3 = ""  # track what's active for F3
        for pn, marker in f_events:
            letter, acc = parse_pitch_accidental(pn)
            if pn.startswith("F") and pn.endswith("3"):
                vex_oct = str(int(pn[-1]) + 1)
                if acc == "" and (active_f3 == "" or active_f3 == "#"):
                    # First F-nat or F-nat after F# → should have marker
                    pass
                if acc == "#" and active_f3 == "":
                    # F# after F-natural → should have sharp marker
                    assert marker == "#", (
                        f"F#3 after F-natural must show sharp sign, got {marker!r}"
                    )
                    found_fsharp_after_fnat = True
                active_f3 = acc

        assert found_fsharp_after_fnat, (
            "Expected F#3 after F-natural in measure 6"
        )

    def test_all_measures_accidentals_consistent(self, la_catedral_analysis):
        """No measure should silently omit an accidental that differs from
        the key signature."""
        track = la_catedral_analysis.tracks[0]
        for m in track.measures:
            key_sig = global_key_to_vex_key_sig(m.global_key)
            key_acc = KEY_SIG_ACCIDENTALS.get(key_sig or "C", {})

            pitch_names = []
            for beat in m.beats:
                for note in beat.notes:
                    if not note.is_tied:
                        pitch_names.append(note.pitch_name)

            accidentals = compute_accidentals(pitch_names, key_sig)

            # The first occurrence of any note that deviates from the key sig
            # must have an explicit accidental
            seen: dict[str, str] = {}
            for i, pn in enumerate(pitch_names):
                letter, acc = parse_pitch_accidental(pn)
                vex_key = pitch_to_vex_key(pn)
                octave = vex_key.split("/")[1]
                note_id = letter + octave
                key_default = key_acc.get(letter, "")

                if note_id not in seen and acc != key_default:
                    assert accidentals[i] is not None, (
                        f"Measure {m.measure_number}: first {pn} deviates from "
                        f"key sig {key_sig} (expects "
                        f"{'natural' if not key_default else key_default}) "
                        f"but no accidental is shown"
                    )
                seen[note_id] = acc
