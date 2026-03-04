from music21 import chord as m21chord, interval as m21interval, pitch as m21pitch

from jackbutler.analysis.base import BaseAnalyzer
from jackbutler.analysis.chord_analyzer import ChordAnalyzer
from jackbutler.analysis.commentary import CommentaryGenerator
from jackbutler.analysis.key_analyzer import (
    KeyAnalyzer,
    choose_best_key,
    detect_key,
    get_scale_degree_label,
)
from jackbutler.analysis.models import (
    ChordInfo,
    MeasureAnalysis,
    SongAnalysis,
    TrackAnalysis,
)
from jackbutler.analysis.roman_numeral import RomanNumeralAnalyzer
from jackbutler.parsing.models import ParsedMeasure, ParsedSong


def _chord_tone_map(chord_info: ChordInfo) -> dict[str, int]:
    """Build a pitch-class → chord-tone-degree map (root=1, 3rd=3, 5th=5, 7th=7)."""
    c = m21chord.Chord(chord_info.midi_pitches)
    tone_map: dict[str, int] = {}
    try:
        tone_map[c.root().name] = 1
    except Exception:
        pass
    if c.third:
        tone_map[c.third.name] = 3
    if c.fifth:
        tone_map[c.fifth.name] = 5
    if c.seventh:
        tone_map[c.seventh.name] = 7
    return tone_map


def _interval_from_root(pc: str, root_name: str) -> str:
    """Return the interval shorthand from chord root to a pitch class (e.g. 'P4')."""
    try:
        root = m21pitch.Pitch(root_name + "3")
        target = m21pitch.Pitch(pc + "3")
        if target.midi < root.midi:
            target.octave += 1
        return m21interval.Interval(root, target).semiSimpleName
    except Exception:
        return "?"


def _chord_tone_label(
    ct_deg: int | None, pc: str, chord_root: str | None
) -> str:
    """Return a display label for a pitch in chord context."""
    if ct_deg == 1:
        return "root"
    if ct_deg == 3:
        return "3rd"
    if ct_deg == 5:
        return "5th"
    if ct_deg == 7:
        return "7th"
    # Non-chord tone: show interval from root
    if chord_root:
        return _interval_from_root(pc, chord_root)
    return "?"


class AnalysisEngine:
    """Runs all analyzers in order on each measure of a song."""

    def __init__(self, analyzers: list[BaseAnalyzer] | None = None):
        self.analyzers = analyzers or [
            KeyAnalyzer(),
            ChordAnalyzer(),
            RomanNumeralAnalyzer(),
            CommentaryGenerator(),
        ]

    def _get_adjacent_pitches(
        self, measures: list[ParsedMeasure], index: int
    ) -> list[int]:
        """Collect pitches from neighboring measures for better key detection."""
        pitches: list[int] = []
        if index > 0:
            pitches.extend(measures[index - 1].all_pitches_midi)
        if index < len(measures) - 1:
            pitches.extend(measures[index + 1].all_pitches_midi)
        return pitches

    def analyze(self, song: ParsedSong) -> SongAnalysis:
        track_analyses: list[TrackAnalysis] = []

        for track in song.tracks:
            if track.is_percussion:
                track_analyses.append(TrackAnalysis(
                    track_name=track.name,
                    track_index=track.index,
                    is_percussion=True,
                    measures=[],
                ))
                continue

            # --- Global key detection across entire track ---
            all_track_pitches: list[int] = []
            for m in track.measures:
                all_track_pitches.extend(m.all_pitches_midi)
            global_key = detect_key(all_track_pitches)

            # --- First pass: per-measure key detection ---
            per_measure_keys = []
            for i, measure in enumerate(track.measures):
                adj = self._get_adjacent_pitches(track.measures, i)
                pitches = measure.all_pitches_midi
                if len(pitches) < 2:
                    pitches = pitches + adj
                mk = detect_key(pitches)
                per_measure_keys.append(mk)

            # --- Second pass: full analysis with global context ---
            measure_analyses: list[MeasureAnalysis] = []
            for i, measure in enumerate(track.measures):
                context: dict = {
                    "adjacent_pitches": self._get_adjacent_pitches(
                        track.measures, i
                    ),
                    "global_key": global_key,
                    "measure_index": i,
                    "total_measures": len(track.measures),
                    "prev_key": per_measure_keys[i - 1] if i > 0 else None,
                    "next_key": per_measure_keys[i + 1] if i < len(track.measures) - 1 else None,
                }

                # Collect unique non-tied pitch names in order
                note_names: list[str] = []
                seen_pitches: set[str] = set()
                for beat in measure.beats:
                    for n in beat.notes:
                        if not n.is_tied and n.pitch_name not in seen_pitches:
                            seen_pitches.add(n.pitch_name)
                            note_names.append(n.pitch_name)

                global_key_name = (
                    f"{global_key.tonic.name} {global_key.mode}" if global_key else None
                )

                results: dict = {
                    "measure_number": measure.number,
                    "time_sig": measure.time_sig,
                    "beats": measure.beats,
                    "note_names": note_names,
                    "scale_degrees": [],
                    "global_key": global_key_name,
                }

                # Run analyzers (KeyAnalyzer runs first, picks best key)
                for analyzer in self.analyzers:
                    findings = analyzer.analyze_measure(measure, context)
                    context.update(findings)
                    results.update(findings)

                # After analyzers: annotate beats with degree numbers.
                # When a chord is detected, color by chord tone (root=1, 3rd=3, 5th=5).
                # Otherwise fall back to scale degree in the detected key.
                chords: list[ChordInfo] = context.get("chords", [])
                chosen_key = context.get("key_result") or global_key
                scale_degrees: list[str] = []
                annotated_beats = []

                # Build chord-tone map if we have chords
                ct_map: dict[str, int] = {}
                chord_root: str | None = None
                if chords:
                    # Use the first/primary chord for coloring
                    ct_map = _chord_tone_map(chords[0])
                    chord_root = chords[0].root

                seen_pcs: set[str] = set()
                for beat in measure.beats:
                    annotated_notes = []
                    for n in beat.notes:
                        pc = m21pitch.Pitch(midi=n.midi).name
                        degree_num = None
                        if not n.is_tied:
                            if ct_map:
                                # Color by chord tone
                                degree_num = ct_map.get(pc)
                            elif chosen_key:
                                # Fall back to key-based scale degree
                                try:
                                    degree_num = chosen_key.getScaleDegreeFromPitch(
                                        m21pitch.Pitch(pc)
                                    )
                                except Exception:
                                    pass
                            if pc not in seen_pcs:
                                seen_pcs.add(pc)
                                if ct_map:
                                    label = _chord_tone_label(
                                        ct_map.get(pc), pc, chord_root
                                    )
                                    scale_degrees.append(f"{pc}={label}")
                                elif chosen_key:
                                    label = get_scale_degree_label(pc, chosen_key)
                                    scale_degrees.append(
                                        f"{pc}={label}" if label else f"{pc}=chromatic"
                                    )
                        annotated_notes.append(n.model_copy(update={"degree": degree_num}))
                    annotated_beats.append(beat.model_copy(update={"notes": annotated_notes}))
                results["beats"] = annotated_beats
                results["scale_degrees"] = scale_degrees

                measure_analyses.append(MeasureAnalysis(**results))

            track_analyses.append(TrackAnalysis(
                track_name=track.name,
                track_index=track.index,
                is_percussion=False,
                tuning=track.tuning,
                string_count=len(track.tuning),
                measures=measure_analyses,
            ))

        return SongAnalysis(
            title=song.title,
            artist=song.artist,
            tracks=track_analyses,
        )
