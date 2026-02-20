# Create `score.json` (melody) → MusicXML + MIDI (librosa + mido)

## Goal

From `uploaded_audio.mp3`, produce these files in the working directory:
- `analysis.json` (measured audio features)
- `score.json` (monophonic melody in beats)
- `score.musicxml` (deterministic notation rendering)
- `output.mid` (deterministic playback rendering)

## Constraints (must follow)
- Output **monophonic melody** only (no overlapping notes).
- `score.json` must be valid JSON (no prose/markdown).
- Use `ticks_per_beat = 480`.
- Use `time_signature = 4/4` unless there is strong evidence otherwise.
- Quantize to `1/16` grid (beats) and avoid tuplets.
- Do not allow a note to cross a measure boundary. If it would, split it.

---

## Step 1: Write `analysis.json` from audio (librosa)

Compute and save:
- `tempo_bpm`
- `beat_times_seconds`
- `onset_times_seconds`
- `pyin_midi_float`, `pyin_voiced_flag`
- `rms`, `rms_times_seconds`

Use this template:

```python
import json
import numpy as np
import librosa

AUDIO_PATH = "uploaded_audio.mp3"
OUT_PATH = "analysis.json"

def to_list(x):
    if isinstance(x, np.ndarray):
        return x.tolist()
    return x

def main():
    y, sr = librosa.load(AUDIO_PATH, sr=None, mono=True)
    duration = float(librosa.get_duration(y=y, sr=sr))

    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beats, sr=sr)

    onset_frames = librosa.onset.onset_detect(y=y, sr=sr, backtrack=False)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)

    f0, voiced_flag, voiced_probs = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C7"),
        sr=sr,
    )

    midi_float = librosa.hz_to_midi(f0)
    midi_float = np.nan_to_num(midi_float, nan=0.0)

    rms = librosa.feature.rms(y=y)[0]
    rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr)

    analysis = {
        "audio_path": AUDIO_PATH,
        "sr": int(sr),
        "duration_seconds": duration,
        "tempo_bpm": float(tempo),
        "beat_times_seconds": to_list(beat_times.astype(float)),
        "onset_times_seconds": to_list(onset_times.astype(float)),
        "pyin_midi_float": to_list(midi_float.astype(float)),
        "pyin_voiced_flag": to_list(voiced_flag.astype(bool)),
        "pyin_voiced_probs": to_list(voiced_probs.astype(float)),
        "rms": to_list(rms.astype(float)),
        "rms_times_seconds": to_list(rms_times.astype(float)),
    }

    with open(OUT_PATH, "w") as f:
        json.dump(analysis, f, indent=2)

    print(f"Wrote {OUT_PATH}")

if __name__ == "__main__":
    main()
```

---

## Step 2: Write `score.json` (monophonic melody)

Use `analysis.json` + audio to produce `score.json` following this schema:

```json
{
  "version": "0.1",
  "title": "optional",
  "tempo_bpm": 68,
  "time_signature": { "beats": 4, "beat_type": 4 },
  "ticks_per_beat": 480,
  "quantization": { "grid": "1/16", "swing": 0.0 },
  "key_signature": { "fifths": 0, "mode": "major" },
  "melody": [
    { "start_beat": 0.0, "duration_beats": 0.5, "midi_note": 71, "velocity": 85 }
  ]
}
```

Rules:
- Notes are sorted by `start_beat`.
- No overlap: for consecutive notes A and B, `A.start_beat + A.duration_beats <= B.start_beat`.
- `midi_note` integer in `[0..127]`. Use `midi_note=0` only for explicit rests (prefer leaving gaps).
- `velocity` integer in `[1..127]`.
- Quantize `start_beat` and `duration_beats` to the `1/16` grid.
- Use `onset_times_seconds` for candidate boundaries; choose a stable pitch per segment from `pyin_midi_float` where `pyin_voiced_flag` is true (median/mode).
- Map `rms` to velocity (e.g., normalize to 55–105). Avoid constant velocity for every note.
- Remove very short notes (noise), e.g. anything shorter than 1/16 or ~0.10s equivalent.

---

## Step 3: Render `score.musicxml` deterministically from `score.json`

Write `render_musicxml.py` that reads `score.json` and writes `score.musicxml`.

Requirements:
- MusicXML `divisions` must equal `ticks_per_beat` (480).
- Measure length (in divisions): `beats * divisions` (4 * 480 = 1920).
- Fill gaps with `<rest/>` notes so each measure sums to exactly 1920 divisions.
- Convert `midi_note` to MusicXML `<step>`, optional `<alter>`, `<octave>`.
- Support durations in multiples of 120 divisions (1/16 grid). Support dotted notes:
  - 360 = dotted eighth (`<type>eighth</type><dot/>`)
  - 720 = dotted quarter
  - 1440 = dotted half

Template:

```python
import json
from dataclasses import dataclass

SCORE_PATH = "score.json"
OUT_PATH = "score.musicxml"

DIVISIONS = 480  # must match score.json ticks_per_beat

PITCH_CLASS_TO_STEP_ALTER = {
    0: ("C", 0),  1: ("C", 1),
    2: ("D", 0),  3: ("D", 1),
    4: ("E", 0),
    5: ("F", 0),  6: ("F", 1),
    7: ("G", 0),  8: ("G", 1),
    9: ("A", 0), 10: ("A", 1),
    11: ("B", 0),
}

def midi_to_pitch(midi_note: int):
    octave = (midi_note // 12) - 1
    pc = midi_note % 12
    step, alter = PITCH_CLASS_TO_STEP_ALTER[pc]
    return step, alter, octave

def duration_to_type_and_dots(duration_div: int):
    # returns (type_str, dots_count) or (None, 0)
    base = {
        120: ("16th", 0),
        240: ("eighth", 0),
        480: ("quarter", 0),
        960: ("half", 0),
        1920: ("whole", 0),
        360: ("eighth", 1),
        720: ("quarter", 1),
        1440: ("half", 1),
    }
    return base.get(duration_div, (None, 0))

def xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace("\"", "&quot;")
         .replace("'", "&apos;")
    )

def main():
    with open(SCORE_PATH, "r") as f:
        score = json.load(f)

    beats = int(score["time_signature"]["beats"])
    beat_type = int(score["time_signature"]["beat_type"])
    divisions = int(score["ticks_per_beat"])
    assert divisions == DIVISIONS

    measure_div = beats * divisions
    title = score.get("title") or "Transcription"
    fifths = int(score.get("key_signature", {}).get("fifths", 0))

    melody = list(score["melody"])
    melody.sort(key=lambda n: n["start_beat"])

    # Build a timeline of segments (rests + notes) in divisions
    events = []
    for n in melody:
        start_div = int(round(float(n["start_beat"]) * divisions))
        dur_div = int(round(float(n["duration_beats"]) * divisions))
        events.append((start_div, dur_div, int(n["midi_note"])))

    total_end = 0
    if events:
        total_end = max(s + d for (s, d, _) in events)

    # Round total length up to full measures
    if total_end % measure_div != 0:
        total_end = ((total_end // measure_div) + 1) * measure_div

    # Create per-measure content
    measures = []
    idx = 0
    for measure_start in range(0, total_end, measure_div):
        measure_end = measure_start + measure_div
        cursor = measure_start
        parts = []

        while idx < len(events) and events[idx][0] < measure_end:
            start_div, dur_div, midi_note = events[idx]
            if start_div < measure_start:
                # should not happen if score.json splits notes at measure boundaries
                start_div = measure_start
            if start_div > cursor:
                # rest gap
                parts.append(("rest", start_div - cursor, None))
                cursor = start_div

            end_div = min(start_div + dur_div, measure_end)
            note_dur = end_div - start_div
            parts.append(("note", note_dur, midi_note))
            cursor = end_div
            idx += 1

        if cursor < measure_end:
            parts.append(("rest", measure_end - cursor, None))

        measures.append(parts)

    # Render MusicXML
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">')
    lines.append('<score-partwise version="4.0">')
    lines.append(f"  <movement-title>{xml_escape(title)}</movement-title>")
    lines.append("  <part-list>")
    lines.append('    <score-part id="P1"><part-name>Piano</part-name></score-part>')
    lines.append("  </part-list>")
    lines.append('  <part id="P1">')

    for i, parts in enumerate(measures, start=1):
        lines.append(f'    <measure number="{i}">')
        if i == 1:
            lines.append("      <attributes>")
            lines.append(f"        <divisions>{divisions}</divisions>")
            lines.append("        <key>")
            lines.append(f"          <fifths>{fifths}</fifths>")
            lines.append("        </key>")
            lines.append("        <time>")
            lines.append(f"          <beats>{beats}</beats>")
            lines.append(f"          <beat-type>{beat_type}</beat-type>")
            lines.append("        </time>")
            lines.append("        <clef><sign>G</sign><line>2</line></clef>")
            lines.append("      </attributes>")

        for kind, dur_div, midi_note in parts:
            type_str, dots = duration_to_type_and_dots(dur_div)
            lines.append("      <note>")
            if kind == "rest":
                lines.append("        <rest/>")
            else:
                step, alter, octave = midi_to_pitch(int(midi_note))
                lines.append("        <pitch>")
                lines.append(f"          <step>{step}</step>")
                if alter != 0:
                    lines.append(f"          <alter>{alter}</alter>")
                lines.append(f"          <octave>{octave}</octave>")
                lines.append("        </pitch>")
            lines.append(f"        <duration>{dur_div}</duration>")
            if type_str is not None:
                lines.append(f"        <type>{type_str}</type>")
                for _ in range(dots):
                    lines.append("        <dot/>")
            lines.append("      </note>")

        lines.append("    </measure>")

    lines.append("  </part>")
    lines.append("</score-partwise>")

    with open(OUT_PATH, "w") as f:
        f.write("\n".join(lines))

    print(f"Wrote {OUT_PATH}")

if __name__ == "__main__":
    main()
```

---

## Step 4: Render `output.mid` deterministically from `score.json` (Mido)

Write `score_to_midi.py` that reads `score.json` and writes `output.mid`.

Instrument:
- Use General MIDI `program_change` with `program=0` (Acoustic Grand Piano) on channel 0.

Template:

```python
import json
from mido import MidiFile, MidiTrack, Message, MetaMessage, bpm2tempo

SCORE_PATH = "score.json"
OUT_PATH = "output.mid"

def main():
    with open(SCORE_PATH, "r") as f:
        score = json.load(f)

    tempo_bpm = float(score["tempo_bpm"])
    beats = int(score["time_signature"]["beats"])
    beat_type = int(score["time_signature"]["beat_type"])
    tpq = int(score["ticks_per_beat"])

    mid = MidiFile(ticks_per_beat=tpq)
    track = MidiTrack()
    mid.tracks.append(track)

    track.append(MetaMessage("set_tempo", tempo=bpm2tempo(tempo_bpm), time=0))
    track.append(MetaMessage("time_signature", numerator=beats, denominator=beat_type, time=0))
    track.append(Message("program_change", program=0, channel=0, time=0))

    events = []
    for n in sorted(score["melody"], key=lambda x: x["start_beat"]):
        midi_note = int(n["midi_note"])
        if midi_note <= 0:
            continue
        start_tick = int(round(float(n["start_beat"]) * tpq))
        dur_tick = int(round(float(n["duration_beats"]) * tpq))
        end_tick = start_tick + max(1, dur_tick)
        vel = int(n.get("velocity", 80))
        vel = max(1, min(127, vel))

        events.append((start_tick, Message("note_on", note=midi_note, velocity=vel, channel=0)))
        events.append((end_tick, Message("note_off", note=midi_note, velocity=0, channel=0)))

    events.sort(key=lambda x: x[0])

    last = 0
    for t, msg in events:
        msg.time = max(0, t - last)
        track.append(msg)
        last = t

    mid.save(OUT_PATH)
    print(f"Wrote {OUT_PATH}")

if __name__ == "__main__":
    main()
```
