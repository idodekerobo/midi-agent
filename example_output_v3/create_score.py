import json
import numpy as np
from scipy.stats import mode

ANALYSIS_PATH = "analysis.json"
OUT_PATH = "score.json"

TICKS_PER_BEAT = 480
QUANTIZE_GRID = 0.25  # 1/16th note in 4/4 time (1 beat = quarter note)

def quantize(value, grid):
    return round(value / grid) * grid

def get_pitch_stats(start_time, end_time, analysis):
    # Find indices in pitch arrays corresponding to this time range
    # pyin analysis has its own time axis, but it's roughly proportional to frames
    # detailed mapping: times = librosa.times_like(f0) which we didn't save explicitly,
    # but we saved the arrays. We can assume the hop length was default.
    # However, better approach: use the array lengths and duration to map time -> index.
    
    n_frames = len(analysis["pyin_midi_float"])
    duration = analysis["duration_seconds"]
    if duration == 0: return 0, False
    
    start_idx = int((start_time / duration) * n_frames)
    end_idx = int((end_time / duration) * n_frames)
    
    # Clamp
    start_idx = max(0, start_idx)
    end_idx = min(n_frames, end_idx)
    
    if start_idx >= end_idx:
        return 0, False

    segment_pitches = analysis["pyin_midi_float"][start_idx:end_idx]
    segment_voiced = analysis["pyin_voiced_flag"][start_idx:end_idx]
    
    # Filter for voiced only
    voiced_pitches = [p for p, v in zip(segment_pitches, segment_voiced) if v]
    
    if not voiced_pitches:
        return 0, False
    
    # Use median for stability
    median_pitch = np.median(voiced_pitches)
    return int(round(median_pitch)), True

def get_velocity(start_time, end_time, analysis):
    n_frames = len(analysis["rms"])
    duration = analysis["duration_seconds"]
    if duration == 0: return 0

    start_idx = int((start_time / duration) * n_frames)
    end_idx = int((end_time / duration) * n_frames)
    
    start_idx = max(0, start_idx)
    end_idx = min(n_frames, end_idx)
    
    if start_idx >= end_idx:
        return 0

    segment_rms = analysis["rms"][start_idx:end_idx]
    if not segment_rms:
        return 0
        
    avg_rms = np.mean(segment_rms)
    # Map RMS to velocity (heuristic)
    # Assuming RMS is usually 0.0 to 0.5? 
    # Let's normalize loosely.
    vel = int(min(127, max(40, avg_rms * 400))) 
    return vel

def main():
    with open(ANALYSIS_PATH, "r") as f:
        analysis = json.load(f)

    bpm = analysis["tempo_bpm"]
    if bpm <= 0: bpm = 120.0
    
    # Use onsets to define segments
    onsets = analysis["onset_times_seconds"]
    duration = analysis["duration_seconds"]
    
    # Add start and end
    boundaries = sorted(list(set([0.0] + onsets + [duration])))
    
    notes = []
    
    for i in range(len(boundaries) - 1):
        start_t = boundaries[i]
        end_t = boundaries[i+1]
        
        # Check if segment is too short to be a note
        if end_t - start_t < 0.05:
            continue

        midi_note, voiced = get_pitch_stats(start_t, end_t, analysis)
        
        if voiced and midi_note > 0:
            velocity = get_velocity(start_t, end_t, analysis)
            
            # Convert to beats
            start_beat = start_t * (bpm / 60.0)
            dur_beats = (end_t - start_t) * (bpm / 60.0)
            
            # Quantize
            q_start = quantize(start_beat, QUANTIZE_GRID)
            q_dur = quantize(dur_beats, QUANTIZE_GRID)
            
            if q_dur == 0:
                q_dur = QUANTIZE_GRID # minimal duration
            
            notes.append({
                "start_beat": q_start,
                "duration_beats": q_dur,
                "midi_note": midi_note,
                "velocity": velocity
            })

    # Post-processing: Resolve overlaps and merge consecutive identical notes?
    # For now, just resolve overlaps by cutting the previous note short
    # Sort first
    notes.sort(key=lambda x: x["start_beat"])
    
    clean_notes = []
    if notes:
        current = notes[0]
        for next_note in notes[1:]:
            # Check overlap
            if current["start_beat"] + current["duration_beats"] > next_note["start_beat"]:
                new_dur = next_note["start_beat"] - current["start_beat"]
                current["duration_beats"] = max(QUANTIZE_GRID, new_dur)
            
            # If after adjustment it still overlaps (e.g. same start time), pick the higher velocity or just skip?
            # Simple approach: if valid duration, keep it.
            if current["duration_beats"] > 0:
                clean_notes.append(current)
            
            current = next_note
        clean_notes.append(current)

    # Final check for measure crossing
    # "Do not allow a note to cross a measure boundary. If it would, split it."
    # Measure length is 4 beats
    final_melody = []
    for note in clean_notes:
        start = note["start_beat"]
        dur = note["duration_beats"]
        note_val = note["midi_note"]
        vel = note["velocity"]
        
        # While the note extends past the next measure boundary
        while True:
            measure_idx = int(start // 4)
            measure_end = (measure_idx + 1) * 4
            
            if start + dur > measure_end:
                # Split
                split_dur = measure_end - start
                if split_dur > 0: # Should be positive
                    final_melody.append({
                        "start_beat": round(start, 4),
                        "duration_beats": round(split_dur, 4),
                        "midi_note": note_val,
                        "velocity": vel
                    })
                
                # Remaining part
                dur -= split_dur
                start = measure_end
                if dur <= 0:
                    break
            else:
                # No split needed
                final_melody.append({
                    "start_beat": round(start, 4),
                    "duration_beats": round(dur, 4),
                    "midi_note": note_val,
                    "velocity": vel
                })
                break

    score = {
        "version": "0.1",
        "title": "Transcription",
        "tempo_bpm": round(bpm),
        "time_signature": { "beats": 4, "beat_type": 4 },
        "ticks_per_beat": TICKS_PER_BEAT,
        "quantization": { "grid": "1/16", "swing": 0.0 },
        "key_signature": { "fifths": 0, "mode": "major" },
        "melody": final_melody
    }

    with open(OUT_PATH, "w") as f:
        json.dump(score, f, indent=2)

    print(f"Wrote {OUT_PATH}")

if __name__ == "__main__":
    main()
