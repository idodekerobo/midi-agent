import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage, bpm2tempo

def create_hotline_bling_midi():
    # 1. Setup MIDI File
    mid = MidiFile(ticks_per_beat=480)
    
    # Track 0: Meta info (Tempo, Time Sig) + Melody
    melody_track = MidiTrack()
    mid.tracks.append(melody_track)
    
    # Track 1: Chords/Backing
    chord_track = MidiTrack()
    mid.tracks.append(chord_track)
    
    # Constants
    bpm = 135
    tempo = bpm2tempo(bpm)
    ticks_per_beat = 480
    
    # Add Tempo and Track Names
    melody_track.append(MetaMessage('track_name', name='Melody', time=0))
    melody_track.append(MetaMessage('set_tempo', tempo=tempo, time=0))
    chord_track.append(MetaMessage('track_name', name='Chords', time=0))
    
    # Helper to convert beats to ticks
    def beat2tick(beat):
        return int(beat * ticks_per_beat)

    # --- Melody Data ---
    # "You used to call me on my cell phone"
    # Rhythm is roughly: 
    # Beat 1.0: "You" (8th)
    # Beat 1.5: "used" (8th)
    # Beat 2.0: "to" (8th)
    # Beat 2.5: "call" (8th)
    # Beat 3.0: "me" (8th)
    # Beat 3.5: "on" (8th)
    # Beat 4.0: "my" (8th)
    # Beat 4.5: "cell" (8th)
    # Beat 5.0: "phone" (Held)
    
    # Notes: F#4, F#4, F#4, E4, D4, B3, A3, B3, B3
    # MIDI Notes: F#4=66, E4=64, D4=62, B3=59, A3=57
    
    melody_events_raw = [
        # Phrase 1: "You used to call me on my cell phone"
        (0.0, 66, 0.4), # You
        (0.5, 66, 0.4), # used
        (1.0, 66, 0.4), # to
        (1.5, 64, 0.4), # call
        (2.0, 62, 0.4), # me
        (2.5, 59, 0.4), # on
        (3.0, 57, 0.4), # my
        (3.5, 59, 0.4), # cell
        (4.0, 59, 2.0), # phone
        
        # Phrase 2: "Late night when you need my love"
        # Similar rhythm, slightly different melody
        # (Rest for a bit)
        # Starts around Beat 8
        (8.0, 66, 0.4), # Late
        (8.5, 66, 0.4), # night
        (9.0, 66, 0.4), # when
        (9.5, 64, 0.4), # you
        (10.0, 62, 0.4), # need
        (10.5, 59, 0.4), # my
        (11.0, 59, 2.0), # love
    ]
    
    # --- Chords Data ---
    # Progression: Bm (i) - A (VII) - Gmaj7 (VI)
    # Loop length: 4 beats (actually often 8 beats in slow feel, but at 135bpm it feels like 2 bars)
    # Let's do:
    # Bar 1 (Beats 0-4): Bm (beats 0-2), A (beats 2-4)
    # Bar 2 (Beats 4-8): Gmaj7 (beats 0-4)
    
    # Bm: B3, D4, F#4 (59, 62, 66)
    # A: A3, C#4, E4 (57, 61, 64)
    # Gmaj7: G3, B3, D4, F#4 (55, 59, 62, 66)
    
    chord_progression = [
        # Bar 1
        (0.0, [59, 62, 66], 2.0), # Bm
        (2.0, [57, 61, 64], 2.0), # A
        # Bar 2
        (4.0, [55, 59, 62, 66], 4.0), # Gmaj7
        
        # Bar 3
        (8.0, [59, 62, 66], 2.0), # Bm
        (10.0, [57, 61, 64], 2.0), # A
        # Bar 4
        (12.0, [55, 59, 62, 66], 4.0), # Gmaj7
    ]

    # --- Process Melody Track ---
    melody_msgs = []
    for start_beat, note, duration in melody_events_raw:
        start_tick = beat2tick(start_beat)
        end_tick = beat2tick(start_beat + duration)
        melody_msgs.append((start_tick, Message('note_on', note=note, velocity=90, time=0)))
        melody_msgs.append((end_tick, Message('note_off', note=note, velocity=0, time=0)))
    
    # Sort and delta-fy melody
    melody_msgs.sort(key=lambda x: x[0])
    last_tick = 0
    for abs_tick, msg in melody_msgs:
        delta = abs_tick - last_tick
        msg.time = delta
        melody_track.append(msg)
        last_tick = abs_tick

    # --- Process Chord Track ---
    chord_msgs = []
    for start_beat, notes, duration in chord_progression:
        start_tick = beat2tick(start_beat)
        end_tick = beat2tick(start_beat + duration)
        for note in notes:
            chord_msgs.append((start_tick, Message('note_on', note=note, velocity=70, time=0)))
            chord_msgs.append((end_tick, Message('note_off', note=note, velocity=0, time=0)))
            
    # Sort and delta-fy chords
    chord_msgs.sort(key=lambda x: x[0])
    last_tick = 0
    for abs_tick, msg in chord_msgs:
        delta = abs_tick - last_tick
        msg.time = delta
        chord_track.append(msg)
        last_tick = abs_tick
        
    mid.save('hotline_bling.mid')
    print("MIDI file 'hotline_bling.mid' created successfully.")

if __name__ == "__main__":
    create_hotline_bling_midi()
