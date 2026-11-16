"""Ground-truth-free model comparison: agreement with the Smart Tagging team tags.

The Smart Tagging is automatic and noisy (a phase spans several possessions), so its agreement
with any labelling is far from 1. But its errors do not depend on our model, so of two labellings
the one that agrees more with it over the whole match is, on average, the better H/A labelling.
Compared on the frames both files call alive, so dead-ball differences do not leak in.

    python solution/tag_agreement.py a.csv b.csv
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from solution.load import load_tags  # noqa: E402

ATTACK = {"build up", "progression", "creating chances", "attacking transition",
          "ball in final third", "ball in the box", "players in the box", "long ball"}
DEFEND = {"defending in defensive third", "defending in middle third",
          "defending in attacking third", "defensive transition"}


def tag_vote(n):
    """Per frame: > 0 if the tags favour home, < 0 away, 0 none / balanced."""
    vote = np.zeros(n)
    for e in load_tags():
        code = (e["code"] or "").strip().lower()
        team = (e["tags"].get("Team") or "").lower()
        side = 1 if team.startswith("barc") else -1 if team.startswith("atl") else 0
        if code in DEFEND:
            side = -side
        elif code not in ATTACK:
            side = 0
        vote[e["start_frame"]:e["end_frame"]] += side
    return vote


if __name__ == "__main__":
    labels = [pd.read_csv(p).label.values for p in sys.argv[1:]]
    vote = tag_vote(len(labels[0]))
    common = (vote != 0) & np.all([np.isin(l, ["H", "A"]) for l in labels], axis=0)
    print("frames compared: {}".format(int(common.sum())))
    for path, l in zip(sys.argv[1:], labels):
        agree = ((vote > 0) & (l == "H")) | ((vote < 0) & (l == "A"))
        print("{:<40} agreement {:.4f}".format(os.path.basename(path), agree[common].mean()))
    if len(labels) == 2:
        differ = common & (labels[0] != labels[1])
        a = ((vote > 0) & (labels[0] == "H")) | ((vote < 0) & (labels[0] == "A"))
        print("frames where the two differ: {}   tags side with the first on {:.3f}".format(
            int(differ.sum()), a[differ].mean()))
