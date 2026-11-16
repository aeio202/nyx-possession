"""Three-state possession model (H / A / D) decoded with Viterbi.

Each frame gets a score per state (log-odds style, larger = more plausible). A path through the
match pays a fixed cost every time it changes state. Viterbi returns the path with the highest
total score. The transition costs are what turns flickering per-frame evidence into possessions:
a team change has to be supported by enough accumulated evidence to pay for itself.

All constants are round-number priors in football / physical units. None was fitted or searched
against a ground truth; how the public window was and was not used is in the technical document.
"""

import numpy as np

from . import features as F

H, A, D = 0, 1, 2
LETTERS = np.array(["H", "A", "D"])

PARAMS = {
    # --- team evidence ---------------------------------------------------------------------
    # The definition asks for *controlled* possession. A player controls the ball when it is
    # within playing distance AND moving with them (see features.team_control). Evidence per
    # frame is control(home) - control(away), in [-1, 1].
    "control_radius": 2.0,       # m, midpoint of the closeness weight
    "control_softness": 0.6,     # m, how sharply closeness falls off
    # Ball velocity relative to the player. A dribbled or received ball stays within a few m/s
    # of the player; a pass going past them differs by the pass speed (8-20 m/s).
    "control_gate": 4.0,         # m/s, midpoint
    "control_gate_softness": 1.0,
    "evidence_floor": 0.02,      # smaller evidence is treated as none (a loose ball)
    # Touches. Control needs the ball to travel with a player, which an interception, a
    # clearance, a header or a first-time pass never shows: on labelled other matches about half
    # of the possessions under 4 s produced no control evidence at all. A sharp change of the
    # ball's velocity means somebody played it; the clearly nearest player's team is credited.
    "touch_change": 6.0,         # m/s change of ball velocity across +/- touch_span
    "touch_span": 0.3,           # s
    "touch_radius": 3.0,         # m; the smoothed ball track cuts the corner at a touch
    "touch_margin": 1.0,         # m nearer than the nearest opponent
    # Evidence per single touch, in the units of one frame of full control. OFF. On labelled
    # other matches a weight of 3 gains about 0.02 spellF1 where every brief possession is
    # labelled and nothing where it is not, and the definition does not count a simple touch or
    # a deflection. Kept for the calibration harness; completed passes (below) are used instead.
    "touch_weight": 0.0,
    # Completed passes: two consecutive touches credited to the same team. Evidence per pass,
    # spread over its duration.
    "pass_weight": 8.0,
    "pass_max_gap": 5.0,         # s between the two touches
    # Receptions held: a touch credited to a team, after which that team holds the ball (control
    # above 0.5 on at least 0.5 s within 0.2-2 s), adds evidence per touch over that span. The
    # definition's "gains controlled possession"; it credits the interception itself, which
    # control never sees. Same weight as a completed pass, not swept. On labelled other matches
    # +0.001 to +0.010 spellF1 under all five labellings, including the hold-out match.
    "reception_weight": 8.0,
    # Restart owner: the team named by a set-piece tag (corners, goal kicks, free kicks) has the
    # ball at the matching decoded restart until the other team gains control (restart_owner).
    # On labelled other matches +0.001 to +0.005 spellF1 under the labellings, all three matches.
    "restart_owner": 1,
    # --- dead-ball evidence (per-frame log-odds dead vs alive) ------------------------------
    # Deliberately small per frame: at 25 fps a 0.1 score is 2.5 per second, so a stoppage is
    # decided by its boundary events (ball out, restart kick -- see the transition costs) and
    # by several seconds of consistent evidence, never by a few frames.
    "dead_prior": 0.0,
    "out_bonus": 1.0,            # ball beyond a line: unambiguous
    "walk_speed": 1.4,           # m/s collective speed; below it play is likely stopped
    "walk_gain": 0.3,
    # Players react to the game state: they need about 2 s to slow down after a whistle and to
    # get moving after a restart. The speed 2 s ahead is read as evidence about the state now.
    "walk_lead": 2.0,            # s
    "walk_clip": 0.15,
    "missing_onset": 3.0,        # s; ball unseen longer than this suggests a stoppage
    "missing_bonus": 0.1,
    "set_piece_bonus": 0.2,      # within 3 s of the start of an automatic SET PIECES interval
    "unattended_dist": 8.0,      # m; ball resting with nobody near
    "unattended_speed": 3.0,     # m/s
    "unattended_bonus": 0.05,
    "fast_ball_speed": 10.0,     # m/s; passes and shots are what live play looks like
    "fast_ball_malus": 0.05,
    # Interval between consecutive ball strikes that the frame lies in: live play strikes the
    # ball every 2-3 s, a stoppage is one long interval without a strike.
    "quiet_gap": 6.0,            # s; a longer interval, with the ball in view and at rest,
    "quiet_bonus": 0.1,          #    is stoppage-like
    "rest_speed": 2.0,           # m/s; below this the ball is resting or drifting
    # A ball travelling under a player's control at running pace is a dribble or a carry: play.
    # (A carry shows no strikes, so without this it would look like a quiet ball.)
    "carry_speed": 2.5,          # m/s
    "carry_control": 0.5,        # control score of the carrying player
    "carry_malus": 0.1,
    "busy_gap": 3.0,             # s; at or below this the full malus applies, fading out
    "busy_malus": 0.1,           #    linearly up to quiet_gap (slow build-up still strikes)
    "strike_halo": 2.0,          # s after any strike the ball is travelling: full malus too
    # For 4 s after a restart (strike of a resting ball after 2 s without strikes): enough to
    # outweigh walking players and a quiet ball (~0.25 per frame) during a slow build-up.
    "restart_support": 0.3,
    # --- transition costs -----------------------------------------------------------------
    # H <-> A. A short possession by the other team pays this twice, so it needs about half a
    # second of sole control. Checked on labelled other matches (solution/external): the best
    # value runs from 3-4 to 8-16 depending on whether brief possessions are labelled, and 12 is
    # inside the flat region for the labelling closest to "controlled possession".
    "switch_cost": 12.0,
    # Play stops on a whistle or the ball crossing a line, and only restarts with a kick or a
    # throw. So leaving D is expensive unless the ball is being struck, and entering D is cheaper
    # on the frame the ball goes out.
    "alive_to_dead": 25.0,
    "alive_to_dead_out": 3.0,    # on the frame the ball crosses a line
    # Whistle signature: mean player speed falling by > 1.0 m/s within 2 s (about the 5th
    # percentile of the match), fully at 2.0 m/s (beyond the 1st). Only makes the stoppage
    # boundary cheaper there; the stoppage itself still needs dead evidence.
    "alive_to_dead_whistle": 10.0,
    "whistle_decel_start": 1.0,  # m/s over 2 s
    "whistle_decel_full": 2.0,
    # The referee's whistle heard in the audio stops play. Like a line crossing, it only makes
    # the boundary cheap at that moment; the stoppage must still be supported by what follows.
    # During a stoppage it changes nothing.
    "alive_to_dead_referee": 3.0,
    "referee_lead": 0.2,         # s before the blast (the foul precedes the whistle)
    "referee_tail": 1.0,         # s after it
    "dead_to_alive": 20.0,
    "dead_to_alive_kick": 3.0,   # on a clear restart kick
}


def emissions(atd, tags, pitch, p=PARAMS, whistles=None):
    """(N, 3) per-frame state scores, plus the feature dict for inspection.

    `whistles` is the (n, 2) array of referee-whistle blasts from audio.whistles(), or None to
    decode without the audio.
    """
    n = len(atd["ball"])
    ball_xy, present, ball_vel, ball_speed, missing_run = F.ball_features(atd["ball"])
    d_home, d_away = F.team_distances(atd["pos"], atd["team"], ball_xy)
    walk = F.collective_speed(atd["spd"])
    out = F.out_of_pitch(ball_xy, pitch)
    set_piece = F.set_piece_mask(tags, n)

    # team evidence: positive favours home
    d_min = np.fmin(d_home, d_away)
    control = F.team_control(atd["pos"], F.player_velocities(atd["pos"]), atd["team"],
                             ball_xy, ball_vel, p["control_radius"], p["control_softness"],
                             p["control_gate"], p["control_gate_softness"])
    team = control[:, 0] - control[:, 1]
    team = np.where(present & ~out & (np.abs(team) >= p["evidence_floor"]), team, 0.0)
    if p["touch_weight"] > 0 or p["pass_weight"] > 0 or p.get("reception_weight", 0) > 0:
        touches, _ = F.touch_events(ball_vel, present & ~out,
                                    int(round(p["touch_span"] * F.FPS)), p["touch_change"])
        if p.get("reception_weight", 0) > 0:
            rsides = F.touch_sides(touches, d_home, d_away, p["touch_radius"], p["touch_margin"])
            team = team + p["reception_weight"] * F.reception_evidence(
                touches, rsides, control, n, delay=5, window=2 * F.FPS, hold=F.FPS // 2)
        if p["touch_weight"] > 0:
            team = team + p["touch_weight"] * F.touch_evidence(
                touches, d_home, d_away, n, p["touch_radius"], p["touch_margin"])
        if p["pass_weight"] > 0:
            sides = F.touch_sides(touches, d_home, d_away, p["touch_radius"], p["touch_margin"])
            team = team + p["pass_weight"] * F.pass_evidence(
                touches, sides, n, int(round(p["pass_max_gap"] * F.FPS)))

    # dead evidence
    dead = np.full(n, p["dead_prior"])
    dead += np.where(out, p["out_bonus"], 0.0)
    lead = int(round(p["walk_lead"] * F.FPS))
    if lead > 0:
        walk = np.r_[walk[lead:], np.full(lead, walk[-1])]
    w = np.where(np.isnan(walk), 0.0, walk)
    dead += np.clip((p["walk_speed"] - w) * p["walk_gain"], -p["walk_clip"], p["walk_clip"])
    dead += np.where(missing_run / F.FPS > p["missing_onset"], p["missing_bonus"], 0.0)
    dead += np.where(set_piece, p["set_piece_bonus"], 0.0)
    with np.errstate(invalid="ignore"):
        unattended = present & (d_min > p["unattended_dist"]) & (ball_speed < p["unattended_speed"])
        fast = present & ~out & (ball_speed > p["fast_ball_speed"])
    dead += np.where(unattended, p["unattended_bonus"], 0.0)
    dead -= np.where(fast, p["fast_ball_malus"], 0.0)
    strikes = F.strike_events(ball_speed, present)
    gap, settled, since_strike = F.strike_gap(strikes)
    # An unseen ball cannot show strikes, and already counts through the missing bonus: the
    # quiet bonus is only for a ball in view that nobody strikes.
    with np.errstate(invalid="ignore"):
        resting = present & (ball_speed < p["rest_speed"])
        carried = (present & ~out & (ball_speed >= p["carry_speed"])
                   & (control.max(axis=1) >= p["carry_control"]))
    dead += np.where(settled & resting & (gap >= p["quiet_gap"]), p["quiet_bonus"], 0.0)
    dead -= np.where(carried, p["carry_malus"], 0.0)
    busy = np.clip((p["quiet_gap"] - gap) / (p["quiet_gap"] - p["busy_gap"]), 0.0, 1.0)
    busy = np.where(since_strike < p["strike_halo"], 1.0, busy)
    dead -= p["busy_malus"] * busy
    kick = F.kick_strength(ball_speed, present)
    support = F.restart_support(kick, strikes)
    dead -= p["restart_support"] * support

    # Team evidence separates H from A only. D receives the same |team| so that a player standing
    # on a dead ball (a keeper placing it, a taker over a free kick) is not evidence of live play.
    scores = np.zeros((n, 3))
    scores[:, H] = team
    scores[:, A] = -team
    scores[:, D] = dead + np.abs(team)

    # per-frame transition costs
    out_onset = F.onset(out)
    decel = F.collective_deceleration(atd["spd"])
    whistle = np.clip((decel - p["whistle_decel_start"])
                      / (p["whistle_decel_full"] - p["whistle_decel_start"]), 0.0, 1.0)
    a2d = p["alive_to_dead"] - whistle * (p["alive_to_dead"] - p["alive_to_dead_whistle"])
    a2d = np.where(out_onset, p["alive_to_dead_out"], a2d)
    if whistles is not None and len(whistles):
        from .audio import whistle_mask
        blown = whistle_mask(whistles, n, before=int(round(p["referee_lead"] * F.FPS)),
                             after=int(round(p["referee_tail"] * F.FPS)))
        a2d = np.where(blown, np.minimum(a2d, p["alive_to_dead_referee"]), a2d)
    d2a = p["dead_to_alive"] - kick * (p["dead_to_alive"] - p["dead_to_alive_kick"])
    costs = dict(a2d=a2d, d2a=d2a)

    feats = dict(ball_xy=ball_xy, present=present, ball_speed=ball_speed, d_home=d_home,
                 d_away=d_away, walk=walk, out=out, set_piece=set_piece, team=team, dead=dead,
                 kick=kick, strike_gap=gap, support=support, costs=costs)
    return scores, feats


HOME_TAG_TEAMS = ("barc", "home")      # set-piece tag team names, lower-case prefixes
AWAY_TAG_TEAMS = ("atl", "away")


def restart_owner(path, tags, team_ev, first, p=PARAMS):
    """The team taking a restart has the ball until the other team gains control.

    Coming out of a stoppage the decoder has no previous team and enters whichever team shows
    control first -- on a corner, usually the defender who clears it -- skipping the taker's
    short possession. For each SET PIECES tag that names a team, the first decoded restart within
    [-2 s, +12 s] of the tag start is given to that team, from the restart up to the first frame
    on which the other team's net evidence reaches 0.5 (or the end of the first decoded spell),
    if that is at least 0.5 s. Edits `path` (codes for the half starting at video frame `first`)
    in place; tags without a team (throw-ins, kick-offs) are ignored."""
    if not p.get("restart_owner", 0):
        return path
    n = len(path)
    dead = path == D
    restarts = np.flatnonzero(dead[:-1] & ~dead[1:]) + 1
    for e in tags:
        if (e.get("code") or "").strip().lower() != "set pieces":
            continue
        team = (e.get("tags", {}).get("Team") or "").strip().lower()
        k = H if team.startswith(HOME_TAG_TEAMS) else A if team.startswith(AWAY_TAG_TEAMS) else None
        if k is None:
            continue
        s = e["start_frame"] - first
        hit = restarts[(restarts >= s - 2 * F.FPS) & (restarts <= s + 12 * F.FPS)]
        if not len(hit):
            continue
        r = int(hit[0])
        if path[r] == k:
            continue
        end = r
        while end < n and path[end] == path[r]:
            end += 1
        other = 1.0 if path[r] == H else -1.0
        against = np.flatnonzero(other * team_ev[r:end] >= 0.5)
        stop = r + (int(against[0]) if len(against) else end - r)
        if stop - r >= F.FPS // 2:
            path[r:stop] = k
    return path


def viterbi(scores, costs, p=PARAMS, force_dead=None):
    """Best H/A/D path with per-frame transition costs.

    Ties between staying and changing are broken towards changing (see the loop).

    costs["a2d"][t] / costs["d2a"][t] are the costs of entering / leaving D *at* frame t.
    `force_dead` (bool array) pins frames to D (before the tagged kick-off).
    """
    n = len(scores)
    sw = p["switch_cost"]
    a2d, d2a = costs["a2d"], costs["d2a"]
    s = scores.copy()
    if force_dead is not None:
        s[force_dead, H] = -1e9
        s[force_dead, A] = -1e9
    back = np.zeros((n, 3), dtype=np.int8)
    v = s[0].copy()
    trans = np.zeros((3, 3))
    trans[H, A] = trans[A, H] = -sw
    states = np.arange(3)
    for t in range(1, n):
        trans[H, D] = trans[A, D] = -a2d[t]
        trans[D, H] = trans[D, A] = -d2a[t]
        cand = v[:, None] + trans          # from x to
        stay = cand[states, states]
        cand[states, states] = -np.inf
        other = np.argmax(cand, axis=0)
        change = cand[other, states]
        # On an exact tie the change is taken, which places it as LATE as possible: across a
        # stretch without evidence (a pass in flight, a loose or unseen ball) the label stays
        # with the previous team until the new one shows control -- the challenge's rule.
        take = change >= stay
        back[t] = np.where(take, other, states)
        v = np.where(take, change, stay) + s[t]
    path = np.zeros(n, dtype=np.int8)
    path[-1] = int(np.argmax(v))
    for t in range(n - 1, 0, -1):
        path[t - 1] = back[t, path[t]]
    return path
