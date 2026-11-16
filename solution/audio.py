"""Referee whistles from the audio track of the tactical video.

The audio is decoded locally with ffmpeg to 32-bit float at its native 48 kHz, first channel
only -- no resampling, no mixing and no rounding to 16 bits, so the samples are the AAC decoder's
own output (the recording is very quiet, and 16-bit rounding is a visible share of the signal in
the whistle band). It is cached next to the tracking cache. The referee's pealess whistle sounds two simultaneous narrow tones a few hundred
hertz apart between 3.4 and 4.7 kHz; spectators whistle a single, lower tone. A blast is a run of
20 ms hops in which both tones stand well above the surrounding spectrum.

    python solution/audio.py            # decode, detect and print summary statistics
    python solution/audio.py --stability   # are the detections robust to decoder-level noise?
"""
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from games import GAME, asset_paths  # noqa: E402

CACHE_DIR = os.path.join(HERE, "cache")
RATE = 48000          # Hz, the track's native rate
WINDOW = 1536         # samples = 32 ms, 31.25 Hz per bin
HOP = 960             # samples = 20 ms, i.e. two hops per video frame
FPS = 25
FLOOR = 1e-12                  # added to powers; far below any real level in float samples
# The whistle band and the comparison band on either side of it.
BAND = (3400.0, 4700.0)
SIDES = ((2500.0, 3400.0), (4700.0, 6000.0))
# Two tones at least 200 Hz apart, 300-600 Hz in this match (the pairs cluster at about 3.8 and
# 4.25 kHz over the whole recording; single strong tones do not cluster and are the crowd).
TONE_SEPARATION = 6            # bins excluded around the first tone when looking for the second
SPACING = (300.0, 600.0)       # Hz
FIRST_DB = 20.0                # the stronger tone over the median of SIDES
SECOND_DB = 12.0               # the weaker tone
MIN_TONE_HOPS = 5              # 0.1 s of two-tone sound in total
JOIN_HOPS = 10                 # blasts up to 0.2 s apart are one whistle (a double blow)


def decode(game=GAME, source="tactical", refresh=False):
    """First channel of the video's audio track as float32 at the native rate (cached)."""
    path = os.path.join(CACHE_DIR, "{}_{}_audio_{}.f32".format(game, source, RATE))
    if refresh or not os.path.exists(path):
        os.makedirs(CACHE_DIR, exist_ok=True)
        video = asset_paths(game, source=source)["video"]
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vn",
                        "-af", "pan=mono|c0=c0", "-f", "f32le", "-acodec", "pcm_f32le", path],
                       check=True)
    return np.fromfile(path, dtype=np.float32)


def median_spectrum(samples, n=40000):
    """Per-bin median power over `n` hops spread evenly across the recording. Crowd sound falls
    by ~25 dB between 1 and 5 kHz; dividing by this flattens it so a tone can be compared with
    its neighbours."""
    from numpy.lib.stride_tricks import sliding_window_view
    frames = sliding_window_view(samples, WINDOW)[::HOP]
    pick = np.linspace(0, len(frames) - 1, n).astype(np.int64)
    x = frames[pick].astype(np.float32) * np.hanning(WINDOW).astype(np.float32)
    return np.median(np.abs(np.fft.rfft(x, axis=1)) ** 2, axis=0) + FLOOR


def two_tone_mask(samples, chunk_hops=20000):
    """Per hop: True where the two-tone whistle signature is present."""
    from numpy.lib.stride_tricks import sliding_window_view
    freqs = np.fft.rfftfreq(WINDOW, 1.0 / RATE)
    lo, hi = np.searchsorted(freqs, BAND[0]), np.searchsorted(freqs, BAND[1])
    sides = np.zeros(len(freqs), dtype=bool)
    for a, b in SIDES:
        sides |= (freqs >= a) & (freqs < b)
    flat = median_spectrum(samples)
    window = np.hanning(WINDOW).astype(np.float32)
    frames = sliding_window_view(samples, WINDOW)[::HOP]
    n_hops = len(frames)
    mask = np.zeros(n_hops, dtype=bool)
    column = np.arange(hi - lo)[None, :]
    for start in range(0, n_hops, chunk_hops):
        x = frames[start:start + chunk_hops].astype(np.float32) * window
        power = (np.abs(np.fft.rfft(x, axis=1)) ** 2 + FLOOR) / flat
        base = np.median(power[:, sides], axis=1)
        three = (power[:, lo - 1:hi - 1] + power[:, lo:hi] + power[:, lo + 1:hi + 1]) / 3.0
        rows = np.arange(len(three))
        k1 = np.argmax(three, axis=1)
        first = 10.0 * np.log10(three[rows, k1] / base)
        rest = np.where(np.abs(column - k1[:, None]) <= TONE_SEPARATION, 0.0, three)
        k2 = np.argmax(rest, axis=1)
        second = 10.0 * np.log10(np.maximum(rest[rows, k2], 1e-12) / base)
        spacing = np.abs(freqs[lo + k1] - freqs[lo + k2])
        mask[start:start + len(rows)] = ((first > FIRST_DB) & (second > SECOND_DB)
                                         & (spacing >= SPACING[0]) & (spacing <= SPACING[1]))
    return mask


def whistle_events(mask):
    """[(first video frame, last video frame)] of whistle blasts from the per-hop mask."""
    edges = np.flatnonzero(np.diff(np.r_[0, mask.astype(np.int8), 0]))
    merged = []
    for a, b in zip(edges[::2], edges[1::2]):
        if merged and a - merged[-1][1] <= JOIN_HOPS:
            merged[-1][1] = b
            merged[-1][2] += b - a
        else:
            merged.append([a, b, b - a])
    return np.array([(hop_to_frame(a), hop_to_frame(b - 1)) for a, b, tone in merged
                     if tone >= MIN_TONE_HOPS], dtype=np.int64).reshape(-1, 2)


def whistles(game=GAME, refresh=False):
    """(n, 2) array of [first frame, last frame] of every referee-whistle blast (cached)."""
    path = os.path.join(CACHE_DIR, "{}_tactical_whistles.npy".format(game))
    if refresh or not os.path.exists(path):
        events = whistle_events(two_tone_mask(decode(game, refresh=refresh)))
        os.makedirs(CACHE_DIR, exist_ok=True)
        np.save(path, events)
        # the decoded audio is 1.5 GB; only the detections are kept
        raw = os.path.join(CACHE_DIR, "{}_tactical_audio_{}.f32".format(game, RATE))
        if os.path.exists(raw):
            os.remove(raw)
    return np.load(path)


def whistle_mask(events, n_frames, before=0, after=0):
    """Per video frame: True from `before` frames ahead of a blast to `after` frames past it."""
    mask = np.zeros(n_frames, dtype=bool)
    for a, b in events:
        mask[max(a - before, 0):min(b + after + 1, n_frames)] = True
    return mask


def hop_to_frame(hop_index):
    """Video frame containing the centre of a hop."""
    return ((hop_index * HOP + WINDOW // 2) * FPS) // RATE


if __name__ == "__main__":
    samples = decode(refresh="--refresh" in sys.argv)
    events = whistle_events(two_tone_mask(samples))
    lengths = (events[:, 1] - events[:, 0] + 1) / FPS
    print("audio {:.1f} s   whistle blasts {}   length quartiles {} s".format(
        len(samples) / RATE, len(events), np.percentile(lengths, [25, 50, 75]).round(2)))
    if "--stability" in sys.argv:
        # A different ffmpeg build may decode with differences in the last places of the float
        # samples. The detections must not depend on that: add noise far larger than any such
        # difference (relative to the recording's RMS level) and compare.
        rng = np.random.default_rng(0)
        rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
        for relative in (1e-5, 1e-4, 1e-3):
            noisy = samples + (rng.standard_normal(len(samples)) * rms * relative).astype(np.float32)
            other = whistle_events(two_tone_mask(noisy))
            same = len(other) == len(events) and np.array_equal(other, events)
            print("noise at {:g} x RMS: {} blasts, identical {}".format(relative, len(other), same))
