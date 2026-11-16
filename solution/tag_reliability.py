"""How reliable is each Smart Tagging code as a statement about the team in possession?

Ground-truth free: measured against a decoded submission, on its live frames, split by whether
the ball is tracked and by time since the tag started. Also the timing of decoded changes of
possession around ATTACKING TRANSITION tag starts.

    python solution/tag_reliability.py solution/output/submission.csv
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from solution import features as F  # noqa: E402
from solution.load import load_atd, load_tags  # noqa: E402

FPS = 25
DEFEND = {"defending in defensive third", "defending in middle third",
          "defending in attacking third", "defensive transition"}
SKIP = {"set pieces", "goals"}


def tag_side(e):
    """+1 if the tag says home has the ball, -1 away, 0 unknown."""
    team = (e["tags"].get("Team") or "").lower()
    side = 1 if team.startswith("barc") else -1 if team.startswith("atl") else 0
    return -side if (e["code"] or "").strip().lower() in DEFEND else side


def rate(code, mask, vote):
    k = mask & (vote != 0) & (code != 0)
    return (code[k] == vote[k]).mean() if k.sum() >= 250 else float("nan")


if __name__ == "__main__":
    labels = pd.read_csv(sys.argv[1]).label.values
    n = len(labels)
    code = np.where(labels == "H", 1, np.where(labels == "A", -1, 0))
    _, present, _, _, _ = F.ball_features(load_atd()["ball"])
    tags = load_tags()
    live = code != 0
    print("live frames {}   of which ball unseen {} ({:.2f})".format(
        int(live.sum()), int((live & ~present).sum()), (live & ~present).sum() / live.sum()))

    by = {}
    for e in tags:
        c = (e["code"] or "").strip().lower()
        if c not in SKIP and tag_side(e) != 0:
            by.setdefault(c, []).append(e)
    print("\nagreement of the tag's team with the decoded team, live frames only")
    print("{:<30}{:>4}{:>8}{:>8}{:>8}{:>8}{:>10}{:>10}".format(
        "code", "n", "med s", "all", "seen", "unseen", "first 4s", "4s-end"))
    everything = np.ones(n, dtype=bool)
    for c, events in sorted(by.items()):
        whole, head, tail = np.zeros(n), np.zeros(n), np.zeros(n)
        for e in events:
            a, b, s = e["start_frame"], e["end_frame"], tag_side(e)
            whole[a:b] = s
            head[a:min(b, a + 4 * FPS)] = s
            tail[min(b, a + 4 * FPS):b] = s
        print("{:<30}{:>4}{:>8.0f}{:>8.3f}{:>8.3f}{:>8.3f}{:>10.3f}{:>10.3f}".format(
            c, len(events), np.median([(e["end_frame"] - e["start_frame"]) / FPS for e in events]),
            rate(code, everything, whole), rate(code, present, whole), rate(code, ~present, whole),
            rate(code, everything, head), rate(code, everything, tail)))

    print("\nATTACKING TRANSITION: decoded change to the tagged team, offset from the tag start")
    offsets, none = [], 0
    for e in by.get("attacking transition", []):
        a, s = e["start_frame"], tag_side(e)
        lo = max(a - 5 * FPS, 1)
        w = code[lo - 1:a + 12 * FPS]
        gained = np.flatnonzero((w[1:] == s) & (w[:-1] != s)) + lo
        if len(gained):
            offsets.append((gained[np.argmin(np.abs(gained - (a + 3 * FPS)))] - a) / FPS)
        else:
            none += 1
    offsets = np.array(offsets)
    print("tags {}   with a change in [-5 s, +12 s]: {}   none: {}".format(
        len(offsets) + none, len(offsets), none))
    print("offset (s): min {:.1f}  quartiles {}  max {:.1f}".format(
        offsets.min(), np.percentile(offsets, [25, 50, 75]).round(1), offsets.max()))
    hist, edges = np.histogram(offsets, bins=np.arange(-5, 13, 1))
    print("per-second histogram from -5 s: " + " ".join(str(h) for h in hist))
