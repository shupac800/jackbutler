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

let analysisData = null;
let currentTrack = null; // track currently being displayed
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
    // Remove clicked alt from alternatives, add old primary
    const newAlts = m.chord_alternatives.filter((_, i) => i !== altIdx);
    if (oldPrimary) {
        newAlts.push(oldPrimary);
        // Sort by confidence descending
        newAlts.sort((a, b) => b.confidence - a.confidence);
    }
    m.chords = [alt];
    m.chord_alternatives = newAlts;
    m.roman_numerals = [alt.roman_numeral || "?"];

    // Re-render the entire track (simplest way to refresh notation + tab + coloring)
    renderMeasures(track);
}
