# History: what was tried and what was learned

Chronological. Public-window scores are quoted for the record only: 17 possessions, one possession
moves spellF1 by about 6 points, so they cannot rank versions (see `WORKING_RULES.md`).

## Facts about the data discovered along the way

- **The ATD ball track is smoothed and interpolated.** A pass leaving the foot at 15 m/s appears as
  a speed ramp of about one second; no frame-to-frame jump exists. Gaps shorter than ~3 s
  essentially do not occur: the ball is either tracked or lost for a long stretch. The raw ball
  speed field is NaN on ~89 % of frames, so speed is derived from positions.
- **Ball unseen is not the same as dead.** In the public window the ball is unseen for up to 9 s of
  live play (crowded attacks), and clearly tracked through whole stoppages.
- ~~Airborne balls are projected onto the ground at the wrong place~~ **(wrong — refuted on 2026-11-11, see the last entry)**, so the nearest player to an
  aerial ball is often the wrong one.
- **Collective player speed separates dead from alive well** (3 s mean of all tracked players:
  median ≈ 1.2 m/s dead, 2.0–2.4 m/s alive in the public window), but players need 2–3 s to slow
  down after a whistle.
- **Smart Tagging set-piece intervals are 35 s long** (5 s for kick-offs) and open a few seconds
  *before* the restart (3.3 s and 3.5 s for the two kick-offs published in the docs; up to ~12 s
  for a free kick). Most of the interval is the live play that follows.
- **Smart Tagging phase team tags agree with possession only ~70–80 %** of live frames; a phase
  spans several possessions. All 26 throw-ins have team `N/A`.
- **Every stoppage over two minutes** falls inside a `GOALS` tag and ends at the kick-off after it.
- Track slots: 24 home, 22 away; slots are tracklets, not players.
- The second half is graded from frame 110,808 but kicks off at 113,742 (published): those frames
  are all `D`.

## Versions

| version | change | possessions | dead share | public spellF1 / macroF1 |
|---|---|---|---|---|
| baselines | nearest player + majority vote (organisers) | — | — | 0.04–0.42 / 0.58–0.62 |
| v1 | Viterbi H/A/D: nearest-player evidence, dead from walking speed / ball out / ball missing | 313 | 0.37 | 0.47 / 0.70 |
| v2–v4 | per-frame transition costs: cheap entry to D when the ball crosses a line, cheap exit on a restart kick; dead evidence rescaled to ~0.1 per frame | 190 | 0.57 | 0.49 / 0.81 |
| v5–v6 | strike detectors rewritten for the smoothed ball (compare speed with the peak over the next second); strike count in ±4 s as live evidence | 232 | 0.52 | 0.51 / 0.86 |
| v7–v9 | restart kick located at the start of the speed ramp; "restart support" for 4 s after a restart that is followed by another strike within 5 s; whistle signature (collective deceleration) | 257 | 0.50 | 0.52 / 0.87 |
| **current** | control evidence (closeness × low relative velocity) replaces nearest player; late tie-breaking; set-piece bonus only around the tag start; inter-strike interval replaces the ±4 s count; carried ball = live; player speed read 2 s ahead | 202 | 0.49 | 0.61 / 0.90 |

## What worked, with the evidence

- **Transition costs that depend on events.** Stoppages begin with the ball crossing a line or a
  whistle and end with a strike; making those frames cheap to switch on fixes boundary timing far
  better than more per-frame evidence does.
- **Control evidence instead of nearest player.** Under the nearest-player rule, evidence taken
  with the ball above 6 m/s contradicted the decoded team 9–37 % of the time (2–4 % for a slow
  ball). After the change, agreement with the team tags rose from 0.758 to 0.801; on the 4,974
  frames where the versions differ the tags side with the new one 77 % of the time, and still
  57–63 % with the possession count matched.
- **Set-piece bonus moved to the tag start, inter-strike interval, carry, 2 s lead on player
  speed.** Tagged set pieces with a decoded restart nearby: 39 → 46 of 58; with no stoppage near:
  6 → 1.
- **Requiring a follow-up strike after a restart** stopped the ball being knocked to the free-kick
  taker from counting as the restart.

## What did not work or was dropped

- **Phase team tags as an H/A prior** (all codes pooled): too noisy. Per-code reliability is
  untested — see `STATUS.md`, idea 1.
- **Quiet bonus while the ball is unseen**: double counts with the missing-ball bonus (an unseen
  ball cannot show strikes) and produced a false stoppage during a 9 s unseen attack.
- **Neutral zone for 3–6 s between strikes**: slow build-up after a restart then looked dead and
  restarts were found up to 7 s late. Replaced by a malus fading from 3 s to 6 s, plus a 2 s halo
  after every strike.
- **Dating a change back to the new team's arrival at the ball**: moved changes by a median of
  4 frames; removed.
- **Using set-piece tag starts as exact restart times**: the lead is not constant (2–12 s).
- **`missing_onset`** has no effect (gaps under 3 s do not occur); kept only for clarity.

## Dead ends worth knowing about

- Tuning anything against the public window: the organisers show it picks the wrong smoothing
  window even for the baseline.
- Estimating dead/alive likelihoods from the decode itself (Viterbi-training style) is circular:
  features the decoder did not use look uninformative by construction.

## 2026-11-11 — external reviews and step 0 of `PLAN.md`

- Two external LLM reviews (`LLMs/`) were assessed in `PLAN.md`. The official scorer was run on
  synthetic sequences (`metric_cases.py`): a missed event and a false one cost the same; the
  existence of an event matters far more than its timing; a missed stoppage costs only when the
  same team has the ball on both sides.
- Audits added (`audit.py`, `tag_reliability.py`, `test_decoder.py`). Findings are listed under
  step 0 in `PLAN.md`. The submission did not change.
- **Tried and reverted:** two rules against four artefact stoppages of 0.7–2.2 s (ball tracked
  beyond a line and straight back). Discarding line crossings that return inside within 2.5 s,
  and blocking cheap restarts for 3 s after a crossing, each deleted real stoppages that have a
  tagged throw-in. A ball that leaves the pitch often bounces back in or crosses the line again
  while being returned.

## 2026-11-11 — step 1: referee whistle from the audio (kept)

- Both videos have an AAC audio track. The tactical one is real stadium sound, very quiet
  (RMS about 43 on a 16-bit scale) with a spectrum falling ~25 dB from 1 to 5 kHz.
- **First attempts failed and why:** (1) "strongest narrow peak in 2–5 kHz" is dominated by the
  spectral tilt and by spectators whistling around 3 kHz; those tones sit inside stoppages and
  before restarts, not at stoppage starts (6 % against 10 % by chance). (2) Requiring a stable
  pitch rejects the referee, whose whistle has two tones.
- **What worked:** looking at the four moments where a whistle is certain showed peaks of
  30–37 dB at ~3.9 and ~4.27 kHz. Over the whole recording, pairs of simultaneous strong tones
  cluster at 3.8 / 4.25 kHz, 400–500 Hz apart. Detector: two simultaneous tones in 3.4–4.7 kHz
  (20 dB and 12 dB over the neighbouring bands), 300–600 Hz apart, at least 0.1 s. 70 blasts.
- **Strictness:** looser thresholds (down to 12 / 8 dB) give up to 284 occasions whose relation
  to stoppages falls to chance. The strict setting is kept.
- **Reproducibility:** with 16-bit decoding at 16 kHz, +/-1 unit of noise changed the detections
  (68 → 70 → 63 blasts). Decoding to 32-bit float at the native 48 kHz, first channel, no
  resampling, makes them identical under noise of 1e-3 x RMS. The decoded audio (1.5 GB) is
  deleted after detection; only the blast list is cached.
- **Use:** entering `D` costs 3 around a blast; play in a half cannot start before the kick-off
  whistle. A variant that also treated gentle ball movement after a "release" whistle as a
  restart changed almost nothing and was not kept. Adding dead evidence after a whistle was
  rejected without trying: the four whistles with no stoppage near them are too few to judge,
  so it would risk four false stoppages to gain at most four.
- **Effect:** ~1 % of graded frames change; same-team stoppages 47 → 51; tagged set pieces with a
  restart found 46 → 47; whistles in live play with the decoder dead within 3 s: 5 → 10 of 15;
  second-half kick-off −82 → +32 frames. Public window unchanged (spellF1 0.61).
- **Honest size of the gain:** small, probably around +0.01 spellF1. The decoder had already
  found a stoppage at 43 of 58 whistles, so the audio mostly confirms it. Its lasting value is
  as an independent check on dead-ball detection (`audit.py`, last line).

## 2026-11-11 — step 3: check on other matches (no parameter changed)

- Downloaded Metrica's public sample matches 1 and 2 into `external/data/` (gitignored). In
  these files the ball position is blank while the ball is dead, the same convention the
  competition describes; 60–70 short blank runs per match are an untracked ball in live play and
  are not stoppages. Labels: `external/sample.py`. About 370 possessions (mean 9 s) and 95
  stoppages (median 17–21 s) per match, 24–29 of them with the same team on both sides.
- Built a degradation model (`external/corrupt.py`) and a scoring harness
  (`external/calibrate.py`). Unlabelled statistics of the degraded matches are close to the
  target's (strikes per live minute 11–16 vs 15; ball-speed quartiles; control share).
- **Bug found by the sample data:** `set_piece_mask` wrapped around when a tag started before
  frame 0 and marked the whole match. Fixed; no effect on the competition output.
- **Priors that hold:** walking speed (flat 1.2–1.4), dead prior and D transition costs, and
  every dead/alive component (each helps slightly). Control radius and gate are near-flat.
- **Where the loss is:** true dead/alive with our teams gives 0.51–0.65; our dead/alive with the
  true teams gives 0.83–0.87. Control evidence is right 95–99 % of the time when strong, but
  half of the possessions under 4 s show none.
- **Switch cost 8 and touch evidence (weight 3): tried on the competition output, reverted.**
  On the sample matches they gain 0.02–0.04 under fragmented labels and nothing under the
  labelling with possessions of up to 3 s merged. On the competition's public window they added
  two possessions, both false: a 3.6 s stretch where an airborne ball's projection passes away
  players (tracked ball 7 m from any home player while home has it), and a 1 s touch by an away
  player that the ground truth does not count. The simulation has neither artefact, and the
  competition's convention is stricter about brief involvement than our event-derived labels.
  Touch code is kept with weight 0.
- **Lesson:** external calibration validated the dead-ball side and the overall design, but
  cannot set the switch cost, because the answer depends on a labelling convention we cannot
  observe and on tracking artefacts the simulation lacks.

## 2026-11-11 — team evidence: airborne hypothesis refuted, completed passes kept

- **Correction of an earlier belief.** I had explained "tracked ball 7–8 m from the team that has
  it" by airborne balls being projected onto the wrong ground position, and blamed the false
  touch in the public window on it. Tested on the whole match: an airborne ball should bow away
  from the camera, always to the same side. Ball paths between consecutive touches are straight
  (median maximum deviation 0.4–0.55 m, including 25–40 m passes) and bow to either side equally
  (45–56 %). So **the ATD ball is interpolated between contacts** and there is no projection
  artefact to detect or simulate. The episode was a long pass in transit past away players, with
  an away deflection that did not win the ball. Items 1 and 2 of the team-evidence list (simulate
  and detect airborne flight) are void.
- **"Ball far from every player" is not a distinguishing statistic:** 15.6 % of live frames
  beyond 5 m on the target, 12–15 % on the degraded sample matches.
- **Single touches stay off.** They fail the all-conventions rule and the definition excludes
  them.
- **Completed passes kept** (`pass_weight` 8): two consecutive touches credited to the same team
  within 5 s add evidence over the pass. External matches: +0.010 / +0.009 / +0.007 under the
  three label conventions, worst variant up too, possession count nearly unchanged. Competition
  match: 208 → 216 possessions, public window unchanged (same 13 segments), audits unchanged.
  The team-tag instrument sides with the old version on 85 % of the 520 differing frames; it
  does that for every added possession (phases span short possessions), so it cannot judge this.
- **Why the switch cost stays at 12, stated without the airborne argument:** the documentation
  defines possession as controlled (a few seconds on the ball, or completed passes) and gives a
  mean possession of 14.2 s; under the sample labelling closest to that, the cost is flat from 8
  to 16.

## 2026-11-12 — collective-reversal test (instrument kept, no model change)

- `reversal.py`: at each direct H↔A change, mean x-velocity of each team's tracked players,
  signed towards the new possessor's attacking goal, mean over [+1 s, +3 s] minus mean over
  [−2 s, 0]. Windows fixed in advance, not tuned. Attack direction per half from mean positions.
- **External matches (target-like degradation, both games pooled):** real decoded changes
  1.62 m/s, false 0.19, AUC 0.75; random live frames −0.20. By length of the new possession:
  <2 s 0.39, 2–4 s 1.14, 4–8 s 1.31, >8 s 1.16. Mixing estimator (core changes = real, random
  frames = false) recovers the real share of the changes added/removed by the switch cost
  (cost 6 added 0.50 vs 0.48 actual; 8 added 0.40 vs 0.49; 16 removed 0.58 vs 0.57).
- **Competition match:** core 0.88 m/s (weaker than external 1.32), random −0.19. Implied real
  share: cost 6 added (47 changes) 0.42, cost 8 added (33) 0.47, cost 16 removed (36) 0.52; each
  5–95 % interval about 0.1–0.9. **Verdict: cannot place the switch cost** at this sample size;
  the point estimates near 0.5 on both sides are consistent with the flat 8–16 found externally.
  Submission unchanged.
- Side observation for "short possessions" work: at cost 12 the decoded possessions of 2–4 s
  start with a weak reversal (0.22 m/s, 25 changes, 48 % positive) against 1.07 for 4–8 s. They
  may be the least reliable band on the real match; small sample.

## 2026-11-12 — external labels that follow the definition (no model change yet)

- `sample.controlled()`: a run of the event-derived labels changes possession only if the new
  team completes `min_passes` passes in it or has the ball >= 3 s (run start to the start of its
  last action); otherwise it goes to the previous team (left to right). Runs after a stoppage
  keep their team. `calibrate.py` and `reversal.py external` take `CONTROLLED_PASSES=n`.
- Label statistics (games 1 / 2): possessions 205 / 204, mean 17.3 / 16.5 s (1 pass);
  165 / 173, 21.6 / 19.4 s (3 passes). Raw 382 / 363 (9.3 s); 3 s merged 250 / 239 (14.2 s).
- Current parameters: spellF1 0.646 (worst 0.610), predicted/true possessions 0.90 (1 pass);
  0.623 (3 passes). Switch-cost sweep, 1 pass: 4 0.587, 6 0.610, 8 0.628, 12 0.646, 16 0.656,
  20 0.658, 24 0.655, 32 0.642. 3 passes: 8 0.588, 12 0.623, 16 0.648, 20 0.658, 24 0.662.
  Same costs 12/16/20 under the old conventions: raw 0.471/0.456/0.446; 1.5 s merged
  0.549/0.537/0.527; 3 s merged 0.601/0.602/0.597.
- **Corrects the reversal test's reading.** Against these labels the changes removed at cost 16
  are 26 % real (57 % under raw labels), those removed at 20 32 %, added at 8 17 %; the
  instrument implies 54 %, 61 %, 36 %. It detects physical changes of hands, brief ones included,
  not control. AUC real vs false against these labels 0.72.
- **Candidate, not applied:** switch cost 16 on the competition match (built in the scratchpad,
  deleted): 184 possessions, mean 17.5 s, median 12.3 s; stoppages 97 → 101, dead share 0.489 →
  0.493; set pieces with a restart 47 of 58 (same); attacking-transition tags: 11 changes found
  (same); whistles in live play with decoder dead within 3 s 10/15 → 9/14; possessions over 60 s
  3 → 7. Team tags side with 16 on 69 % of 1,650 differing frames (biased towards smoother
  output, not evidence). Fails the "good under all conventions" rule (raw −0.015, 1.5 s −0.013)
  but those conventions count brief recoveries the definition excludes. Decision left to the
  user.
- **Proposed, not tried:** an evidence-dependent switch cost (high by default, discounted where
  the new team completes a pass soon after the change), to keep cost 16's removal of weakly
  supported changes without losing controlled ones. Plan and success test in `STATUS.md`,
  "Next session", item 4.

## 2026-11-12 — evidence-dependent switch cost (tried, failed its test, removed)

- Cost of a change to team k lowered from `switch_cost` to `switch_cost_pass` when k completes a
  pass (two consecutive touches by k within 5 s) whose first touch lies within [-2 s, +3 s] of
  the change. Success test fixed beforehand: match or beat cost 12 under raw and ≤1.5 s merged
  labels AND cost 16 under both controlled labellings; if it fails, keep 12.
- spellF1 on the external matches (raw / 1.5 s / 3 s / controlled 1 pass / 3 passes):
  plain 12: 0.471 / 0.549 / 0.601 / 0.646 / 0.623; plain 16: 0.456 / 0.537 / 0.602 / 0.656 /
  0.648; 16 with 8 when confirmed: 0.471 / 0.552 / 0.603 / 0.650 / 0.630; 16 with 12: 0.461 /
  0.541 / 0.603 / 0.655 / 0.644; 20 with 8: 0.460 / 0.541 / 0.598 / 0.651 / 0.640; 20 with 12:
  0.456 / 0.537 / 0.601 / 0.657 / 0.648.
- **Failed.** The best variant (16, 8 if confirmed) keeps cost 12's scores under the brief
  labellings but recovers only about a quarter of cost 16's gain under the controlled ones; the
  rest slide along the same trade-off. Its means are at or above plain 12 everywhere (by at most
  0.007), but its worst variant is lower under raw and controlled-1 labels: too small and
  inconsistent for a late change. The changes cost 16 removes are not told apart by a following
  pass, so 12 vs 16 is purely a question of the labelling convention. **Switch cost stays 12;
  open decision 5 closed.** Code removed; output verified byte-identical.

## 2026-11-12 — hold-out external match 3 (kept; no model change)

- `sample.py` reads match 3 (FIFA EPTS text + XML metadata + JSON events): players indexed by
  identity (substitutions move them between the 22 slots), events normalised to the game 1–2
  table (`event_table`), `CARRY` dropped so that the label rules are identical. Ball blank on
  32 % of frames; no event starts on a blank ball, so the blank-ball-is-dead rule holds.
  `calibrate.py` selects matches with `EXTERNAL_GAMES` (default 1,2). Refactor checked: games
  1–2 rebuilt from the raw files reproduce 0.4712 (raw, cost 12) and 0.6461 (controlled).
- Match 3 labels: 408 possessions, mean 9.6 s; 104 stoppages, median 12.2 s; dead share 0.32.
- Hold-out results with the submitted parameters (raw / 1.5 s / 3 s / controlled 1 / 3):
  0.488 / 0.555 / 0.616 / 0.650 / 0.632, macroF1 0.87 — at or above matches 1–2. Without
  completed passes: 0.480 / 0.545 / 0.610 / 0.641 / 0.635 (the pass evidence holds except under
  the strict 3-pass labelling, −0.003). Switch cost 8 / 12 / 16: raw 0.500 / 0.488 / 0.476;
  1.5 s 0.562 / 0.555 / 0.545; 3 s 0.616 / 0.616 / 0.619; controlled 1 0.649 / 0.650 / 0.650;
  controlled 3 0.618 / 0.632 / 0.644. Cost 16's +0.010 under controlled 1 on matches 1–2 does
  not carry over; supports keeping 12.
- Accident, harmless: the match 1–2 caches (`sample_game_*.npz`) were deleted by a clean-up
  command before the comparison could use them; they are derived files and were rebuilt from
  the raw downloads, and the reproduced scores show they are unchanged.

## 2026-11-12 — item 1, possessions of 4–8 s: reception held (candidate, awaiting the user)

- **Diagnostic first** (matches 1–2, target-like): of 130 true possessions of 4–8 s the decoder
  finds 83 and misses 47. The missed ones carry almost no team evidence (median net 2.5 against
  31): an own touch credited in 55 % (88 % for found ones), a completed pass in 19 % (51 %), a
  touch then held by a team-mate in 21 % (53 %), mean 0.9 own touches. Most missed possessions
  are invisible in this tracking; the ceiling of any touch-based idea is about a fifth of them.
- **Chains of three touches: dropped without trying** — missed possessions have under one
  credited touch on average, and two-touch chains are already counted as completed passes.
- **Reception held** (`features.reception_evidence`, `reception_weight`): a touch credited to
  team k followed, 0.2–2 s later, by k's control above 0.5 on at least 0.5 s adds evidence (in
  total `reception_weight` per touch) from the touch to the end of the 2 s window. Weight 8,
  the same as `pass_weight`; not swept. Code in the model with weight 0 (output identical).
- External spellF1, weight 0 → 8 (raw / 1.5 s / 3 s / controlled 1 / 3):
  matches 1–2: +0.009 / +0.010 / +0.009 / +0.002 / +0.001 (worst variant +0.002 / +0.007 /
  +0.013 / +0.001 / −0.003), macroF1 up everywhere, possession ratio +0.01;
  **hold-out match 3: +0.008 / +0.008 / +0.006 / +0.010 / +0.004.** Passes the rule.
- Competition match (candidate built in the scratchpad): 370 frames differ (0.2 %); 216 → 218
  possessions; 4 changes added, 2 removed. Team tags side with the current version on 97 % of
  271 differing frames (the same direction as for completed passes, 85 %, where added changes
  were judged to be what the tags cannot see); attacking-transition tags matched 11 → 10;
  same-team stoppages 51 → 49; set pieces, dead share, whistles unchanged. Reversal: 4 added
  changes, too few to read. Public window identical (13 possessions, 0.613).
- **Status:** passes every external test; small effect on the real match with weak, mixed
  signals there. **Adopted by the user** (`reception_weight` 8). New submission sha256 starts
  `0ec6e5a706bef84d` (was `c00926124ab668da`): 218 possessions, mean 14.9 s; regenerated twice
  byte-identical; valid; identical to the checked candidate. Sensitivity: `reception_weight`
  x0.7 / x1.3 change no frame; other priors as before (switch cost 246 / 218 / 192, walking speed
  dead share 0.42 / 0.49 / 0.55).

## 2026-11-12 — broadcast synchronisation pilot (alignment works; fusion dropped)

- `broadcast.py` loads the broadcast ATD (same format; cached in `cache/`) and aligns it by the
  ball's pitch position, per second, in 5-minute windows of the broadcast. Best lag 161 s in
  every first-half window and 1077 s in every second-half window; median ball distance 1.6–3.5 m
  at the best lag against 17–23 m at the next best. At frame level: 4014 (first half) and 26920
  (second half), constant to ±1 frame; median distance 0.7–1.3 m. The broadcast dropped about
  15 minutes of the half-time break.
- On graded live frames (decoded H/A, 81,121): broadcast picture live-consistent (≥ 6 players,
  median distance to the nearest tactical team-mate < 1.5 m) on 0.887; tactical ball seen 0.925,
  broadcast 0.830; where the tactical ball is missing (0.075) the broadcast sees it on 0.425.
  Both see the ball: distance quartiles 0.37 / 0.77 / 2.05 m, 95th percentile 9.7 m. Both strong
  control evidence (≥ 0.3): same sign 0.953. Broadcast strong where tactical has none: 3,133
  frames (0.039), agreeing with the decoded team 0.824.
- **Fill-in tried** (broadcast control evidence where the tactical one is zero, weight 1):
  218 → 231 possessions, 2,938 frames differ. Reversal: 18 added changes −0.20 m/s (random
  frames −0.24; implied real 0.04, interval −0.75–0.86); 6 removed changes 0.95 m/s (kept ones
  0.72). Team tags neutral (51 % of 1,426 differing frames); attacking-transition tags 10 → 9;
  dead share 0.489 → 0.497. **Dropped** without trying other weights (that would tune on the
  real match with no labels; the external matches have no broadcast). Hooks removed from
  `model.py` / `run.py`; output verified identical. `broadcast.py` kept as an analysis tool;
  its lags are hard-coded for analysis only.
- Upload file `solution/output/NYX.csv` generated with `run.py --name NYX`: identical to
  `submission.csv` (sha256 starts `0ec6e5a706bef84d`), valid.

## 2026-11-12 — second LLM round and the restart owner (candidate, awaiting the user)

- `LLMs/brief_v2.md` sent; two answers from the same model (`gpt6-astra_response_v2.md`, `_v3.md`).
  Assessed: valid points — the simulator smooths the ball but does not draw it straight between
  contacts (checked: `corrupt.py` has no such step), so touch-based ideas need an
  interpolation-aware degradation; contact detection from corners in the piecewise-straight
  ball path; timing matters for short spells (a 2 s spell tolerates ~0.35 s at IoU 0.7); match 3
  is now a validation match, not a pristine hold-out. New ideas: set-piece team at the restart
  (this entry) and the IDSSE dataset (7 Bundesliga matches, CC BY 4.0; possession flag not yet
  confirmed). Skipped for time: event-level classifier, expected-spellF1 edit selection,
  shirt-colour team repair, tracklet repair.
- **Opportunity count** (current submission): of 27 set pieces whose tag names a team (12
  corners, 10 goal kicks, 5 free kicks), 21 have a decoded restart within [−2 s, +12 s] of the
  tag start; in 6 of them (4 corners, 2 goal kicks) the first decoded spell (6–25 s) belongs to
  the other team. Out of a stoppage the decoder has no previous team and enters whichever team
  shows control first (on a corner, the defender who clears it), skipping the taker's spell.
- **Rule** (`model.restart_owner`, `restart_owner` 0/1, applied after Viterbi in `run.py` and
  `calibrate.py`): at that restart, the tagged team has the ball until the other team's net
  evidence reaches 0.5 (or the first decoded spell ends), if that is at least 0.5 s.
- Simulator: tags of corners / goal kicks / free kicks now carry a team, wrong 10 % of the time,
  from a separate generator (all earlier degradations and scores reproduced exactly).
- External spellF1, off → on (raw / 1.5 s / 3 s / controlled 1 / 3): matches 1–2 +0.004 /
  +0.004 / +0.003 / +0.004 / +0.001 (worst variant +0.004 / +0.007 / −0.000 / +0.006 / −0.001);
  match 3 +0.005 / +0.005 / +0.001 / +0.001 / −0.000. macroF1 up everywhere.
- Competition match (scratchpad candidate): 5 edits, taker spells of 1.7 / 1.9 / 2.0 / 2.8 /
  9.8 s; 218 → 223 possessions; team tags neutral (55 % of 376 differing frames with the current
  file); same-team stoppages 49 → 52; attacking-transition tags unchanged (10).
- **Adopted by the user** (`restart_owner` 1). New submission and `NYX.csv` sha256 start
  `0de7e99bc0f3cd2a` (was `0ec6e5a706bef84d`): 223 possessions, mean 14.6 s; regenerated twice
  identical; valid; decoder tests pass; audit as for the candidate; teamed restarts decoded for
  the other team 6 → 1 of 21 (the remaining one: the other team shows control within 0.5 s).
  Public window identical (13 possessions, 0.613).

## 2026-11-12 — IDSSE possession-flag check (time-boxed; no import, no model change)

- IDSSE (Bassek et al., Scientific Data 2025; 7 Bundesliga / 2. Bundesliga matches, CC BY 4.0,
  mirrored at huggingface.co/datasets/pysport/idsse-data): one positions XML per match (~350–420
  MB). Byte-range probes of one file (nothing kept on disk): the ball's frames carry
  `BallPossession` (1/2) and `BallStatus` (0/1) on every frame — the provider's own possession
  and alive flags.
- An 11-minute slice of one match: 45 possession spells, mean 10.1 s, median 4.3 s, shortest
  0.20 s, 14 under 2 s, 4 under 1 s; 8 stoppages (median 21.4 s); 36 direct changes. This
  provider (Sportec, not Metrica) labels possession about as finely as our raw event-derived
  labels (mean 9.3 s, median 4.2–4.6 s), and flickers (0.2 s spells), so it looks like an
  automatic flag rather than a judgement of control. The competition's public sample is less
  fragmented (mean 14.2 s).
- **Conclusion:** one more argument against raising the switch cost; not one for lowering it
  (the public sample and the definition argue against that). 12 stays. Importing full IDSSE
  matches (half a day) would test us against another provider's convention; not done.

## 2026-11-12 — straight-line simulator and corner-based contacts (stopped by its stop test)

- **Simulator option `INTERP=1`** (`calibrate.py`; `sample.contact_frames`,
  `corrupt.interpolate_between`): before the usual degradation, the ball is redrawn as straight
  lines between contact anchors taken from the events (start of every on-ball event or
  challenge, end of every pass), 25 % of anchors left out at random. Raised by both answers of
  the second LLM round. `event_table` now also returns End Frame (default scores reproduced).
- **Realism** (corners / touches per live minute): target 23.4 / 25.3; old smoothed simulator
  20.8–23.1 / 25.3–28.9; straight-line simulator 16.7–19.6 / 18.4–21.2. The old simulator is
  closer to the target's contact rates; the straight one is harsher (probably the 25 % of
  dropped anchors). Change-size quartiles similar everywhere (about 8 / 11–12 / 15–16 m/s).
- **Adopted evidence re-checked under `INTERP=1`** (raw / 1.5 s / 3 s / controlled 1 / 3):
  completed passes 0 → 8: +0.007 / +0.007 / +0.005 / +0.007 / +0.002; receptions held 0 → 8:
  +0.003 / +0.006 / +0.007 / +0.000 / +0.004. Both hold. Absolute scores are lower on the harsher
  simulator (0.44 / 0.51 / 0.55 / 0.58 / 0.56).
- **Corner detector** (mean ball velocity over [−1.5, −0.5] s against [+0.5, +1.5] s, local
  maxima above 3 m/s; credited to a team with a player within 2 m and nearer than any
  opponent, no margin). Stop test on the straight-line simulator, matches 1–2: of missed true
  possessions under 4 s (234), an own-team corner in 18 % against an own-team touch from the
  current detector in 23 % (corner where no touch: 7 %); of missed 4–8 s possessions (49): 61 %
  against 55 % (corner where no touch: 18 %, about 9 possessions). Credited corners name the
  true possessor 90 % of the time. **Stopped**: it adds a single contact to a handful of
  possessions, and single-contact evidence already failed. Detector removed from
  `features.py`; output verified identical. The missed short possessions leave no usable turn
  in the ball's path either.

## 2026-11-12 — end of session

- Proposed, not started: extend the restart owner to restarts without a team tag (throw-ins,
  untagged corners and goal kicks), taking the taker's team from the player nearest the resting
  ball just before the restart kick. Plan in `STATUS.md`, "Next session", item 4.
- Assessed as not worth the remaining time: a learned classifier on the practice matches, ball
  detection in the video, importing IDSSE matches, the second-half kick-off timing, the artefact
  stoppages, further dead-ball work.
- State: `NYX.csv` / `submission.csv` sha256 `0de7e99bc0f3cd2a`; branch `nyx-solution`, latest
  commit before this note `854b522`.
