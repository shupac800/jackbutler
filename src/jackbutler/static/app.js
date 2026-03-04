const loading = document.getElementById("loading");
const errorEl = document.getElementById("error");
const results = document.getElementById("results");
const songTitle = document.getElementById("song-title");
const songArtist = document.getElementById("song-artist");
const trackTabs = document.getElementById("track-tabs");
const measuresEl = document.getElementById("measures");

const STRING_LABELS = ["e", "B", "G", "D", "A", "E"];

// Low-saturation colors for scale degrees
const DEGREE_COLORS = {
    1: "#cc7777", // root - muted red
    3: "#cccc77", // third - muted yellow
    5: "#7777cc", // fifth - muted blue
    7: "#cc77cc", // seventh - muted purple
};
const DEFAULT_NOTE_COLOR = "#e0e0e0";

function degreeColor(degree) {
    return DEGREE_COLORS[degree] || DEFAULT_NOTE_COLOR;
}

// Map quarter-note duration values to VexFlow duration strings
// VexFlow durations: w=whole(4), h=half(2), q=quarter(1), 8=eighth(0.5), 16=sixteenth(0.25)
function durationToVex(quarterLen) {
    if (quarterLen >= 4) return "w";
    if (quarterLen >= 2) return "h";
    if (quarterLen >= 1.5) return "qd"; // dotted quarter
    if (quarterLen >= 1) return "q";
    if (quarterLen >= 0.75) return "8d"; // dotted eighth
    if (quarterLen >= 0.5) return "8";
    if (quarterLen >= 0.25) return "16";
    return "32";
}

// Convert pitch_name like "C#4" to VexFlow key format "C#/5"
// Guitar is a transposing instrument: notation is written one octave higher than sounding pitch.
function pitchToVexKey(pitchName) {
    // pitchName is like "A3", "C#4", "G-4" (music21 uses - for flat)
    const match = pitchName.match(/^([A-G][#\-b]?)(\d+)$/);
    if (!match) return "C/4";
    let noteName = match[1].replace("-", "b");
    const octave = parseInt(match[2], 10) + 1;
    return noteName + "/" + octave;
}

// Pitch class name → semitone number (handles both sharps and flats)
const PC_TO_SEMI = {
    "C": 0, "C#": 1, "D-": 1, "D": 2, "D#": 3, "E-": 3,
    "E": 4, "E#": 5, "F-": 4, "F": 5, "F#": 6, "G-": 6,
    "G": 7, "G#": 8, "A-": 8, "A": 9, "A#": 10, "B-": 10,
    "B": 11, "C-": 11,
};

const SEMI_TO_INTERVAL = {
    0: "P1", 1: "m2", 2: "M2", 3: "m3", 4: "M3", 5: "P4",
    6: "TT", 7: "P5", 8: "m6", 9: "M6", 10: "m7", 11: "M7",
};

function pitchClassFromName(pitchName) {
    return pitchName.replace(/\d+$/, "");
}

/** Build a semitone-PC → degree map from a ChordInfo's root + midi_pitches. */
function buildChordToneMap(chord) {
    const rootSemi = PC_TO_SEMI[chord.root];
    if (rootSemi === undefined) return {};
    const map = {};
    for (const midi of chord.midi_pitches) {
        const pc = midi % 12;
        const interval = (pc - rootSemi + 12) % 12;
        if (interval === 0) map[pc] = 1;
        else if (interval <= 4) map[pc] = 3;
        else if (interval <= 8) map[pc] = 5;
        else map[pc] = 7;
    }
    return map;
}

/** Return a human label for a note's role relative to a chord. */
function chordToneLabel(degree, noteSemi, rootSemi) {
    if (degree === 1) return "root";
    if (degree === 3) return "3rd";
    if (degree === 5) return "5th";
    if (degree === 7) return "7th";
    if (rootSemi !== undefined && noteSemi !== undefined) {
        const interval = (noteSemi - rootSemi + 12) % 12;
        return SEMI_TO_INTERVAL[interval] || "?";
    }
    return "?";
}

/** Re-derive note degrees and scale_degrees on a measure for a given chord. */
function recolorMeasure(measure, chord) {
    const ctMap = buildChordToneMap(chord);
    const rootSemi = PC_TO_SEMI[chord.root];

    for (const beat of measure.beats) {
        for (const note of beat.notes) {
            if (note.is_tied) continue;
            const semi = note.midi % 12;
            note.degree = ctMap[semi] || null;
        }
    }

    const seenSemi = new Set();
    const newDegrees = [];
    for (const beat of measure.beats) {
        for (const note of beat.notes) {
            if (note.is_tied) continue;
            const semi = note.midi % 12;
            if (seenSemi.has(semi)) continue;
            seenSemi.add(semi);
            const deg = ctMap[semi] || null;
            const pc = pitchClassFromName(note.pitch_name);
            const label = chordToneLabel(deg, semi, rootSemi);
            newDegrees.push(`${pc}=${label}`);
        }
    }
    measure.scale_degrees = newDegrees;
}

// Major/minor scale intervals and degree labels for commentary generation
const MAJOR_SEMITONES = [0, 2, 4, 5, 7, 9, 11];
const MINOR_SEMITONES = [0, 2, 3, 5, 7, 8, 10];
const MAJOR_DEGREE_LABELS = ["I", "II", "III", "IV", "V", "VI", "VII"];
const MINOR_DEGREE_LABELS = ["i", "ii", "III", "iv", "v", "VI", "VII"];

/** Parse a key string like "B minor" → { tonic: "B", mode: "minor" } */
function parseKeyString(keyStr) {
    if (!keyStr) return null;
    const parts = keyStr.split(" ");
    if (parts.length < 2) return null;
    return { tonic: parts[0], mode: parts[1] };
}

/** Get the scale degree label of a pitch class in a key (e.g. "i", "III"). */
function scaleDegreeInKey(pc, keyStr) {
    const k = parseKeyString(keyStr);
    if (!k) return null;
    const tonicSemi = PC_TO_SEMI[k.tonic];
    const pcSemi = PC_TO_SEMI[pc];
    if (tonicSemi === undefined || pcSemi === undefined) return null;
    const interval = (pcSemi - tonicSemi + 12) % 12;
    const semitones = k.mode === "minor" ? MINOR_SEMITONES : MAJOR_SEMITONES;
    const labels = k.mode === "minor" ? MINOR_DEGREE_LABELS : MAJOR_DEGREE_LABELS;
    const idx = semitones.indexOf(interval);
    return idx >= 0 ? labels[idx] : null;
}

/** Generate client-side commentary for a chord in context of a measure. */
function generateCommentary(chord, measure) {
    const parts = [];
    const ctMap = buildChordToneMap(chord);
    const rootSemi = PC_TO_SEMI[chord.root];

    // Collect unique pitch classes in order
    const seenPcs = new Set();
    const pcs = [];
    for (const beat of measure.beats) {
        for (const note of beat.notes) {
            if (note.is_tied) continue;
            const pc = pitchClassFromName(note.pitch_name);
            if (!seenPcs.has(pc)) {
                seenPcs.add(pc);
                pcs.push({ name: pc, semi: note.midi % 12 });
            }
        }
    }
    if (pcs.length === 0) return "Rest measure.";

    // Chord tone breakdown
    const toneLabels = pcs.map((p) => {
        const deg = ctMap[p.semi] || null;
        const label = chordToneLabel(deg, p.semi, rootSemi);
        return `${p.name}=${label}`;
    });
    parts.push(`${chord.name}: ${toneLabels.join(", ")}.`);

    // Count chord tones vs non-chord tones
    const chordToneCount = pcs.filter((p) => ctMap[p.semi]).length;
    const nonChordTones = pcs.filter((p) => !ctMap[p.semi]);
    if (nonChordTones.length > 0) {
        const nctNames = nonChordTones.map((p) => p.name).join(", ");
        parts.push(`${chordToneCount}/${pcs.length} pitches are chord tones; ${nctNames} ${nonChordTones.length === 1 ? "is a" : "are"} non-chord ${nonChordTones.length === 1 ? "tone" : "tones"}.`);
    } else {
        parts.push(`All ${pcs.length} pitches are chord tones.`);
    }

    // Roman numeral + key relationship
    const globalKey = measure.global_key;
    const rn = chord.roman_numeral;
    if (globalKey && rn) {
        const rootDeg = scaleDegreeInKey(chord.root, globalKey);
        if (rootDeg) {
            parts.push(`${rn} in ${globalKey} \u2014 ${chord.root} is ${rootDeg}.`);
        } else {
            parts.push(`${rn} in ${globalKey}.`);
        }
    }

    // Quality notes
    const name = chord.name.toLowerCase();
    if (name.includes("dim")) {
        parts.push("Diminished quality creates tension, typically resolving stepwise.");
    } else if (name.includes("aug")) {
        parts.push("Augmented quality creates instability, pulling toward resolution.");
    }

    return parts.join(" ");
}

let analysisData = null;
let measureCounter = 0; // unique IDs for VexFlow containers

// Auto-load demo on page load
loadDemo();

async function loadDemo() {
    loading.classList.remove("hidden");
    errorEl.classList.add("hidden");
    results.classList.add("hidden");

    try {
        const resp = await fetch("/api/demo");
        if (!resp.ok) {
            const text = await resp.text();
            throw new Error(text || `HTTP ${resp.status}`);
        }
        analysisData = await resp.json();
        renderResults();
    } catch (err) {
        errorEl.textContent = `Analysis failed: ${err.message}`;
        errorEl.classList.remove("hidden");
    } finally {
        loading.classList.add("hidden");
    }
}

function renderResults() {
    songTitle.textContent = analysisData.title;
    songArtist.textContent = analysisData.artist;

    trackTabs.innerHTML = "";
    const playableTracks = analysisData.tracks.filter((t) => !t.is_percussion);

    if (playableTracks.length > 0 && playableTracks[0].measures.length > 0) {
        const globalKey = playableTracks[0].measures[0].global_key;
        if (globalKey) {
            songArtist.textContent += ` \u2014 Key of ${globalKey}`;
        }
    }

    playableTracks.forEach((track, i) => {
        const tab = document.createElement("button");
        tab.className = "track-tab" + (i === 0 ? " active" : "");
        tab.textContent = track.track_name || `Track ${track.track_index + 1}`;
        tab.addEventListener("click", () => {
            document.querySelectorAll(".track-tab").forEach((t) => t.classList.remove("active"));
            tab.classList.add("active");
            renderMeasures(track);
        });
        trackTabs.appendChild(tab);
    });

    if (playableTracks.length > 0) {
        renderMeasures(playableTracks[0]);
    }

    results.classList.remove("hidden");
}

function buildTab(measure, stringCount) {
    const numStrings = stringCount || 6;
    const labels = STRING_LABELS.slice(0, numStrings);

    // Build columns: each beat becomes a column with {fret, degree} per string
    const columns = [];
    for (const beat of measure.beats) {
        const col = new Array(numStrings).fill(null);
        for (const note of beat.notes) {
            const idx = note.string - 1;
            if (idx >= 0 && idx < numStrings) {
                col[idx] = {
                    text: note.is_tied ? "~" : String(note.fret),
                    degree: note.degree,
                };
            }
        }
        columns.push(col);
    }

    if (columns.length === 0) return null;

    // SVG dimensions
    const lineSpacing = 20;
    const topPad = 12;
    const leftPad = 20;  // space for string labels
    const rightPad = 10;
    const colWidth = 28;
    const svgWidth = leftPad + columns.length * colWidth + rightPad;
    const svgHeight = topPad + (numStrings - 1) * lineSpacing + 12;
    const lineColor = "#666";
    const bgColor = "#111";

    let svg = `<svg width="${svgWidth}" height="${svgHeight}" xmlns="http://www.w3.org/2000/svg">`;

    // String lines and labels
    for (let s = 0; s < numStrings; s++) {
        const y = topPad + s * lineSpacing;
        // String line
        svg += `<line x1="${leftPad}" y1="${y}" x2="${svgWidth - rightPad}" y2="${y}" stroke="${lineColor}" stroke-width="1"/>`;
        // String label
        svg += `<text x="${leftPad - 4}" y="${y + 4}" text-anchor="end" fill="#888" font-size="11" font-family="monospace">${labels[s]}</text>`;
    }

    // Fret numbers
    for (let c = 0; c < columns.length; c++) {
        const x = leftPad + (c + 0.5) * colWidth;
        for (let s = 0; s < numStrings; s++) {
            const cell = columns[c][s];
            if (cell === null) continue;
            const y = topPad + s * lineSpacing;
            const color = degreeColor(cell.degree);
            // Opaque background to mask the string line behind the number
            const textWidth = cell.text.length * 8 + 4;
            svg += `<rect x="${x - textWidth / 2}" y="${y - 9}" width="${textWidth}" height="18" fill="${bgColor}" rx="2"/>`;
            // Fret number
            svg += `<text x="${x}" y="${y + 6}" text-anchor="middle" fill="${color}" font-size="16" font-weight="bold" font-family="monospace">${cell.text}</text>`;
        }
    }

    svg += `</svg>`;
    return svg;
}

function renderNotation(containerId, measure, timeSig) {
    const { Factory, StaveNote } = Vex.Flow;

    const el = document.getElementById(containerId);
    if (!el || !measure.beats || measure.beats.length === 0) return;

    // Calculate width based on number of beats
    const width = Math.max(300, measure.beats.length * 45 + 80);

    try {
        const vf = new Factory({
            renderer: { elementId: containerId, width: width, height: 130 },
        });

        const score = vf.EasyScore();
        const system = vf.System({ width: width - 10 });

        // Build VexFlow notes from beat data, colored by scale degree
        const vexNotes = [];
        for (const beat of measure.beats) {
            const nonTied = beat.notes.filter((n) => !n.is_tied);
            if (nonTied.length === 0) continue;

            const dur = durationToVex(beat.duration);
            const keys = nonTied.map((n) => pitchToVexKey(n.pitch_name));
            const sn = new StaveNote({ keys: keys, duration: dur });

            // Color each note key by its scale degree
            for (let ki = 0; ki < nonTied.length; ki++) {
                const color = degreeColor(nonTied[ki].degree);
                sn.setKeyStyle(ki, { fillStyle: color, strokeStyle: color });
            }
            // Color stem and flag by first note's degree
            const stemColor = degreeColor(nonTied[0].degree);
            sn.setStemStyle({ fillStyle: stemColor, strokeStyle: stemColor });
            sn.setFlagStyle({ fillStyle: stemColor, strokeStyle: stemColor });

            vexNotes.push(sn);
        }

        if (vexNotes.length === 0) return;

        const voice = score.voice(vexNotes, { time: timeSig });
        voice.setMode(Vex.Flow.Voice.Mode.SOFT);

        system.addStave({ voices: [voice] }).addClef("treble").addTimeSignature(timeSig);

        vf.draw();

        // Invert colors: light notes/lines on dark background
        const svg = el.querySelector("svg");
        if (svg) {
            svg.setAttribute("fill", "#e0e0e0");
            svg.setAttribute("stroke", "#e0e0e0");
            svg.style.color = "#e0e0e0";
            svg.style.background = "transparent";
            // Fix elements with explicit black attributes (ledger lines, etc.)
            // Preserve degree colors that VexFlow may set as attributes (e.g. flags).
            const LIGHT = "#e0e0e0";
            const PRESERVE = new Set(Object.values(DEGREE_COLORS));
            PRESERVE.add(LIGHT);
            svg.querySelectorAll("line, path, rect").forEach((node) => {
                const s = node.getAttribute("stroke");
                if (s && s !== "none" && !PRESERVE.has(s)) {
                    node.setAttribute("stroke", LIGHT);
                }
                const f = node.getAttribute("fill");
                if (f && f !== "none" && !PRESERVE.has(f)) {
                    node.setAttribute("fill", LIGHT);
                }
            });
        }
    } catch (e) {
        el.textContent = "(notation error)";
        el.style.color = "#666";
        el.style.fontStyle = "italic";
    }
}

function renderMeasures(track) {
    measuresEl.innerHTML = "";
    measureCounter = 0;

    track.measures.forEach((m, mIdx) => {
        const card = document.createElement("div");
        card.className = "measure-card";
        measureCounter++;
        const notationId = "notation-" + measureCounter;

        let html = "";

        // Header row
        html += `<div class="measure-header">`;
        html += `<span class="measure-number">M${m.measure_number}</span>`;
        html += `<span class="time-sig">${m.time_sig}</span>`;
        const hasChords = m.chords && m.chords.length > 0;
        if (hasChords) {
            m.chords.forEach((c, i) => {
                const rn = c.roman_numeral || (m.roman_numerals && m.roman_numerals[i]);
                if (rn) {
                    html += `<span class="numeral-badge">${rn}</span>`;
                }
                html += `<span class="chord-badge">${c.name}`;
                if (c.confidence > 0) {
                    html += ` <span class="confidence">${Math.round(c.confidence * 100)}%</span>`;
                }
                html += `</span>`;
            });
        }
        if (m.detected_key && !hasChords) {
            const lowConf = m.key_confidence !== null && m.key_confidence < 0.8;
            const matchesGlobal = m.detected_key === m.global_key;
            html += `<span class="key-badge${lowConf ? " low-confidence" : ""}">${m.detected_key}`;
            if (m.key_confidence !== null) {
                html += ` <span class="confidence">${Math.round(m.key_confidence * 100)}%</span>`;
            }
            html += `</span>`;
            if (!matchesGlobal && m.global_key) {
                html += `<span class="key-drift">differs from global ${m.global_key}</span>`;
            }
        }
        html += `</div>`;

        // Notation + Tab + Alternatives side by side
        const tabSvg = buildTab(m, track.string_count);
        html += `<div class="notation-tab-row">`;
        html += `<div class="notation-pane" id="${notationId}"></div>`;
        if (tabSvg) {
            html += `<div class="tab-display">${tabSvg}</div>`;
        }
        // Alternatives panel
        const alts = m.chord_alternatives || [];
        if (alts.length > 0) {
            html += `<div class="alternatives-panel">`;
            html += `<div class="alternatives-label">Alternatives</div>`;
            alts.forEach((alt, ai) => {
                const pct = alt.confidence > 0 ? ` ${Math.round(alt.confidence * 100)}%` : "";
                const rn = alt.roman_numeral ? `<span class="alt-rn">${alt.roman_numeral}</span> ` : "";
                html += `<div class="alt-row" data-measure-idx="${mIdx}" data-alt-idx="${ai}">${rn}${alt.name}<span class="alt-conf">${pct}</span></div>`;
            });
            html += `</div>`;
        }
        html += `</div>`;

        // Build pitch-to-degree lookup from beat data
        const pitchDegreeMap = {};
        for (const beat of m.beats) {
            for (const note of beat.notes) {
                if (note.degree && note.pitch_name) {
                    // Strip octave to get pitch class
                    const pc = note.pitch_name.replace(/\d+$/, "");
                    pitchDegreeMap[pc] = note.degree;
                }
            }
        }

        // Scale degrees
        if (m.scale_degrees && m.scale_degrees.length > 0) {
            html += `<div class="degrees-row"><span class="row-label">Scale degrees:</span> `;
            m.scale_degrees.forEach((d) => {
                const isChromatic = d.includes("chromatic");
                // Extract pitch class from "A=i" format
                const pc = d.split("=")[0];
                const deg = pitchDegreeMap[pc];
                const color = isChromatic ? "#ff9090" : degreeColor(deg);
                html += `<span class="degree-badge" style="color:${color};border-color:${color}">${d}</span>`;
            });
            html += `</div>`;
        }

        // Notes
        if (m.note_names && m.note_names.length > 0) {
            html += `<div class="notes-row"><span class="notes-label">Notes:</span> `;
            m.note_names.forEach((n) => {
                html += `<span class="note-badge">${n}</span>`;
            });
            html += `</div>`;
        }

        // Roman numerals (only when no chord badge in header)
        if (!hasChords && m.roman_numerals && m.roman_numerals.length > 0) {
            html += `<div class="roman-row"><span class="row-label">Progression:</span> `;
            m.roman_numerals.forEach((rn) => {
                html += `<span>${rn}</span>`;
            });
            html += `</div>`;
        }

        // Commentary
        if (m.commentary) {
            html += `<div class="commentary">${m.commentary}</div>`;
        }

        card.innerHTML = html;
        measuresEl.appendChild(card);

        // Render VexFlow notation after the DOM element exists
        renderNotation(notationId, m, m.time_sig);
    });

    // Attach click handlers for alternative rows
    measuresEl.querySelectorAll(".alt-row").forEach((row) => {
        row.addEventListener("click", () => {
            const mi = parseInt(row.dataset.measureIdx, 10);
            const ai = parseInt(row.dataset.altIdx, 10);
            switchToAlternative(track, mi, ai);
        });
    });
}

function switchToAlternative(track, measureIdx, altIdx) {
    const m = track.measures[measureIdx];
    if (!m || !m.chord_alternatives || !m.chord_alternatives[altIdx]) return;
    const alt = m.chord_alternatives[altIdx];

    // Swap: current primary becomes an alternative, clicked alternative becomes primary
    const oldPrimary = m.chords[0];
    const newAlts = m.chord_alternatives.filter((_, i) => i !== altIdx);
    if (oldPrimary) {
        newAlts.push(oldPrimary);
        newAlts.sort((a, b) => b.confidence - a.confidence);
    }
    m.chords = [alt];
    m.chord_alternatives = newAlts;
    m.roman_numerals = [alt.roman_numeral || "?"];

    // Re-derive note degrees, scale degrees, colors, and commentary
    recolorMeasure(m, alt);
    m.commentary = generateCommentary(alt, m);

    // Re-render the entire track
    renderMeasures(track);
}
