"""Collective-reversal test: a label-free check of whether a decoded change of possession is real.

When the ball really changes hands, both teams switch roles within a couple of seconds: the new
team in possession moves towards the goal it attacks and the team that lost the ball retreats.
For a false change (the decoder hands the ball over while the same team keeps it) no such
reversal happens.

Statistic, at a direct H<->A change at frame t, new possessor k:
    v_team(f)  mean x-velocity (m/s) of that team's tracked players at frame f
    s_k        +1 if k attacks towards +x in this half, else -1 (from the teams' mean positions
               in the half: a team spends most of a half nearer the goal it defends)
    reversal   s_k * ( mean v over [t+1 s, t+3 s]  -  mean v over [t-2 s, t] )
reported for the new team, for the old team and for both together (the block). Positive means
movement turned towards the new possessor's attacking goal. The windows are round-number priors
for "within a couple of seconds" and are not fitted.

    python solution/reversal.py external        # check on the labelled other matches
    python solution/reversal.py match 6 8 12 16  # competition match, changes vs switch_cost

Prints aggregates only (counts, means, quantiles, AUC); no frame-level values.
"""
import os
import sys
import warnings

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from solution import features as F  # noqa: E402

FPS = 25
BEFORE = (-2 * FPS, 0)       # frames relative to the change, half-open
AFTER = (1 * FPS, 3 * FPS)
MATCH_TOL = 2 * FPS          # a decoded change within this of a reference change is the same one
# external check only: CONTROLLED_PASSES=n takes sample.controlled labels as the truth
CONTROLLED = int(os.environ.get("CONTROLLED_PASSES", "0"))
H, A, D = 0, 1, 2


def team_velocity(pos, team, step=5):
    """(N, 2) mean x-velocity of home and away tracked players (m/s, over +/- 0.2 s)."""
    vx = F.player_velocities(pos, step=step)[..., 0]
    out = np.full((len(pos), 2), np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for side in (0, 1):
            out[:, side] = np.nanmean(vx[:, team == side], axis=1)
    return out


def attack_signs(pos, team, periods):
    """[(first, last, sign_home)] per period; sign_home = +1 if home attacks towards +x."""
    out = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for a, b in periods:
            x = pos[int(a):int(b) + 1, :, 0]
            home = np.nanmean(x[:, team == 0])
            away = np.nanmean(x[:, team == 1])
            out.append((int(a), int(b), 1 if home < away else -1))
    return out


def changes(labels, periods):
    """[(frame, new team)] for every direct H<->A change inside a period."""
    out = []
    for a, b in periods:
        seg = labels[int(a):int(b) + 1]
        cut = np.flatnonzero(seg[1:] != seg[:-1]) + 1
        for c in cut:
            if seg[c - 1] in (H, A) and seg[c] in (H, A):
                out.append((int(a) + int(c), int(seg[c])))
    return out


def reversal(vel, signs, events):
    """(n, 3) reversal of new team, old team and block at each (frame, new team); NaN if a
    window leaves the period or has no tracked players."""
    out = np.full((len(events), 3), np.nan)
    for i, (t, k) in enumerate(events):
        for a, b, s_home in signs:
            if a <= t + BEFORE[0] and t + AFTER[1] <= b + 1:
                s = s_home if k == H else -s_home
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    before = np.nanmean(vel[t + BEFORE[0]:t + BEFORE[1]], axis=0)
                    after = np.nanmean(vel[t + AFTER[0]:t + AFTER[1]], axis=0)
                d = s * (after - before)
                out[i] = d[k], d[1 - k], np.mean(d)
                break
    return out


def null_events(labels, periods, rng, n=2000, guard=3 * FPS):
    """Pseudo-changes at random live frames at least `guard` from any change of state: the team
    in possession is unchanged, the pseudo-change hands the ball to the other team."""
    lab = np.asarray(labels)
    ok = np.zeros(len(lab), dtype=bool)
    for a, b in periods:
        ok[int(a) + guard:int(b) + 1 - guard] = True
    edge = np.flatnonzero(lab[1:] != lab[:-1]) + 1
    near = np.zeros(len(lab) + 1, dtype=int)
    np.add.at(near, np.clip(edge - guard, 0, len(lab)), 1)
    np.add.at(near, np.clip(edge + guard, 0, len(lab)), -1)
    ok &= np.cumsum(near)[:len(lab)] == 0
    ok &= (lab == H) | (lab == A)
    frames = rng.choice(np.flatnonzero(ok), size=min(n, int(ok.sum())), replace=False)
    return [(int(t), 1 - int(lab[t])) for t in np.sort(frames)]


def match_events(events, reference, tol=MATCH_TOL):
    """Boolean per event: a reference change to the same team lies within `tol` frames."""
    ref = {H: np.array([t for t, k in reference if k == H]),
           A: np.array([t for t, k in reference if k == A])}
    out = np.zeros(len(events), dtype=bool)
    for i, (t, k) in enumerate(events):
        r = ref[k]
        out[i] = len(r) > 0 and np.min(np.abs(r - t)) <= tol
    return out


def auc(pos, neg):
    """Probability that a positive scores above a negative (ties count half)."""
    pos, neg = pos[~np.isnan(pos)], neg[~np.isnan(neg)]
    if not len(pos) or not len(neg):
        return np.nan
    diff = pos[:, None] - neg[None, :]
    return float((diff > 0).mean() + 0.5 * (diff == 0).mean())


def describe(name, r, width=34):
    """One line: n, mean (block), median, share positive, and new / old team means."""
    ok = ~np.isnan(r[:, 2])
    r = r[ok]
    if not len(r):
        return "{:<{w}}{:>5}".format(name, 0, w=width)
    return "{:<{w}}{:>5}{:>8.2f}{:>8.2f}{:>8.2f}{:>9.2f}{:>9.2f}".format(
        name, len(r), r[:, 2].mean(), np.median(r[:, 2]), (r[:, 2] > 0).mean(),
        r[:, 0].mean(), r[:, 1].mean(), w=width)


HEADER = "{:<34}{:>5}{:>8}{:>8}{:>8}{:>9}{:>9}".format(
    "", "n", "mean", "median", ">0", "new tm", "old tm")


def implied_real_share(r_set, r_real, r_false):
    """Share of real changes in a set, from its mean block reversal, by linear mixing of the
    means of a reference real set and a reference false set."""
    m = np.nanmean(r_set[:, 2])
    return (m - np.nanmean(r_false[:, 2])) / (np.nanmean(r_real[:, 2]) - np.nanmean(r_false[:, 2]))


def implied_ci(r_set, r_real, r_false, n_boot=2000, seed=0):
    """5-95 % bootstrap interval of implied_real_share, resampling all three sets."""
    rng = np.random.default_rng(seed)
    sets = [r[~np.isnan(r[:, 2]), 2] for r in (r_set, r_real, r_false)]
    if min(len(s) for s in sets) < 2:
        return np.nan, np.nan
    out = []
    for _ in range(n_boot):
        m, real, false = (rng.choice(s, len(s)).mean() for s in sets)
        out.append((m - false) / (real - false))
    return tuple(np.percentile(out, [5, 95]))


# --------------------------------------------------------------------------------------------
# decoding at several switch costs (emissions do not depend on it, so they are computed once)

def _decode_external(atd, tags, periods, params, costs_list):
    from solution.external import sample
    from solution.model import emissions, viterbi
    scores, feats = emissions(atd, tags, sample.PITCH, params, None)
    out = {}
    for c in costs_list:
        p = dict(params, switch_cost=float(c))
        path = np.full(len(scores), D, dtype=np.int8)
        for a, b in periods:
            seg = slice(int(a), int(b) + 1)
            path[seg] = viterbi(scores[seg], {k: v[seg] for k, v in feats["costs"].items()}, p)
        out[c] = path
    return out


def _decode_match(params, costs_list):
    from games import GAME, GAMES, half_video_blocks
    from solution.audio import whistles
    from solution.load import load_atd, load_tags
    from solution.model import emissions, viterbi
    from solution.run import HALF_NAMES, kickoff_release
    atd, tags = load_atd(GAME), load_tags(GAME)
    blasts = whistles(GAME)
    scores, feats = emissions(atd, tags, GAMES[GAME]["pitch"], params, blasts)
    kickoffs = F.kickoff_frames(tags)
    blocks = half_video_blocks(GAME)
    out = {}
    for c in costs_list:
        p = dict(params, switch_cost=float(c))
        path = np.full(len(scores), 3, dtype=np.int8)          # 3 = ungraded
        for half, first, last in blocks:
            seg = slice(first, last + 1)
            force = np.zeros(last + 1 - first, dtype=bool)
            k = kickoffs.get(HALF_NAMES[half])
            if k is not None and k > first:
                force[:kickoff_release(k, blasts) - first] = True
            path[seg] = viterbi(scores[seg], {k2: v[seg] for k2, v in feats["costs"].items()},
                                p, force_dead=force)
        out[c] = path
    periods = [(first, last) for _, first, last in blocks]
    return atd, periods, out


def compare_costs(paths, base, periods):
    """For each cost: its changes, those added (no base change to the same team within
    MATCH_TOL) and those removed (base changes with no counterpart); plus the base changes
    present in every decode."""
    ev_base = changes(paths[base], periods)
    res = {}
    for c, path in paths.items():
        ev = changes(path, periods)
        added = [e for e, m in zip(ev, match_events(ev, ev_base)) if not m]
        removed = [e for e, m in zip(ev_base, match_events(ev_base, ev)) if not m]
        res[c] = (ev, added, removed)
    keep = np.all([match_events(ev_base, res[c][0]) for c in paths], axis=0)
    common = [e for e, k in zip(ev_base, keep) if k]
    return res, common


def _length_after(labels, events):
    out = []
    for t, _ in events:
        e = t
        while e < len(labels) and labels[e] == labels[t]:
            e += 1
        out.append((e - t) / FPS)
    return np.array(out)


BANDS = ((0, 2), (2, 4), (4, 8), (8, 1e9))


def _band(lo, hi):
    return "{}-{} s".format(lo, hi if hi < 1e9 else "inf")


def run_external(costs_list=(6, 8, 12, 16), base=12.0):
    from solution.external import sample
    from solution.external.calibrate import base_params
    from solution.external.corrupt import corrupt
    rng = np.random.default_rng(0)
    params = base_params()
    pooled = {}

    def add(key, r):
        pooled.setdefault(key, []).append(r)

    for gid in sample.GAMES:
        game = sample.load(gid)
        atd, tags = corrupt(game, seed=0)
        periods = [tuple(map(int, p)) for p in game["periods"]]
        vel = team_velocity(atd["pos"], atd["team"])
        signs = attack_signs(atd["pos"], atd["team"], periods)
        raw = game["labels"]
        merged = sample.merge_brief(raw, game["periods"], 3 * FPS)
        if CONTROLLED:
            # reference = labels that follow the definition (sample.controlled)
            raw = sample.controlled(gid, raw, game["periods"], 3.0, CONTROLLED)

        true_ev = changes(raw, periods)
        r_true = reversal(vel, signs, true_ev)
        lengths = _length_after(raw, true_ev)
        add("true change (reference labels)", r_true)
        for lo, hi in BANDS:
            add("  new possession " + _band(lo, hi), r_true[(lengths >= lo) & (lengths < hi)])
        add("true change (brief merged, 3 s)", reversal(vel, signs, changes(merged, periods)))
        add("null (random live frame)", reversal(vel, signs, null_events(raw, periods, rng)))

        paths = _decode_external(atd, tags, periods, params, costs_list)
        res, common = compare_costs(paths, base, periods)
        ev = res[base][0]
        real = match_events(ev, true_ev)
        r_dec = reversal(vel, signs, ev)
        add("decoded {:g}: matches a true change".format(base), r_dec[real])
        add("decoded {:g}: false".format(base), r_dec[~real])
        add("in every decode (core)", reversal(vel, signs, common))
        add("core & real", reversal(vel, signs, [e for e, m in zip(
            common, match_events(common, true_ev)) if m]))
        for c in costs_list:
            if c == base:
                continue
            _, added, removed = res[c]
            for kind, e in (("added", added), ("removed", removed)):
                r = reversal(vel, signs, e)
                m = match_events(e, true_ev) if e else np.zeros(0, dtype=bool)
                add("cost {:g}: {}".format(c, kind), r)
                add("cost {:g}: {} & real".format(c, kind), r[m])
                add("cost {:g}: {} & false".format(c, kind), r[~m])

    pooled = {k: np.concatenate(v) for k, v in pooled.items()}
    print("external matches 1+2 (target-like degradation); reversal in m/s; reference labels: {}"
          .format("controlled, {} pass(es) or 3 s".format(CONTROLLED) if CONTROLLED else "raw"))
    print(HEADER)
    for k, r in pooled.items():
        print(describe(k, r))
    real_ref = pooled["decoded {:g}: matches a true change".format(base)]
    false_ref = pooled["decoded {:g}: false".format(base)]
    print("\nAUC real vs false decoded changes (block / new team / old team): "
          "{:.3f} / {:.3f} / {:.3f}".format(*(auc(real_ref[:, j], false_ref[:, j])
                                              for j in (2, 0, 1))))
    print("AUC false decoded changes vs null: {:.3f}".format(
        auc(false_ref[:, 2], pooled["null (random live frame)"][:, 2])))
    print("\nshare of real changes: actual vs implied by mean reversal "
          "(references: core = real, null = false)")
    for c in costs_list:
        if c == base:
            continue
        for kind in ("added", "removed"):
            r_all = pooled["cost {:g}: {}".format(c, kind)]
            n_all = int((~np.isnan(r_all[:, 2])).sum())
            n_real = int((~np.isnan(pooled["cost {:g}: {} & real".format(c, kind)][:, 2])).sum())
            imp = implied_real_share(r_all, pooled["in every decode (core)"],
                                     pooled["null (random live frame)"])
            lo, hi = implied_ci(r_all, pooled["in every decode (core)"],
                                pooled["null (random live frame)"])
            print("  cost {:>4g} {:<8} n {:>4}  actual {:.2f}  implied {:.2f}  (5-95 % {:.2f}-{:.2f})"
                  .format(c, kind, n_all, n_real / max(n_all, 1), imp, lo, hi))


def run_match(costs_list=(6, 8, 12, 16), base=12.0):
    from solution.model import PARAMS
    rng = np.random.default_rng(0)
    atd, periods, paths = _decode_match(dict(PARAMS), costs_list)
    vel = team_velocity(atd["pos"], atd["team"])
    signs = attack_signs(atd["pos"], atd["team"], periods)
    res, common = compare_costs(paths, base, periods)
    r_core = reversal(vel, signs, common)
    r_null = reversal(vel, signs, null_events(paths[base], periods, rng))
    ev_base = res[base][0]
    r_base = reversal(vel, signs, ev_base)
    lengths = _length_after(paths[base], ev_base)
    print("competition match; reversal in m/s (base switch_cost {:g})".format(base))
    print(HEADER)
    print(describe("decoded {:g}: all direct changes".format(base), r_base))
    for lo, hi in BANDS:
        print(describe("  new possession " + _band(lo, hi),
                       r_base[(lengths >= lo) & (lengths < hi)]))
    print(describe("in every decode (core)", r_core))
    print(describe("null (random live frame)", r_null))
    for c in sorted(costs_list):
        if c == base:
            continue
        ev, added, removed = res[c]
        print("cost {:g}: {} direct changes".format(c, len(ev)))
        for kind, e in (("added", added), ("removed", removed)):
            r = reversal(vel, signs, e)
            if not e:
                continue
            imp = implied_real_share(r, r_core, r_null)
            lo, hi = implied_ci(r, r_core, r_null)
            print(describe("  " + kind, r) + "   implied real {:.2f} (5-95 % {:.2f}-{:.2f})"
                  .format(imp, lo, hi))


if __name__ == "__main__":
    warnings.simplefilter("ignore")
    mode = sys.argv[1] if len(sys.argv) > 1 else "external"
    cl = tuple(float(v) for v in sys.argv[2:]) or (6.0, 8.0, 12.0, 16.0)
    if 12.0 not in cl:
        cl = cl + (12.0,)
    (run_external if mode == "external" else run_match)(cl)
