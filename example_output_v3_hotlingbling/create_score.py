import json
import numpy as np

ANALYSIS_PATH = "analysis.json"
SCORE_PATH = "score.json"

TICKS_PER_BEAT = 480

def main():
    with open(ANALYSIS_PATH, "r") as f:
        analysis = json.load(f)

    tempo_bpm = analysis["tempo_bpm"]
    duration = analysis["duration_seconds"]
    onsets = np.array(analysis["onset_times_seconds"])
    
    # Pitch and voicing
    midi_float = np.array(analysis["pyin_midi_float"])
    voiced = np.array(analysis["pyin_voiced_flag"])
    
    # Time axis for pitch frames
    n_frames = len(midi_float)
    frame_times = np.linspace(0, duration, n_frames)
    
    # RMS for velocity
    rms = np.array(analysis["rms"])
    # RMS might have different length, interpolate to pitch frames
    rms_interp = np.interp(frame_times, np.linspace(0, duration, len(rms)), rms)
    
    # Quantize function
    def time_to_beat(t):
        return t * (tempo_bpm / 60.0)
    
    def quantize_beat(b):
        return round(b * 4) / 4.0  # 1/16th grid
    
    melody = []
    
    # Iterate through onsets to form notes
    # If onsets are sparse, we might miss notes. 
    # But usually onsets are good note boundaries.
    # We can also check for pitch changes between onsets? 
    # For now, let's just use onsets as boundaries.
    
    # Add 0.0 and duration to onsets if not present
    boundaries = np.sort(np.unique(np.concatenate(([0.0, duration], onsets))))
    
    for i in range(len(boundaries) - 1):
        t_start = boundaries[i]
        t_end = boundaries[i+1]
        
        # Find frames in this segment
        mask = (frame_times >= t_start) & (frame_times < t_end)
        if not np.any(mask):
            continue
            
        segment_voiced = voiced[mask]
        if np.mean(segment_voiced) < 0.3: # Mostly unvoiced -> Rest
            continue
            
        segment_pitch = midi_float[mask]
        # Filter out zeros (unvoiced in pitch array)
        segment_pitch = segment_pitch[segment_pitch > 0]
        if len(segment_pitch) == 0:
            continue
            
        median_pitch = np.median(segment_pitch)
        note_int = int(round(median_pitch))
        
        # Velocity from RMS
        segment_rms = rms_interp[mask]
        avg_rms = np.mean(segment_rms)
        # Normalize RMS to velocity 40-110
        # typical rms is 0.0 to 0.5?
        velocity = int(np.clip(avg_rms * 400 + 40, 40, 110))
        
        # Quantize start and duration
        b_start = quantize_beat(time_to_beat(t_start))
        b_end = quantize_beat(time_to_beat(t_end))
        dur = b_end - b_start
        
        if dur <= 0:
            continue
            
        if note_int < 21 or note_int > 108: # Piano range
            continue
            
        melody.append({
            "start_beat": float(b_start),
            "duration_beats": float(dur),
            "midi_note": note_int,
            "velocity": velocity
        })
        
    # Resolve overlaps (though simple segmentation shouldn't have them, 
    # quantization might cause slight issues if not careful, 
    # but here b_end of one is b_start of next, so it's fine)
    
    # Sort just in case
    melody.sort(key=lambda x: x["start_beat"])
    
    # Remove duplicates or zero duration
    clean_melody = []
    for note in melody:
        if note["duration_beats"] > 0:
            clean_melody.append(note)
            
    score = {
        "version": "0.1",
        "title": "Uploaded Song",
        "tempo_bpm": tempo_bpm,
        "time_signature": { "beats": 4, "beat_type": 4 },
        "ticks_per_beat": TICKS_PER_BEAT,
        "quantization": { "grid": "1/16", "swing": 0.0 },
        "key_signature": { "fifths": 0, "mode": "major" },
        "melody": clean_melody
    }
    
    with open(SCORE_PATH, "w") as f:
        json.dump(score, f, indent=2)
        
    print(f"Wrote {SCORE_PATH} with {len(clean_melody)} notes")

if __name__ == "__main__":
    main()
