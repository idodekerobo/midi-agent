# Using Mido to Create MIDI Files in Python

This guide explains how to use **Mido** to create MIDI files, assuming:

- The `mido` package is **already installed**.
- You don’t care (for now) about sending MIDI to external devices or DAWs in real time.
- You only need to **generate `.mid` files** in your working directory that other tools can open.

---

## 1. Core Concepts: Messages, Tracks, and Files

Mido revolves around three core objects:

- **`Message`**: a single MIDI event, like “note_on” or “note_off”.
- **`MidiTrack`**: an ordered list of messages (subclass of `list`).
- **`MidiFile`**: a complete MIDI file containing one or more tracks that you can save as `.mid`.

### 1.1 Messages

A `Message` represents one MIDI event:

```python
from mido import Message

msg = Message('note_on', note=60, velocity=64, time=0)
```

Important inputs (for note messages):

- `type`: message type, e.g. `'note_on'`, `'note_off'`.
- `note`: MIDI note number `0–127` (e.g. 60 = middle C, 61 = C#, etc.).
- `velocity`: how hard the note is played `0–127` (0 = silent, 127 = max).
- `channel`: MIDI channel `0–15` (defaults to 0).
- `time`: **delta time in ticks** when used inside a track (how long to wait after the previous message).

Example pair:

```python
msg_on = Message('note_on', note=60, velocity=80, time=0)     # start immediately
msg_off = Message('note_off', note=60, velocity=64, time=480) # stop after 480 ticks
```

You’ll usually never modify messages in place; instead, you can use `.copy()` to derive variants:

```python
msg2 = msg_on.copy(note=64, time=240)
```

---

## 2. Time, Ticks, and Tempo

Inside a `MidiFile`, time is in **ticks**, not seconds.

- `MidiFile.ticks_per_beat` (PPQN) defines how many ticks are in a quarter note.
- Each message in a `MidiTrack` has `.time` as **delta time in ticks** since the previous message.

Default:

```python
from mido import MidiFile

mid = MidiFile()
print(mid.ticks_per_beat)  # default is 480
```

At the default MIDI tempo (500000 microseconds per quarter note ≈ 120 BPM) and 480 ticks per beat:

- 1 quarter note = 480 ticks ≈ 0.5 seconds.
- 1 eighth note = 240 ticks.
- 1 half note = 960 ticks.

If you want more precise control, you can convert between beats, ticks, and tempo, but for many use cases you can just use simple multiples of `ticks_per_beat`.

---

## 3. Minimal “Hello World” MIDI File

First, the smallest possible script that creates a `.mid` file in the current working directory:

```python
from mido import Message, MidiFile, MidiTrack

mid = MidiFile()          # type 1 by default, ticks_per_beat = 480
track = MidiTrack()
mid.tracks.append(track)

# Middle C (note 60) as a quarter note at default tempo
track.append(Message('note_on', note=60, velocity=64, time=0))
track.append(Message('note_off', note=60, velocity=64, time=480))

mid.save('hello_mido.mid')
```

This will write `hello_mido.mid` into the process’s working directory. You can open that file in any DAW, MIDI player, or editor.

---

## 4. Creating a Melody from Known Notes and Durations

Assume you already know:

- The sequence of notes you want (`MIDI note numbers`).
- How long each note should last (in beats).

### 4.1 Simple Representation

Let’s store the melody as `(note, duration_in_beats)` pairs, where duration is measured in **quarter notes**:

```python
from mido import Message, MidiFile, MidiTrack

mid = MidiFile(ticks_per_beat=480)
track = MidiTrack()
mid.tracks.append(track)

# (note, duration_in_beats)
melody = [
    (60, 1.0),  # C4, quarter note
    (62, 1.0),  # D4, quarter note
    (64, 1.0),  # E4, quarter note
    (65, 1.0),  # F4, quarter note
    (67, 2.0),  # G4, half note
]

ticks_per_beat = mid.ticks_per_beat
channel = 0
velocity = 80

for note, duration_beats in melody:
    duration_ticks = int(duration_beats * ticks_per_beat)

    # Note on immediately after the last message
    track.append(
        Message(
            'note_on',
            note=note,
            velocity=velocity,
            channel=channel,
            time=0,  # no delay before starting this note
        )
    )

    # Note off after duration_ticks
    track.append(
        Message(
            'note_off',
            note=note,
            velocity=64,
            channel=channel,
            time=duration_ticks,
        )
    )

mid.save('simple_melody.mid')
```

What’s happening:

- For each note:
  - A `note_on` message starts the note with `time=0` (no delay from the previous message).
  - A `note_off` message ends the note, with its `time` set to the note duration in ticks.

---

## 5. Scheduling Notes with Start Times

If your data has explicit **start times** and **durations**, you can map them cleanly into the MIDI timeline.

### 5.1 Representing Notes with Start and Duration

Format: `(start_beat, note, duration_beats)`:

```python
from mido import Message, MidiFile, MidiTrack

mid = MidiFile(ticks_per_beat=480)
track = MidiTrack()
mid.tracks.append(track)

ticks_per_beat = mid.ticks_per_beat
channel = 0
velocity = 90

events = [
    (0.0, 60, 1.0),  # start at beat 0, C4, 1 beat
    (1.0, 64, 1.0),  # start at beat 1
    (2.0, 67, 2.0),  # start at beat 2, lasts 2 beats
]

# 1) Convert to absolute tick times with messages
messages = []
for start_beat, note, dur_beats in events:
    start_tick = int(start_beat * ticks_per_beat)
    end_tick = int((start_beat + dur_beats) * ticks_per_beat)

    messages.append((start_tick, Message('note_on', note=note, velocity=velocity, channel=channel)))
    messages.append((end_tick,  Message('note_off', note=note, velocity=64, channel=channel)))

# 2) Sort by absolute tick time
messages.sort(key=lambda item: item[0])

# 3) Convert absolute times to delta times and append
last_tick = 0
for abs_tick, msg in messages:
    delta = abs_tick - last_tick
    msg.time = delta
    track.append(msg)
    last_tick = abs_tick

mid.save('scheduled_notes.mid')
```

This approach is good for:

- Overlapping notes / chords.
- Data-driven compositions where notes are defined in terms of start/end times.

---

## 6. Adding Basic Meta Information (Tempo, Track Name)

Even if you’re only saving `.mid` files, adding **tempo** and **track names** can make the file easier to work with downstream.

### 6.1 Setting Tempo

MIDI tempo is stored as *microseconds per quarter note* via a `MetaMessage`:

```python
from mido import MetaMessage, bpm2tempo, MidiFile, MidiTrack, Message

mid = MidiFile(ticks_per_beat=480)
track = MidiTrack()
mid.tracks.append(track)

# Set tempo to 100 BPM
tempo = bpm2tempo(100)  # microseconds per quarter note
track.append(MetaMessage('set_tempo', tempo=tempo, time=0))

# Now add note messages
track.append(Message('note_on', note=60, velocity=64, time=0))
track.append(Message('note_off', note=60, velocity=64, time=480))

mid.save('tempo_example.mid')
```

### 6.2 Naming Tracks

`MidiTrack` has a `name` property that reads/writes a `track_name` meta message under the hood:

```python
track.name = 'Piano Melody'
mid.save('named_track.mid')
```

Tools that display track names (DAWs, editors) will show this label.

---

## 7. Reading and Inspecting Saved MIDI Files

Even if your agent only needs to write `.mid` files, being able to read them back is useful for debugging or analysis.

### 7.1 Opening a File

```python
from mido import MidiFile

mid = MidiFile('simple_melody.mid')

print('Ticks per beat:', mid.ticks_per_beat)
print('Number of tracks:', len(mid.tracks))

for i, track in enumerate(mid.tracks):
    print(f'Track {i}: {track.name!r}')
    for msg in track:
        print(msg)
```

Inside each `track`:

- `msg.time` is a delta time in ticks.
- `msg.type` tells you the kind of message (`'note_on'`, `'note_off'`, `'set_tempo'`, etc.).
- `msg.is_meta` tells you if it’s a meta message.

---

## 8. Utility Functions and Patterns You’ll Actually Use

### 8.1 Converting Beats/Seconds ↔ Ticks

If you have note durations or start times in **seconds** instead of beats:

```python
from mido import bpm2tempo, second2tick, tick2second

ticks_per_beat = 480
tempo = bpm2tempo(120)

# seconds → ticks
duration_seconds = 0.75
duration_ticks = int(second2tick(duration_seconds, ticks_per_beat, tempo))

# ticks → seconds
seconds_back = tick2second(duration_ticks, ticks_per_beat, tempo)
```

### 8.2 Copying Messages Safely

Mido’s idiom is to **copy messages rather than mutate**:

```python
from mido import Message

base = Message('note_on', note=60, velocity=80, time=0)

variants = [
    base.copy(note=62),
    base.copy(note=64),
    base.copy(note=65),
]
```

This keeps your “templates” intact and makes it easy to generate lots of related events.

---

## 9. Practical Checklist for an Agent That Writes `.mid` Files

When you’re implementing an agent or script that turns symbolic note data into a `.mid` file in its working directory, it will usually:

1. Create a `MidiFile`, optionally configuring `ticks_per_beat`.
2. Create one or more `MidiTrack` objects and attach them.
3. (Optional) Add a `set_tempo` meta message and track name.
4. Convert its internal representation of notes (beats or seconds) into:
   - `note_on` messages.
   - `note_off` messages.
   - Correct delta `time` values in ticks.
5. Call `mid.save('some_name.mid')` to write the file.

No backends, no ports, no realtime sending—just **pure MIDI file generation** in the current directory.