**I would keep your Viterbi decoder, but change what constitutes evidence for a transition.** Your biggest opportunity is to separate three questions: *who eventually establishes control, when that control began, and whether play was live*. At present, sustained control evidence and collective speed are doing too much of all three jobs.

Also, **possession count and dead share are not identifiable from these unlabelled observations without additional assumptions**. You can constrain them much better, but neither an unsupervised model nor a stability test can establish that 202 possessions or 49% dead is correct.

The proposals below are hypotheses for your data, not claims of demonstrated improvements. All match-specific processing would run locally, and none requires manual review or annotation.

**First, several corrections to the current reasoning**

- **Timing penalties depend on spell length.** If a true spell lasts $L$ and you trim $\delta$ from one end, its IoU is $1-\delta/L$. If you shift the entire spell by $\delta$, it is $(L-\delta)/(L+\delta)$. Thus “8 frames costs 11%” is not a general property of the metric. The effect also jumps at the five matching thresholds.
- **A false split does not necessarily destroy every match.** Dividing a spell into two equal pieces allows one piece to match at thresholds up to 0.5, assuming inclusive thresholds. It still adds false positives and loses higher-threshold matches, but the precise scorer matters.
- **Your switch penalty mathematically suppresses short possessions.** An interior `H–A–H` excursion pays two switches: 24. If the emission-score advantage of `A` over `H` is bounded by 1 per frame, it needs over 0.96 s of maximal evidence; if bounded by 2, over 0.48 s. Check your actual score mapping. This is an implicit minimum evidence-duration requirement.
- **Offline Viterbi does not necessarily “keep the previous team” through missing evidence.** If switching anywhere in a gap costs the same, many boundary locations can be equally good; implementation tie-breaking can choose the location. This deserves a synthetic correctness test.
- **Audit whether `D` becomes a cheap route between teams.** Your contextual transition costs can make `H→D→A` cheaper than `H→A`. That is appropriate only when there is genuine stoppage evidence.
- **Ball speed is not proof of live play.** A dead ball can be kicked back for a restart. Conversely, a stationary ball can be live. Missingness, rest and speed should describe observations, not determine legal state.

A constant team prediction can also match a spell under the general matching definition, although it may score zero on this particular match because its IoUs are tiny. I would verify these details against the official evaluator using synthetic sequences—not the public five minutes.

**Ranked by expected benefit relative to effort**

Effort estimates assume your existing tracking pipeline is reusable. Confidence refers to the usefulness of the mechanism, not a guaranteed leaderboard gain.

| Rank | Approach | Weaknesses addressed | Effort | Confidence |
|---|---|---|---|---|
| 1 | Masked-observation validation and independent evidence audits | 1–3, validation generally | ½–1 day | High for finding failures |
| 2 | Confirm control, then localise its onset with contact chains | 1, 4, 8–10 | 1–2 days | Medium–high |
| 3 | Detect stoppages as paired events with spatial context | 2, 5–7 | 1–2 days | Medium–high |
| 4 | Whistle audio, if usable audio exists | 5, 6 | ½–1 day | Medium, conditional |
| 5 | Calibrate on corrupted external matches | 1, 2, 8 | 1–2 days initially | Medium |
| 6 | Ball-free team evidence trained from independent anchors | 3, 9, 10 | 1 day | Medium |
| 7 | Synchronise broadcast through player configurations | 3, 9, 10 | 1–3 days | Medium; integration risk |
| 8 | Metric-aware selection among alternative segmentations | 1, 4, 8 | 1–2 days | Medium–low without calibration |

I would not attempt all eight in one week.

**1. Build a validation system that hides observations, not labels**

Your best cheap experiment is **artificially removing ball observations from otherwise well-observed passages**.

Before removal, construct sparse algorithmic anchors: unambiguous co-motion with one team, a clear receiving sequence, or a well-supported restart. Then remove contiguous ball blocks and ask whether a candidate method recovers the anchors and transition intervals.

Important details:

- Use gap lengths resembling your actual missing stretches, rather than isolated random frames.
- Stratify by crowding, pitch location, ball speed, distance to the touchline and camera visibility.
- Include blocks containing turnovers, not just settled possession.
- Build anchors from the original ball evidence; evaluate a ball-free method that never receives that evidence.
- Report performance separately by stratum. Genuine missingness is selective, so average artificial-gap performance will be optimistic.

Measure **team recovery at held-out anchors, false inserted transitions, and boundary displacement where a contact chain supplies an algorithmic reference**. These are proxy errors, not ground-truth spellF1.

Add two complementary checks:

1. **Observation perturbations:** remove short player tracklets, perturb coordinates within measured noise, alter sampling phase, or substitute independently estimated velocities. Genuine event boundaries should usually survive small perturbations.
2. **Independent evidence enrichment:** compare new boundaries with a withheld source, such as whistle detections or broadcast contacts. Compare against time-shifted or context-matched control times, so merely predicting more boundaries does not look better.

Crucially, stability alone rewards constant predictions. Require both stability **and recovery of withheld events**.

For tag agreement, use a fixed evaluation mask. If each model defines its own “live frames,” it can improve agreement simply by declaring difficult frames dead. Report agreement, coverage and tag support on disagreements separately.

**2. Confirm control using the future, then date it using the contact sequence**

Your existing backdating experiment asked when a new player became close. That misses the key distinction: **the observation proving possession may occur later than the action establishing it**.

Construct short contact hypotheses using:

- ball–player proximity;
- changes in ball direction, not just speed;
- incoming and outgoing trajectory compatibility;
- separation of the ball from the player after contact;
- subsequent reception or sustained control by that team.

For a suspected first-time interception/pass:

1. Identify reliable subsequent control by team A.
2. Trace the incoming ball trajectory backwards.
3. Look for a plausible earlier A contact that redirects it toward the receiver.
4. Compare that explanation with uninterrupted travel, an H touch, or an uncontrolled deflection.
5. If the contact-chain explanation wins, place the turnover at the earlier contact.

For a duel, require evidence that distinguishes the winner from a nearby presser: the ball exits with their movement, the opposing player separates, or a subsequent team action supports the claim. Do not let shared proximity and velocity independently count as two strong pieces of evidence when both arise from the same chase.

**Decoder change:** let a strongly supported control-acquisition event reduce the switch cost locally. This allows a short, decisive possession without reducing the global penalty and creating flicker everywhere.

Also attach reliability to the ball observation. Impossible motion, unstable projection, or inconsistency with every plausible contact should weaken team evidence. Treat “no trustworthy ball position” as uncertainty, not as evidence for the opposing team. Avoid simply enlarging the control radius to accommodate 7–8 m errors.

**Validation:** withhold the later reception from candidate generation and test whether earlier contact hypotheses predict its team and location. Use synthetic trajectory corruption to test timing robustness. Track short spells supported by an independent contact chain separately from short spells created only by parameter changes.

**3. Replace the walking threshold with stoppage episodes and paired boundaries**

Mean speed confounds slow live possession with dead-ball preparation. It also changes when different players become visible.

Use short continuous tracklets to calculate:

- the distribution of within-player speed changes;
- the fraction decelerating, separately for each team;
- local versus distant-player responses;
- cessation of pursuit toward the last reliable ball region;
- convergence toward a restart formation;
- disappearance and later reappearance of the ball near a compatible restart location.

This does not require persistent player identity. It requires reliable local continuity; exclude slot jumps and normalise for visibility.

Some useful spatial signatures are:

| Restart hypothesis | Spatial/behavioural evidence | What it contributes |
|---|---|---|
| Throw-in | Last ball trajectory toward a touchline; local players reorient toward that sideline; subsequent reception nearby | Supports a short stoppage even without global slowdown |
| Corner | Corner-region evidence plus attacking/defending concentration near one goal | Identifies preparation; does not determine the exact kick |
| Goal kick | Ball/players reorganise near the defending goal; nearby support options form | Distinguishes preparation from generic slow play |
| Free kick | Local interruption followed by opponents retreating or holding distance around a location | Supports stoppage onset and preparation |
| Kick-off | Centre-area setup followed by release and coordinated departure | Detects gentle starts without a 7 m/s requirement |

These must remain soft signatures: formations overlap with live play. Tracking-based event research has used player configurations to distinguish set pieces, so the general mechanism has precedent; its reliability on your incomplete tracks remains untested. [Source: Automatic event detection in football using tracking data](https://link.springer.com/article/10.1007/s12283-022-00381-6).

**The key change is to score a candidate stoppage interval jointly.** An uncertain out-of-play event followed shortly by a plausible throw-in reception can support a brief `D` episode even if neither endpoint alone beats your current penalties.

For gentle restarts, detect **release from a prepared configuration**, supported by ball displacement, a receiver response or a local video contact cue. Speed need not become high.

Use tags to propose broad search regions, not as observations repeatedly pushing frames toward `D`. A tag interval is one uncertain event hint, not hundreds of independent votes.

For foul timing, estimate a distribution of response delays from independently anchored stoppages. Then infer onset from the pattern of reactions rather than shifting all mean-speed evidence exactly two seconds backwards. Some fouls will remain unidentifiable without another modality.

**Validation:** predict restart locations and types from pre-restart evidence, then test against withheld post-restart observations. Measure whether accepted stoppages explain both endpoints. Audit rejected candidates as well: otherwise a method can improve apparent precision simply by detecting fewer events.

**4. Audio may provide the independent foul-onset signal you lack**

If either recording has usable audio, inspect it algorithmically for whistle-like events: short-time spectral concentration, tonal persistence, onset and offset. This is feasible on a CPU. Published approaches use band-limited energy and spectral structure rather than large models. [Source: Automated Referee Whistle Sound Detection for Extraction of Highlights from Sports Video](https://ijca.phdfocus.com/archives/volume12/issue11/1729-2340/).

Use a detected whistle to propose a boundary, with context:

- during likely live play, a following interruption supports `live→D`;
- during preparation, a whistle may authorise a restart rather than begin one;
- crowd whistles, replay audio and repeated referee whistles require rejection;
- absence of a whistle says little about throw-ins.

Account for audio/video offset and acoustic delay. Whistle timing is an additional observation, not exact ground truth.

**Validation:** hold whistles out of the original decoder and test whether they disproportionately precede collective reactions or compatible restart episodes compared with control times. After incorporating audio, retain a different withheld channel for evaluation.

This has unusually good potential because it adds information your current tracking-derived features cannot supply. Do not use commentary transcripts or human event descriptions.

**5. External calibration is useful if you transfer measurement conditions, not possession counts**

[Metrica’s public sample repository](https://github.com/metrica-sports/sample-data) provides synchronised tracking and event data, making it a practical starting point. Its documentation does not establish that its labels reproduce your competition’s exact possession convention. [Source: Metrica Sports sample-data README](https://github.com/metrica-sports/sample-data#readme).

Your domain-gap concern is correct. Address it by creating several degraded versions of external matches:

- remove contiguous ball stretches;
- smooth ball trajectories over a range of plausible kernels;
- fragment player tracks and introduce visibility loss;
- add occasional team errors;
- vary positional error and suppress out-of-pitch observations.

Estimate corruption characteristics from unlabelled measurement statistics where possible. Do not pretend airborne projection errors are ordinary Gaussian noise; stress-test those separately.

Then select switch penalties and dead/live feature weights by **external spellF1 across corruption scenarios**, preferably holding out whole matches. Choose a broad robust region rather than a sharp optimum on one corruption recipe.

Two limitations matter:

- Event timestamps and event definitions are not automatically precise framewise possession/dead labels.
- Matching your target’s 41% missing rate is insufficient if external gaps occur in easier contexts.

If the available external labels cannot support faithful spell reconstruction, calibrate narrower components—contact recognition, response delays, restart signatures—rather than manufacturing false precision.

**Validation without target labels:** test external-match generalisation and whether performance degrades gracefully under target-like corruption. This is stronger evidence than matching a typical possession count, although it cannot certify the target score.

**6. Learn ball-free team evidence from sparse independent anchors**

Do not learn from your complete Viterbi output. Learn from a restricted set of high-confidence ball-supported examples, withholding ambiguous periods.

Use features that are symmetric under team exchange:

- team-wise longitudinal velocity quantiles;
- movement of defensive and attacking lines;
- changes in width, depth and inter-team separation;
- local numerical balance around the last reliable ball position;
- convergence toward likely receiving areas;
- team-relative pitch occupancy.

Infer attack direction automatically, then normalise halves. Account explicitly for which portion of the pitch is visible; otherwise camera movement can masquerade as team movement.

Fit a small regularised classifier and validate on disjoint contiguous blocks. Avoid random frame splitting because adjacent frames are nearly duplicates.

Use its output as **weak evidence during missing-ball periods**, with low confidence outside the anchor feature distribution. Team shape often reflects tactical state or counterpressing rather than actual ownership.

For individual tag types, estimate reliability against withheld anchors, separated by tag type and time since tag onset. Treat defending tags according to their semantics; their team need not be the possessing team. If tags enter the model, they cease to be independent validation.

**Validation:** the artificial-gap tests in idea 1, especially gaps spanning opposing-team anchors. Note that equal-team anchors at both ends do not prove no intermediate turnover occurred.

**7. Synchronise broadcast using player configurations before using its ball**

Synchronisation does not require player identities or a visible ball.

For valid broadcast homographies:

1. Convert visible players to pitch coordinates.
2. Compare each team’s point cloud against candidate tactical times.
3. Use robust partial matching, accommodating missing players and false detections.
4. Find a sequence of uniquely supported temporal matches.
5. Fit separate time mappings for contiguous live segments, rejecting cuts and replays.

Start with coarse temporal descriptors, then refine promising matches. Replays can match an earlier configuration very well, so spatial agreement alone is insufficient: require consistent temporal progression and segment context.

After alignment, fuse ball observations according to reliability; do not average incompatible positions. A second view can also reveal that a tactical ball position is unreliable.

If missingness were independent, 59% tactical coverage and 50.5% broadcast coverage would imply roughly 80% union coverage. **That is only an independence benchmark**: replay rejection and correlated failures could reduce the actual gain substantially.

**Validation:** align using players, then assess held-out ball agreement and contact timing. Measure additional reliable coverage specifically within tactical gaps.

I would time-box this to a pilot. It could have the largest ceiling, but it could also consume your week.

**8. Optimise segmentation decisions for spellF1 only after improving evidence**

Viterbi is a suitable computational framework. The mismatch is its objective: a best-scoring framewise path need not maximise expected spellF1.

A practical extension is to retain several plausible segmentations around disputed events:

- no turnover versus a short turnover;
- no stoppage versus a brief stoppage;
- alternative contact or restart times.

For each candidate output, evaluate its spellF1 against weighted plausible latent paths using the **actual one-to-one matcher**. Select the output with the highest weighted expected score.

However, hand-scored paths do not supply calibrated probabilities. Exponentiating your scores does not fix that. Without external calibration, use this as a robustness analysis across plausible hypotheses, not as a trustworthy expected-score optimiser.

For uncertain timing, optimise adjacent spells jointly. A boundary’s midpoint or posterior median is not generally optimal because the five IoU thresholds and unequal neighbouring durations matter.

For short possessions, distinguish:

- **strong event evidence, short duration:** permit them;
- **weak team evidence, short duration:** retain the conservative penalty.

Do not apply a universal minimum duration.

`X` provides no special advantage under forward-fill. It can implement “hold previous,” but cannot represent uncertainty to the scorer.

**What I would actually do in the remaining week**

1. **Day 1:** verify scorer behaviour with synthetic sequences; audit missing-evidence tie-breaking and `D` shortcuts; build masked-ball tests and fixed-mask diagnostics.
2. **Days 2–3:** implement contact-chain confirmation and paired stoppage candidates. These directly address timing and short events without replacing the whole system.
3. **Day 4:** add whistle evidence if audio is usable; otherwise prototype the ball-free classifier.
4. **Day 5:** test external calibration under corruption, provided compatible labels are readily usable. Otherwise spend the time on a tightly scoped broadcast-alignment pilot.
5. **Days 6–7:** compare a small, preregistered set of variants using withheld evidence; freeze parameters; verify deterministic regeneration and document data/model versions.

I would prioritise **independent evidence for event boundaries over additional smooth state features**. Your current system already produces plausible global statistics. The next improvement should explain specific missing or mistimed events—and survive a test that did not generate those events in the first place.
