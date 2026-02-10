import mido
from mido import Message, MidiFile, MidiTrack, MetaMessage, bpm2tempo

# Constants
FILENAME = "hotline_bling.mid"
TEMPO_BPM = 135
TICKS_PER_BEAT = 480
TOTAL_BARS = 68  # Approx 2 minutes at 135 BPM

# MIDI Note Numbers
NOTE_C3 = 48
NOTE_D3 = 50
NOTE_E3 = 52
NOTE_F3 = 53
NOTE_G3 = 55
NOTE_A3 = 57
NOTE_Bb3 = 58
NOTE_C4 = 60
NOTE_D4 = 62
NOTE_E4 = 64
NOTE_F4 = 65
NOTE_G4 = 67
NOTE_A4 = 69
NOTE_Bb4 = 70

# Drum Map (GM)
KICK = 36
SNARE = 38
HIHAT_CLOSED = 42

def create_midi():
    mid = MidiFile(ticks_per_beat=TICKS_PER_BEAT)
    
    # Track 0: Meta (Tempo)
    track_meta = MidiTrack()
    mid.tracks.append(track_meta)
    track_meta.append(MetaMessage('track_name', name='Meta', time=0))
    track_meta.append(MetaMessage('set_tempo', tempo=bpm2tempo(TEMPO_BPM), time=0))
    track_meta.append(MetaMessage('time_signature', numerator=4, denominator=4, clocks_per_click=24, notated_32nd_notes_per_beat=8, time=0))

    # Track 1: Drums
    track_drums = MidiTrack()
    mid.tracks.append(track_drums)
    track_drums.append(MetaMessage('track_name', name='Drums', time=0))
    
    # Track 2: Chords (Electric Organ/Pad)
    track_chords = MidiTrack()
    mid.tracks.append(track_chords)
    track_chords.append(MetaMessage('track_name', name='Chords', time=0))
    track_chords.append(Message('program_change', program=16, time=0)) # Drawbar Organ

    # Track 3: Bass
    track_bass = MidiTrack()
    mid.tracks.append(track_bass)
    track_bass.append(MetaMessage('track_name', name='Bass', time=0))
    track_bass.append(Message('program_change', program=33, time=0)) # Electric Bass (finger)

    # Track 4: Melody
    track_melody = MidiTrack()
    mid.tracks.append(track_melody)
    track_melody.append(MetaMessage('track_name', name='Melody', time=0))
    track_melody.append(Message('program_change', program=80, time=0)) # Lead (square) or Synth

    # --- Helper to convert (bar, beat) to absolute ticks ---
    def get_tick(bar, beat):
        # bar is 0-indexed, beat is 0-indexed (0 to 3.99)
        total_beats = (bar * 4) + beat
        return int(total_beats * TICKS_PER_BEAT)

    # We will collect events as (absolute_tick, message) and then sort/write
    events_drums = []
    events_chords = []
    events_bass = []
    events_melody = []

    # --- Pattern Generation ---

    for bar in range(TOTAL_BARS):
        # 1. Chords & Bass
        # Pattern: Bars 0-1: Bbmaj7, Bars 2-3: Am7 (Repeating every 4 bars)
        cycle_pos = bar % 4
        
        chord_notes = []
        bass_note = None

        if cycle_pos == 0 or cycle_pos == 1:
            # Bbmaj7: Bb, D, F, A
            chord_notes = [NOTE_Bb3, NOTE_D4, NOTE_F4, NOTE_A4]
            bass_note = NOTE_Bb3 - 24 # Lower octave
        else:
            # Am7: A, C, E, G
            chord_notes = [NOTE_A3, NOTE_C4, NOTE_E4, NOTE_G4]
            bass_note = NOTE_A3 - 24

        # Add Chord (Start of bar, duration 4 beats)
        start_tick = get_tick(bar, 0)
        end_tick = get_tick(bar+1, 0)
        for note in chord_notes:
            events_chords.append((start_tick, Message('note_on', note=note, velocity=70, channel=0)))
            events_chords.append((end_tick, Message('note_off', note=note, velocity=64, channel=0)))
        
        # Add Bass (Start of bar, duration 4 beats)
        events_bass.append((start_tick, Message('note_on', note=bass_note, velocity=90, channel=1)))
        events_bass.append((end_tick, Message('note_off', note=bass_note, velocity=64, channel=1)))

        # 2. Drums
        # Hi-hats every 8th note (0, 0.5, 1, 1.5 ...)
        for i in range(8):
            beat_pos = i * 0.5
            tick = get_tick(bar, beat_pos)
            events_drums.append((tick, Message('note_on', note=HIHAT_CLOSED, velocity=60, channel=9)))
            events_drums.append((tick + 60, Message('note_off', note=HIHAT_CLOSED, velocity=0, channel=9))) # Short blip
        
        # Kick on 0 and 2.5 (classic trap-ish/pop feel) -> Beat 1 and "and of 3"
        # Actually Hotline bling kick is sparse. Let's do Beat 1 and Beat 3.5 (the "and" of 4) or 2.5
        # Let's stick to: Kick on 1 (0.0) and 2.5 (the "and" of 3). 
        # Snare on 3 (2.0) - wait, beat 3 is 2.0. 
        # Beats: 1(0), 2(1), 3(2), 4(3).
        # Kick: 0.0, 2.5? Or 0.0 and 1.75?
        # Let's do Kick: 0.0
        # Snare: 2.0
        # Kick: 3.5 (pickup to next bar)
        
        kicks = [0.0, 3.5]
        if bar % 2 == 1: # slightly different every other bar
            kicks = [0.0, 2.5]
            
        for k in kicks:
            tick = get_tick(bar, k)
            events_drums.append((tick, Message('note_on', note=KICK, velocity=100, channel=9)))
            events_drums.append((tick + 100, Message('note_off', note=KICK, velocity=0, channel=9)))

        # Snare on Beat 3 (index 2.0)
        snare_tick = get_tick(bar, 2.0)
        events_drums.append((snare_tick, Message('note_on', note=SNARE, velocity=110, channel=9)))
        events_drums.append((snare_tick + 100, Message('note_off', note=SNARE, velocity=0, channel=9)))

    # 3. Melody
    # Hook: "You used to call me on my cell phone"
    # Rhythm: 8th notes mostly.
    # Start usually on the 'and' of 4 of the previous bar? Or right on 1?
    # "You used to call me on my cell phone"
    # Beats: 1(&) 2(&) 3(&) 4(&) ...
    # It actually starts around beat 2 of the bar often in the verse, but the chorus starts on the 1.
    # Let's simplify: Start on Beat 1.
    # Notes: A, A, A, G, F, G, A, G, F, D
    # Rhythm (approx in beats): 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 1.0 ...
    
    hook_melody = [
        (0.0, NOTE_A4, 0.5), # You
        (0.5, NOTE_A4, 0.5), # used
        (1.0, NOTE_A4, 0.5), # to
        (1.5, NOTE_G4, 0.5), # call
        (2.0, NOTE_F4, 0.5), # me
        (2.5, NOTE_G4, 0.5), # on
        (3.0, NOTE_A4, 0.5), # my
        (3.5, NOTE_G4, 0.5), # cell
        (4.0, NOTE_F4, 1.0), # phone (Next bar beat 1)
        (5.5, NOTE_D4, 2.0), # (gap) ... phone/breath
    ]

    # Add hooks at specific intervals
    # Chorus usually at bar 4, 12, 20...
    melody_start_bars = [4, 8, 12, 20, 28, 36, 44, 52, 60]

    for start_bar in melody_start_bars:
        base_tick = get_tick(start_bar, 0)
        for rel_beat, note, dur in hook_melody:
            start_t = base_tick + int(rel_beat * TICKS_PER_BEAT)
            end_t = start_t + int(dur * TICKS_PER_BEAT)
            events_melody.append((start_t, Message('note_on', note=note, velocity=95, channel=2)))
            events_melody.append((end_t, Message('note_off', note=note, velocity=64, channel=2)))
            
    # "Late night when you need my love"
    # Similar melody but resolves differently. Let's just repeat the hook for simplicity as it's a demo.

    # --- Write Events to Tracks ---
    def write_track(track, events):
        events.sort(key=lambda x: x[0])
        last_tick = 0
        for abs_tick, msg in events:
            delta = abs_tick - last_tick
            if delta < 0: delta = 0
            msg.time = delta
            track.append(msg)
            last_tick = abs_tick

    write_track(track_drums, events_drums)
    write_track(track_chords, events_chords)
    write_track(track_bass, events_bass)
    write_track(track_melody, events_melody)

    mid.save(FILENAME)
    print(f"Successfully created {FILENAME}")

if __name__ == "__main__":
    create_midi()
