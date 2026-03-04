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

// Convert pitch_name like "C#4" to VexFlow key format "C#/4"
function pitchToVexKey(pitchName) {
    // pitchName is like "A3", "C#4", "G-4" (music21 uses - for flat)
    const match = pitchName.match(/^([A-G][#\-b]?)(\d+)$/);
    if (!match) return "C/4";
    let noteName = match[1].replace("-", "b");
    const octave = match[2];
    return noteName + "/" + octave;
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

    // Build HTML lines with colored spans
    const lines = [];
    for (let s = 0; s < numStrings; s++) {
        let line = labels[s] + "|";
        for (const col of columns) {
            const cell = col[s];
            if (cell === null) {
                line += "--";
            } else {
                const color = degreeColor(cell.degree);
                const pad = cell.text.length === 1 ? "-" : "";
                line += `<span style="color:${color}">${cell.text}</span>${pad}`;
            }
        }
        line += "|";
        lines.push(line);
    }
    return lines.join("\n");
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

    track.measures.forEach((m) => {
        const card = document.createElement("div");
        card.className = "measure-card";
        measureCounter++;
        const notationId = "notation-" + measureCounter;

        let html = "";

        // Header row
        html += `<div class="measure-header">`;
        html += `<span class="measure-number">M${m.measure_number}</span>`;
        html += `<span class="time-sig">${m.time_sig}</span>`;
        if (m.chords && m.chords.length > 0) {
            html += `<span class="chord-badge">${m.chords.map((c) => c.name).join(" ")}</span>`;
        }
        if (m.detected_key) {
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

        // Notation + Tab side by side
        const tabText = buildTab(m, track.string_count);
        html += `<div class="notation-tab-row">`;
        html += `<div class="notation-pane" id="${notationId}"></div>`;
        if (tabText) {
            html += `<pre class="tab-display">${tabText}</pre>`;
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

        // Chords
        if (m.chords && m.chords.length > 0) {
            html += `<div class="chords-row"><span class="row-label">Chords:</span> `;
            m.chords.forEach((c) => {
                html += `<span>${c.name}</span>`;
            });
            html += `</div>`;
        }

        // Roman numerals
        if (m.roman_numerals && m.roman_numerals.length > 0) {
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
}
