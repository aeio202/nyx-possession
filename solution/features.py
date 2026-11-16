"""Per-frame evidence computed from the tactical ATD and the Smart Tagging.

Everything here is a deterministic function of the provided automatic data. Nothing is fitted to
any ground truth; every constant is a physical or football prior (metres, seconds, m/s).
"""

import numpy as np

FPS = 25


# ----------------------------------------------------------------------------------------------
# small numeric helpers
# ----------------------------------------------------------------------------------------------
def nan_smooth(x, width):
    """Centred moving average of width `width` frames that ignores NaN (NaN where all are NaN)."""
    valid = ~np.isnan(x)
    k = np.ones(int(width))
    num = np.convolve(np.where(valid, x, 0.0), k, "same")
    den = np.convolve(valid.astype(float), k, "same")
    out = np.full(len(x), np.nan)
    ok = den > 0
    out[ok] = num[ok] / den[ok]
    return out


def run_lengths(mask):
    """For each frame, the length of the run of equal `mask` values it belongs to."""
    n = len(mask)
    out = np.zeros(n, dtype=np.int64)
    if n == 0:
        return out
    change = np.flatnonzero(np.diff(mask.astype(np.int8))) + 1
    starts = np.r_[0, change]
    stops = np.r_[change, n]
    for a, b in zip(starts, stops):
        out[a:b] = b - a
    return out


def interpolate_short_gaps(values, max_gap):
    """Linear interpolation across NaN gaps of at most `max_gap` frames, per column."""
    out = values.copy()
    missing = np.isnan(out[:, 0])
    lengths = run_lengths(missing)
    fill = missing & (lengths <= max_gap)
    idx = np.arange(len(out))
    good = ~missing
    if good.sum() < 2:
        return out
    for c in range(out.shape[1]):
        out[fill, c] = np.interp(idx[fill], idx[good], out[good, c])
    # interpolation must not extrapolate past the first / last observation
    first, last = idx[good][0], idx[good][-1]
    out[:first] = np.nan
    out[last + 1:] = np.nan
    return out


# ----------------------------------------------------------------------------------------------
# features
# ----------------------------------------------------------------------------------------------
# A ball hidden for up to half a second is almost always occluded by the player on it (a dribble,
# a body in front of the camera). Bridging that is physically safe; longer gaps are not.
BALL_GAP_FILL = 12  # frames


def ball_features(ball_raw):
    """Interpolated ball position, velocity (m/s), speed, and the length of the gap a frame is in.

    `missing_run` is 0 where the ball is seen and otherwise the total length (frames) of the
    unseen stretch the frame belongs to.
    """
    xy = interpolate_short_gaps(ball_raw[:, :2].astype(np.float64), BALL_GAP_FILL)
    present = ~np.isnan(xy[:, 0])
    vx = np.gradient(nan_smooth(xy[:, 0], 5)) * FPS
    vy = np.gradient(nan_smooth(xy[:, 1], 5)) * FPS
    velocity = np.stack([vx, vy], axis=1)
    velocity[~present] = np.nan
    speed = np.hypot(vx, vy)
    speed[~present] = np.nan
    missing_run = np.where(present, 0, run_lengths(present))
    return xy, present, velocity, speed, missing_run


def player_velocities(pos, step=2):
    """Velocity vectors (m/s) per track slot from positions, by a centred difference over
    +/- `step` frames. NaN at the edges of a tracklet, where no difference exists."""
    vel = np.full(pos.shape, np.nan, dtype=np.float32)
    vel[step:-step] = (pos[2 * step:] - pos[:-2 * step]) * (FPS / (2.0 * step))
    return vel


def team_control(pos, vel, team, ball_xy, ball_vel, radius, softness, gate, gate_softness):
    """Per-frame control score in [0, 1] for home and for away.

    A player controls the ball when it is close to them AND moving with them: the score is
    (closeness) x (low ball velocity relative to that player), taken for the best player of each
    team. A pass travelling past an opponent is
    close but has a large relative velocity and scores nothing; a dribble, a reception or a ball
    held still scores fully. Where a player's velocity is unknown (tracklet edge) the player is
    taken as standing.
    """
    n = len(pos)
    control = np.zeros((n, 2))
    b_xy = ball_xy.astype(np.float32)
    b_v = ball_vel.astype(np.float32)
    chunk = 20000
    for a in range(0, n, chunk):
        sl = slice(a, min(n, a + chunk))
        d = np.linalg.norm(pos[sl] - b_xy[sl, None, :], axis=2)
        v = np.where(np.isnan(vel[sl]), 0.0, vel[sl])
        rel = np.linalg.norm(v - b_v[sl, None, :], axis=2)
        with np.errstate(over="ignore", invalid="ignore"):
            c = (1.0 / (1.0 + np.exp((d - radius) / softness))
                 / (1.0 + np.exp((rel - gate) / gate_softness)))
        c = np.where(np.isnan(c), 0.0, c)
        for side in (0, 1):
            control[sl, side] = c[:, team == side].max(axis=1)
    return control


def touch_events(ball_vel, present, span, min_change):
    """Frames where the ball's velocity changes sharply: somebody played it.

    The change is measured across +/- `span` frames (the ball track is smoothed, so a touch is
    spread over several frames) as |v(t + span) - v(t - span)|, direction included: a first-time
    pass that redirects the ball at constant speed counts as much as a strike from rest. An event
    is a local maximum of that change above `min_change` m/s.
    """
    n = len(ball_vel)
    change = np.full(n, np.nan)
    change[span:n - span] = np.linalg.norm(ball_vel[2 * span:] - ball_vel[:n - 2 * span], axis=1)
    seen = np.convolve(present.astype(float), np.ones(2 * span + 1), "same") > 2 * span + 0.5
    change = np.where(seen, change, np.nan)
    peak = _window_stat(change, -span, 2 * span + 1, np.nanmax)
    with np.errstate(invalid="ignore"):
        is_peak = (change >= peak) & (change > min_change)
    return np.flatnonzero(onset(np.nan_to_num(is_peak).astype(bool))), np.nan_to_num(change)


def touch_evidence(events, d_home, d_away, n, radius, margin, spread=2):
    """Per-frame team evidence from touches: +1 (home) or -1 (away) in total per touch, spread
    over 2 * `spread` + 1 frames, when a player of one team is within `radius` metres of the ball
    at the touch and at least `margin` metres nearer than the nearest opponent. A touch between
    two players equally close (a duel) is credited to nobody."""
    out = np.zeros(n)
    share = 1.0 / (2 * spread + 1)
    for t in events:
        a, b = max(t - 2, 0), min(t + 3, n)
        with np.errstate(all="ignore"):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                dh, da = np.nanmin(d_home[a:b]), np.nanmin(d_away[a:b])
        if np.isnan(dh) and np.isnan(da):
            continue
        dh = np.inf if np.isnan(dh) else dh
        da = np.inf if np.isnan(da) else da
        if min(dh, da) > radius or abs(dh - da) < margin:
            continue
        out[max(t - spread, 0):min(t + spread + 1, n)] += share if dh < da else -share
    return out


def touch_sides(events, d_home, d_away, radius, margin):
    """Per touch: +1 if a home player is within `radius` of the ball and at least `margin` nearer
    than the nearest away player, -1 for the reverse, 0 if nobody clearly played it."""
    import warnings
    n = len(d_home)
    sides = np.zeros(len(events), dtype=np.int8)
    for i, t in enumerate(events):
        a, b = max(t - 2, 0), min(t + 3, n)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            dh, da = np.nanmin(d_home[a:b]), np.nanmin(d_away[a:b])
        dh = np.inf if np.isnan(dh) else dh
        da = np.inf if np.isnan(da) else da
        if min(dh, da) <= radius and abs(dh - da) >= margin:
            sides[i] = 1 if dh < da else -1
    return sides


def pass_evidence(events, sides, n, max_gap):
    """Per-frame team evidence from completed passes: two consecutive touches credited to the
    same team no more than `max_gap` frames apart. The evidence totals +1 (home) or -1 (away)
    per pass, spread evenly from the first touch to the second -- the ball is that team's while
    it travels between them. A lone touch by the other team (a deflection, a failed
    interception) is credited nothing, as the definition requires."""
    out = np.zeros(n)
    for i in range(len(events) - 1):
        a, b = events[i], events[i + 1]
        if sides[i] != 0 and sides[i] == sides[i + 1] and 0 < b - a <= max_gap:
            out[a:b + 1] += sides[i] / float(b - a + 1)
    return out


def reception_evidence(events, sides, control, n, delay, window, hold, level=0.5):
    """Per-frame team evidence from a touch that the same team then holds: a touch credited to
    team k (`sides`), followed between `delay` and `window` frames later by at least `hold`
    frames on which k's control score exceeds `level`. +1 (home) / -1 (away) in total per such
    touch, spread from the touch to the end of the window. A lone touch is not possession; a
    touch after which the team keeps the ball is the definition's "gains controlled
    possession", and it credits the interception itself, which control never sees."""
    out = np.zeros(n)
    for t, side in zip(events, sides):
        if side == 0:
            continue
        col = 0 if side > 0 else 1
        a, b = t + delay, min(t + window, n)
        if a < b and (control[a:b, col] > level).sum() >= hold:
            out[t:b] += side / float(b - t)
    return out


def team_distances(pos, team, ball_xy):
    """Distance (m) from the ball to the nearest home and nearest away tracked player."""
    import warnings
    d = np.linalg.norm(pos - ball_xy[:, None, :].astype(np.float32), axis=2)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        d_home = np.nanmin(np.where(team[None, :] == 0, d, np.nan), axis=1)
        d_away = np.nanmin(np.where(team[None, :] == 1, d, np.nan), axis=1)
    return d_home.astype(np.float64), d_away.astype(np.float64)


def collective_speed(spd, width=3 * FPS):
    """Mean speed of all tracked players, smoothed over 3 s. Players walk during stoppages."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mean = np.nanmean(spd, axis=1)
    return nan_smooth(mean.astype(np.float64), width)


def collective_deceleration(spd, horizon=2 * FPS):
    """How much the mean player speed (1 s smoothed) drops over the next `horizon` frames (m/s,
    positive = slowing). Twenty-two players slowing together is what a whistle looks like."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mean = np.nanmean(spd, axis=1)
    ms = nan_smooth(mean.astype(np.float64), FPS)
    future = np.r_[ms[horizon:], np.full(horizon, np.nan)]
    return np.nan_to_num(ms - future)


def out_of_pitch(ball_xy, pitch, margin=1.0):
    """Ball clearly beyond a touchline or goal line (margin in metres absorbs tracking noise)."""
    length, width = pitch
    x, y = ball_xy[:, 0], ball_xy[:, 1]
    with np.errstate(invalid="ignore"):
        return (x < -margin) | (x > length + margin) | (y < -margin) | (y > width + margin)


def _window_stat(x, offset, length, fn):
    """fn over x[t+offset : t+offset+length] for every t (NaN-aware, NaN outside the array)."""
    import warnings
    from numpy.lib.stride_tricks import sliding_window_view
    n = len(x)
    pad = abs(offset) + length + 1
    ext = np.r_[np.full(pad, np.nan), x, np.full(pad, np.nan)]
    win = sliding_window_view(ext, length)[pad + offset:pad + offset + n]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return fn(win, axis=1)


# The automatic ball track is heavily smoothed: a pass that leaves the foot at 15 m/s shows up as
# a ramp over roughly a second (see the technical document). Strike detectors therefore compare
# the speed now with the peak over the following second, instead of looking for a jump.
RISE_WINDOW = FPS  # frames


def kick_strength(ball_speed, present, before=15):
    """0..1 per frame: how much frame t looks like a restart -- a resting or unseen ball struck.

    Resting = median speed over the previous `before` frames (unseen counts as resting: a ball in
    hands or behind a wall). Struck = peak speed over the next second. A kick-off tap or a short
    free kick peaks around 6 m/s; full strength at ~7 m/s above rest.
    """
    sp = np.where(present, ball_speed, np.nan)
    prev = _window_stat(sp, -before, before, np.nanmedian)
    prev = np.where(np.isnan(prev), 0.0, prev)
    peak = _window_stat(sp, 0, RISE_WINDOW, np.nanmax)
    gain = (peak - np.maximum(prev, 1.5) - 2.0) / 3.5
    gain = np.where(np.isnan(gain), 0.0, gain)
    # Localise the strike where the speed ramp starts: a local speed minimum, or the first frame
    # the ball is seen again (a throw-in, a ball emerging from a wall). Without this the peak
    # look-ahead flags every frame of the second before the kick.
    local_min = _window_stat(sp, -5, 11, np.nanmin)
    with np.errstate(invalid="ignore"):
        start = (sp <= local_min) | (present & ~np.r_[False, present[:-1]])
    return np.where(start, np.clip(gain, 0.0, 1.0), 0.0)


def restart_support(kick, strikes, quiet=2 * FPS, hold=4 * FPS, follow=5 * FPS, min_kick=0.5):
    """1 on the `hold` frames after a restart: a strike of a resting ball after `quiet` frames
    without any strike, followed by at least one more strike within `follow` frames (play goes
    on; a ball merely passed to the taker during a stoppage is then placed and left still).
    A slow build-up after a restart looks stoppage-like (walking players, few passes); this is
    the evidence that play has resumed."""
    n = len(kick)
    strike_count = np.r_[0, np.cumsum(strikes.astype(np.int64))]
    idx = np.arange(n)
    before = strike_count[idx] - strike_count[np.maximum(idx - quiet, 0)]
    # strikes in (t + 5, t + follow]: skip the restart's own ramp
    after = (strike_count[np.minimum(idx + follow + 1, n)]
             - strike_count[np.minimum(idx + 6, n)])
    restarts = np.flatnonzero((kick >= min_kick) & (before == 0) & (after > 0))
    out = np.zeros(n)
    for r in restarts:
        out[r:r + hold] = 1.0
    return out


def strike_events(ball_speed, present, min_rise=5.0):
    """Frames where a strike starts: a local speed minimum followed by a rise of > `min_rise` m/s
    within the next second. Catches one-touch passes too (they start from a moving ball)."""
    sp = np.where(present, ball_speed, np.nan)
    local_min = _window_stat(sp, -5, 11, np.nanmin)
    peak = _window_stat(sp, 0, RISE_WINDOW, np.nanmax)
    with np.errstate(invalid="ignore"):
        ev = (sp <= local_min) & (peak - sp > min_rise)
    return onset(np.nan_to_num(ev).astype(bool))


def strike_gap(strikes, travel=FPS):
    """Per frame: (length in seconds of the interval between the two consecutive strikes the
    frame lies in, whether the frame is past the last strike's travel time, seconds since the
    last strike).

    Live play strikes the ball every 2-3 s; a stoppage is one long interval without a strike.
    Measuring the interval a frame lies in -- rather than counting strikes in a window around
    it -- keeps the boundaries sharp: the quiet starts at the last strike and ends at the next.
    The first `travel` frames after a strike are that pass still on its way, not yet quiet.
    """
    n = len(strikes)
    idx = np.arange(n)
    at = np.flatnonzero(strikes)
    if len(at) == 0:
        return np.full(n, n / FPS), np.ones(n, dtype=bool), np.full(n, n / FPS)
    k = np.searchsorted(at, idx, side="right")          # strikes at or before each frame
    prev = np.where(k > 0, at[np.maximum(k - 1, 0)], -10 * n)
    nxt = np.where(k < len(at), at[np.minimum(k, len(at) - 1)], 10 * n)
    return (nxt - prev) / FPS, (idx - prev) >= travel, (idx - prev) / FPS


def onset(mask):
    """True on the first frame of every run of True in `mask`."""
    return mask & ~np.r_[False, mask[:-1]]


def set_piece_mask(tags, n_frames, before=3 * FPS, after=3 * FPS):
    """Frames around the START of a Smart Tagging SET PIECES interval.

    A tagged interval is 35 s long (5 s for a kick-off) and opens a few seconds before the
    restart -- 3.3 s and 3.5 s before the two kick-offs whose frames DATA.md / FAQ.md publish --
    so most of it is the live play that follows. Only the frames around its start are likely
    to be the stoppage itself.
    """
    mask = np.zeros(n_frames, dtype=bool)
    for e in tags:
        if (e["code"] or "").strip().lower() == "set pieces":
            a = max(0, e["start_frame"] - before)
            b = min(n_frames, e["start_frame"] + after)
            if b > a:                      # a tag opening before frame 0 must not wrap around
                mask[a:b] = True
    return mask


def kickoff_frames(tags):
    """{half_name: start frame of the 'Kick Off (Start)' set piece}, from the Smart Tagging."""
    out = {}
    for e in tags:
        if ((e["code"] or "").strip().lower() == "set pieces"
                and (e["tags"].get("Type") or "").strip().lower() == "kick off (start)"):
            out[e["tags"].get("Half")] = e["start_frame"]
    return out
