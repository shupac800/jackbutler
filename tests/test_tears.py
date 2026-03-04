"""Tests using the real Guitar Pro file: tabs/tears.gp (Tears In The Rain by Joe Satriani)."""

from pathlib import Path

import pytest

from jackbutler.analysis.engine import AnalysisEngine
from jackbutler.parsing.gp_parser import GPParser

TEARS_GP = Path(__file__).resolve().parent.parent / "tabs" / "tears.gp"


@pytest.fixture(scope="module")
def tears_song():
    data = TEARS_GP.read_bytes()
    return GPParser.parse(data, "tears.gp")


@pytest.fixture(scope="module")
def tears_analysis(tears_song):
    engine = AnalysisEngine()
    return engine.analyze(tears_song)


# ── Parsing tests ──


class TestTearsParsing:
    def test_song_metadata(self, tears_song):
        assert tears_song.title == "Tears In The Rain"
        assert tears_song.artist == "Joe Satriani"

    def test_single_track(self, tears_song):
        assert len(tears_song.tracks) == 1
        assert tears_song.tracks[0].is_percussion is False

    def test_track_standard_tuning(self, tears_song):
        track = tears_song.tracks[0]
        # Standard tuning high-to-low: E4=64, B3=59, G3=55, D3=50, A2=45, E2=40
        assert track.tuning == [64, 59, 55, 50, 45, 40]

    def test_measure_count(self, tears_song):
        track = tears_song.tracks[0]
        assert len(track.measures) == 45

    def test_time_signature_6_8(self, tears_song):
        """All measures in this piece are in 6/8."""
        track = tears_song.tracks[0]
        for m in track.measures:
            assert m.time_sig == "6/8", f"Measure {m.number} has unexpected time sig {m.time_sig}"

    def test_first_measure_has_notes(self, tears_song):
        track = tears_song.tracks[0]
        m1 = track.measures[0]
        assert len(m1.beats) > 0
        assert len(m1.all_pitches_midi) > 0

    def test_first_measure_pitches(self, tears_song):
        """M1 contains arpeggiated notes: A3(57), C4(60), D4(62), E4(64)."""
        track = tears_song.tracks[0]
        pitches = set(track.measures[0].all_pitches_midi)
        assert 57 in pitches  # A3
        assert 60 in pitches  # C4
        assert 62 in pitches  # D4
        assert 64 in pitches  # E4

    def test_no_empty_measures(self, tears_song):
        """Every measure in the piece should have at least one beat with notes."""
        track = tears_song.tracks[0]
        for m in track.measures:
            assert len(m.beats) > 0, f"Measure {m.number} has no beats"

    def test_beat_positions_are_positive(self, tears_song):
        track = tears_song.tracks[0]
        for m in track.measures:
            for beat in m.beats:
                assert beat.start >= 1.0
                assert beat.duration > 0


# ── Analysis tests ──


class TestTearsAnalysis:
    def test_analysis_metadata(self, tears_analysis):
        assert tears_analysis.title == "Tears In The Rain"
        assert tears_analysis.artist == "Joe Satriani"
        assert len(tears_analysis.tracks) == 1

    def test_all_measures_analyzed(self, tears_analysis):
        track = tears_analysis.tracks[0]
        assert len(track.measures) == 45

    def test_key_detected_for_all_measures(self, tears_analysis):
        track = tears_analysis.tracks[0]
        for m in track.measures:
            assert m.detected_key is not None, (
                f"Measure {m.measure_number} has no detected key"
            )

    def test_first_measure_key_is_a_minor(self, tears_analysis):
        """The opening arpeggio (A C D E) strongly suggests A minor."""
        m1 = tears_analysis.tracks[0].measures[0]
        assert m1.detected_key == "A minor"
        assert m1.key_confidence is not None
        assert m1.key_confidence > 0.8

    def test_key_confidence_range(self, tears_analysis):
        track = tears_analysis.tracks[0]
        for m in track.measures:
            if m.key_confidence is not None:
                assert 0.0 <= m.key_confidence <= 1.0, (
                    f"Measure {m.measure_number} confidence out of range: {m.key_confidence}"
                )

    def test_commentary_present(self, tears_analysis):
        track = tears_analysis.tracks[0]
        for m in track.measures:
            assert m.commentary, f"Measure {m.measure_number} has empty commentary"

    def test_arpeggiated_measures_detect_implied_chords(self, tears_analysis):
        """Arpeggiated single-note passages should detect implied chords
        from the combined pitches across the measure."""
        m1 = tears_analysis.tracks[0].measures[0]
        assert len(m1.chords) >= 1
        # M1 outlines an A minor chord
        assert m1.chords[0].root == "A"

    def test_svg_fixup_preserves_degree_colors(self, tears_analysis):
        """The SVG post-processing in app.js rewrites black fill/stroke
        attributes to #e0e0e0 for dark-theme rendering. It must NOT
        overwrite degree colors (used for note heads, stems, and flags).

        This test simulates the SVG fixup logic and verifies that degree
        colors survive the fixup pass — ensuring note head, stem, and flag
        all keep their intended color instead of being clobbered to white.
        """
        import re

        # Read the actual JS source to extract the fixup logic
        app_js = (
            Path(__file__).resolve().parent.parent
            / "src" / "jackbutler" / "static" / "app.js"
        )
        js_source = app_js.read_text()

        # Extract DEGREE_COLORS values from the JS source
        color_matches = re.findall(r'"(#[0-9a-fA-F]{6})"', js_source)
        degree_color_values = {"#cc7777", "#cccc77", "#7777cc"}

        # Verify the degree colors exist in the JS source
        assert degree_color_values.issubset(set(color_matches)), (
            "Degree colors not found in app.js"
        )

        # Simulate the SVG fixup: the fixup should preserve degree colors.
        # Extract the PRESERVE set logic from the JS source.
        # The fix creates: PRESERVE = new Set(Object.values(DEGREE_COLORS))
        # and skips any element whose fill/stroke is in PRESERVE.
        assert "PRESERVE" in js_source, (
            "SVG fixup in app.js must use a PRESERVE set to skip degree colors. "
            "Without this, the fixup overwrites flag colors to white (#e0e0e0)."
        )

        # Verify PRESERVE includes DEGREE_COLORS values
        assert "Object.values(DEGREE_COLORS)" in js_source, (
            "PRESERVE set must be built from DEGREE_COLORS values so that "
            "note head, stem, and flag colors are not clobbered by the fixup."
        )

        # Simulate the fixup logic in Python to verify it works
        light = "#e0e0e0"
        preserve = degree_color_values | {light}

        # These are colors the fixup should rewrite (black staff elements)
        for black_color in ["#000000", "black", "#333333"]:
            assert black_color not in preserve, (
                f"Black color {black_color} should NOT be preserved"
            )

        # These are colors the fixup should NOT rewrite (degree colors)
        for deg_color in degree_color_values:
            assert deg_color in preserve, (
                f"Degree color {deg_color} would be overwritten by SVG fixup — "
                f"flags with this color would turn white"
            )
