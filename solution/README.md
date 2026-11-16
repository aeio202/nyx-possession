# Possession by control evidence and restart-aware Viterbi decoding

A three-state model (`H` / `A` / `D`) over every frame of the tactical video, decoded with Viterbi.
Classical, no learning and no labels: every constant is a physical or football prior written in
metres, seconds, m/s, hertz or decibels. Runs in under 10 seconds after a one-off parse of the
tracking (15 s) and of the audio (about 45 s).

## Reproduce

```bash
pip install -r solution/requirements.txt          # numpy + pandas, pinned
# ffmpeg must be on the PATH (used once, to decode the audio track of the tactical video)
# unpack the match data into ./data (or set MTAH_DATA_DIR), see DATA.md
python solution/run.py --name <team_name>         # -> solution/output/<team_name>.csv
python evaluation/validate_submission.py solution/output/<team_name>.csv
```

The run is deterministic: the same data gives a byte-identical file. The first run parses the ATD
and detects the referee whistles into `solution/cache/` (gitignored: derived match data must not
be published). Deleting the cache and running again reproduces the file exactly.

The submission was generated with ffmpeg `N-121700-g36e5576a44` (build of 2025-11-08). The audio
is taken as 32-bit float at its native 48 kHz, first channel, with no resampling or mixing, and
the whistle detections are unchanged when noise a thousand times larger than decoder rounding is
added to the samples (`python solution/audio.py --stability`), so another ffmpeg build should
give the same file. `python solution/run.py --no-audio` runs without ffmpeg and without the
whistle evidence; it changes about 1 % of graded frames.

## Files

| file | what |
|---|---|
| `load.py` | parse the tactical ATD into dense arrays (metres), cache them; read the Smart Tagging |
| `audio.py` | referee-whistle blasts from the audio track of the tactical video |
| `features.py` | per-frame evidence: ball velocity, team control, collective player speed, ball out of pitch, strikes and restart kicks, set-piece starts |
| `model.py` | per-frame state scores, per-frame transition costs, Viterbi |
| `run.py` | decode each half, write the submission, print possession statistics |
| `tag_agreement.py` | ground-truth-free comparison of two submissions against the Smart Tagging team tags |
| `audit.py` | ground-truth-free audit of stoppages against tagged set pieces and the published kick-offs |
| `sensitivity.py` | ground-truth-free robustness check of every prior |
| `tag_reliability.py` | ground-truth-free reliability of each Smart Tagging code |
| `metric_cases.py` | what the official metric rewards, on synthetic sequences |
| `test_decoder.py` | synthetic checks of the decoder |
| `inspect_public.py` | debugging aid: predicted vs public ground-truth segments |
| `external/sample.py` | download Metrica's public sample matches; derive H/A/D labels |
| `external/corrupt.py` | degrade them to resemble the competition tracking |
| `external/calibrate.py` | run the pipeline on them and score it with the official metric |
| `reversal.py` | label-free collective-reversal test of decoded changes of possession (checked on the external matches) |
| `broadcast.py` | broadcast-to-tactical alignment and what the broadcast adds (analysis only; not used by the submission) |
| `NYX.md` | the short technical document submitted with the file (this README is the long version) |

## Approach

### Why a state model

The ranking metric (`spellF1`) scores whole possessions, so the output must be a realistic number
of segments, not a per-frame classification. A path through H/A/D that pays a cost for every
change of state expresses that directly: a change of possession or a stoppage has to be supported
by enough accumulated evidence to pay for itself.

### H versus A: control, not proximity

The challenge defines a change of possession by *controlled* possession. A player controls the
ball when it is **close to them and moving with them**:

```
control(player) = closeness(distance, midpoint 2 m) × slowness(|v_ball − v_player|, midpoint 4 m/s)
evidence(frame) = max control over home players − max control over away players      in [−1, 1]
```

A dribble, a reception or a ball held still scores fully. A pass travelling past an opponent is
close but has a large relative velocity and scores nothing. Evidence below 0.02 is treated as none (a loose ball). Ball gaps of up
to 0.5 s are bridged linearly.

This replaced an earlier nearest-player rule. The reason is measurable without ground truth: under
the nearest-player rule, evidence taken while the ball moved faster than 6 m/s contradicted the
decoded team 9–37 % of the time, against 2–4 % for a slow ball.

**Completed passes.** Control alone misses possessions made of quick passing: on labelled other
matches, possessions of 4–8 s were right only about 60 % of the time. A *touch* is a sharp change
of the ball's velocity (more than 6 m/s across ±0.3 s, direction included), credited to a team
when one of its players is within 3 m of the ball and at least 1 m nearer than any opponent. Two
consecutive touches credited to the same team, at most 5 s apart, are a completed pass, and add
evidence worth 8 frames of full control spread over the pass. A lone touch adds nothing: the
definition says a simple touch or a deflection is not a change of possession.

**Receptions held.** Control also misses the moment a team wins the ball: an interception or a
tackle never has the ball travelling with the player who makes it. A touch credited to a team
(as above) after which that same team holds the ball (control above 0.5 on at least 0.5 s,
between 0.2 s and 2 s after the touch) adds evidence worth 8 frames of full control, spread from
the touch to the end of those 2 s. This is the definition's "gains controlled possession": the
touch counts only because the team then keeps the ball. On the labelled other matches it gains
+0.001 to +0.010 spellF1 under all five labellings, on the two calibration matches and on the
hold-out match alike. On the competition match it changes 4 + 2 changes of possession
(216 → 218 possessions).

**Restart owner.** Coming out of a stoppage the decoder has no previous team, so it enters
whichever team shows control first; on a corner that is usually the defender who clears it, and
the taker's short possession is skipped. By the definition the team taking a restart has the ball
until the other team gains control. Where a Smart Tagging set piece names a team (corners, goal
kicks, free kicks; throw-ins and kick-offs carry none), the first decoded restart within
[−2 s, +12 s] of the tag start is given to that team, from the restart until the other team's net
evidence reaches 0.5, if that lasts at least 0.5 s. On the competition match this changed 5 of
the 21 matched restarts (taker spells of 1.7–9.8 s; 218 → 223 possessions); restarts decoded for
the other team fell from 6 to 1. On the labelled other matches (simulated tags present for 60 %
of restarts, team wrong 10 % of the time) it gains +0.001 to +0.005 spellF1 under the labellings,
on all three matches.

**Loose balls.** When neither team shows control (a pass in flight, a loose or unseen ball) the
decoder keeps the previous team until the other one shows control: exact ties are broken towards
the latest possible change. This is the challenge's rule that possession stays with the last team.

### Dead versus alive

Per-frame evidence is small (≈0.1, i.e. 2.5 per second), so a stoppage is decided by several
seconds of consistent evidence and by its boundary events, never by a few frames.

| signal | direction | reasoning |
|---|---|---|
| ball beyond a line (1 m margin) | strongly dead | unambiguous |
| collective player speed below 1.4 m/s, read 2 s ahead | dead (alive above) | players walk during stoppages, and need about 2 s to react to a whistle or a restart |
| ball unseen (in this data, always a gap of over 3 s) | dead | stoppages lose the ball (hands, crowd, wall) |
| ball in view, at rest, in an interval of ≥ 6 s between strikes | dead | live play strikes the ball every 2–3 s |
| interval between strikes < 6 s, or within 2 s after a strike | alive | |
| ball carried under control at ≥ 2.5 m/s | alive | a dribble shows no strikes but is play |
| ball faster than 10 m/s inside the pitch | alive | passes and shots |
| ball resting with nobody within 8 m | dead | |
| within 3 s of the **start** of a Smart Tagging `SET PIECES` interval | dead | see below |
| within 4 s after a restart | alive | a slow build-up otherwise looks like a stoppage |

Team control is added to the D score as well, so a player standing over a dead ball (a keeper
placing it, a taker over a free kick) is not evidence of live play.

**Set-piece tags.** A tagged interval is 35 s long (5 s for a kick-off) and opens a few seconds
before the restart — 3.3 s and 3.5 s before the two kick-offs whose frames the documentation
publishes. Most of the interval is therefore the live play that follows, so only the frames around
its start are used as stoppage evidence.

### Transitions: restarts are events

| transition | cost |
|---|---|
| H ↔ A | 12 — about half a second of sole control by the other team pays for a short change |
| alive → D | 25; down to 10 at a collective-deceleration signature; 3 on the frame the ball crosses a line; 3 at a referee whistle heard in the audio |
| D → alive | 20, falling to 3 on a detected restart kick |

- **Restart kick:** a resting (< 1.5 m/s) or unseen ball whose speed peaks above ~7 m/s within the
  next second, located at the start of the speed ramp.
- **Collective deceleration:** the mean speed of all tracked players falling by more than 1 m/s
  within 2 s.
- **Referee whistle (audio):** see the next section.
- **Restart support:** a restart counts as play resuming only if another strike follows within 5 s;
  otherwise it is the ball being knocked to the taker during the stoppage.

The automatic ball track is heavily smoothed and interpolated: a pass that leaves the foot at
15 m/s appears as a ramp of about one second, and short gaps do not exist. Strike detectors
therefore compare the current speed with the peak over the following second.

### The referee's whistle, from the audio

The tactical video has an audio track. A referee's pealess whistle sounds two simultaneous narrow
tones; spectators whistle a single, lower one. Over the whole recording, pairs of strong
simultaneous tones cluster at about 3.8 kHz and 4.25 kHz, 400–500 Hz apart, while single strong
tones do not cluster. A blast is detected where, in 20 ms hops:

- the strongest narrow peak between 3.4 and 4.7 kHz is more than 20 dB above the median level of
  the neighbouring bands (2.5–3.4 and 4.7–6 kHz), after flattening the spectrum by its
  match-wide median;
- a second peak at least 200 Hz away is more than 12 dB above it, 300–600 Hz from the first;
- this holds for at least 0.1 s in total, joining blasts less than 0.2 s apart.

This finds 70 blasts in the recording (58 whistle occasions in graded time). Checks that do not
use ground truth: blasts are found 1.6 s before both kick-offs (whose frames the documentation
publishes) and at the final whistle; 43 of the 58 fall inside a stoppage the tracking-only
decoder had already found, and a whistle in decoded live play is followed by a decoded stoppage
within 10 s in two thirds of cases against about a quarter for random live frames. Looser
thresholds add detections that behave like chance, so the strict ones are kept.

Use in the model: from 0.2 s before a blast to 1 s after it, entering `D` costs 3 instead of 25.
The stoppage must still be supported by the evidence that follows; a whistle alone creates
nothing, and during a stoppage it changes nothing. In each half, play cannot start before the end
of the first whistle heard in the kick-off tag window.

Effect: about 1 % of graded frames change. Four more stoppages with the same team on both sides
are found (47 → 51); of the 15 whistles in live play, the decoder is dead within 3 s of 10
(5 without the audio); the second-half kick-off is decoded 32 frames late instead of 82 early.

### Halves, kick-off, abstention

Each half is decoded separately over its graded frames. Frames before the start of the Smart
Tagging `Kick Off (Start)` window, and then until the referee's whistle inside it, are pinned
to D. Frames outside the halves are `X`. No `X` is
written on graded frames: under `spellF1` an `X` repeats the previous label, which the decoder
already does through occlusions.

## Validation without ground truth

The private ground truth is unavailable and the public window has 17 possessions, so two
instruments built on the automatic Smart Tagging are used to compare versions over the whole match.

**Team tags (`tag_agreement.py`).** Phase tags (Build Up, Defending in …) carry a team. They are
noisy, but their errors do not depend on this model. Against the earlier nearest-player version:

| | agreement with team tags |
|---|---|
| nearest-player evidence | 0.758 |
| control evidence (this version) | 0.801 |
| on the 4,974 frames where the two differ | tags side with this version on 77 % |

Phase tags favour smoother labellings, so the comparison was repeated with the possession count
matched (switch cost lowered until this version produced 251–268 possessions against 257): the tags
still sided with control evidence on 57–63 % of differing frames.

**Set pieces and kick-offs (`audit.py`).** Every tagged restart should coincide with a decoded
stoppage ending.

| | before the dead-ball changes | tracking only | with the whistle |
|---|---|---|---|
| tagged set pieces with a decoded restart within [−2 s, +12 s] of the tag start | 39 of 58 | 46 of 58 | 47 of 58 |
| tagged set pieces with no stoppage near | 6 | 1 | 1 |
| stoppages / dead share | 82 / 0.49 | 93 / 0.49 | 97 / 0.49 |
| stoppages with the same team on both sides | | 47 | 51 |

The second-half kick-off (published as frame 113,742) is decoded 32 frames late: the referee's
whistle releases it, but a kick-off tap is too gentle for the restart-kick detector.

**Structure checks (`audit.py`, `metric_cases.py`).** The official metric, run on synthetic
sequences, charges a missed event and a falsely inserted one the same, cares far more about
whether an event exists than about its timing, and charges a missed stoppage only when the same
team has the ball on both sides. The audit therefore counts same-team stoppages, very short
stoppages (4 artefacts of under 3 s remain, where the ball is tracked beyond a line and straight
back) and very long possessions (15 over 40 s; most are the home team with the ball in view and
no opposing control).

**Collective reversal (`reversal.py`).** After a real change of possession both teams switch
roles within a couple of seconds: the new team moves towards the goal it attacks, the old one
retreats. At each direct H↔A change the instrument takes the mean x-velocity of each team's
tracked players, signed towards the new possessor's attacking goal (attack direction per half
from the teams' mean positions), and subtracts the mean over the 2 s before the change from the
mean over +1 s to +3 s. It uses no labels and no tags.

- *Checked on the external matches first.* Decoded changes that match a true change reverse by
  1.62 m/s on average (89 % positive); false ones by 0.19 m/s (53 %); AUC 0.75 per event. True
  possessions under 2 s reverse weakly (0.39 m/s). The share of real changes in a set, estimated from its mean reversal
  with references available on any match (changes found at every switch cost = real, random
  live frames = false), recovers the known share: 0.50 vs 0.48, 0.40 vs 0.49, 0.58 vs 0.57.
- *On the competition match* the signal is weaker (changes found at every cost: 0.88 m/s against
  1.32 on the external matches). Changes added by lowering the switch cost to 8 or 6 come out
  about 47 % and 42 % real, changes removed by raising it to 16 about 52 %, each with a 5–95 %
  bootstrap interval of roughly 0.1–0.9 (33–47 changes per set). The marginal changes either
  side of 12 are about as likely real as false, which is consistent with a flat optimum, but the
  instrument is too noisy at this sample size to place the switch cost. It stays at 12.
- *Limit, found with the definition-following labels below:* the instrument sees whether the
  ball physically changed hands, not whether the new team gained *control*. Of the changes a
  switch cost of 16 removes on the external matches, 57 % are real under the raw labels but
  only 26 % under the controlled ones, while the instrument implies 54–58 %. It cannot settle
  the question the switch cost depends on.

## Check on other matches (external data)

`solution/external/` runs the unchanged pipeline on other matches and scores it with the
official metric. It confirmed the existing priors, showed where the remaining error is, and
led to one addition: evidence from completed passes. Every choice was made on matches 1 and 2;
match 3 was added afterwards as a hold-out and confirmed them (end of this section).

- **Data:** Metrica Sports' public sample matches 1, 2 and 3
  (https://github.com/metrica-sports/sample-data): anonymised tracking at 25 fps for both teams
  and the ball, and an event list (match 3 in FIFA EPTS format with JSON events; its players are
  indexed by identity because substitutions move them between slots, and its `CARRY` events are
  ignored so that the label rules are the same on all three). Downloaded by
  `external/sample.py`; not redistributed here.
- **Labels (derived by our code, nobody labelled anything by hand for this project):** `D` where
  the tracking has no ball position and that blank run leads to a set-piece event or lasts at
  least 4 s; otherwise the team of the most recent on-ball event. The events themselves were
  annotated by Metrica. Our H/A rule is not Metrica's possession signal and is more fragmented
  than the competition's appears to be (mean possession 9 s), so every result is also computed
  with possessions of up to 1.5 s and up to 3 s between two possessions of the other team merged
  away.
- **Degradation (`external/corrupt.py`):** the clean tracking is made to resemble the ATD: the
  ball smoothed over a second, lost in long stretches (7 % of live frames, starting before and
  ending after stoppages), shown rolling on or placed during part of the stoppages, 7 % of
  player positions removed in tracklets, automatic-looking set-piece tags for 60 % of restarts.
  Strike rate, ball-speed distribution and control share of the degraded matches are close to
  the target's. No whistle is simulated.

What it showed, averaged over two matches and six degradation variants:

| question | result |
|---|---|
| pipeline before this check | spellF1 0.46 (raw labels), 0.54 (≤ 1.5 s merged), 0.59 (≤ 3 s merged); macroF1 0.84 |
| pipeline with completed passes | 0.47, 0.55, 0.60 |
| pipeline with receptions held | 0.48, 0.56, 0.61 |
| pipeline as submitted (also restart owner) | 0.48, 0.56, 0.61 (+0.003 to +0.004) |
| walking-speed threshold | flat from 1.2 to 1.4 m/s; 1.4 kept |
| dead prior, cost of entering / leaving `D` | current values at or next to the best |
| set-piece bonus, restart support, carry, 2 s lead | each helps slightly (+0.003 to +0.009) |
| control radius and gate | near-flat around 2 m and 4 m/s |
| H ↔ A switch cost | best at 3–4 on raw labels, flat 4–8 with ≤ 1.5 s merged, flat 8–16 with ≤ 3 s merged, 16–24 with the definition-following labels (below); 12 kept |
| **where the loss is** | with the true dead/alive and our teams: 0.51–0.65; with our dead/alive and the true teams: 0.83–0.87 |

So on these matches dead-ball detection is already good (82–88 of 93–98 stoppages found; the
missed ones are about 4 s long), and the error is in the team: half of the possessions under 4 s
show no control evidence at all, because an interception, a clearance or a first-time pass never
has the ball travelling with a player.

**Single touches, tried and switched off.** Crediting every touch to the clearly nearest
player's team (92–93 % correct on the sample matches) gains about 0.02 spellF1 where brief
possessions are labelled and nothing where they are not, so it fails the "good under all three
labellings" rule. It also contradicts the definition (a simple touch, or a deflection that does
not intercept the pass, is not a change). The same reasoning kept the switch cost at 12.

**Completed passes, kept.** Two consecutive touches by the same team gain under all three
labellings (+0.010, +0.009, +0.007 at weight 8; the worst variant improves as well) and leave
the possession count almost unchanged. This is the one change the external check produced. On
the competition match it adds 8 possessions (208 → 216).

**Labels that follow the definition (`sample.controlled`).** The bracket above (raw labels,
brief possessions merged) is crude. CHALLENGE.md's proxies for *controlled* possession are a
player keeping the ball for a few seconds, or completed passes. In these labels a run of the
event-derived labels changes possession only if the new team completes a pass in it (a Metrica
`PASS` is a completed pass) or has the ball for at least 3 s (from the start of the run to the
start of its last action in it); otherwise it stays with the previous team. A run that follows
a stoppage keeps its team. Lenient reading: 1 pass; strict reading ("more than two consecutive
passes"): 3. Mean possession 16.5–17.3 s (lenient) and 19.4–21.6 s (strict), against 9.3 s raw
and 14.1–14.2 s with up to 3 s merged.

| switch cost | raw | ≤ 1.5 s merged | ≤ 3 s merged | controlled, 1 pass or 3 s | controlled, 3 passes or 3 s |
|---|---|---|---|---|---|
| 12 (submitted) | 0.471 | 0.549 | 0.601 | 0.646 | 0.623 |
| 16 | 0.456 | 0.537 | 0.602 | 0.656 | 0.648 |
| 20 | 0.446 | 0.527 | 0.597 | 0.658 | 0.658 |

The labellings that follow the definition favour a higher switch cost (16–24); those that count
brief recoveries, which the definition excludes, favour a lower one. On the competition match a
cost of 16 gives 184 possessions (mean 17.5 s) instead of 216, the same attacking-transition
recall (11 of 24 tags), 101 stoppages instead of 97 and 7 possessions over a minute instead of 3.
**Possessions of 4–8 s, the weakest band.** Of the true possessions of 4–8 s on matches 1–2 the
decoder finds about two thirds; the ones it misses carry almost no team evidence of any kind
(median net evidence 2.5 frames of control, against 31 for those found; under one credited touch
on average). They are mostly invisible in tracking of this kind. "Receptions held" (above) is the
one addition aimed at them; chains of three touches were not tried, as there is almost nothing
to chain.

**Tried and dropped: an evidence-dependent switch cost.** A change of possession costing 16, or
8 when the new team completes a pass within a few seconds of it, was meant to keep the
higher cost's removal of weakly supported changes without losing controlled ones. It matched
cost 12 under the brief-recovery labellings but recovered only about a quarter of cost 16's
gain under the controlled ones (0.650 / 0.630 against 0.656 / 0.648); the changes a higher
cost removes are not told apart by a following pass. Since 12 and 16 tie under the labelling
closest to the public window (≤ 3 s merged), the submission keeps 12.

**Hold-out match (sample match 3).** Loaded after all the choices above were made and used
only to check them (`EXTERNAL_GAMES=3`). Its labels look like those of matches 1–2 (408
possessions, mean 9.6 s; 104 stoppages, median 12.2 s; dead share 0.32).

| spellF1 | raw | ≤ 1.5 s merged | ≤ 3 s merged | controlled, 1 pass | controlled, 3 passes |
|---|---|---|---|---|---|
| matches 1–2 (calibration) | 0.471 | 0.549 | 0.601 | 0.646 | 0.623 |
| match 3 (hold-out), before receptions held | 0.488 | 0.555 | 0.616 | 0.650 | 0.632 |
| match 3, with receptions held | 0.496 | 0.563 | 0.621 | 0.659 | 0.636 |
| match 3, as submitted (also restart owner) | 0.500 | 0.568 | 0.622 | 0.660 | 0.636 |
| match 3 without completed passes | 0.480 | 0.545 | 0.610 | 0.641 | 0.635 |
| match 3, switch cost 8 / 16 | 0.500 / 0.476 | 0.562 / 0.545 | 0.616 / 0.619 | 0.649 / 0.650 | 0.618 / 0.644 |

The pipeline does not score worse on the match it was not chosen on; completed passes help
under the three original labellings (+0.006 to +0.009); the switch cost shows the same pattern
as on matches 1–2, and the gain of a cost of 16 under the lenient controlled labelling does not
carry over (flat 0.649–0.650), which supports keeping 12.

**A harsher simulator: the ball drawn straight between contacts (`INTERP=1`).** On this
match the ball runs in straight lines between contacts, which smoothing a real trajectory does
not reproduce. With the simulated ball redrawn that way (contacts taken from the events, a
quarter of them left out), completed passes (+0.002 to +0.007) and receptions held (+0.000 to
+0.007) still help under every labelling. A contact detector looking for turns in the ball's
straight path, tried on it, found an own-team contact in few more missed short possessions than
the existing touch detector (7 % of those under 4 s, 18 % of those of 4–8 s) and was dropped.

The simulation's limits: no team mislabelled on a track, labels that count every brief recovery, and
stoppages that are easier to see than on the target (the ball is blank through most of them).

## Robustness

`python solution/sensitivity.py` scales each prior by 0.7 and 1.3. Most leave over 98 % of graded
frames unchanged. The ones that matter:

| constant | possessions (×0.7 / default / ×1.3) | dead share |
|---|---|---|
| H ↔ A switch cost | 246 / 218 / 192 | ≈ 0.49 |
| control radius | 188 / 218 / 233 | ≈ 0.49 |
| control gate | 183 / 218 / 236 | ≈ 0.49 |
| collective walking speed | 216 / 218 / 212 | **0.42 / 0.49 / 0.55** |

The weights of completed passes and of receptions held move almost nothing (±30 % changes at
most 0.1 % of frames).

The number of possessions and the dead share are the two quantities `spellF1` depends on most, and
neither can be pinned down without labels. The walking-speed threshold is the most fragile prior:
a 30 % change moves 5–10 % of frames between dead and alive. The default dead share (0.49,
including the 2 minutes graded before the second-half kick-off and four goal stoppages) is in the
range of typical effective playing time. On the labelled other matches the score is flat for a
threshold between 1.2 and 1.4 m/s, so this fragility in the dead share costs little in spellF1.

## Assets

| asset | used | how |
|---|---|---|
| tactical ATD | yes | everything above |
| Smart Tagging | yes, weakly | set-piece starts as stoppage evidence; set-piece team at the matching restart; kick-off windows; validation instruments |
| tactical homography | no | the ATD is already in pitch coordinates |
| tactical video | audio only | referee whistles (above); the pictures are not used |
| broadcast ATD | analysis only | aligned to the tactical timeline; tried as extra team evidence and dropped (below) |
| broadcast video and homography | no | |

Tried and dropped:

- **Smart Tagging phase teams as an H/A prior.** They agree with the team in possession only about
  75–80 % of live frames because a phase spans several possessions. Kept as a validation instrument.
- **Nearest-player evidence with a ball-speed cut-off**, replaced by control evidence (above).
- **Counting strikes in a ±4 s window** as live-play evidence. It blurred every stoppage boundary
  by up to 4 s; replaced by the interval between consecutive strikes.
- **Dating a change of possession back to the new team's arrival at the ball.** It moved changes
  by a median of 4 frames; not worth the extra rule.
- **The broadcast tracking as a second view (`broadcast.py`).** A live TV feed runs in real time,
  so the broadcast timeline maps to the tactical one by one constant offset per half. Matching
  the two ball tracks in 5-minute windows finds it without ambiguity (median ball distance
  0.7–1.3 m at the best lag, 17–23 m at any other) and to the frame, constant within each half
  to ±1 frame. With it, 89 % of live frames have a broadcast picture whose players lie on the
  tactical ones (replays and close-ups do not). Where the tactical ball is missing (7.5 % of
  live frames) the broadcast sees it on 43 %; where the tactical control evidence is empty, the
  broadcast has strong evidence on 3.9 % of live frames. Used only there, as a fill-in, it made
  things worse by the label-free reversal test: the 18 changes it added reverse like random
  frames (implied about 4 % real) and the 6 it removed reverse more strongly than those kept.
  Where one camera loses the ball the other is often wrong too. Dropped; it cannot be checked
  on the external matches, which have no broadcast.

## Training data and use of the public ground truth

No model is trained and no parameter was fitted or searched against any ground truth of the
competition match. One weight was chosen on labelled data from other matches (below).

**External labelled data:** Metrica Sports' public sample matches 1, 2 and 3 (tracking
and events, published by Metrica; the events were annotated by Metrica, the frame labels were
derived from them by `external/sample.py`). They were used to check the pipeline, as described
under "Check on other matches"; match 3 only as a hold-out. The parameters were swept there; the existing ones were kept
and one new evidence term (completed passes, weight 8) was chosen there, as a value that is
good under all three label conventions and all degradation variants.

**IDSSE** (Bassek et al., Scientific Data 2025; seven Bundesliga / 2. Bundesliga matches,
CC BY 4.0): inspected only. The provider's per-frame possession flag was read on an 11-minute
slice of one match (45 possessions, mean 10.1 s, some under 1 s) to see how a tracking provider
labels brief possessions. Nothing from it is used by the model.

**Public 5-minute ground truth:** used to check frame alignment and label meaning, and its
segments were read next to the predictions while developing, to understand failure modes (a pass
travelling past an opponent, a stoppage found late, a long pass in transit past opponents,
a brief touch that the ground truth does not count as a possession). Design changes were
motivated by those mechanisms and by the ground-truth-free instruments above; constants are
round-number priors. The public score was looked at after each change but is too noisy
(17 possessions) to choose between versions, and no constant was fitted to it.

## Limitations

- **Changes of possession are dated 1–2 s off in duels and one-touch wins.** A pressing opponent
  moving with the ball looks like control before they have it; a ball won with a first-time pass
  shows no control until the team-mate receives it.
- **Short possessions (under ~1 s of control) are not detected**, by design of the switch cost.
- **The switch cost depends on a labelling convention we cannot observe.** Labels that count
  every brief recovery favour a lower cost; labels that follow the definition of controlled
  possession favour a higher one (16–24). The submitted 12 sits between them.
- **The ball track is interpolated between contacts.** Paths between touches are straight
  (median deviation under 0.6 m even over 25–40 m), so a ball in the air is drawn as a line on
  the ground and nothing in the track says who won a header.
- **Short stoppages with the ball unseen** depend on the players visibly slowing down or on a
  whistle; quick throw-ins have neither.
- **The whistle is missed under a loud crowd** (the half-time whistle is not detected), and four
  whistles in live play are followed by no decoded stoppage.
- **Gentle restarts** (kick-off taps, short free kicks) can be dated late or early by 1–3 s.
- The untracked or mis-teamed player on the ball cannot be recovered from the ATD alone; a ball
  and player detector on the video would be the next step.
