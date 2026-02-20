import json
from mido import MidiFile, MidiTrack, Message, MetaMessage, bpm2tempo

SCORE_PATH = "score.json"
OUT_PATH = "output.mid"

def main():
    try:
        with open(SCORE_PATH, "r") as f:
            score = json.load(f)
    except FileNotFoundError:
        print(f"Error: {SCORE_PATH} not found.")
        return

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
