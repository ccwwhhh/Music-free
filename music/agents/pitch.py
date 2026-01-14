# Utilities for converting audio into Jianpu notation and MIDI using pitch tracking.

import numpy as np
import os
import tempfile
from typing import Optional, List
from mido import Message, MidiFile, MidiTrack, MetaMessage, bpm2tempo
import matplotlib.pyplot as plt
import librosa
from pydub import AudioSegment
import re




KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
MAJOR_INTERVALS = np.array([0, 2, 4, 5, 7, 9, 11])
MINOR_INTERVALS = np.array([0, 2, 3, 5, 7, 8, 10])

DEGREE_STR = ["1","2","3","4","5","6","7"]
TOKEN_RE = re.compile(r"^(?P<acc>[#b]*)(?P<deg>[1-7])(?P<oct>[',]*)$")
FFMPEG = r"D:\OpenAgents\music_free\ffmpeg-2025-12-10-git-4f947880bd-essentials_build\bin\ffmpeg.exe"
FFPROBE = r"D:\OpenAgents\music_free\ffmpeg-2025-12-10-git-4f947880bd-essentials_build\bin\ffprobe.exe"
bin_dir = os.path.dirname(FFMPEG)
os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")

def limit_rests(tokens: List[str], max_rest_ratio: float = 0.2) -> List[str]:
    # Limit the proportion of rest tokens ("0") relative to note tokens.
    if not tokens:
        return tokens

    note_cnt = sum(t != "0" for t in tokens)
    if note_cnt == 0:
        return tokens

    rest_idx = [i for i, t in enumerate(tokens) if t == "0"]
    rest_cnt = len(rest_idx)
    allowed = int(np.floor(note_cnt * max_rest_ratio))

    if rest_cnt <= allowed:
        return tokens

    need_remove = rest_cnt - allowed
    remove_set = set()

    # 1) leading rests
    i = 0
    while i < len(tokens) and tokens[i] == "0" and need_remove > 0:
        remove_set.add(i)
        need_remove -= 1
        i += 1

    # 2) trailing rests
    j = len(tokens) - 1
    while j >= 0 and tokens[j] == "0" and need_remove > 0:
        remove_set.add(j)
        need_remove -= 1
        j -= 1

    if need_remove == 0:
        return [t for k, t in enumerate(tokens) if k not in remove_set]

    # 3) rests between identical notes: A 0 A
    for k in range(1, len(tokens) - 1):
        if need_remove == 0:
            break
        if tokens[k] == "0" and tokens[k - 1] != "0" and tokens[k + 1] != "0" and tokens[k - 1] == tokens[k + 1]:
            remove_set.add(k)
            need_remove -= 1

    if need_remove == 0:
        return [t for k, t in enumerate(tokens) if k not in remove_set]

    # 4) remove remaining rests left-to-right
    for k in range(len(tokens)):
        if need_remove == 0:
            break
        if tokens[k] == "0" and k not in remove_set:
            remove_set.add(k)
            need_remove -= 1

    return [t for k, t in enumerate(tokens) if k not in remove_set]
def load_audio(path: str):
    # Use pydub so we can accept many input formats and normalize to WAV.
    audio = AudioSegment.from_file(path)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp_path = tmp.name
    tmp.close()

    audio.export(tmp_path, format="wav")
    y, sr = librosa.load(tmp_path, sr=None, mono=True)
    os.remove(tmp_path)
    return y, sr


def estimate_f0(
    y: np.ndarray,
    sr: int,
    fmin: str = "C2",
    fmax: str = "C6",
    frame_length: int = 2048,
    hop_length: int = 256,
):
    # Estimate frame-level F0 using librosa's probabilistic YIN (pyin).
    f0, voiced_flag, voiced_prob = librosa.pyin(
        y,
        fmin=librosa.note_to_hz(fmin),
        fmax=librosa.note_to_hz(fmax),
        frame_length=frame_length,
        hop_length=hop_length,
    )
    times = librosa.frames_to_time(np.arange(len(f0)), sr=sr, hop_length=hop_length)
    return f0, voiced_flag, times


def compute_rms(y: np.ndarray, frame_length: int = 2048, hop_length: int = 256) -> np.ndarray:
    # Frame-level RMS energy for basic activity/volume estimation.
    return librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]


def adaptive_rms_threshold(rms: np.ndarray, floor: float = 0.02, ratio: float = 0.2) -> float:
    # Derive a simple adaptive threshold from the loudest frames.
    if rms.size == 0:
        return floor
    ref = float(np.percentile(rms, 95))
    return max(floor, ref * ratio)


def plot_waveform(y: np.ndarray, sr: int, max_seconds: Optional[float] = None):
    # Quick visualization helper for raw waveforms.
    if max_seconds is not None:
        n = int(sr * max_seconds)
        y = y[:n]
    t = np.arange(len(y)) / sr
    plt.figure(figsize=(14, 4))
    plt.plot(t, y)
    plt.xlabel("Time (s)")
    plt.ylabel("Amplitude")
    plt.title("Waveform")
    plt.tight_layout()
    plt.show()


def plot_rms(times: np.ndarray, rms: np.ndarray, thr: Optional[float] = None):

    # Plot RMS curve, optionally drawing the activity threshold.
    plt.figure(figsize=(14, 3))
    plt.plot(times[: len(rms)], rms)
    if thr is not None:
        plt.axhline(thr)
    plt.xlabel("Time (s)")
    plt.ylabel("RMS")
    plt.title("RMS (energy) over time")
    plt.tight_layout()
    plt.show()


def plot_f0(times: np.ndarray, f0: np.ndarray, ymin: float = 50.0, ymax: float = 800.0):
    # Visualize pitch contour in Hz for debugging or inspection.
    plt.figure(figsize=(14, 3))
    plt.plot(times, f0)
    plt.ylim(ymin, ymax)
    plt.xlabel("Time (s)")
    plt.ylabel("F0 (Hz)")
    plt.title("Pitch contour (F0)")
    plt.tight_layout()
    plt.show()

def estimate_key_ks(midi_notes: np.ndarray):
    # Key estimation using Krumhansl-Schmuckler profiles for major/minor.
    midi_int = np.round(midi_notes).astype(int)
    pc = np.mod(midi_int, 12)
    hist = np.bincount(pc, minlength=12).astype(float)
    if hist.sum() == 0:
        return 0, "major", 0.0
    hist = hist / (hist.sum() + 1e-9)

    best_score = -1e18
    best_tonic = 0
    best_mode = "major"

    for t in range(12):
        s_major = float(np.dot(hist, np.roll(KS_MAJOR, t)))
        s_minor = float(np.dot(hist, np.roll(KS_MINOR, t)))
        if s_major > best_score:
            best_score, best_tonic, best_mode = s_major, t, "major"
        if s_minor > best_score:
            best_score, best_tonic, best_mode = s_minor, t, "minor"

    return best_tonic, best_mode, best_score


def pick_tonic_midi(tonic_pc: int, midi_int: np.ndarray) -> int:
    # Choose a tonic MIDI number whose octave is close to the median pitch.
    mid = int(np.median(midi_int))
    tonic = (mid // 12) * 12 + int(tonic_pc)


    if tonic - mid > 6:
        tonic -= 12
    elif mid - tonic > 6:
        tonic += 12
    return tonic

# degree 1..7 semitone offsets
DEGREE_STR = ["1", "2", "3", "4", "5", "6", "7"]


def midi_to_jianpu_symbol(m: int, tonic_midi: int,mode:str) -> str:
    # Map a MIDI note to a Jianpu degree symbol with accidentals and octave marks.

    delta = m - tonic_midi
    octv = int(np.floor(delta / 12))
    rel = int(delta % 12)

    intervals = MAJOR_INTERVALS if mode == "major" else MINOR_INTERVALS

    idx = int(np.argmin(np.abs(intervals - rel)))
    base_rel = int(intervals[idx])
    degree = DEGREE_STR[idx]

    acc = rel - base_rel
    if acc > 6: acc -= 12
    if acc < -6: acc += 12

    if acc == 1:
        degree = "#" + degree
    elif acc == -1:
        degree = "b" + degree
    elif acc != 0:
        degree = ("#" * acc + degree) if acc > 0 else ("b" * (-acc) + degree)

    if octv > 0:
        degree = degree + ("'" * octv)
    elif octv < 0:
        degree = degree + ("," * (-octv))

    return degree


def compress_symbols(symbols: List[str], min_len: int = 3) -> List[str]:
    """
    Simple note-level compression:
    - Merge consecutive identical symbols
    - Keep only runs with length >= min_len frames
    """
    # Collapse frame-level symbols into coarser note events.
    if not symbols:
        return []
    out: List[str] = []
    cur = symbols[0]
    cnt = 1
    for s in symbols[1:]:
        if s == cur:
            cnt += 1
        else:
            if cnt >= min_len:
                out.append(cur)
            cur = s
            cnt = 1
    if cnt >= min_len:
        out.append(cur)
    return out


def smooth_midi(midi: np.ndarray, win: int = 7) -> np.ndarray:
    """
    Median filter to reduce jitter. Good for voice, sometimes too aggressive for staccato piano.

    """
    # Apply a simple median filter in MIDI space to smooth noisy pitch tracks.
    if len(midi) < win:
        return midi
    half = win // 2
    sm = midi.copy()
    for i in range(half, len(midi) - half):
        sm[i] = np.median(midi[i - half : i + half + 1])
    return sm


def f0_to_jianpu(
    f0: np.ndarray,

    tonic_midi_user: Optional[int] = None,  # if provided, treat as "1"
    use_smoothing: bool = False,
    min_run_frames: int = 3,
) -> str:
    """
    Convert f0 (Hz per frame) to simplified Jianpu sequence:
    - Supports accidentals (#/b) + octave marks (', ,)
    - If user provides tonic_midi_user, use it; else auto-estimate key (KS)
    - Insert rests as "0" for unvoiced frames (np.nan)
    - Compress to note-level by keeping stable runs (including rests)
    """
    # 1) Collect voiced frames and estimate key/tonic from their MIDI pitches.
    if not np.any(~np.isnan(f0)):
        return ""


    f0_voiced = f0[~np.isnan(f0)]
    midi_voiced = librosa.hz_to_midi(f0_voiced)

    if use_smoothing:
        midi_voiced = smooth_midi(midi_voiced, win=7)

    midi_int = np.round(midi_voiced).astype(int)

    if tonic_midi_user is not None:
        tonic_midi = int(tonic_midi_user)
        mode = "major"   # user-provided tonic: just assume major template for degree mapping
        score = None
    else:
        tonic_pc, mode, score = estimate_key_ks(midi_voiced)
        tonic_midi = pick_tonic_midi(tonic_pc, midi_int)

    mode_use = mode if mode in ("major", "minor") else "major"


    print("tonic_midi:", tonic_midi, "tonic_pc:", tonic_midi % 12, "mode:", mode_use, "score:", score)
    print("midi range:", int(midi_int.min()), int(midi_int.max()), "median:", int(np.median(midi_int)))

    # 2) Convert each frame into a Jianpu symbol or rest, then compress.
    symbols: List[str] = []
    it = iter(midi_int.tolist())
    for v in f0:
        if np.isnan(v):
            symbols.append("0")  # rest
        else:
            m = next(it)
            symbols.append(midi_to_jianpu_symbol(int(m), tonic_midi, mode_use))


    symbols2 = compress_symbols(symbols, min_len=min_run_frames)


    symbols2 = limit_rests(symbols2, max_rest_ratio=0.2)

    return " ".join(symbols2)


def jianpu_token_to_midi(token: str, tonic_midi: int):
    # Parse a single Jianpu token into an absolute MIDI pitch.
    token = token.strip()
    if token == "0":
        return None

    m = TOKEN_RE.match(token)
    if not m:
        raise ValueError(f"Bad jianpu token: {token}")

    acc_str = m.group("acc") or ""
    deg = int(m.group("deg"))
    oct_str = m.group("oct") or ""

    base = int(MAJOR_INTERVALS[deg - 1])
    acc = acc_str.count("#") - acc_str.count("b")
    octv = oct_str.count("'") - oct_str.count(",")

    return int(tonic_midi + base + acc + 12 * octv)


def jianpu_to_midi_file(
    jianpu_str: str,
    out_mid_path: str,
    tonic_midi: int,
    bpm: int = 100,
    note_len_beats: float = 0.5,
    velocity: int = 80,
    program: int = 0,
):
    # Render a simple monophonic MIDI file from a Jianpu token sequence.
    tokens = [t for t in jianpu_str.split() if t.strip()]

    mid = MidiFile()
    track = MidiTrack()
    mid.tracks.append(track)

    track.append(MetaMessage("set_tempo", tempo=bpm2tempo(bpm), time=0))
    track.append(Message("program_change", program=program, time=0))

    dur = int(note_len_beats * mid.ticks_per_beat)

    for tok in tokens:
        pitch = jianpu_token_to_midi(tok, tonic_midi)

        if pitch is None:

            track.append(Message("note_off", note=0, velocity=0, time=dur))
        else:
            track.append(Message("note_on", note=pitch, velocity=velocity, time=0))
            track.append(Message("note_off", note=pitch, velocity=0, time=dur))

    mid.save(out_mid_path)
