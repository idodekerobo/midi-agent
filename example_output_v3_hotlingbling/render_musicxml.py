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
