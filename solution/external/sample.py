"""Metrica Sports public sample matches as labelled calibration data.

Source: https://github.com/metrica-sports/sample-data (Sample_Game_1 and Sample_Game_2: tracking
CSV per team at 25 fps plus an event CSV). These are OTHER matches, anonymised, published by
Metrica; nothing here touches the competition match. `download()` fetches the files.

Labels, per frame:
  D   where the tracking has no ball position AND that blank run either leads to a SET PIECE
      event or lasts at least 4 s. In these files the ball is blank while it is out of play
      (97 % of the time between the event that stops play and the next set piece) -- the
      convention the competition describes for its own ground truth -- but also for 60-70 short
      moments per match, under 2 s, that end in a RECOVERY or CHALLENGE: a ball untracked in the
      air during live play. Those stay live, with the previous owner.
  H/A otherwise: the team of the most recent on-ball event (PASS, SHOT, RECOVERY, SET PIECE,
      BALL LOST, BALL OUT, FAULT RECEIVED). A BALL LOST still belongs to the team losing it; the
      ball changes hands at the opponent's next on-ball event. CHALLENGE and CARD are ignored.
The H/A rule is ours, written to follow the competition's definition (possession stays with the
last team until the other one has the ball); it is not Metrica's own possession signal.
It counts every recovery, however brief. `controlled()` derives labels closer to the definition:
a change needs a completed pass by the new team or a few seconds on the ball.

    python solution/external/sample.py        # download if needed, print label statistics
"""
import os
import sys
import urllib.request

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
BASE = "https://raw.githubusercontent.com/metrica-sports/sample-data/master/data"
GAMES = (1, 2)                 # calibration matches: every result so far was judged on these
HOLDOUT = (3,)                 # hold-out (added 2026-11-12): judged on only after a choice is made
FPS = 25
PITCH = (105.0, 68.0)          # metres; the files are normalised 0-1
H, A, D, X = 0, 1, 2, 3
MIN_DEAD = 4 * FPS             # a blank-ball run this long is a stoppage whatever follows it
ON_BALL = {"PASS", "SHOT", "RECOVERY", "SET PIECE", "BALL LOST", "BALL OUT", "FAULT RECEIVED"}


def files(game):
    stem = "Sample_Game_{}".format(game)
    if game == 3:   # FIFA EPTS format: one tracking text file, XML metadata, JSON events
        return {"events": stem + "_events.json", "tracking": stem + "_tracking.txt",
                "metadata": stem + "_metadata.xml"}
    return {"events": stem + "_RawEventsData.csv",
            "home": stem + "_RawTrackingData_Home_Team.csv",
            "away": stem + "_RawTrackingData_Away_Team.csv"}


def event_table(game):
    """Event table with the columns of the game 1-2 CSV that the label rules use: Type,
    Subtype, Team ("Home" / "Away"), Start Frame and End Frame (counted from 1; End Frame 0 when
    the event has no end), sorted by Start Frame.
    Game 3's CARRY events are dropped: games 1-2 have none, and the label rules must be the
    same on every match (a carry continues the same player's possession anyway)."""
    path = os.path.join(DATA, files(game)["events"])
    if game != 3:
        table = pd.read_csv(path)
    else:
        import json
        with open(path) as fh:
            data = json.load(fh)["data"]

        def subtype(e):
            st = e["subtypes"]
            if st is None:
                return np.nan
            if isinstance(st, dict):
                return st["name"]
            return "-".join(x["name"] for x in st)

        table = pd.DataFrame({
            "Type": [e["type"]["name"] for e in data],
            "Subtype": [subtype(e) for e in data],
            # Team A is the local (home) team of the metadata, listed first
            "Team": ["Home" if e["team"]["name"] == "Team A" else "Away" for e in data],
            "Start Frame": [int(e["start"]["frame"]) for e in data],
            "End Frame": [int(e["end"]["frame"]) if e["end"]["frame"] is not None else 0
                          for e in data],
        })
        table = table[table["Type"] != "CARRY"]
    return table.sort_values("Start Frame", kind="stable").reset_index(drop=True)


def _tracking_epts(game):
    """Game 3: (period per frame, positions (N, players, 2) normalised, team per player, ball
    (N, 2) normalised). Players are indexed by identity, not by slot: substitutions move
    players between slots, which would make a slot's track jump."""
    import xml.etree.ElementTree as ET
    f = files(game)
    root = ET.parse(os.path.join(DATA, f["metadata"])).getroot()
    params = {pp.findtext("Name"): pp.findtext("Value")
              for pp in root.find(".//ProviderGlobalParameters")}
    team_ids = [t.get("id") for t in root.iter("Team")]          # first = local (home)
    players = [pl.get("id") for pl in root.iter("Player")]
    team = np.array([0 if pl.get("teamId") == team_ids[0] else 1 for pl in root.iter("Player")],
                    dtype=np.int8)
    col = {pid: i for i, pid in enumerate(players)}
    channel_player = {c.get("id"): c.get("playerId") for c in root.iter("PlayerChannel")}
    specs = []
    for spec in root.iter("DataFormatSpecification"):
        slots = [col[channel_player[g.find("PlayerChannelRef").get("playerChannelId")]]
                 for g in spec.find("SplitRegister")]
        specs.append((int(spec.get("startFrame")), int(spec.get("endFrame")), slots))
    n = int(params["second_half_end"])
    pos = np.full((n, len(players), 2), np.nan, dtype=np.float32)
    ball = np.full((n, 2), np.nan, dtype=np.float32)
    k = 0
    with open(os.path.join(DATA, f["tracking"])) as fh:
        for line in fh:
            frame, groups, b = line.rstrip("\n").split(":")
            fr = int(frame)
            while not specs[k][0] <= fr <= specs[k][1]:
                k += 1
            i = fr - 1
            for slot, g in zip(specs[k][2], groups.split(";")):
                x, y = g.split(",")
                pos[i, slot] = float(x), float(y)
            bx, by = b.split(",")
            ball[i] = float(bx), float(by)
    period = np.where(np.arange(1, n + 1) <= int(params["first_half_end"]), 1, 2)
    return period, pos, team, ball


def download():
    os.makedirs(DATA, exist_ok=True)
    for game in GAMES:
        for name in files(game).values():
            path = os.path.join(DATA, name)
            if not os.path.exists(path):
                url = "{}/Sample_Game_{}/{}".format(BASE, game, name)
                print("downloading", url)
                urllib.request.urlretrieve(url, path)


def _tracking(path):
    table = pd.read_csv(path, skiprows=2)
    values = table.iloc[:, 3:].to_numpy(dtype=np.float32)
    players = values[:, :-2].reshape(len(table), -1, 2)
    ball = values[:, -2:]
    return table["Period"].to_numpy(), players, ball


def load(game):
    """dict with the same arrays as solution.load.load_atd, plus labels and structure:

    ball (N, 3), pos (N, S, 2), spd (N, S), team (S,)   -- metres, m/s, 0 = home / 1 = away
    labels (N,)        H / A / D codes
    periods            [(first frame, last frame)] per half
    set_pieces         [(frame, subtype, team code)]
    """
    cache = os.path.join(DATA, "sample_game_{}.npz".format(game))
    if os.path.exists(cache):
        z = np.load(cache, allow_pickle=True)
        return {k: z[k] for k in z.files}
    if game == 3:
        period, pos, team, ball = _tracking_epts(game)
    else:
        download()
        f = files(game)
        period, home, ball = _tracking(os.path.join(DATA, f["home"]))
        _, away, _ = _tracking(os.path.join(DATA, f["away"]))
        pos = np.concatenate([home, away], axis=1)
        team = np.r_[np.zeros(home.shape[1]), np.ones(away.shape[1])].astype(np.int8)
    pos[..., 0] *= PITCH[0]
    pos[..., 1] *= PITCH[1]
    ball3 = np.full((len(ball), 3), np.nan, dtype=np.float32)
    ball3[:, 0] = ball[:, 0] * PITCH[0]
    ball3[:, 1] = ball[:, 1] * PITCH[1]

    # player speed (m/s) from positions, smoothed over 0.4 s like a tracking provider would
    vel = np.full(pos.shape, np.nan, dtype=np.float32)
    vel[5:-5] = (pos[10:] - pos[:-10]) * (FPS / 10.0)
    spd = np.linalg.norm(vel, axis=2)

    n = len(ball)
    cut = np.flatnonzero(np.diff(period)) + 1
    starts = np.r_[0, cut]
    stops = np.r_[cut, n] - 1
    periods = np.array(list(zip(starts, stops)), dtype=np.int64)

    every = event_table(game)
    every_frames = every["Start Frame"].to_numpy() - 1
    every_types = every["Type"].to_numpy()
    blank = np.isnan(ball[:, 0])
    dead = np.zeros(n, dtype=bool)
    edges = np.flatnonzero(np.diff(np.r_[0, blank.astype(np.int8), 0]))
    for a, b in zip(edges[::2], edges[1::2]):
        k = np.searchsorted(every_frames, b - 2)          # first event at the end of the run
        to_set_piece = k < len(every) and every_types[k] == "SET PIECE"
        if to_set_piece or b - a >= MIN_DEAD:
            dead[a:b] = True
    events = every[every["Type"].isin(ON_BALL)]
    owner = np.full(n, -1, dtype=np.int8)
    frames = events["Start Frame"].to_numpy() - 1        # the files count frames from 1
    sides = np.where(events["Team"].to_numpy() == "Home", H, A)
    order = np.searchsorted(frames, np.arange(n), side="right") - 1
    owner[order >= 0] = sides[order[order >= 0]]
    labels = np.where(dead, D, owner).astype(np.int8)
    labels[labels < 0] = D

    sp = events[events["Type"] == "SET PIECE"]
    set_pieces = np.array([(int(fr) - 1, str(st), H if tm == "Home" else A)
                           for fr, st, tm in zip(sp["Start Frame"], sp["Subtype"], sp["Team"])],
                          dtype=object)
    out = dict(ball=ball3, pos=pos, spd=spd, team=team, labels=labels, periods=periods,
               set_pieces=set_pieces)
    np.savez_compressed(cache, **out)
    return out


def contact_frames(game, drop=0.25, seed=0):
    """Frames (from 0) where the ball was played according to the events: the start of every
    on-ball event or challenge and the end of every pass (its reception). A share `drop` of them,
    chosen at random, is left out: the target's provider surely misses some contacts too, and
    anchoring the simulated ball at every annotated contact would make contacts unrealistically
    easy to find."""
    ev = event_table(game)
    ev = ev[ev["Type"].isin(ON_BALL | {"CHALLENGE"})]
    frames = list(ev["Start Frame"] - 1)
    passes = ev[(ev["Type"] == "PASS") & (ev["End Frame"] > 0)]
    frames += list(passes["End Frame"] - 1)
    frames = np.unique(np.array(frames, dtype=np.int64))
    frames = frames[frames >= 0]
    keep = np.random.default_rng(seed + 2000).random(len(frames)) >= drop
    return frames[keep]


def merge_brief(labels, periods, max_frames):
    """A less fragmented labelling: possessions of at most `max_frames` frames that sit between
    two possessions of the other team (no stoppage in between) are given to that team.

    Our H/A rule turns every RECOVERY into a possession, however brief; the competition asks for
    *controlled* possession and its public sample is less fragmented. Scoring against both
    labellings brackets the convention we cannot observe.
    """
    out = labels.copy()
    for a, b in periods:
        seg = out[int(a):int(b) + 1]
        cut = np.flatnonzero(seg[1:] != seg[:-1]) + 1
        starts, stops = np.r_[0, cut], np.r_[cut, len(seg)]
        for i in range(1, len(starts) - 1):
            lab = seg[starts[i]]
            before, after = seg[starts[i] - 1], seg[stops[i]]
            if (lab != D and stops[i] - starts[i] <= max_frames and before == after
                    and before != D and before != lab):
                seg[starts[i]:stops[i]] = before
    return out


def controlled(game_id, labels, periods, hold_s=3.0, min_passes=1):
    """Labels that follow the competition's definition: possession changes only when the other
    team gains *controlled* possession (CHALLENGE.md, "Controlled possession").

    A run of the event-derived labels by team k counts as controlled if k completes at least
    `min_passes` passes in it (a Metrica PASS is a completed pass; a failed one is BALL LOST),
    or if k has the ball for at least `hold_s` seconds: from the start of the run to the start
    of k's last on-ball action in it. A run that is not controlled goes to the team that had
    the ball before it -- processed left to right, so a chain of brief recoveries collapses onto
    the last controlled team. A run that starts a period or follows a stoppage keeps its team:
    the restart gives that team the ball.

    CHALLENGE.md's own proxies are "keeps the ball for a few seconds" and "more than two
    consecutive passes"; min_passes=1 is the lenient reading, min_passes=3 the strict one.
    """
    ev = event_table(game_id)
    ev = ev[ev["Type"].isin(ON_BALL)]
    frames = ev["Start Frame"].to_numpy() - 1
    sides = np.where(ev["Team"].to_numpy() == "Home", H, A)
    is_pass = (ev["Type"] == "PASS").to_numpy()
    order = np.argsort(frames, kind="stable")
    frames, sides, is_pass = frames[order], sides[order], is_pass[order]
    out = labels.copy()
    for a, b in periods:
        a, b = int(a), int(b)
        seg = labels[a:b + 1]
        cut = np.flatnonzero(seg[1:] != seg[:-1]) + 1
        prev = D
        for s, e in zip(np.r_[0, cut], np.r_[cut, len(seg)]):
            k = seg[s]
            if k == D:
                prev = D
                continue
            if prev in (H, A) and prev != k:
                lo, hi = np.searchsorted(frames, [a + s, a + e])
                mine = sides[lo:hi] == k
                passes = int(is_pass[lo:hi][mine].sum())
                hold = (frames[lo:hi][mine].max() - (a + s)) / FPS if mine.any() else 0.0
                if passes < min_passes and hold < hold_s:
                    out[a + s:a + e] = prev
                    continue
            prev = k
    return out


def spells(labels, periods):
    """Lengths (frames) of possessions and of stoppages, split at period boundaries."""
    poss, dead = [], []
    for a, b in periods:
        seg = labels[a:b + 1]
        cut = np.flatnonzero(seg[1:] != seg[:-1]) + 1
        for s, e in zip(np.r_[0, cut], np.r_[cut, len(seg)]):
            (dead if seg[s] == D else poss).append(e - s)
    return np.array(poss), np.array(dead)


if __name__ == "__main__":
    for game in GAMES + HOLDOUT:
        g = load(game)
        poss, dead = spells(g["labels"], g["periods"])
        lab = g["labels"]
        print("game {}: frames {}  H {:.2f}  A {:.2f}  D {:.2f}".format(
            game, len(lab), (lab == H).mean(), (lab == A).mean(), (lab == D).mean()))
        print("   possessions {}  mean {:.1f} s  median {:.1f} s  under 2 s: {}  over 40 s: {}".format(
            len(poss), poss.mean() / FPS, np.median(poss) / FPS, int((poss < 50).sum()),
            int((poss > 1000).sum())))
        print("   stoppages {}  median {:.1f} s  under 4 s: {}".format(
            len(dead), np.median(dead) / FPS, int((dead < 100).sum())))
        seg = []
        for a, b in g["periods"]:
            s = lab[a:b + 1]
            cut = np.flatnonzero(s[1:] != s[:-1]) + 1
            seg.append([(s[i], j - i) for i, j in zip(np.r_[0, cut], np.r_[cut, len(s)])])
        same = sum(1 for half in seg for i in range(1, len(half) - 1)
                   if half[i][0] == D and half[i - 1][0] == half[i + 1][0])
        print("   stoppages with the same team on both sides: {}".format(same))
        with np.errstate(all="ignore"):
            walk = np.nanmean(g["spd"], axis=1)
        print("   mean player speed: live {:.2f} m/s, dead {:.2f} m/s; players tracked per frame {:.1f}"
              .format(np.nanmean(walk[lab != D]), np.nanmean(walk[lab == D]),
                      np.mean((~np.isnan(g["pos"][..., 0])).sum(axis=1))))
