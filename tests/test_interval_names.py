"""Tests for interval naming convention: R, b2, 2, b3, 3, 4, b5, 5, b6, 6, b7, 7."""

import re
from pathlib import Path

import pytest

from jackbutler.analysis.engine import _interval_from_root as engine_interval
from jackbutler.analysis.commentary import _interval_from_root as commentary_interval

VALID_LABELS = {"R", "b2", "2", "b3", "3", "4", "b5", "5", "b6", "6", "b7", "7"}

APP_JS = Path(__file__).resolve().parent.parent / "src" / "jackbutler" / "static" / "app.js"


# ---------------------------------------------------------------------------
# Python backend: _interval_from_root
# ---------------------------------------------------------------------------


class TestEngineIntervalFromRoot:
    """engine.py interval labels."""

    def test_unison_is_R(self):
        assert engine_interval("C", "C") == "R"

    def test_minor_third(self):
        assert engine_interval("E-", "C") == "b3"

    def test_major_third(self):
        assert engine_interval("E", "C") == "3"

    def test_perfect_fifth(self):
        assert engine_interval("G", "C") == "5"

    def test_minor_seventh(self):
        assert engine_interval("B-", "C") == "b7"

    def test_major_seventh(self):
        assert engine_interval("B", "C") == "7"

    def test_tritone(self):
        assert engine_interval("F#", "C") == "b5"

    def test_perfect_fourth(self):
        assert engine_interval("F", "C") == "4"

    def test_all_chromatic_from_c(self):
        pcs = ["C", "C#", "D", "E-", "E", "F", "F#", "G", "A-", "A", "B-", "B"]
        expected = ["R", "b2", "2", "b3", "3", "4", "b5", "5", "b6", "6", "b7", "7"]
        for pc, exp in zip(pcs, expected):
            assert engine_interval(pc, "C") == exp, f"{pc} from C should be {exp}"

    def test_all_labels_are_valid(self):
        pcs = ["C", "C#", "D", "E-", "E", "F", "F#", "G", "A-", "A", "B-", "B"]
        for pc in pcs:
            label = engine_interval(pc, "C")
            assert label in VALID_LABELS, f"Got invalid label '{label}' for {pc}"


class TestCommentaryIntervalFromRoot:
    """commentary.py interval labels."""

    def test_unison_is_R(self):
        assert commentary_interval("C", "C") == "R"

    def test_minor_third(self):
        assert commentary_interval("E-", "C") == "b3"

    def test_major_third(self):
        assert commentary_interval("E", "C") == "3"

    def test_perfect_fifth(self):
        assert commentary_interval("G", "C") == "5"

    def test_all_chromatic_from_a(self):
        """Test from a non-C root."""
        pcs = ["A", "B-", "B", "C", "C#", "D", "E-", "E", "F", "F#", "G", "G#"]
        expected = ["R", "b2", "2", "b3", "3", "4", "b5", "5", "b6", "6", "b7", "7"]
        for pc, exp in zip(pcs, expected):
            assert commentary_interval(pc, "A") == exp, f"{pc} from A should be {exp}"


# ---------------------------------------------------------------------------
# JS frontend: SEMI_TO_INTERVAL and chordToneLabel
# ---------------------------------------------------------------------------


class TestAppJsIntervalNames:
    """Verify app.js uses the new interval notation."""

    @pytest.fixture(autouse=True)
    def _load_js(self):
        self.js = APP_JS.read_text()

    def test_semi_to_interval_uses_new_notation(self):
        # Extract the SEMI_TO_INTERVAL object from JS
        match = re.search(r'const SEMI_TO_INTERVAL\s*=\s*\{([^}]+)\}', self.js)
        assert match, "SEMI_TO_INTERVAL not found in app.js"
        body = match.group(1)

        # Should contain new-style labels
        assert '"R"' in body
        assert '"b3"' in body
        assert '"5"' in body
        assert '"b7"' in body

        # Should NOT contain old-style labels
        assert '"P1"' not in body
        assert '"m2"' not in body
        assert '"M2"' not in body
        assert '"m3"' not in body
        assert '"M3"' not in body
        assert '"P4"' not in body
        assert '"TT"' not in body
        assert '"P5"' not in body

    def test_chord_tone_label_uses_R(self):
        """chordToneLabel should return 'R' not 'root'."""
        assert '"R"' in self.js
        # The old ordinal labels should not appear in chordToneLabel
        assert '"root"' not in self.js or self.js.count('"root"') == 0 or \
            'return "root"' not in self.js

    def test_no_ordinal_labels_in_chord_tone_label(self):
        """chordToneLabel should not return '3rd', '5th', '7th'."""
        assert 'return "3rd"' not in self.js
        assert 'return "5th"' not in self.js
        assert 'return "7th"' not in self.js

    def test_tooltip_maps_new_labels_to_degrees(self):
        """noteTooltipHtml must map 'R' → 1, '3' → 3, '5' → 5, '7' → 7."""
        assert '"R": 1' in self.js or '"R":1' in self.js


# ---------------------------------------------------------------------------
# Integration: real analysis data uses new labels
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


class TestAnalysisUsesNewLabels:
    """scale_degrees in analysis output use new interval notation."""

    def test_scale_degrees_use_valid_labels(self, la_catedral_analysis):
        track = la_catedral_analysis.tracks[0]
        for m in track.measures:
            for sd in m.scale_degrees:
                # Format is "PC=label"
                parts = sd.split("=", 1)
                assert len(parts) == 2, f"Bad scale_degree format: {sd}"
                label = parts[1]
                assert label in VALID_LABELS or label == "?", (
                    f"Measure {m.measure_number}: scale_degree label '{label}' "
                    f"is not in the valid set {VALID_LABELS}"
                )

    def test_no_old_style_labels(self, la_catedral_analysis):
        """Ensure 'root', '3rd', '5th', '7th' no longer appear."""
        old_labels = {"root", "3rd", "5th", "7th", "P1", "m2", "M2", "m3",
                      "M3", "P4", "TT", "P5", "m6", "M6", "m7", "M7"}
        track = la_catedral_analysis.tracks[0]
        for m in track.measures:
            for sd in m.scale_degrees:
                label = sd.split("=", 1)[1]
                assert label not in old_labels, (
                    f"Measure {m.measure_number}: old-style label '{label}' "
                    f"found in scale_degrees"
                )
