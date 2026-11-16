"""Degrade a clean sample match so that it resembles the competition's automatic tracking.

The sample matches have a complete, identified, unsmoothed tracking; the competition ATD does
not. Each degradation below mirrors a property measured on the unlabelled target data:

  ball smoothing     a strike appears as a speed ramp of about one second
  ball gaps          the ball is lost in long stretches only; about 7 % of live frames, and the
                     loss starts before / ends after the stoppage rather than exactly at it
  ball in stoppages  the target tracks the ball on roughly a quarter of dead frames: a ball
                     rolling on after play stops, or placed and waiting for the restart
  player gaps        about 20.5 of 22 players tracked on average, in tracklets
  set-piece tags     an automatic tag for about 60 % of restarts, opening 2-8 s before them

Everything is driven by a seeded generator, so a variant is reproducible.
"""
import numpy as np

FPS = 25
D = 2


def _runs(mask):
    edges = np.flatnonzero(np.diff(np.r_[0, mask.astype(np.int8), 0]))
    return list(zip(edges[::2], edges[1::2]))


def _smooth_segments(xy, width):
    """Triangular moving average of `width` frames inside each contiguous seen segment."""
    if width <= 1:
        return xy
    out = xy.copy()
    half = np.ones(max(width // 2, 1))
    kernel = np.convolve(half, half)
    kernel /= kernel.sum()
    pad = len(kernel) // 2
    for a, b in _runs(~np.isnan(xy[:, 0])):
        if b - a < 3:
            continue
        for c in (0, 1):
            seg = np.pad(xy[a:b, c], pad, mode="edge")
            out[a:b, c] = np.convolve(seg, kernel, "valid")[:b - a]
    return out


def interpolate_between(ball, anchors):
    """The target's ball is drawn as straight lines between contacts. Replace the path between
    consecutive anchor frames by the straight line joining the positions at those frames, where
    the ball is seen at both and throughout."""
    out = ball.copy()
    seen = ~np.isnan(ball[:, 0])
    blank_before = np.cumsum(~seen)
    for a, b in zip(anchors[:-1], anchors[1:]):
        if b - a < 2 or not (seen[a] and seen[b]) or blank_before[b] - blank_before[a] > 0:
            continue
        w = np.linspace(0.0, 1.0, b - a + 1)[:, None]
        out[a:b + 1] = (1 - w) * ball[a] + w * ball[b]
    return out


def corrupt(game, seed=0, smooth=25, live_missing=0.07, dead_seen=True, player_missing=0.07,
            tag_share=0.6, anchors=None):
    """Return (arrays like load_atd, tags like load_tags) for a degraded copy of `game`.

    `anchors`: sorted contact frames; if given, the ball is first redrawn as straight lines
    between them (interpolate_between), as on the target."""
    rng = np.random.default_rng(seed)
    labels = game["labels"]
    n = len(labels)
    ball = game["ball"][:, :2].astype(np.float64).copy()
    if anchors is not None:
        ball = interpolate_between(ball, np.asarray(anchors, dtype=np.int64))
    dead = labels == D

    # --- the ball during stoppages -----------------------------------------------------------
    if dead_seen:
        for a, b in _runs(dead):
            if b >= n or a < 2 or np.isnan(ball[b, 0]) or np.isnan(ball[a - 1, 0]):
                continue
            # rolling on after play stops: carry the last velocity, decaying, for 0.5-2 s
            if rng.random() < 0.4 and not np.isnan(ball[a - 2, 0]):
                k = min(int(rng.uniform(0.5, 2.0) * FPS), b - a)
                v = ball[a - 1] - ball[a - 2]
                steps = np.cumsum(0.95 ** np.arange(1, k + 1))
                ball[a:a + k] = ball[a - 1] + steps[:, None] * v
            # placed and waiting: at the restart position for the last 2-10 s
            if rng.random() < 0.5:
                k = min(int(rng.uniform(2.0, 10.0) * FPS), b - a)
                ball[b - k:b] = ball[b]

    # --- losing the ball ---------------------------------------------------------------------
    lost = np.zeros(n, dtype=bool)
    for a, b in _runs(dead):
        if rng.random() < 0.6:                       # lost shortly before play stops
            lost[max(a - int(rng.uniform(0.0, 2.0) * FPS), 0):a] = True
        if rng.random() < 0.5:                       # found shortly after the restart
            lost[b:min(b + int(rng.uniform(0.0, 1.5) * FPS), n)] = True
    live = np.flatnonzero(~dead)
    target = live_missing * len(live)
    guard = 0
    while lost[live].sum() < target and guard < 10000:
        guard += 1
        start = int(rng.choice(live))
        lost[start:start + int((3.0 + rng.exponential(4.0)) * FPS)] = True
    ball[lost & ~dead] = np.nan

    ball = _smooth_segments(ball, smooth)
    ball3 = np.full((n, 3), np.nan, dtype=np.float32)
    ball3[:, :2] = ball

    # --- losing players ----------------------------------------------------------------------
    pos = game["pos"].copy()
    spd = game["spd"].copy()
    slots = pos.shape[1]
    on_pitch = ~np.isnan(pos[..., 0])
    want = player_missing * on_pitch.sum()
    gone = np.zeros(on_pitch.shape, dtype=bool)
    guard = 0
    while (gone & on_pitch).sum() < want and guard < 100000:
        guard += 1
        s = int(rng.integers(slots))
        start = int(rng.integers(n))
        gone[start:start + int(rng.uniform(5.0, 20.0) * FPS), s] = True
    pos[gone] = np.nan
    spd[gone] = np.nan

    # --- automatic-looking set-piece tags ----------------------------------------------------
    tags = []
    kickoff_names = {0: "1st Half", 1: "2nd Half"}
    period_starts = [int(a) for a, _ in game["periods"]]
    # Team of the tag: as on the target, only corners, goal kicks and free kicks carry one, and an
    # automatic tag can be wrong (10 %, a round prior). A separate generator, so that adding the
    # team leaves every other degradation exactly as before.
    team_rng = np.random.default_rng(seed + 1000)
    for frame, subtype, team in game["set_pieces"]:
        frame = int(frame)
        half = int(np.searchsorted(period_starts, frame, side="right") - 1)
        opening = frame in period_starts or frame - 1 in period_starts
        if opening:
            start, length, kind = frame - int(3.4 * FPS), 5 * FPS, "Kick Off (Start)"
        elif rng.random() < tag_share:
            start, length, kind = frame - int(rng.uniform(2.0, 8.0) * FPS), 35 * FPS, str(subtype).title()
        else:
            continue
        side = "N/A"
        if kind.lower().startswith(("corner", "goal", "free")):
            wrong = team_rng.random() < 0.1
            side = "Home" if (int(team) == 0) != wrong else "Away"
        tags.append({"code": "SET PIECES", "start_frame": start, "end_frame": start + length,
                     "start_s": start / FPS, "end_s": (start + length) / FPS,
                     "tags": {"Type": kind, "Half": kickoff_names.get(half, "1st Half"),
                              "Team": side}})
    atd = {"ball": ball3, "pos": pos, "spd": spd, "team": game["team"]}
    return atd, tags
