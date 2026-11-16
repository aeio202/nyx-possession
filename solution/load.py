"""Parse the tactical ATD into dense numpy arrays, cached on disk.

Arrays (index = video frame, 0 .. n_frames-1):
    ball   (N, 3)      x, y in metres, speed (m/s)   -- NaN where the ball is not tracked
    pos    (N, S, 2)   x, y in metres per track slot -- NaN where the slot is empty
    spd    (N, S)      speed per track slot (m/s)
    team   (S,)        0 = home, 1 = away

The cache lives in solution/cache/ and is gitignored: it is derived match data and must not be
published (RULES.md, "Do not publish derived data that would reconstruct it").
"""

import os
import sys
import xml.etree.ElementTree as ET

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from games import GAME, GAMES, require, source_frames  # noqa: E402

CACHE_DIR = os.path.join(HERE, "cache")


def _team_of_slots(meta_path):
    root = ET.parse(meta_path).getroot()
    team_ids = [t.get("id") for t in root.iter("Team")]
    home = team_ids[0]  # FIFA/EPTS convention: first team is home (Barcelona)
    return np.array([0 if p.get("teamId") == home else 1 for p in root.iter("Player")],
                    dtype=np.int8)


def _parse(raw_path, n_frames, n_slots, pitch):
    length, width = pitch
    ball = np.full((n_frames, 3), np.nan, dtype=np.float32)
    pos = np.full((n_frames, n_slots, 2), np.nan, dtype=np.float32)
    spd = np.full((n_frames, n_slots), np.nan, dtype=np.float32)
    with open(raw_path) as fh:
        for line in fh:
            parts = line.rstrip("\n").split(":")
            if len(parts) != 3:
                continue
            f = int(parts[0]) - 1  # frame_id counts from 1, video frames from 0
            if not 0 <= f < n_frames:
                continue
            b = parts[2].split(",")
            ball[f] = [float(v) for v in b[:3]]
            for s, grp in enumerate(parts[1].split(";")[:n_slots]):
                if grp[0] == "N":
                    continue
                v = grp.split(",")
                pos[f, s, 0] = float(v[0])
                pos[f, s, 1] = float(v[1])
                spd[f, s] = float(v[2])
    ball[:, 0] *= length
    ball[:, 1] *= width
    pos[..., 0] *= length
    pos[..., 1] *= width
    return ball, pos, spd


def load_atd(game=GAME, data_dir=None, refresh=False):
    cache = os.path.join(CACHE_DIR, "{}_tactical_atd.npz".format(game))
    if os.path.exists(cache) and not refresh:
        z = np.load(cache)
        return {k: z[k] for k in z.files}
    meta_path, raw_path = require(["atd_meta", "atd_raw"], game, data_dir)
    team = _team_of_slots(meta_path)
    n = source_frames("tactical", game)
    ball, pos, spd = _parse(raw_path, n, len(team), GAMES[game]["pitch"])
    os.makedirs(CACHE_DIR, exist_ok=True)
    np.savez_compressed(cache, ball=ball, pos=pos, spd=spd, team=team)
    return {"ball": ball, "pos": pos, "spd": spd, "team": team}


def load_tags(game=GAME, data_dir=None):
    """Smart Tagging as a list of dicts with start/end video frames (end exclusive)."""
    from starter.load_smart_tagging import load
    return load(game, data_dir)


if __name__ == "__main__":
    d = load_atd(refresh="--refresh" in sys.argv)
    for k, v in d.items():
        print(k, v.shape, v.dtype)
    print("ball present:", np.mean(~np.isnan(d["ball"][:, 0])))
