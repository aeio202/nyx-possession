# Brief (v2, 2026-11-12): ideas wanted to improve a football possession-labelling system

## What I am asking you for

I am competing in a data challenge with a working, validated solution and about four days left.
I want **ideas to improve its accuracy, not code**. Several rounds of plausible ideas have already
been tried; section 9 lists them with the measured outcome, so please do not re-propose those
unless you can say what was wrong with the test.

The most useful answers will:

- name a concrete mechanism (what signal, computed from what, and why it separates the cases);
- say which remaining weakness it targets (section 8) and roughly how many events it could fix;
- say how I could tell whether it helped **without ground truth on this match** (section 6);
- respect the rules (section 4) and fit in a few days on a laptop CPU.

Rank ideas by expected gain against effort, and give your confidence. If you think part of the
design or of my reasoning is wrong, say so. Be specific: "use machine learning" is not an idea;
"train X on Y with target Z, validate by W" is.

## 1. The task

One professional football match (FC Barcelona vs Athletic Club, LaLiga 2024-25). For each of the
199,319 frames of a wide-angle "tactical" video at 25 fps, output one label:

| label | meaning |
|---|---|
| `H` | home team in possession, ball in play |
| `A` | away team in possession, ball in play |
| `D` | dead ball (out, foul, before a restart) |
| `X` | abstain (forward-filled with the previous label before scoring, so useless) |

158,857 frames are graded (the two halves). The ground truth is private, derived mechanically from
**corrected** tracking: `D` where the corrected tracking marks the ball dead, otherwise the team
it names as owning the ball.

The organisers' definition:

- While the ball is in play exactly one team has possession; no "contested" state.
- Possession changes when the other team gains **controlled** possession. Suggested proxies: a
  player keeps the ball for a few seconds; a team completes more than two consecutive passes.
- Not a change: a simple touch without control; a deflection that does not intercept a pass; an
  aerial duel won without subsequent control.
- While the ball is loose, possession stays with the last team.

Only 5 minutes of ground truth are public: 17 possessions (0.76 s to 42 s, mean 14.2 s) and 4
stoppages. It may be used to check the pipeline, **not to tune it**.

## 2. The metric, and what it rewards (checked by running the official scorer on synthetic cases)

**spellF1**: a possession is a maximal run of `H` or of `A` (a stoppage splits it). Predicted
possessions are matched one-to-one to true ones of the same team by temporal IoU; the F1 of the
matching is averaged over IoU thresholds 0.3–0.7. Tie-break: per-frame macro-F1 over H/A/D.

- A missed possession and a false one cost the same.
- Whether an event exists matters far more than its timing: 1–3 s timing errors cost little.
- A missed stoppage costs only when the same team has the ball on both sides of it.
- One false change of possession inside a long true possession destroys that possession and adds
  false ones.

Organisers' baseline on the full match: spellF1 0.243. They say differences under ~0.04 on the
full match are noise.

## 3. The data

All automatic and uncorrected.

- **Tracking (ATD)** per frame: positions and speeds of up to 46 track slots (tracklets with a
  team, no identity, no roles; about 20.5 tracked at a time) and the ball, in metres.
- **The ball**: tracked on about 92.5 % of live frames (and on part of the dead frames: a ball
  rolling on, or placed for the restart). Gaps under ~3 s essentially do not occur; losses are
  long. The track is smoothed (a kick appears as a ~1 s speed ramp) and, crucially, **interpolated
  between contacts**: paths between consecutive touches are straight lines (median maximum
  deviation 0.4–0.55 m even for 25–40 m passes) and bow to neither side. So an aerial ball is
  drawn as a straight ground line, and nothing in the track says who won a header.
- **Smart Tagging**: 638 automatic intervals. Phases with a team (Build Up, Progression, Attacking
  Transition, Defending in X Third, ...), which agree with the team in possession on only ~75–80 %
  of live frames because a phase spans several possessions; 59 set pieces (throw-ins have no
  team), whose tag opens 2–12 s before the restart.
- **Audio** of the tactical video (stadium sound, quiet).
- **Homography** per frame, the tactical video itself, and a **broadcast recording** with its own
  tracking (see section 9 for what it turned out to be worth).

## 4. Rules

- Labels must come from an algorithm. No hand labelling or correction of this match, for any
  purpose; no constants tied to specific frames of this match.
- No private ground truth and no human-produced data about this match (event data, corrected
  tracking, annotations).
- Human-labelled data about **other** matches is allowed and must be documented.
- The public 5 minutes are not a tuning set.
- The submission must be regenerated exactly by a public repository (deterministic pipeline).
- Practical: one laptop (CPU), Python with numpy/pandas; about four days.

## 5. The current system

A three-state (H/A/D) Viterbi decoder per half over hand-set per-frame scores, with per-frame
transition costs. No training; every constant is a round-number prior in metres, seconds or m/s.

**H versus A evidence**, positive for home:

- *Control*: `closeness(ball-player distance, midpoint 2 m) × slowness(|v_ball − v_player|,
  midpoint 4 m/s)`, best home player minus best away player, in [−1, 1] per frame. A ball close
  to a player and moving with them counts; a pass going past an opponent does not.
- *Completed passes*: a "touch" is a sharp change of ball velocity (> 6 m/s across ±0.3 s,
  direction included), credited to a team when one of its players is within 3 m and at least 1 m
  nearer than any opponent. Two consecutive touches by the same team within 5 s add evidence worth
  8 frames of full control, spread over the pass.
- *Receptions held*: a touch credited to a team after which that team holds the ball (control >
  0.5 on at least 0.5 s within 2 s) adds 8 frames' worth from the touch to the end of the hold.
- Single touches add nothing (the definition excludes them).
- With no evidence, the previous team is kept (ties broken towards the latest change).

**Dead versus alive evidence** (log-odds, deliberately small, ~0.1 per frame): ball beyond a line
(+1.0); collective player speed below 1.4 m/s read 2 s ahead; ball unseen > 3 s; ball at rest in
view inside a long interval (≥ 6 s) between ball strikes; recent strikes and carries (alive); fast
ball (alive); unattended resting ball; set-piece tag start; restart support after a detected
restart kick.

**Transition costs**: H↔A 12 (a short possession by the other team pays it twice, so it needs
about half a second of sole control). Alive→dead 25, lowered to 10 when all players decelerate
together, to 3 on the frame the ball crosses a line, and to 3 around a **referee whistle detected
in the audio** (two simultaneous tones at ~3.8 and ~4.25 kHz; 70 blasts). Dead→alive 20, 3 on a
clear restart kick. Before each half's tagged kick-off (released by the kick-off whistle) the
state is forced to `D`.

**Output on the full match**: 218 possessions (mean 14.9 s, median 9.9 s), 97 stoppages, dead
share 0.489. Public window: spellF1 0.61 (bootstrap 5–95 % 0.44–0.79), macro-F1 0.90; the best
organiser baseline scores 0.42 there. Runs in a few seconds (plus a one-off audio pass).

## 6. How I validate without ground truth

1. **External labelled matches** (Metrica Sports' three public sample matches: clean tracking and
   human-annotated events). Frame labels are derived from the events by my own rules; the clean
   tracking is degraded to resemble mine (ball smoothed over 1 s, lost in long stretches on 7 %
   of live frames, shown rolling on or placed in part of the stoppages, players dropped in
   tracklets, automatic-looking set-piece tags). Unlabelled statistics of the degraded matches
   (strike rate, ball-speed quartiles, control share) are close to mine. **The labelling
   convention is unknowable**, so every result is computed under five labellings: raw
   (every recovery is a possession, mean 9.3 s), brief possessions ≤ 1.5 s / ≤ 3 s merged into the
   surrounding team (mean ~14 s with 3 s), and two that follow the definition (a change needs a
   completed pass, or 3 passes, or 3 s on the ball; mean 17–22 s). Matches 1–2 are used for
   choices; match 3 is a hold-out checked once per choice. Current scores (spellF1, five
   labellings): matches 1–2: 0.48 / 0.56 / 0.61 / 0.65 / 0.62; match 3: 0.50 / 0.56 / 0.62 /
   0.66 / 0.64. macro-F1 0.84–0.88.
2. **Collective-reversal test** (label-free, on the real match): after a real change of possession
   both teams' mean velocity turns towards the new possessor's attacking goal within ~2 s. On the
   external matches it separates real from false decoded changes (1.62 vs 0.19 m/s, AUC 0.75 per
   change) and recovers the real share of a set of changes. Limits: it also fires for brief real
   recoveries (it sees "the ball changed hands", not "controlled"), and on the real match its
   signal is weaker, so sets of < ~50 changes give intervals of ±0.4.
3. **Smart Tagging** agreement (team tags; biased towards smoother outputs), set-piece audit
   (47 of 58 tagged restarts have a decoded restart within [−2, +12] s), attacking-transition
   tags, referee whistles vs decoded stoppages, plausibility (dead share, no possession > 1 min).
4. Sensitivity of every prior to ±30 %.

## 7. What I now know (the findings that set the priorities)

1. **Dead-ball detection is near its ceiling; the error is in the team.** On the external
   matches: true dead/alive with my teams scores 0.51–0.65; my dead/alive with the true teams
   0.83–0.87. 82–88 of 93–98 stoppages are found; missed ones are ~4 s long.
2. **Short possessions are mostly invisible.** Half the true possessions under 4 s show no control
   evidence at all (interceptions, clearances, first-time passes never have the ball travelling
   with a player). Of true possessions of 4–8 s, a third are missed, and the missed ones carry
   almost no evidence of any kind: median net evidence 2.5 frames-of-control (31 for found ones),
   under one credited touch on average, a completed pass in only 19 %.
3. **The switch cost depends on the labelling convention, which I cannot observe.** Labels that
   count every brief recovery favour a cost of 3–8; labels that follow the definition favour
   16–24; the ≤ 3 s merged labelling (closest to the public sample's mean of 14.2 s) is flat
   8–16. On the hold-out match the lenient definition-following labelling is flat 8–16 as well.
   12 is kept.
4. **The public window**: its 7 unmatched true possessions are all short (0.8–3.5 s), plus the long
   possessions they split. So the organisers do label some brief possessions.

## 8. Remaining weaknesses

1. **Short possessions (< ~4 s) and a third of the 4–8 s ones** are not detected: no evidence.
2. **Timing of changes** in duels (a pressing opponent moving with the ball looks like control
   early) and after first-time passes (no control until the team-mate receives).
3. **The player on the ball is sometimes untracked or on a mislabelled tracklet.**
4. **Aerial play**: the ball is a straight interpolated line; headers and long balls are guessed.
5. Small items: 4 artefact stoppages (ball tracked beyond a line and straight back, 0.7–2.2 s),
   gentle restarts dated late, the half-time whistle missed under crowd noise.

## 9. Tried and dropped (with the measured reason)

- **Single-touch evidence** (weight 3) and a **lower switch cost (8)**: gain only under labellings
  that count brief recoveries; on the public window they added two false possessions.
- **Evidence-dependent switch cost** (16, or 8 when the new team completes a pass soon after):
  kept cost 12's scores under the brief labellings but recovered only a quarter of cost 16's
  gain under the definition-following ones. A following pass does not identify the changes a
  higher cost removes.
- **Chains of three touches**: not tried; missed possessions have under one touch on average.
- **Airborne-ball projection model** (detect/simulate an aerial ball drawn at the wrong ground
  position): refuted; the track is interpolated, not mis-projected.
- **Broadcast tracking as a second view.** It aligns to the tactical timeline by one constant
  offset per half, to the frame. It shows the live picture on 89 % of live frames; where my ball
  is missing it sees the ball on 43 %. Used as control evidence where mine is empty (3.9 % of
  live frames), it made things worse by the reversal test (the changes it added behaved like
  random moments, those it removed like real changes): where one camera loses the ball, the
  other is often wrong too.
- **Phase tags pooled as an H/A prior**: too noisy (75–80 %). Per-tag reliability measured; not used.
- Dead-ball variants: neutral zone between strikes, quiet bonus for an unseen ball, set-piece tag
  as exact restart time, two rules against the artefact stoppages (each deleted real stoppages),
  whistle as dead evidence (too few cases to judge), strikes counted in a ±4 s window.
- **Dating a change back to the new team's arrival at the ball**: moved changes by ~4 frames.
- **Estimating likelihoods from the decoder's own output**: circular.

## 10. Directions not yet tried

- Ball detection in the tactical video (heavy; must run locally; multi-day).
- Team shape and collective movement as H/A evidence when the ball is unseen (only ~7.5 % of live
  frames have no ball, so limited reach).
- A learned model (e.g. a gradient-boosted frame or segment classifier) trained on the degraded
  external matches and applied here, instead of hand-set scores. Concern: domain gap, and only
  three matches.
- Using the broadcast for dead-ball evidence (cuts, replays): dead ball is already near its ceiling.

## 11. Questions

1. Given finding 2, **is there any signal in tracking of this kind (automatic, ball interpolated
   between contacts, no player identities) that reveals brief possessions**: interceptions,
   clearances, first-time passes, headers? For instance from the movement of the players around
   the ball rather than from the ball itself.
2. Is there a **principled way to choose between labelling conventions** (and so the switch cost)
   from what I can observe: the organisers' wording, the public sample's statistics (17
   possessions, mean 14.2 s, shortest 0.76 s), the external matches?
3. Under the metric, is there a **decoding strategy that raises expected spellF1 when I am
   uncertain** whether a brief possession exists (e.g. insert it only under certain geometric
   conditions, or prefer a particular boundary placement)?
4. Would a **learned model trained on the degraded external matches** beat hand-set scores, given
   three matches and the domain gap? How would you set it up and check it?
5. Is there a **better label-free check** on the real match than the reversal test and the tags,
   especially one that distinguishes a controlled possession from a brief touch?
6. Is anything in my reasoning, validation or use of the external data **wrong or biased**?
7. **Anything else.** The questions above are where I see the problem, but I may be looking in the
   wrong place. If you have any other idea that could improve accuracy, about the data, the
   model, the decoding, the validation, or something I have not thought of, please suggest it,
   even if it does not fit any question here.

Please answer with ideas and reasoning only, not code.
