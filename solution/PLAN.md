# Improvement plan after the external reviews

Written 2026-11-11. Deadline 2026-11-17. Sources: `LLMs/gemini-argon_response.md` ("Argon") and
`LLMs/gpt6-astra_response.md` ("Astra"), both answering `LLMs/brief.md`. Steps 0, 1 and 3 are done (results under each step);
steps 2, 4 and 5 are not started. **Read section 6 before continuing: step 3 changed the priorities.** The user approved all steps, the Metrica sample-data download and
ffmpeg as a dependency. Working rules in `WORKING_RULES.md` apply to every step (local processing only,
aggregates only in assistant sessions, no tuning on the public window).

## 1. What the metric really rewards (checked, not assumed)

The two reviews disagree about the scorer, so I ran the official `possession_metrics.spell_scores`
on synthetic sequences (no match data). In a sequence of ~42 possessions, where one fully lost
possession costs about 0.023:

| case | spellF1 loss |
|---|---|
| miss a 1 s possession in the middle of a 37 s one | 0.038 |
| insert a false 1 s possession in the middle of a 37 s one | 0.038 |
| short possession found, but 0.5 s late | 0.019 |
| miss / insert a 1 s possession near the end (30 / 1 / 6 s) | 0.024 / 0.024 |
| miss / insert a 3 s stoppage with the **same team** on both sides | 0.027 / 0.027 |
| miss a 3 s stoppage with **different teams** on either side | 0.000 |
| stoppage start 3 s late, 12 s possession before it | 0.000 |
| stoppage start 3 s late, 5 s possession before it | 0.005 |
| restart 3 s late, 5 s possession after it | 0.014 |
| change of possession 1.5 s late, 5 s or 12 s possessions | 0.000 |

Conclusions that reorder the priorities:

1. **Misses and false insertions cost exactly the same.** Argon's claim that a false merge is far
   worse than a false split is wrong; Astra's correction is right. There is no reason to bias the
   decoder towards splitting. An event is worth inserting when it is more likely true than not.
2. **Whether an event exists matters far more than when it happens.** Timing errors of 1–3 s cost
   little or nothing unless the neighbouring possession is short. A short possession found half a
   second late still recovers half the loss, because it rescues the two long possessions around it.
3. **A missed stoppage only costs when the same team has the ball before and after it** (a foul
   won by the team in possession, a throw-in kept). Those are the stoppages to find.

So the work that pays is: get the *set* of changes of possession and same-team stoppages right.
Work that only refines timing (back-dating to the first touch, exact restart frame) is low value.
This demotes weakness 4 in `STATUS.md` and Argon's rank 3 and rank 6.

## 2. Verdict on each proposal

| # | proposal | from | verdict | why |
|---|---|---|---|---|
| a | Referee-whistle detection from audio | Astra 4 | **Do — top priority** | Both videos have an AAC audio track (checked with ffprobe). It is the only genuinely new information source for fouls, which are exactly the same-team stoppages the metric punishes. CPU-only. The tactical audio is on the submission timeline already. |
| b | Calibrate on other matches with a corruption model | Argon 5, Astra 5 | **Do — top priority** | The only route to pin the two unpinned quantities (switch cost → number of possessions; walking speed → dead share). Allowed by the rules. Player-speed statistics should transfer well; ball-dependent parts need the corruption model. |
| c | Synchronise the broadcast tracking | Argon 1, Astra 7 | **Pilot, time-boxed** | A TV feed runs in real time, so the mapping is probably one constant offset per half, not a per-shot search as Argon describes. If so the sync is cheap. Payoff 1: a second ball track. Payoff 2: broadcast cuts and replays as a signal, and as a **validation instrument**, for dead ball. Argon's "directors never cut away during live play" is overstated (close-ups happen in play), so treat it as soft evidence and measure it. |
| d | Kick-off half-plane rule | Argon 2 | **Do — cheap** | A law of the game: before a kick-off each team is in its own half. Fixes the known second-half kick-off error and the four kick-offs after goals. Small gain (6 events), small cost. |
| e | Throw-in signatures: ball lost while heading over a touchline; a player standing on the touchline | Argon 2, Astra 3 | **Do** | Throw-ins are the most frequent stoppage and often short and unseen (weakness 5). The 26 tagged throw-ins give an audit. Players off the pitch may not be tracked, so the touchline-taker part needs a feasibility count first. |
| f | Decoder audits: `D` as a cheap bridge between teams; tie-breaking through gaps; very short `D` runs | Astra corrections | **Do — half a day** | Real risk: entering `D` on a line crossing (3) and leaving on a kick (3) costs 6, less than a direct change (12), and a few-frame `D` in the middle of a possession splits it. Cheap to check and to guard with a minimum stoppage length. |
| g | Collective-reversal test for the switch cost | Argon Q3/4 | **Try — half a day** | After a real change of possession both teams reverse direction within ~2 s. Measuring that reversal for the changes added as the switch cost is lowered gives a label-free elbow. Signal strength unknown; cheap to find out. |
| h | `Attacking Transition` tag recall; per-tag reliability | Argon Q3/4, Astra 6, already in `STATUS.md` | **Do — cheap** | A recall measure for changes of possession that does not favour smooth outputs. |
| i | Masked-ball validation harness | Astra 1, Argon 4 | **Do only if (j) is attempted** | Sound method: hide the ball on well-observed passages and test recovery. It is the validation for ball-free evidence, not a gain by itself. |
| j | Ball-free team evidence (team shape and movement) trained on confident frames | Argon 4, Astra 6 | **Later, if time** | Addresses blindness while the ball is unseen, but section 1 shows that a change noticed late costs little. Value is limited to gaps containing two changes. "Pressing-ray phantom ball" is speculative; skip it. |
| k | Contact vertices from ball acceleration (direction changes, not only speed) | Argon 3, Astra 2 | **Partly** | Detecting redirects at constant speed is a real improvement to strike detection and helps the dead/alive "interval between strikes" feature. The back-dating part is low value (section 1). Astra's "local switch discount at a confirmed contact chain" is the useful form; only worth doing after (b) gives a way to measure it. |
| l | Polarisation of player velocities as a whistle signature | Argon 2 | **Test only** | The claimed threshold is asserted, not shown. Cheap to compute; keep it only if whistles from (a) confirm it. Mostly superseded by (a). |
| m | Goalkeeper identification | Argon 1D | **Skip unless needed by (d)/(e)** | Easy, but the claimed benefit (keeper holding the ball mistaken for dead) is unmeasured. |
| n | Airborne-ball gate from camera geometry | Argon 1C / 6 | **Skip** | The ball track is smoothed and interpolated, so the bowing it relies on is unlikely to survive; the relative-velocity gate already removes mid-flight evidence. |
| o | Anchor-calibrated likelihoods; "bridge-split" thresholds by position in the spell | Argon 7 | **Skip** | Anchors are selected by the same features (circular), the autocorrelation correction is a free parameter, and the asymmetric thresholds rest on the merge-is-worse claim that section 1 refutes. |
| p | Expected-spellF1 selection among alternative segmentations | Astra 8 | **Skip** | Needs calibrated probabilities we do not have; Astra says so too. |
| q | Targeted video crop differencing for restarts | Argon 8 | **Skip** | Only refines restart timing, which is low value, and is fragile. |
| r | "A match has 76–86 stoppages, so 93 means false positives" | Argon | **Reject** | Based on the tagged set pieces, which under-count (26 throw-ins tagged; a match typically has about 40). |

## 3. Plan, in order

Each step lists what to build, how to judge it without ground truth, and when to stop. One change
at a time; update `README.md`, `STATUS.md`, `HISTORY.md` when a step is kept or dropped.

### Step 0 — Audits and instruments (half a day)

Build:
- `metric_cases.py`: the synthetic scorer cases from section 1, kept as a runnable record.
- In `audit.py`: count of stoppages shorter than 2 s and of `X→D→X` same-team stoppages shorter
  than 3 s; count of `H→D→A` paths where the `D` lasts under 1 s; number of possessions over 40 s
  and over 60 s; `Attacking Transition` recall (a decoded change to the tagged team within ±3 s
  of the tag start, or that team already in possession).
- A synthetic test that the decoder holds the previous team through a no-evidence gap and
  switches at the first control frame.
- Per-tag-type agreement, split by ball seen / unseen and by time since tag start.

Decide:
- If very short stoppages exist, add a minimum stoppage length through the decoder (a cost that
  makes leaving `D` within ~1.5 s of entering it expensive unless both boundary events fired),
  not a post-filter.
- If a tag type is ≥ 90 % consistent in its first seconds, note it as a candidate weak prior for
  unseen-ball frames (it then stops being a validation signal for H/A).

**Done 2026-11-11. Results (the submission is unchanged):**

- Built `metric_cases.py`, `test_decoder.py` (4 synthetic tests, all pass), `tag_reliability.py`,
  and extended `audit.py` with stoppage/possession structure and attacking-transition recall.
- **The decoder is sound:** it holds the previous team through a gap in both directions, ignores
  a 6-frame touch, accepts 20 frames of control, and does not use `D` as a bridge (0 stoppages
  under 1 s between different teams).
- **Blindness while the ball is unseen is a small problem:** only 7 % of live frames (5,940 of
  80,514) have no ball position; unseen time is mostly stoppages. Ball-free team evidence
  (items i, j) is demoted to "probably not worth doing".
- **Stoppage structure:** 93 stoppages; 47 have the same team on both sides (the kind that
  costs when missed or invented), median 21.5 s. No stoppage is shorter than 4 s apart from four
  artefacts, so quick throw-ins and quick free kicks are being missed.
- **Four artefact stoppages (0.7–2.2 s):** the ball tracked beyond a line and straight back.
  Two fixes were tried and reverted, because each removed real stoppages with tagged throw-ins:
  (1) discard a line crossing if the ball is tracked inside again within 2.5 s — a ball that goes
  out often bounces back off the boards; (2) no cheap restart within 3 s of a crossing — the ball
  can cross the line several times while being returned. Left as is.
- **Long possessions:** 16 over 40 s, 3 over 60 s. Twelve look genuine (home team, ball in view
  throughout, no opposing control, tags agree). **Four contain a 9–12 s unseen stretch with clear
  dead evidence that falls just short of the transition costs** — probable missed same-team
  stoppages. Steps 1 and 4 target exactly these.
- **Attacking-transition tags:** 22 of 24 have a decoded change to the tagged team within
  [−5 s, +12 s], but offsets spread from −3.4 s to +8.8 s (median +2.3 s). Recall of real changes
  looks fine; the tag cannot date a change.
- **Tag reliability:** six of the twelve team-tagged codes are mirror duplicates (Build Up ≡
  Defending in Attacking Third, Progression ≡ Defending in Middle Third, Creating Chances ≡
  Defending in Defensive Third, Attacking ≡ Defensive Transition). Agreement with the decode in
  the first 4 s of a tag: Progression 0.96, Creating Chances 0.95, Ball in Final Third 0.89,
  Ball in the Box 0.88, Build Up 0.81, Long Ball 0.76, Players in the Box 0.76, Attacking
  Transition 0.46 (it starts before the turnover). Not used as input: with only 7 % of live
  frames unseen there is little for a prior to add, and using it would cost a validation signal.

### Step 1 — Whistle detection from audio (1 day)

Build `audio.py`:
1. Decode the tactical audio locally with ffmpeg to mono PCM at a fixed rate (deterministic
   command, pinned in the README). Cache next to the ATD cache (gitignored).
2. Short-time spectrum (numpy FFT, ~20 ms hop). Whistle score per hop: energy concentrated in a
   narrow band around 3.5–4.5 kHz relative to neighbouring bands, with tonal persistence of at
   least ~0.15 s. Referee whistles are narrow-band and sustained; crowd whistling is broader and
   more diffuse. Produce events (start frame, duration, strength) mapped to video frames.
3. If the tactical audio is unusable (ambient only, no audible whistle), try the broadcast audio
   after step 2's sync. If neither works, drop the step and record why.

Use in the model (transition costs, not per-frame evidence):
- A whistle during play lowers the cost of entering `D` at that frame (like the ball crossing a
  line). The stoppage must still be supported by what follows.
- A whistle during a stoppage, followed by a strike, lowers the cost of leaving `D` (the referee
  releasing a free kick or kick-off).

Judge:
- Enrichment: do whistle events precede collective deceleration and coincide with existing
  stoppage starts far more often than time-shifted control times do? If not, the detector is
  hearing the crowd; stop.
- After adding it: tagged free kicks (5) and kick-offs (6) in `audit.py`; change in the number of
  same-team stoppages; dead share stays plausible; sensitivity to the whistle threshold.
- Keep the broadcast-cut signal (step 2) out of the model while judging this, as the independent
  check.

Cost and risk: adds ffmpeg as a build dependency. Barcelona crowds whistle a lot; the tonal test
is the whole difficulty.

**Done 2026-11-11, kept.** The referee's two-tone whistle is detectable (70 blasts) and is now
in the model as a cheap entry to `D` and as the release of each half's kick-off. Details and
numbers are in `HISTORY.md` and `README.md`. Outcome against the plan: the enrichment test
passed for the strict detector only; the gain is small (~1 % of frames, four more same-team
stoppages) because the decoder already had a stoppage at 43 of 58 whistles. The whistle check
in `audit.py` is now the independent instrument for dead-ball detection; do not also use it to
tune the whistle's own parameters.

### Step 2 — Broadcast synchronisation pilot (1 day, hard stop)

Build `broadcast.py`:
1. Parse the broadcast ATD and homography with the existing loader pattern.
2. Test the constant-offset hypothesis: on broadcast frames with a valid homography, compute each
   team's centroid; cross-correlate against the tactical centroids over a range of lags, per half.
   A sharp single peak per half means the mapping is affine. Otherwise fall back to per-shot
   matching (Argon's method) or stop.
3. With the mapping: label each tactical frame as broadcast-live (valid homography and player
   configuration agrees with tactical), broadcast-replay (valid homography, configuration
   disagrees) or broadcast-away (no homography).

Judge the sync: where both feeds track the ball, median distance between the two ball positions
after alignment should be about a metre or two.

Use, in this order:
- **As a validation instrument first.** Share of broadcast-away / replay time inside decoded `D`
  versus decoded live play. If cuts and replays are strongly concentrated in `D`, this is an
  independent check on dead-ball detection for every later step (and for step 1).
- **As dead evidence** only if the concentration is strong, and then weakly (a cut longer than a
  few seconds raises the dead score). Once used as input it is no longer a validation signal.
- **Ball fusion:** fill tactical ball gaps with the broadcast ball where the sync is live. Measure
  how much of the tactical gap inside decoded live play it covers before integrating; below ~20 %
  it is not worth the complexity.

Stop if no clean offset is found within the day.

### Step 3 — Calibration on other matches (1.5–2 days)

Needs a decision from the user: downloading Metrica's public sample games (tracking + events,
three matches) from GitHub.

Build `external/`:
1. Loader for the sample games into the same arrays as `load.py` (strip identities, keep teams).
2. Labels: frame-level `H`/`A`/`D` from the event data — dead between a ball-out / foul event and
   the following set piece; otherwise the team of the last controlled event. Write the rules
   down; they will not match the competition's convention exactly, and the document must say so.
3. Corruption to resemble this ATD, each measured from the unlabelled target data: smooth the ball
   (kernel chosen so strike ramps last about a second), remove the ball in long blocks with the
   target's gap-length distribution and its bias towards stoppages and crowded areas, drop player
   tracklets to match the mean tracked count, suppress the ball beyond the lines.
4. Run the unchanged pipeline on several corruption variants and score with the official metric.

Use:
- Choose `switch_cost`, the control radius/gate and `walk_speed` from a **broad region that is
  good across matches and corruption variants**, not a sharp optimum. If the region contains the
  current values, keep them and say so.
- Use the same harness to test steps 0, 4 and (k) properly, since it has labels.

Judge the transfer: the corrupted matches should reproduce the target's unlabelled statistics
(ball-missing share, strike rate, collective-speed distribution, sensitivity pattern). If they do
not, trust only the player-speed parameter (`walk_speed`), which does not depend on the ball.

Risk: label convention mismatch; corruption fidelity. This is still the only step that can move
the two largest uncertainties.

**Done 2026-11-11. No parameter changed.** Full account in `HISTORY.md` and in the README
section "Check on other matches". Outcome against the plan:

- The broad-region rule did its job: for every dead-ball parameter the current value is inside
  the good region. For the switch cost the good region depends on the labelling convention
  (3–4, 4–8 or 8–16), so it cannot be narrowed; 12 stays.
- The harness answers "where is the loss": in the team, not in dead ball (0.83–0.87 with true
  teams against 0.51–0.65 with true dead/alive).
- Touch evidence works on the sample matches and is off in the submission (airborne-ball
  artefacts on the real tracking; the definition does not count a simple touch).

### Step 4 — Restart geometry (1 day)

- **Kick-off rule:** inside a kick-off tag window, play cannot be live while every tracked player
  is in their own half (inferred per half from team centroids) and the ball, if seen, is at the
  centre. The restart is the first frame that breaks. Check against the two published kick-off
  frames.
- **Throw-in entry:** ball last seen within a few metres of a touchline, moving outward, then
  unseen for over a second → cheap entry to `D` at the extrapolated crossing time. Same for goal
  lines (goal kicks, corners).
- **Throw-in taker** (only if a count shows players are tracked on the touchline during tagged
  throw-ins): a slow player on the line gives the team taking the throw and supports `D`.

Judge: `audit.py` on the 26 tagged throw-ins, 12 corners, 10 goal kicks; number of same-team
stoppages; and the broadcast-cut instrument if step 2 succeeded.

### Step 5 — If time remains

- Collective-reversal elbow for the switch cost (g), as a second opinion on step 3.
- Contact vertices from ball acceleration (k), tested in the step 3 harness.
- Ball-free team evidence with the masked-ball harness (i, j).

### Final day — freeze

Regenerate twice and compare; validate; run `audit.py`, `tag_agreement.py`, `sensitivity.py`;
update the technical document with every asset used and dropped, the external data and who
labelled it, and the ffmpeg command; rename outputs to the team name.

## 4. Suggested schedule

| day | work |
|---|---|
| Wed 11 | Step 0; start step 1 |
| Thu 12 | Step 1 finish; step 2 pilot |
| Fri 13 – Sat 14 | Step 3 |
| Sun 15 | Step 4 |
| Mon 16 | Step 5 or slack; freeze |
| Tue 17 | Final checks and submission |

If only two things get done, do steps 1 and 3.

## 5. Decisions needed from the user

1. **External data:** may the Metrica public sample games be downloaded and used (step 3)? They
   must then be cited in the technical document.
2. **ffmpeg as a dependency** for audio decoding (step 1). It is installed on this machine; the
   organisers would need it to regenerate the file.
3. **Scope:** all five steps, or only steps 0, 1 and 3?

## 6. Revised priorities after step 3 (2026-11-11)

Step 3 showed that dead-ball detection is close to its ceiling on comparable matches and that
the remaining error is in which team has the ball. That demotes the remaining dead-ball work:

- **Step 4 (restart geometry)** and **step 2's dead-ball use of broadcast cuts**: low expected
  gain now. The missed stoppages are short (about 4 s); a throw-in detector could still find a
  few same-team ones. Do only if time is left.
- **Step 2's ball fusion** gains interest for a different reason: a second, closer view of the
  ball could correct the airborne-ball and occlusion errors that mislead the team evidence.
  Still a pilot with a hard stop.

What would actually move the score is better team evidence on the **real** tracking:

1. **Make the simulation contain the real artefacts** so that team-evidence ideas can be tested
   honestly: displace the ball during long, fast passes (airborne projection error, radial from
   an assumed camera position), mislabel the team of a tracked player for a few seconds, and
   label brief touches the way the definition does. Without this, the harness over-rewards
   anything that trusts the ball more.
2. **Detect airborne flight** on the real ball track and suppress all team evidence (control
   and touch) during it. If that removes the false-touch problem, touch evidence can be
   switched on. A cheap proxy to test first: a long strike interval with high speed and no
   player within reach of the tracked ball for more than about a second.
3. **Possessions of 4–8 s** are right only about 60 % of the time on the sample matches, with
   median evidence barely above the round-trip switch cost. They are long enough to be
   "controlled" under any convention, so evidence aimed at them (reception of a pass by a
   team-mate, two consecutive touches by the same team) is safer than lowering the cost.

**Update, same day.** Items 1 and 2 above are void: the airborne-projection hypothesis was tested
on the real ball track and refuted (paths between touches are straight and bow to neither side;
the ball is interpolated between contacts). Under item 3, completed-pass evidence was added and
kept. The current list of what is left is in `STATUS.md`, "Work in progress".

**Update, 2026-11-12.** Proposal (g), the collective-reversal test, was built (`reversal.py`). It
separates real from false changes on the external matches (AUC 0.75) but, on the competition
match, the 33–47 changes that a switch cost of 6, 8 or 16 adds or removes are too few for it to
place the cost (implied real share ~0.5, intervals ~0.1–0.9). Details in `HISTORY.md`.
External labels that follow the definition (`sample.controlled`) were added the same day; they
favour a switch cost of 16–24 where the brief-recovery labellings favour 3–8. Not applied; the
choice is with the user (`STATUS.md`, open decision 5). An evidence-dependent switch cost
(high by default, lowered where the new team completes a pass) was then tried and failed to get
the best of both; the switch cost stays at 12 (`HISTORY.md`). Sample match 3 was then added as
a hold-out and confirmed the submitted model, the completed-pass evidence and the cost of 12.
For possessions of 4–8 s, "receptions held" (a touch the same team then holds) passed on all
three matches and was adopted. The broadcast pilot (step 2) aligned the two recordings to the
frame, but the broadcast's team evidence, used where ours is empty, made the reversal test worse
and was dropped. From the second LLM round, the set-piece team at the matching restart
("restart owner") passed on all three external matches and was adopted. A straight-line ball
simulator confirmed the touch-based evidence; a corner-based contact detector was stopped by its
stop test. Modelling is finished apart from one optional half-day idea (restart owner for
restarts without a team tag, `STATUS.md`); the remaining work is the freeze.
