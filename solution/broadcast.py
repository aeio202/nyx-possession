"""Broadcast synchronisation pilot (time-boxed; see STATUS.md).

The broadcast recording has its own ATD on its own timeline (cuts, replays, close-ups) and no
mapping to the tactical video is provided. A live TV feed runs in real time, so between replays
the mapping should be one constant frame offset. Step 1 tests that: the ball's pitch position is
compared between the two tracks over a range of lags, in windows of the broadcast timeline, and
the best lag per window is reported.

    python solution/broadcast.py align      # best lag per 5-minute window (seconds)
    python solution/broadcast.py refine     # the same, to the frame
    python solution/broadcast.py coverage   # what the aligned broadcast adds on live frames

Prints aggregates only (best lag per window, match error); no frame-level values.
"""
import os
import sys
import warnings

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from games import GAME, GAMES, require, source_frames  # noqa: E402
from solution.load import CACHE_DIR, _parse, _team_of_slots, load_atd  # noqa: E402

FPS = 25


def load_broadcast(game=GAME, refresh=False):
    """Same arrays as load.load_atd, for the broadcast recording (cached, gitignored)."""
    cache = os.path.join(CACHE_DIR, "{}_broadcast_atd.npz".format(game))
    if os.path.exists(cache) and not refresh:
        z = np.load(cache)
        return {k: z[k] for k in z.files}
    meta_path, raw_path = require(["atd_meta", "atd_raw"], game, None, source="broadcast")
    team = _team_of_slots(meta_path)
    n = source_frames("broadcast", game)
    ball, pos, spd = _parse(raw_path, n, len(team), GAMES[game]["pitch"])
    os.makedirs(CACHE_DIR, exist_ok=True)
    np.savez_compressed(cache, ball=ball, pos=pos, spd=spd, team=team)
    return {"ball": ball, "pos": pos, "spd": spd, "team": team}


def per_second(xy):
    """(n_seconds, 2) mean position per second; NaN where fewer than half the frames are seen."""
    n = len(xy) // FPS
    blocks = xy[:n * FPS].reshape(n, FPS, -1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mean = np.nanmean(blocks, axis=1)
    seen = (~np.isnan(blocks[..., 0])).sum(axis=1) >= FPS // 2
    mean[~seen] = np.nan
    return mean


def window_lags(b_sec, t_sec, window=300, min_overlap=60):
    """For each `window`-second block of the broadcast: the tactical lag (seconds) minimising the
    median ball distance, that median distance, the second-best lag's distance (from a lag at
    least 30 s away), and the number of overlapping seconds."""
    nt = len(t_sec)
    out = []
    for a in range(0, len(b_sec) - window + 1, window):
        blk = b_sec[a:a + window]
        if (~np.isnan(blk[:, 0])).sum() < min_overlap:
            out.append((a, np.nan, np.nan, np.nan, 0))
            continue
        best = []
        for lag in range(-a, nt - a - window + 1):
            tb = t_sec[a + lag:a + lag + window]
            d = np.linalg.norm(blk - tb, axis=1)
            ok = ~np.isnan(d)
            if ok.sum() >= min_overlap:
                best.append((np.median(d[ok]), lag, ok.sum()))
        best.sort()
        d0, lag0, n0 = best[0]
        d1 = next((d for d, lag, _ in best if abs(lag - lag0) >= 30), np.nan)
        out.append((a, lag0, d0, d1, n0))
    return out


def align():
    tac = load_atd(GAME)
    bro = load_broadcast(GAME)
    t_sec = per_second(tac["ball"][:, :2])
    b_sec = per_second(bro["ball"][:, :2])
    print("seconds: tactical {}, broadcast {}; ball seen (per-second) {:.2f} / {:.2f}".format(
        len(t_sec), len(b_sec), np.mean(~np.isnan(t_sec[:, 0])), np.mean(~np.isnan(b_sec[:, 0]))))
    print("{:>10}{:>10}{:>12}{:>14}{:>10}".format(
        "bcast min", "lag s", "median m", "next-best m", "overlap"))
    for a, lag, d0, d1, n0 in window_lags(b_sec, t_sec):
        print("{:>10.0f}{:>10}{:>12.2f}{:>14.2f}{:>10}".format(
            a / 60, "-" if np.isnan(lag) else int(lag), d0, d1, n0))


def refine(b_ball, t_ball, coarse_s, a, b, span=50):
    """Best frame lag near coarse_s * FPS for broadcast frames a..b: (lag, median distance m,
    frames compared). Frame-level ball positions; both tracks must see the ball."""
    best = None
    nt = len(t_ball)
    for lag in range(coarse_s * FPS - span, coarse_s * FPS + span + 1):
        lo, hi = max(a, -lag), min(b, nt - lag)
        d = np.linalg.norm(b_ball[lo:hi] - t_ball[lo + lag:hi + lag], axis=1)
        ok = ~np.isnan(d)
        if ok.sum() < 500:
            continue
        m = np.median(d[ok])
        if best is None or m < best[1]:
            best = (lag, m, int(ok.sum()))
    return best


def refine_all(window_s=300):
    tac = load_atd(GAME)
    bro = load_broadcast(GAME)
    t_sec = per_second(tac["ball"][:, :2])
    b_sec = per_second(bro["ball"][:, :2])
    tb, bb = tac["ball"][:, :2], bro["ball"][:, :2]
    print("{:>10}{:>12}{:>12}{:>10}".format("bcast min", "lag frames", "median m", "frames"))
    for a, lag, d0, d1, n0 in window_lags(b_sec, t_sec, window_s):
        if np.isnan(lag):
            continue
        res = refine(bb, tb, int(lag), a * FPS, (a + window_s) * FPS)
        if res:
            print("{:>10.0f}{:>12}{:>12.2f}{:>10}".format(a / 60, *res))


# Frame offsets found by `refine` (broadcast frame = tactical frame - lag), constant within each
# half to +/- 1 frame over 45 minutes. Analysis only: the submission does not use the broadcast
# (the pilot's fill-in evidence was tried and dropped, see README). A pipeline that did would
# have to find these by `align` + `refine` at run time, not hard-code them.
LAGS = {1: 4014, 2: 26920}


def mapped(tac_n, bro, game=GAME):
    """Broadcast arrays re-indexed on the tactical timeline (NaN outside the halves or where the
    broadcast has no frame)."""
    from games import half_video_blocks
    ball = np.full((tac_n, 2), np.nan, dtype=np.float32)
    pos = np.full((tac_n, bro["pos"].shape[1], 2), np.nan, dtype=np.float32)
    nb = len(bro["ball"])
    for half, first, last in half_video_blocks(game):
        t = np.arange(first, last + 1)
        b = t - LAGS[half]
        ok = (b >= 0) & (b < nb)
        ball[t[ok]] = bro["ball"][b[ok], :2]
        pos[t[ok]] = bro["pos"][b[ok]]
    return ball, pos


def live_consistent(t_pos, t_team, b_pos, b_team, tol=1.5, min_players=6):
    """Per tactical frame: the mapped broadcast frame shows the live picture -- at least
    `min_players` broadcast players, whose median distance to the nearest tactical player of the
    same team is under `tol` m. Replays, close-ups and crowd shots fail."""
    n = len(t_pos)
    out = np.zeros(n, dtype=bool)
    chunk = 5000
    for a in range(0, n, chunk):
        sl = slice(a, min(n, a + chunk))
        meds = np.full(sl.stop - sl.start, np.inf)
        cnt = np.zeros(sl.stop - sl.start, dtype=int)
        dists = []
        for side in (0, 1):
            bp = b_pos[sl][:, b_team == side]
            tp = t_pos[sl][:, t_team == side]
            d = np.linalg.norm(bp[:, :, None, :] - tp[:, None, :, :], axis=3)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                dists.append(np.nanmin(d, axis=2))
        d = np.concatenate(dists, axis=1)
        cnt = (~np.isnan(d)).sum(axis=1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            meds = np.nanmedian(d, axis=1)
        out[sl] = (cnt >= min_players) & (meds < tol)
    return out


def second_view(tac, game=GAME):
    """Control evidence (home - away, in [-1, 1]) from the broadcast, on the tactical timeline,
    zero where the mapped broadcast frame is not live-consistent or has no ball."""
    from solution import features as F
    from solution.model import PARAMS as p
    bro = load_broadcast(game)
    n = len(tac["ball"])
    b_ball, b_pos = mapped(n, bro, game)
    live = live_consistent(tac["pos"], tac["team"], b_pos, bro["team"])
    b3 = np.full((n, 3), np.nan, dtype=np.float32)
    b3[:, :2] = np.where(live[:, None], b_ball, np.nan)
    pos = np.where(live[:, None, None], b_pos, np.nan)
    bxy, present, bvel, _, _ = F.ball_features(b3)
    c = F.team_control(pos, F.player_velocities(pos), bro["team"], bxy, bvel, p["control_radius"],
                       p["control_softness"], p["control_gate"], p["control_gate_softness"])
    return np.where(present & live, c[:, 0] - c[:, 1], 0.0)


def coverage():
    """What the aligned broadcast adds on graded live frames (decoded H or A). Aggregates only."""
    from games import half_video_blocks
    from solution import features as F
    from solution.model import PARAMS as p
    tac = load_atd(GAME)
    bro = load_broadcast(GAME)
    n = len(tac["ball"])
    b_ball, b_pos = mapped(n, bro)
    live = live_consistent(tac["pos"], tac["team"], b_pos, bro["team"])
    sub = np.loadtxt(os.path.join(HERE, "output", "submission.csv"), delimiter=",",
                     skiprows=1, dtype=str)[:, 1]
    graded = np.zeros(n, dtype=bool)
    for _, first, last in half_video_blocks(GAME):
        graded[first:last + 1] = True
    alive = graded & np.isin(sub, ["H", "A"])
    t_seen = ~np.isnan(tac["ball"][:, 0])
    b_seen = ~np.isnan(b_ball[:, 0]) & live
    print("graded live frames {}; broadcast frame live-consistent on {:.3f}".format(
        alive.sum(), live[alive].mean()))
    print("tactical ball seen {:.3f}; broadcast ball seen (consistent frames) {:.3f}".format(
        t_seen[alive].mean(), b_seen[alive].mean()))
    print("tactical ball missing: {:.3f} of live frames; broadcast sees it on {:.3f} of those".format(
        (~t_seen[alive]).mean(), b_seen[alive & ~t_seen].mean()))
    both = alive & t_seen & b_seen
    d = np.linalg.norm(tac["ball"][both, :2] - b_ball[both], axis=1)
    print("both see the ball: {} frames, distance quartiles (m) {}".format(
        both.sum(), np.percentile(d, [25, 50, 75, 95]).round(2)))

    def control_ev(pos, team, ball_raw):
        bxy, present, bvel, _, _ = F.ball_features(ball_raw)
        c = F.team_control(pos, F.player_velocities(pos), team, bxy, bvel, p["control_radius"],
                           p["control_softness"], p["control_gate"], p["control_gate_softness"])
        return np.where(present, c[:, 0] - c[:, 1], 0.0)

    te = control_ev(tac["pos"], tac["team"], tac["ball"])
    b3 = np.full((n, 3), np.nan, dtype=np.float32)
    b3[:, :2] = np.where(live[:, None], b_ball, np.nan)
    be = control_ev(np.where(live[:, None, None], b_pos, np.nan), bro["team"], b3)
    dec = np.where(sub == "H", 1, np.where(sub == "A", -1, 0))
    strong = 0.3
    tb = alive & (np.abs(te) >= strong) & (np.abs(be) >= strong)
    print("both strong control evidence: {} frames, same sign {:.3f}".format(
        tb.sum(), (np.sign(te[tb]) == np.sign(be[tb])).mean()))
    only_b = alive & (np.abs(te) < p["evidence_floor"]) & (np.abs(be) >= strong)
    only_t = alive & (np.abs(te) >= strong) & (np.abs(be) < p["evidence_floor"]) & live
    print("broadcast strong where tactical has none: {} frames ({:.3f} of live); agrees with the"
          " decoded team {:.3f}".format(only_b.sum(), only_b.sum() / alive.sum(),
                                        (np.sign(be[only_b]) == dec[only_b]).mean()))
    print("tactical strong where broadcast (live) has none: {} frames".format(only_t.sum()))
    sel = alive & (np.abs(te) >= strong)
    print("tactical strong evidence agrees with the decoded team {:.3f}".format(
        (np.sign(te[sel]) == dec[sel]).mean()))
    return dict(live=live, te=te, be=be, alive=alive, dec=dec)


if __name__ == "__main__":
    warnings.simplefilter("ignore")
    if len(sys.argv) > 1 and sys.argv[1] == "coverage":
        coverage()
    elif len(sys.argv) > 1 and sys.argv[1] == "align":
        align()
    elif len(sys.argv) > 1 and sys.argv[1] == "refine":
        refine_all()
    else:
        print(__doc__)
