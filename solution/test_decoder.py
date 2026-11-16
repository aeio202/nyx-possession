"""Synthetic checks of the decoder's behaviour. No match data is read.

    python solution/test_decoder.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from solution.model import A, D, H, PARAMS, viterbi  # noqa: E402


def decode(team, dead=None, a2d=None, d2a=None):
    n = len(team)
    dead = np.full(n, -1.0) if dead is None else dead
    scores = np.zeros((n, 3))
    scores[:, H], scores[:, A], scores[:, D] = team, -team, dead + np.abs(team)
    costs = {"a2d": np.full(n, PARAMS["alive_to_dead"]) if a2d is None else a2d,
             "d2a": np.full(n, PARAMS["dead_to_alive"]) if d2a is None else d2a}
    return viterbi(scores, costs)


def changes(path):
    return [(int(i + 1), int(path[i]), int(path[i + 1])) for i in np.flatnonzero(np.diff(path))]


def test_holds_previous_team_through_a_gap():
    """Home control, 100 frames without evidence, away control: the change is at the first
    frame of away control, in both directions."""
    for sign in (1.0, -1.0):
        team = np.r_[np.full(50, sign), np.zeros(100), np.full(50, -sign)]
        assert [c[0] for c in changes(decode(team))] == [150], changes(decode(team))


def test_brief_touch_does_not_change_possession():
    """Six frames of opposing control inside a long possession pay 2 x 6 < 2 x switch_cost."""
    team = np.r_[np.full(100, 1.0), np.full(6, -1.0), np.full(100, 1.0)]
    assert changes(decode(team)) == []


def test_sustained_control_changes_possession():
    team = np.r_[np.full(100, 1.0), np.full(20, -1.0), np.full(100, 1.0)]
    assert [c[0] for c in changes(decode(team))] == [100, 120]


def test_dead_is_not_a_free_bridge():
    """A line crossing and a kick on adjacent frames, with no dead evidence in between, must not
    create a stoppage inside a possession."""
    n = 200
    team = np.full(n, 1.0)
    a2d = np.full(n, PARAMS["alive_to_dead"])
    d2a = np.full(n, PARAMS["dead_to_alive"])
    a2d[100] = PARAMS["alive_to_dead_out"]
    d2a[103] = PARAMS["dead_to_alive_kick"]
    assert changes(decode(team, dead=np.zeros(n), a2d=a2d, d2a=d2a)) == []


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok  ", name)
