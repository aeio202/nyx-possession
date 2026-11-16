"""What the ranking metric rewards, measured with the official scorer on synthetic sequences.

No match data is read. Each case is embedded between 40 perfectly matched possessions, so the
loss is in spellF1 points for a sequence of ~42 possessions (one fully lost possession ~ 0.023).

    python solution/metric_cases.py

Findings this script records (see PLAN.md, section 1):
  - a missed event and a falsely inserted one cost exactly the same;
  - whether an event exists matters far more than when it happens;
  - a missed stoppage only costs when the same team has the ball on both sides of it.
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "evaluation"))
import possession_metrics as pm  # noqa: E402

H, A, D = 0, 1, 2
FPS = 25
CONTEXT = [(H, 12), (A, 12)] * 10
GAP = [(D, 5)]

CASES = [
    ("miss a 1 s A in the middle of H (18/1/18)", [(H, 18), (A, 1), (H, 18)], [(H, 37)]),
    ("false 1 s A in the middle of H", [(H, 37)], [(H, 18), (A, 1), (H, 18)]),
    ("short A found, 0.5 s late", [(H, 18), (A, 1), (H, 18)], [(H, 18.5), (A, 1), (H, 17.5)]),
    ("short A found, 1 s late (no overlap)", [(H, 18), (A, 1), (H, 18)], [(H, 19), (A, 1), (H, 17)]),
    ("miss a 1 s A near the end (30/1/6)", [(H, 30), (A, 1), (H, 6)], [(H, 37)]),
    ("false 1 s A near the end", [(H, 37)], [(H, 30), (A, 1), (H, 6)]),
    ("miss a 3 s stoppage, same team both sides", [(H, 18), (D, 3), (H, 18)], [(H, 39)]),
    ("false 3 s stoppage inside a possession", [(H, 39)], [(H, 18), (D, 3), (H, 18)]),
    ("miss a 3 s stoppage, different teams", [(H, 18), (D, 3), (A, 18)], [(H, 19.5), (A, 19.5)]),
    ("stoppage start 3 s late, 12 s possession before", [(A, 12), (D, 15), (H, 12)],
     [(A, 15), (D, 12), (H, 12)]),
    ("stoppage start 3 s late, 5 s possession before", [(A, 5), (D, 15), (H, 12)],
     [(A, 8), (D, 12), (H, 12)]),
    ("restart 3 s late, 5 s possession after", [(A, 12), (D, 15), (H, 5)],
     [(A, 12), (D, 18), (H, 2)]),
    ("change 1.5 s late, 5 s possessions", [(A, 5), (H, 5)], [(A, 6.5), (H, 3.5)]),
    ("change 1.5 s late, 12 s possessions", [(A, 12), (H, 12)], [(A, 13.5), (H, 10.5)]),
]


def sequence(parts):
    return np.concatenate([np.full(int(round(seconds * FPS)), code) for code, seconds in parts])


def loss(truth, prediction):
    gt = sequence(CONTEXT + GAP + truth + GAP + CONTEXT)
    pred = sequence(CONTEXT + GAP + prediction + GAP + CONTEXT)
    return 1.0 - pm.spell_scores(gt, pred, pm.valid_runs(gt))["mean_f1"]


if __name__ == "__main__":
    for name, truth, prediction in CASES:
        print("{:<50} spellF1 loss {:.4f}".format(name, loss(truth, prediction)))
