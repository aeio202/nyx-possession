"""Ground-truth-free audit of a submission's stoppages against published and automatic facts.

  1. The two kick-off frames published in DATA.md / FAQ.md (11185 and 113742): how far is the
     decoded start of play from each?
  2. Smart Tagging SET PIECES: every tagged restart should coincide with a decoded stoppage
     ending. Counts how many do, and how many have no stoppage near them at all.

    python solution/audit.py solution/output/submission.csv
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from games import GAME, half_video_blocks  # noqa: E402
from solution.load import load_tags  # noqa: E402

FPS = 25
PUBLISHED_KICKOFFS = (11185, 113742)


def audit(labels):
    dead = labels == "D"
    restarts = np.flatnonzero(dead[:-1] & ~dead[1:]) + 1
    alive_frames = np.flatnonzero(np.isin(labels, ["H", "A"]))
    for k in PUBLISHED_KICKOFFS:
        near = alive_frames[alive_frames >= k - 20 * FPS]
        print("kick-off {}: decoded start of play {:+d} frames".format(k, int(near[0] - k)))

    graded = np.zeros(len(labels), dtype=bool)
    for _, a, b in half_video_blocks(GAME):
        graded[a:b + 1] = True
    tagged = found = late = none = 0
    offsets = []
    for e in load_tags():
        if (e["code"] or "").strip().lower() != "set pieces":
            continue
        a, b = e["start_frame"], e["end_frame"]
        if not graded[a] or a in range(11000, 11200):
            continue
        tagged += 1
        hit = restarts[(restarts >= a - 2 * FPS) & (restarts <= a + 12 * FPS)]
        if len(hit):
            found += 1
            offsets.append((hit[0] - a) / FPS)
        elif dead[max(a - 10 * FPS, 0):a + 12 * FPS].mean() < 0.1:
            none += 1
        else:
            late += 1
    print("tagged set pieces: {}   restart decoded within [-2 s, +12 s] of the tag start: {}   "
          "elsewhere: {}   no stoppage near: {}".format(tagged, found, late, none))
    print("restart offset from tag start (s): quartiles {}".format(
        np.percentile(offsets, [25, 50, 75]).round(1)))
    runs = np.diff(np.flatnonzero(np.diff(np.r_[0, dead[graded].astype(int), 0])))[::2]
    print("stoppages: {}   median {:.1f} s   dead share {:.3f}".format(
        len(runs), np.median(runs) / FPS, dead[graded].mean()))
    structure(labels)
    transition_recall(labels)
    whistle_check(labels, graded)


def whistle_check(labels, graded, apart=4 * FPS):
    """Referee whistles heard in the audio, against the decoded stoppages. A whistle in open
    play stops it, so the decoder should be dead within a few seconds of nearly every one."""
    from solution.audio import whistles
    dead = labels == "D"
    first = whistles()[:, 0]
    first = first[graded[np.minimum(first, len(labels) - 1)]]
    first = first[np.r_[True, np.diff(first) > apart]]
    in_dead = dead[first]
    soon = np.array([dead[t:t + 3 * FPS].any() for t in first])
    later = np.array([dead[t:t + 10 * FPS].any() for t in first])
    print("referee whistles: {}   during a decoded stoppage: {}   in live play: {}, of which the "
          "decoder is dead within 3 s: {}, within 10 s: {}".format(
              len(first), int(in_dead.sum()), int((~in_dead).sum()),
              int((soon & ~in_dead).sum()), int((later & ~in_dead).sum())))


def segments(labels):
    """[(label, start, length)] per half, graded frames only."""
    out = []
    for _, a, b in half_video_blocks(GAME):
        seg = labels[a:b + 1]
        cut = np.flatnonzero(seg[1:] != seg[:-1]) + 1
        starts = np.r_[0, cut]
        stops = np.r_[cut, len(seg)]
        out.append([(seg[s], a + s, e - s) for s, e in zip(starts, stops)])
    return out


def structure(labels):
    """Shapes the metric is sensitive to (metric_cases.py): stoppages with the same team on both
    sides, very short stoppages, D used as a bridge between teams, very long possessions."""
    same = diff = short_same = short_any = bridge = 0
    same_lengths, spells = [], []
    for half in segments(labels):
        for i, (lab, _, length) in enumerate(half):
            if lab in "HA":
                spells.append(length / FPS)
            if lab != "D" or i == 0 or i == len(half) - 1:
                continue
            before, after = half[i - 1][0], half[i + 1][0]
            short_any += length < 2 * FPS
            if before == after:
                same += 1
                same_lengths.append(length / FPS)
                short_same += length < 3 * FPS
            else:
                diff += 1
                bridge += length < FPS
    spells = np.array(spells)
    print("stoppages by neighbours: same team both sides {} (median {:.1f} s), different teams {}"
          .format(same, np.median(same_lengths) if same_lengths else 0.0, diff))
    print("short stoppages: under 2 s: {}   same-team under 3 s: {}   "
          "bridge between teams under 1 s: {}".format(short_any, short_same, bridge))
    print("possessions: {}   over 40 s: {}   over 60 s: {}   under 2 s: {}   under 1 s: {}".format(
        len(spells), int((spells > 40).sum()), int((spells > 60).sum()),
        int((spells < 2).sum()), int((spells < 1).sum())))


def transition_recall(labels, window=3 * FPS):
    """ATTACKING TRANSITION tags mark a team winning the ball. For each one: is there a decoded
    change to that team within +/- `window` frames of the tag start? Unlike agreement over whole
    phases, this does not favour smoother labellings."""
    code = np.where(labels == "H", 1, np.where(labels == "A", -1, 0))
    counts = {"change to the tagged team": 0, "tagged team already in possession": 0,
              "other team throughout": 0, "dead or mixed": 0}
    for e in load_tags():
        if (e["code"] or "").strip().lower() != "attacking transition":
            continue
        team = (e["tags"].get("Team") or "").lower()
        side = 1 if team.startswith("barc") else -1 if team.startswith("atl") else 0
        a = e["start_frame"]
        w = code[max(a - window, 0):a + window]
        if side == 0 or len(w) == 0:
            continue
        gained = np.any((w[1:] == side) & (w[:-1] != side))
        if gained:
            counts["change to the tagged team"] += 1
        elif np.all(w == side):
            counts["tagged team already in possession"] += 1
        elif np.all(w == -side):
            counts["other team throughout"] += 1
        else:
            counts["dead or mixed"] += 1
    print("attacking-transition tags: " + "   ".join(
        "{}: {}".format(k, v) for k, v in counts.items()))


if __name__ == "__main__":
    audit(pd.read_csv(sys.argv[1]).label.values)
