import json
import numpy as np
import librosa
import os

AUDIO_PATH = "uploaded_audio.mp3"
OUT_PATH = "analysis.json"

def to_list(x):
    if isinstance(x, np.ndarray):
        return x.tolist()
    return x

def main():
    if not os.path.exists(AUDIO_PATH):
        print(f"File not found: {AUDIO_PATH}")
        return

    y, sr = librosa.load(AUDIO_PATH, sr=22050, mono=True, duration=120)
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
