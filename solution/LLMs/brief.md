# Brief: ideas wanted for a football ball-possession labelling system

## What I am asking you for

I am competing in a data challenge and have a working solution. I want **ideas to improve it, not
code**. Please read the whole brief, then propose approaches I have not tried. The most useful
answers will:

- name a concrete mechanism (what signal, computed from what, and why it would separate the cases),
- say which of my known weaknesses it addresses (section 8),
- say how I could tell whether it helped **without ground truth** (section 6 explains why that
  matters),
- respect the competition rules (section 4).

Rank your ideas by expected benefit against effort, and say how confident you are in each. If you
think part of my current design is wrong rather than incomplete, say so. Unconventional ideas are
welcome as long as they are within the rules.

## 1. The task

One full professional football match (FC Barcelona vs Athletic Club, LaLiga 2024-25). For each of
the 199,319 frames of a wide-angle "tactical" video at 25 fps, output one label:

| label | meaning |
|---|---|
| `H` | home team in possession, ball in play |
| `A` | away team in possession, ball in play |
| `D` | dead ball: the ball is not in play (out, foul, before a restart) |
| `X` | abstain |

158,857 frames are graded (the two halves); the rest (before kick-off, half-time, after the final
whistle) are ignored. The ground truth is private. It was derived mechanically from **corrected**
tracking data: a frame is `D` where the corrected tracking marks the ball dead, otherwise it takes
the team the tracking names as owning the ball. Nothing is smoothed afterwards.

Possession rules stated by the organisers:

- While the ball is in play, exactly one team has possession. There is no "contested" state.
- Possession changes when the opposing team gains **controlled** possession. A simple touch, a
  deflection, or an aerial duel won without subsequent control does not change it.
- While the ball is loose or contested, possession stays with the last team that had it.
- Dead-ball ownership is not asked for: when the ball is dead the answer is `D`.

Only 5 minutes of ground truth are public (17 possessions and 4 stoppages). In that sample,
possessions last from 0.76 s to 42 s (mean 14.2 s) and stoppages from 5.5 s to 20 s.

## 2. The metric (this drives everything)

The ranking metric is **spellF1**, not per-frame accuracy.

- A *possession* is a maximal run of `H` or of `A`. `H H H A A` is two possessions.
  `H H D D H H` is also two: a stoppage splits a possession.
- Predicted possessions are matched one-to-one to true possessions of the same team by temporal
  IoU. The F1 of the matching is averaged over IoU thresholds 0.3, 0.4, 0.5, 0.6, 0.7.
- Consequences: a possession found 1 frame late costs nothing; 8 frames late costs about 11 %;
  1 second late costs about 35 %. One false change of possession in the middle of a long true
  possession destroys it (the pieces no longer reach the IoU thresholds) and adds false
  possessions. Any constant guess scores exactly 0.
- `X` on a graded frame is forward-filled with the previous label before matching, so it is
  equivalent to repeating the previous answer.
- Tie-break metric: macro-F1 over `H`, `A`, `D` per frame.

So two things decide the score, and they matter about equally:

1. **Dead-ball detection and its timing.** Every stoppage has two boundaries, and each boundary is
   also the boundary of a possession. With roughly 100 stoppages and roughly 200 possessions, most
   possessions touch a stoppage.
2. **How many changes of possession are produced, and where.** Too many splits long possessions;
   too few merges them.

The organisers' baseline (nearest tracked player to the ball, then a majority vote over a ±2 s
window) scores spellF1 0.2433 on the full match. They state that differences below about 0.04 on
the full match are noise.

## 3. The data I have

Everything is **automatic and uncorrected**.

- **Tracking (ATD)**, one record per frame: positions and speeds of up to 46 "track slots" and the
  ball, in pitch coordinates. Slots are tracklets, not players: there are no identities, slots
  appear, vanish and swap. Each slot has a team (24 home, 22 away). About 20.5 objects are
  tracked on average. There is no role information (goalkeeper, outfield).
- **The ball is missing on 41 % of graded frames.** Properties I measured:
  - The ball track is smoothed and interpolated. A pass that leaves the foot at 15 m/s appears as
    a speed ramp lasting about one second; there is no frame-to-frame jump at a kick.
  - Gaps shorter than about 3 s essentially do not occur. The ball is either tracked or lost for
    a long stretch.
  - Missing does not mean dead: in the public sample the ball is unseen for up to 9 s of live
    play (a crowded attack) and is tracked through entire stoppages.
  - Airborne balls are projected onto the ground at the wrong place, so the nearest player to an
    aerial ball is often wrong.
  - The ball is tracked beyond the pitch lines on only about 2 % of frames; most balls that go
    out are simply lost.
- **Smart Tagging**: 638 automatically generated intervals with a code and tags.
  - Phases with a team tag: Build Up, Progression, Creating Chances, Attacking Transition,
    Defensive Transition, Defending in (Defensive / Middle / Attacking) Third, Long Ball, Ball in
    Final Third, Ball in the Box, Players in the Box, Goals.
  - Set pieces (59): throw-in 26, corner 12, goal kick 10, free kick 5, kick-off 6. Throw-ins
    have no team. A set-piece interval is 35 s long (5 s for the two opening kick-offs) and opens
    a variable few seconds before the restart (about 2 to 12 s), so most of it is the play that
    follows.
  - Phase team tags agree with the team in possession only about 70–80 % of live frames, because
    a phase spans several possessions.
- **Homography** per frame (pitch to pixels), valid on every tactical frame.
- **The tactical video** itself (1920×1080, 25 fps, about 2 h 13 min).
- **A second, broadcast recording** with its own tracking and homography. It is not synchronised
  to the tactical video, has cuts, replays and zooms, and only 66 % of its frames have a usable
  homography. Its ball is visible on 50.5 % of its frames. I have not used it.

## 4. Rules that constrain ideas

- Labels must come from an algorithm. **No hand labelling or hand correction of this match**, in
  any amount, for any purpose, and no constants tied to specific frames of this match.
- The private ground truth and any human-produced data about this match (event data, corrected
  tracking, annotations) are forbidden.
- The public 5 minutes are for checking that the pipeline is correct. They are **not** training
  data and **not** a tuning set.
- Allowed: any method, any model, pre-trained models, self-supervised or unsupervised learning on
  this match, algorithmic pseudo-labels, my own detection or tracking on the video, and
  **human-labelled data from other matches** in any amount (it must be accessible to the
  organisers and documented).
- The match data may not be uploaded to hosted or cloud LLMs or services; anything that reads the
  video or tracking must run locally.
- The submission must be regenerated exactly by a public repository, so the pipeline must be
  deterministic.
- Practical limits: one week to the deadline, one person, an ordinary laptop (assume no large
  GPU), currently numpy and pandas only.

## 5. What I have built

A three-state model (`H`, `A`, `D`) decoded with Viterbi over each half. Each frame gets a score
per state; a path pays a cost each time it changes state. There is **no training**: every
constant is a hand-set prior in metres, seconds or m/s. It runs in about 6 seconds.

**H versus A evidence ("control").** For each player:
`control = closeness(distance to ball, midpoint 2 m) × slowness(|v_ball − v_player|, midpoint 4 m/s)`.
Frame evidence = best home control − best away control, in [−1, 1]. So a ball that is close to a
player *and moving with them* counts; a pass travelling past an opponent does not. When neither
team shows control (pass in flight, loose ball, ball unseen), the previous team is kept until the
other team shows control.

**Dead versus alive evidence**, each about ±0.1 per frame:

| signal | direction |
|---|---|
| ball tracked beyond a line (1 m margin) | strongly dead (+1.0) |
| mean speed of all tracked players below 1.4 m/s, read 2 s ahead to allow for reaction time | dead; alive above |
| ball unseen | dead |
| ball in view and at rest, inside an interval of at least 6 s between two ball strikes | dead |
| interval between strikes under 6 s, or within 2 s after a strike | alive |
| ball moving at 2.5 m/s or more under a player's control (a carry) | alive |
| ball faster than 10 m/s | alive |
| ball resting with nobody within 8 m | dead |
| within 3 s of the start of a tagged set-piece interval | dead |
| within 4 s after a detected restart that is followed by another strike within 5 s | alive |

A "strike" is detected as a local minimum of ball speed followed by a rise of more than 5 m/s
within the next second (because of the smoothing described above).

**Transition costs:**

| transition | cost |
|---|---|
| H ↔ A | 12 |
| alive → dead | 25; 10 when all players decelerate together (mean speed drops more than 1 m/s in 2 s); 3 on the frame the ball crosses a line |
| dead → alive | 20; 3 at a "restart kick" (a resting or unseen ball that reaches about 7 m/s within a second) |

Frames before the tagged opening kick-off of each half are forced to `D`. No `X` is written on
graded frames.

**Output for the full match:** 202 possessions (mean 15.9 s, median 10.8 s), 93 stoppages, 49 %
of graded frames dead. Alive time splits 64 % home, 36 % away.

## 6. How I evaluate, and why it is hard

I cannot see the full-match score. The public sample has 17 possessions, where one possession
moves spellF1 by about 6 points, and the rules forbid tuning on it. On that sample the current
model scores spellF1 0.61 and macro-F1 0.90 (the best organiser baseline scores 0.42 there), but
I treat this only as a correctness check.

Ground-truth-free checks I use over the whole match:

- **Agreement with Smart Tagging team tags** on live frames, and in particular which of two
  versions the tags side with on the frames where the versions differ. The current version scores
  0.801; replacing nearest-player evidence with control evidence raised it from 0.758, and the
  tags sided with the new version on 77 % of differing frames (57–63 % when the possession count
  was matched). Caveat: phase tags favour smoother labellings.
- **Set-piece audit:** of 58 tagged set pieces, 46 have a decoded restart within [−2 s, +12 s] of
  the tag start, and 1 has no stoppage near it.
- **Plausibility:** dead share against typical effective playing time; every stoppage over two
  minutes coincides with a tagged goal.
- **Sensitivity:** scaling each constant by 0.7 and 1.3.

**Better label-free validation ideas are as valuable to me as better features.** At the moment I
cannot calibrate the two quantities the metric depends on most (next section).

## 7. What the sensitivity analysis shows

| constant | effect of ×0.7 / ×1.3 |
|---|---|
| H ↔ A switch cost | 231 / 172 possessions (default 202) |
| control radius | 174 / 220 possessions |
| relative-velocity gate | 170 / 217 possessions |
| walking-speed threshold | dead share 0.40 / 0.55 (default 0.49) |
| everything else | under 2 % of frames change |

So the number of possessions and the dead share each rest on one or two hand-set priors that I
have no principled way to set.

## 8. Known weaknesses

1. **The number of possessions is unpinned** (see above).
2. **The dead share hinges on one threshold** on collective player speed.
3. **Blind while the ball is unseen.** During live play without a ball position, the model keeps
   the previous team. A change of possession in that time is only noticed when the ball
   reappears, and its timing is unknown.
4. **Timing of changes of possession is 1–2 s off** in two situations: duels (a pressing opponent
   moving alongside the ball looks like control before they have it) and balls won with a
   first-time pass (no control appears until the team-mate receives it, but the ground truth
   seems to date the change at the first touch).
5. **Short stoppages with the ball unseen** (a quick throw-in, a quick foul) are found only if
   the players visibly slow down. Stoppages shorter than about 5 s are probably missed.
6. **Stoppage starts after a foul are found late** when players keep running for a few seconds.
7. **Gentle restarts** (a kick-off tap, a short free kick, a throw-in) are not detected as
   restart kicks. The second-half kick-off is decoded about 3 s early.
8. **Short possessions** (under about 1 s of control) are never detected, by design of the switch
   cost. The public sample contains possessions of 0.76 s and 1.3 s.
9. **The player on the ball is sometimes untracked or assigned to the wrong team**, and then the
   evidence points to the other team.
10. **In the public sample** there are cases where the ground truth gives possession to a team
    whose nearest tracked player is 7–8 m from the tracked ball, which suggests the ball position
    itself is wrong there (probably airborne).

## 9. What I already tried and dropped

- Nearest-player evidence with a ball-speed cut-off (replaced by control evidence).
- All phase team tags pooled as a prior for H versus A: too noisy. I have **not** tested whether
  individual tag types (for example Build Up, or the first seconds of an Attacking Transition)
  are reliable enough to use, particularly while the ball is unseen.
- Counting strikes in a ±4 s window as live-play evidence: it blurred every stoppage boundary by
  up to 4 s. Replaced by the interval between consecutive strikes.
- Treating a tagged set-piece start as the exact restart time: the lead is not constant.
- Dating a change of possession back to the moment the new team's player reached the ball: it
  moved changes by a median of only 4 frames.
- Estimating dead/alive likelihoods from the decoder's own output: circular, because signals the
  decoder did not use look uninformative by construction.

## 10. Directions I have considered but not done

- Using public labelled data from **other matches** (for example open tracking-plus-events
  datasets) to calibrate the switch cost and the walking-speed threshold. My concern is domain
  gap: those datasets have clean, identified tracking with a complete ball, and mine does not.
- Synchronising the broadcast tracking to the tactical timeline to get a second view of the ball.
- Detecting the ball in the tactical video locally to fill the 41 % gap.
- Using the geometry of both teams (team shape, centroid movement, direction of collective
  movement, compactness, which way the lines are moving) as evidence of who is attacking when
  the ball is unseen.
- Replacing hand-set scores with an unsupervised or self-supervised model fitted on this match.

## 11. Questions I most want answered

1. How can I detect **dead ball and its exact start and end** better from this kind of data,
   especially when the ball is unseen? Are there collective player-behaviour signatures of
   throw-ins, goal kicks, corners, free kicks and fouls that I am not using?
2. How can I tell **which team has the ball when the ball is not tracked**?
3. How can I set the **number of possessions** (the switch cost) and the **dead share** in a
   principled way without labels on this match?
4. Is there a **label-free validation signal** better than agreement with noisy automatic tags?
5. Is a hand-scored Viterbi decoder the right architecture, or would a different formulation
   (segment-level models, explicit duration models, event detection first, a learned model
   trained on other matches or on pseudo-labels) be more robust given that I cannot validate?
6. Given the metric, are there **decoding or post-processing strategies** that raise expected
   spellF1 under uncertainty, for example how to treat short uncertain possessions, where to
   place a boundary whose time is uncertain, or whether abstaining can ever help?
7. Is there anything in the task definition, the metric or the data that I appear to have
   **misunderstood or overlooked**?

Please answer with ideas and reasoning only. Do not write code.
