"""Run the unchanged competition pipeline on degraded sample matches and score it.

    python solution/external/calibrate.py                 # default parameters, all variants
    python solution/external/calibrate.py switch_cost 6 8 10 12 16 20
    python solution/external/calibrate.py walk_speed 1.0 1.2 1.4 1.6 1.8
    CONTROLLED_PASSES=1 python solution/external/calibrate.py   # definition-following labels
    EXTERNAL_GAMES=3 python solution/external/calibrate.py      # the hold-out match only
    INTERP=1 python solution/external/calibrate.py              # ball straight between contacts

The score is the official spellF1 / macroF1 against labels derived from the sample matches'
own tracking and events (see sample.py for the label rules). Results are averaged over the
matches and over degradation variants, and the spread is printed, because a parameter should be
chosen from a broad region that is good everywhere, not from the peak of one variant.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "evaluation"))

import possession_metrics as pm  # noqa: E402
from solution.external import sample  # noqa: E402
from solution.external.corrupt import corrupt  # noqa: E402
from solution.model import PARAMS, emissions, restart_owner, viterbi  # noqa: E402

# (name, keyword arguments of corrupt). "target-like" is the best guess; the others bracket it.
VARIANTS = [
    ("target-like", dict(seed=0)),
    ("target-like, other seed", dict(seed=1)),
    ("lighter ball smoothing", dict(seed=0, smooth=13)),
    ("heavier ball smoothing", dict(seed=0, smooth=37)),
    ("more ball lost in play", dict(seed=0, live_missing=0.15)),
    ("ball never seen when dead", dict(seed=0, dead_seen=False)),
]


def decode(atd, tags, periods, params):
    scores, feats = emissions(atd, tags, sample.PITCH, params, None)
    path = np.zeros(len(scores), dtype=np.int8)
    for a, b in periods:
        seg = slice(int(a), int(b) + 1)
        costs = {k: v[seg] for k, v in feats["costs"].items()}
        path[seg] = viterbi(scores[seg], costs, params)
        path[seg] = restart_owner(path[seg], tags, feats["team"][seg], int(a), params)
    return path


def with_breaks(codes, periods):
    """Concatenate the halves with an ungraded frame between them, as the scorer expects."""
    parts = []
    for a, b in periods:
        parts += [codes[int(a):int(b) + 1], np.array([pm.X], dtype=codes.dtype)]
    return np.concatenate(parts[:-1])


# Possessions this short between two possessions of the other team are merged away in the
# "controlled" labelling (see sample.merge_brief). 0 = the raw event-derived labels.
MERGE_BRIEF = int(float(os.environ.get("MERGE_BRIEF_S", "0")) * sample.FPS)
# CONTROLLED_PASSES=n: labels following the definition instead (sample.controlled): a change of
# possession needs n completed passes by the new team or CONTROLLED_HOLD_S seconds on the ball.
# 1 is the lenient reading of CHALLENGE.md, 3 ("more than two consecutive passes") the strict.
CONTROLLED = int(os.environ.get("CONTROLLED_PASSES", "0"))
CONTROLLED_HOLD = float(os.environ.get("CONTROLLED_HOLD_S", "3"))
_LABELS = {}


def reference_labels(game):
    labels = game["labels"]
    if CONTROLLED:
        key = game["game_id"]
        if key not in _LABELS:
            _LABELS[key] = sample.controlled(key, labels, game["periods"], CONTROLLED_HOLD,
                                             CONTROLLED)
        return _LABELS[key]
    if MERGE_BRIEF:
        return sample.merge_brief(labels, game["periods"], MERGE_BRIEF)
    return labels


def score(game, path):
    labels = reference_labels(game)
    gt = with_breaks(labels.astype(np.int64), game["periods"])
    pred = with_breaks(path.astype(np.int64), game["periods"])
    pred[gt == pm.X] = pm.X
    runs = pm.valid_runs(gt)
    spell = pm.spell_scores(gt, pred, runs)
    cm3 = pm.scored_confusion(pm.confusion(gt, pred))
    return dict(spell=spell["mean_f1"], macro=pm.macro_f1(cm3), n_pred=spell["n_pred"],
                n_gt=spell["n_gt"], dead_pred=float((pred == pm.D).mean()),
                dead_gt=float((gt == pm.D).mean()))


def base_params():
    """PARAMS with overrides from the environment, e.g. PARAMS_BASE="switch_cost=8,walk_speed=1.3"."""
    p = dict(PARAMS)
    for item in filter(None, os.environ.get("PARAMS_BASE", "").split(",")):
        k, v = item.split("=")
        p[k] = float(v)
    return p


_CACHE = {}


# INTERP=1: the ball is first redrawn as straight lines between contacts (sample.contact_frames,
# 25 % of them left out), as on the target, before the usual degradation.
INTERP = os.environ.get("INTERP", "0") == "1"


def degraded(game_id, name, kwargs):
    key = (game_id, name)
    if key not in _CACHE:
        game = dict(sample.load(game_id), game_id=game_id)
        if INTERP:
            kwargs = dict(kwargs, anchors=sample.contact_frames(game_id, seed=kwargs.get("seed", 0)))
        _CACHE[key] = (game,) + corrupt(game, **kwargs)
    return _CACHE[key]


# EXTERNAL_GAMES=3 scores the hold-out match instead of the calibration matches 1 and 2.
GAMES = tuple(int(g) for g in os.environ.get("EXTERNAL_GAMES", "1,2").split(","))


def evaluate(params, variants=VARIANTS, games=GAMES):
    rows = []
    for name, kwargs in variants:
        for game_id in games:
            game, atd, tags = degraded(game_id, name, kwargs)
            rows.append((name, game_id, score(game, decode(atd, tags, game["periods"], params))))
    return rows


def summary(rows):
    spell = np.array([r[2]["spell"] for r in rows])
    macro = np.array([r[2]["macro"] for r in rows])
    ratio = np.array([r[2]["n_pred"] / r[2]["n_gt"] for r in rows])
    dead = np.array([r[2]["dead_pred"] - r[2]["dead_gt"] for r in rows])
    return spell.mean(), spell.min(), macro.mean(), ratio.mean(), dead.mean()


if __name__ == "__main__":
    import warnings
    warnings.simplefilter("ignore")
    if len(sys.argv) > 2:
        key, values = sys.argv[1], [float(v) for v in sys.argv[2:]]
        print("{:<22}{:>9}{:>9}{:>9}{:>12}{:>12}".format(
            key, "spellF1", "worst", "macroF1", "poss ratio", "dead diff"))
        for v in values:
            p = base_params()
            p[key] = v
            print("{:<22g}{:>9.4f}{:>9.4f}{:>9.4f}{:>12.2f}{:>+12.3f}".format(
                v, *summary(evaluate(p))))
    else:
        rows = evaluate(base_params())
        print("{:<28}{:>5}{:>9}{:>9}{:>8}{:>8}{:>8}{:>8}".format(
            "variant", "game", "spellF1", "macroF1", "pred", "true", "D pred", "D true"))
        for name, game_id, r in rows:
            print("{:<28}{:>5}{:>9.4f}{:>9.4f}{:>8}{:>8}{:>8.3f}{:>8.3f}".format(
                name, game_id, r["spell"], r["macro"], r["n_pred"], r["n_gt"],
                r["dead_pred"], r["dead_gt"]))
        print("mean spellF1 {:.4f}  worst {:.4f}  mean macroF1 {:.4f}  possessions pred/true {:.2f}"
              "  dead share pred-true {:+.3f}".format(*summary(rows)))
