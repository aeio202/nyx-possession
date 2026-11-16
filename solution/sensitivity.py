"""Robustness check: scale each prior by 0.7 and 1.3 and measure how much the output moves.

Ground-truth free. For every perturbation it reports, over the full match:
  - frame agreement with the default submission,
  - possession count and mean duration,
  - dead-ball share.
A model whose output swings on a +/-30 % change of one constant is resting on that constant.

    python solution/sensitivity.py
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from games import GAME, GAMES, half_video_blocks  # noqa: E402
from solution import model as M  # noqa: E402
from solution.load import load_atd, load_tags  # noqa: E402
from solution.run import predict_with  # noqa: E402

KEYS = ["control_radius", "control_gate", "pass_weight", "reception_weight", "walk_speed", "walk_gain",
        "missing_onset", "quiet_gap", "quiet_bonus", "busy_malus", "carry_malus", "set_piece_bonus",
        "restart_support", "switch_cost",
        "alive_to_dead", "dead_to_alive", "dead_to_alive_kick", "alive_to_dead_whistle"]


def stats(labels):
    graded = np.concatenate([labels[a:b + 1] for _, a, b in half_video_blocks(GAME)])
    spells = []
    for _, a, b in half_video_blocks(GAME):
        seg = labels[a:b + 1]
        s = 0
        for i in range(1, len(seg) + 1):
            if i == len(seg) or seg[i] != seg[s]:
                if seg[s] in "HA":
                    spells.append(i - s)
                s = i
    return graded, len(spells), np.mean(spells) / 25, np.mean(graded == "D")


if __name__ == "__main__":
    atd, tags = load_atd(), load_tags()
    base = predict_with(atd, tags, dict(M.PARAMS))
    g0, n0, d0, s0 = stats(base)
    print("{:<24} {:>6} {:>6} {:>6} {:>6}".format("variant", "agree", "poss", "dur", "Dshare"))
    print("{:<24} {:>6.3f} {:>6d} {:>6.1f} {:>6.3f}".format("default", 1.0, n0, d0, s0))
    for key in KEYS:
        for f in (0.7, 1.3):
            p = dict(M.PARAMS)
            p[key] = M.PARAMS[key] * f
            lab = predict_with(atd, tags, p)
            g, n, d, s = stats(lab)
            print("{:<24} {:>6.3f} {:>6d} {:>6.1f} {:>6.3f}".format(
                "{} x{}".format(key, f), np.mean(g == g0), n, d, s))
