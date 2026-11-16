**My highest-priority experiment would be to recover contact events more reliably, then score short possession candidates as whole events.** I would keep the existing decoder as the baseline. Your evidence does not yet establish that the missing possessions are invisible in the tracking; it establishes that they are nearly invisible to your current features.

The biggest concern is your external validation: smoothing clean ball tracking is not equivalent to replacing its trajectory with straight lines between contacts. That difference could change which ideas appear useful.

The recommendations below are hypotheses based on your brief, not findings from inspecting the underlying match.

**1. Ranked priorities**

| Priority | Experiment | Weakness targeted | Effort | Confidence |
|---|---|---|---|---|
| 1 | Audit the degradation model and distinguish undetected contacts from unattributed contacts | Whether your experiments transfer at all | Half a day | High value diagnostically |
| 2 | Recover trajectory breakpoints using longer temporal context and retain ambiguous team attribution | First-time passes, interceptions, some clearances | About one day | Medium |
| 3 | Classify proposed short possession intervals using local player movement and contact geometry | Brief possessions with weak control evidence | One to two days | Medium, conditional on candidate coverage |
| 4 | Select candidate edits by their expected effect on the official spell metric | False splits versus missed possessions | Half to one day | High confidence in the principle; medium in practical gain |
| 5 | Repair team labels on tracklets using tactical-video shirt appearance | Mislabelled tracked players | About one day | Medium mechanism confidence; unknown reach |

These overlap; I would not attempt all five independently within four days.

I cannot honestly estimate “this fixes 15 events” without candidate counts. Below I specify how to measure the reachable number. That is more informative than extrapolating seven public-window misses to the whole match.

**2. Your first audit should separate three different failure modes.**

For every missed short possession in the external matches, measure:

1. Was there a detectable change in ball trajectory?
2. If so, was a plausible player present near that change?
3. If so, did the attribution rule reject it, or did the decoder reject the accumulated evidence?

Your “under one credited touch” statistic combines all three. They require different remedies.

In particular, demanding that one team be **at least 1 m nearer than the other** is likely to suppress evidence precisely during interceptions and duels. That might be appropriate for confidently attributing individual touches, but it is expensive if rejected touches disappear entirely.

Also inspect the degradation pipeline. Your description mentions one-second smoothing but does not explicitly mention reconstructing the ball as contact-to-contact straight segments.

If that reconstruction is absent:

- External passes may retain curvature or small physical variations unavailable in your target.
- External contacts may have different breakpoint sharpness.
- A detector can perform well externally for reasons that cannot transfer.

Build a small, fixed family of degradations that includes straight-segment interpolation, smoothing, contact-location error, and occasional missing contact knots. Use external event information to generate these simulations, but never expose those events to the predictor. Do not assume the event feed exhaustively enumerates physical touches.

Metrica’s repository supplies synchronized tracking and events and links its event definitions; synchronization alone does not establish that every physical contact is annotated. [Source: Metrica Sports sample data](https://github.com/metrica-sports/sample-data).

Validate more than marginal statistics. Add:

- Breakpoint spacing and strength.
- Distance between breakpoints and nearest players.
- Team-attribution ambiguity at breakpoints.
- Missing-player frequency around external possession changes.
- Ball-loss frequency conditional on long passes, crowding, and pitch position.

**Matching speed quartiles and average control share does not establish that the simulator reproduces the errors that matter.**

Reach: this audit does not directly fix events, but it tells you whether the next experiment has five opportunities or fifty.

**3. Recover contacts from piecewise trajectory structure, not only a short-window velocity threshold.**

Your present detector asks whether velocity changes by more than 6 m/s across ±0.3 s. A one-second smoothing ramp can spread a genuine change so that this test misses it. First-time passes with modest redirection are especially vulnerable.

A concrete alternative:

- Fit a single constant-velocity trajectory over a short window.
- Fit two constant-velocity trajectories with a possible breakpoint.
- Measure the reduction in position residual after penalizing the extra breakpoint.
- Repeat over a few externally fixed window lengths.
- Require reasonable fit on both sides and continuity at the inferred contact location.
- Reject or downweight windows spanning tracking gaps or obvious jumps.

The useful signal is **a sustained change between incoming and outgoing motion**, rather than a large instantaneous derivative.

This can detect changes in speed as well as direction. It cannot recover a contact that leaves no observable change, or one the tracker has completely interpolated away.

Then retain **soft team attribution**:

- Distance of each candidate player to the inferred contact point.
- Whether the player approaches that point before the event.
- Whether their trajectory passes through its neighborhood.
- Presence and proximity of opponents.
- Track continuity and localization quality.

Do not give every soft contact a possession bonus. Pass its uncertainty forward to an event-level decision.

This differs materially from the failed single-touch experiment: that experiment added weight to existing credited touches; this one changes contact recall and preserves evidence currently discarded by the attribution margin.

**Reach:** count missed external spells gaining at least one additional plausible contact. On the target, count distinct candidate spells newly supported—not raw additional breakpoints. If most missed external spells remain without candidates, stop here.

**Label-free check:** test whether new breakpoints survive modest coordinate perturbation and modest changes in fitting window. Compare player proximity at those breakpoints with matched non-breakpoint times from similarly fast ball segments. This tests whether you found plausible contacts, not whether they count as possessions.

**4. Use local player movement to classify candidate spells, rather than adding a global team-motion prior.**

There is potentially useful player-only evidence beyond collective reversal. Its strongest role is to distinguish plausible short events already localized in time.

For each proposed `H → A → H` interval, construct features from a neighborhood around its entry and exit:

| Signal | Computation | Why it might help |
|---|---|---|
| Entry interception geometry | Incoming ball segment, inferred contact point, and nearby players’ approach trajectories | Separates a player reaching the ball from an opponent merely standing near its interpolated path |
| Immediate distribution | Outgoing segment after contact and a plausible teammate near its endpoint | Captures first-time passing without a carry |
| Local pressure response | Changes in distances and closing velocities of the nearest opponents after contact | Control may cause opponents to converge on a new carrier |
| Teammate response | Changes in nearby teammates’ movement relative to the candidate carrier and outgoing ball | Offers weak evidence of supporting a newly established attack |
| Evidence for the exit | A separate plausible recovery by the original team | Supports a complete short possession rather than one isolated deflection |

Use a few nearest players or distance-weighted summaries. Long-term identities are unnecessary; short track continuity is enough.

These signals are imperfect:

- A loose ball attracts opponents too.
- A deflection can trigger collective reversal.
- A clearance may be deliberate without satisfying the possession convention.
- Aerial contacts may have no recoverable ground-location evidence.

The discriminating question is therefore:

> Does the joint entry–interior–exit pattern resemble a short possession, under each external convention?

This is not the rejected “lower the cost if there is a following pass.” That experiment conditioned the switch cost on one feature. Here the decision unit is an entire interval and both of its boundaries.

**Reach:** define candidate recall before training. If your generator covers only 20% of missed 4–8 s possessions, no classifier can recover more than that 20%. Likewise, improving classification precision cannot recover possessions with no candidate.

**Label-free check:** reserve some downstream signals for validation rather than training. For instance, if the classifier uses only local motion up to one second after entry, assess later externally validated continuation evidence separately. This is supporting evidence, not target accuracy.

**5. A small learned event model is worth trying; a replacement frame classifier is a worse four-day bet.**

I would train a regularized logistic model first, with shallow boosted trees as a second option only if your permitted dependencies allow them.

Use:

- **Unit:** a proposed insertion, removal, or boundary correction—not an individual frame.
- **Features:** your existing evidence summaries, breakpoint evidence, attribution ambiguity, local movement, missingness, and surrounding spell lengths.
- **Targets:** whether the candidate corresponds to a true possession, separately under each convention.
- **Evaluation:** the full output scored by the official scorer, including damage to neighboring spells.

An alternative target is the candidate’s actual spellF1 improvement on an external match. That directly captures neighboring damage, although it depends on the baseline prediction and surrounding errors.

Important controls:

- Include hard negatives where the current pipeline nearly switches but should not.
- Keep all degradation variants of a given match together.
- Evaluate on held-out matches, not random frames or randomly split candidate events.
- Report performance on short events separately.
- Compare across degradation families, not just random corruption seeds.
- Avoid match ID, absolute clock time, and named-team features.

Three matches can contain enough candidate events for a small model, but they still provide only three match environments. Thousands of correlated windows do not solve domain transfer.

**My adoption criterion:** useful improvements across multiple plausible degradations and conventions, with no material collapse under the others. A tiny average gain confined to one simulator should not replace your baseline.

**6. Optimize whether to insert an event using the actual spell metric.**

Your intuition that event existence matters is right. Two refinements matter.

First, a false insertion does not necessarily destroy every match involving the original long spell. One surviving fragment may still match it at lower IoU thresholds.

Second, timing is not forgiving for the very possessions you are missing. Two equal two-second intervals shifted by one second have:

$$
\operatorname{IoU}=\frac{1}{3}.
$$

They match at 0.3 but fail at thresholds above one third. A one-second error can completely separate two 0.76-second intervals.

Thus:

**Timing is often forgiving for long spells; it can determine whether a short recovered spell scores at all.**

For each candidate edit, consider two hypotheses: the short possession exists, or it does not. Let:

- $p$ be its estimated probability of existing;
- $g$ be the spellF1 gain from inserting it when it exists;
- $\ell$ be the spellF1 loss from inserting it when it does not.

In this simplified two-hypothesis setting, insert when:

$$
pg-(1-p)\ell>0
\quad\Longleftrightarrow\quad
p>\frac{\ell}{g+\ell}.
$$

The threshold depends on neighboring spell lengths, event location, and boundary uncertainty. It should not be a universal “0.5 probability” rule.

Estimate $g$ and $\ell$ by running the official scorer on complete external predictions with and without the edit. For an uncertain target candidate, average over a small set of plausible boundary placements and convention scenarios. Nearby edits interact, so score their combined alternatives together.

General F1-optimal classification thresholds already depend on the objective and score distribution; the familiar calibrated-classifier result does **not** directly transfer to one-to-one temporal spell matching. [Source: Lipton, Elkan, and Narayanaswamy, “Thresholding Classifiers to Maximize F1 Score”](https://arxiv.org/abs/1402.1892).

A practical implementation need not replace Viterbi. Keep it, propose a small number of event edits, and select among those alternatives.

**Do not inject `D` as a way to split uncertain live possessions.** That creates an unsupported stoppage rather than resolving possession uncertainty.

**7. You cannot identify the hidden convention from the available aggregate statistics.**

The public sample’s mean of 14.2 s is weak evidence about the full-match annotation policy. It depends on match phase, stoppages, and which five minutes were selected.

A 0.76-second possession proves that some short events count. It does not establish that all recoveries lasting that long count, or which observable feature made this one count.

Also, duration merging is only a proxy. It can erase a short but clearly controlled first-time passing sequence while retaining a longer scramble. A definition-based convention and a duration-based convention can share a mean and disagree on the events that matter.

I would:

- Keep cost 12 as the established baseline.
- Avoid weighting conventions by similarity to the public sample’s mean.
- Compare candidate methods by their regret under each plausible convention.
- Prefer improvements that survive uncertainty about the convention.

For example, measure each method’s deficit from the best tested method under each convention, then seek a small worst deficit. This does not discover the true convention; it makes the uncertainty explicit.

There is also a rules issue in your existing reasoning: **if cost 8 or single-touch evidence was rejected because it added two false public-window possessions, that is tuning on the public window.** Reporting that observation is different from using it to select the submitted system. Base future choices on external data.

**8. No label-free check can certify “controlled possession,” but your checks can become more informative.**

I would use three distinct checks:

- **External candidate precision:** among events resembling the target candidates, how often is the proposed edit correct under each convention?
- **Target feature support:** do the target candidates fall within the ranges and combinations seen externally? Explicitly distrust out-of-distribution cases.
- **Withheld behavioral evidence:** do added events show downstream movement or continuation patterns not used to select them?

Match comparison groups by ball speed, pitch region, missingness, crowding, and distance to stoppages. Comparing candidate switches against arbitrary random moments is too easy and may confound the result.

Your reversal test has an additional transfer assumption. Recovering the fraction of real switches from a mixture requires the conditional reversal distributions for true and false switches to transfer. You already observe a weaker target signal. That weakens the interpretation of the inferred “real share”; it is not merely wider sampling uncertainty.

If you use reversal as a model feature, stop treating the same reversal statistic as independent validation.

**Reach:** these checks can reject harmful batches. They are unlikely to resolve individual ambiguous events, especially in groups smaller than your existing uncertainty allows.

**9. A targeted visual repair may be more feasible than ball detection.**

For team-mislabelled tracklets, consider tactical-video appearance:

- Project tracked player positions into the image with the homography.
- Sample small torso regions above the projected ground points.
- Accumulate color evidence over each tracklet.
- Learn team appearance from automatically selected, spatially isolated tracklets with consistent labels.
- Correct only strong, persistent contradictions.

Player crops are much larger than the ball, making this a plausible CPU task. But camera geometry, crop contamination, goalkeeper kits, and referees can defeat it. Keep an “uncertain appearance” outcome.

Validate by injecting team-label errors into external data and checking the effect of repairing them; validate the visual component on other permitted footage if available.

**Reach:** count suspicious tracklets that actually participate in possession decisions. Ten suspicious tracklets far from the ball offer essentially no benefit. Untracked players remain untracked.

I would pursue this only if the initial audit shows attribution failures around existing tracks are a substantial problem.

**10. Two further validation corrections matter.**

“Match 3 checked once per choice” is a repeatedly consulted validation match if its result affects which choices survive. It is no longer a fresh hold-out. Repeated selection against a finite evaluation set can bias reported performance. [Source: Cawley and Talbot, “On Over-fitting in Model Selection and Subsequent Selection Bias in Performance Evaluation”](https://www.jmlr.org/beta/papers/v11/cawley10a.html).

For the remaining work, freeze a small experiment set, report results across all three matches, and describe them as development evidence. Leave-one-match-out evaluation is useful, but it cannot undo earlier exposure.

Your dead/alive oracle result is strong evidence about **the external simulations**. It does not prove dead-ball detection is at its ceiling on this target. Nevertheless, given your audits and time limit, deprioritizing it is reasonable.

Likewise, “differences under 0.04 are noise” should be treated as an organizer heuristic unless its statistical basis is known. A fixed submission’s score is deterministic; uncertainty concerns how well your validation predicts it.

**My four-day allocation would be:**

1. **Day 1:** audit contact detection versus attribution failures; add interpolation-aware degradation; measure candidate coverage.
2. **Day 2:** implement the breakpoint-based candidate generator and soft attribution. Stop if coverage remains poor.
3. **Day 3:** train one small event model and compare scorer-based candidate decisions against the existing decoder.
4. **Day 4:** freeze decisions, evaluate across matches/conventions/degradations, and verify deterministic regeneration.

The experiment I would prioritize is whether **missed breakpoints and discarded ambiguous contacts can support a jointly credible entry and exit for short possessions**. If that fails, I would keep the current system rather than expect a more elaborate decoder to recover information the inputs do not contain.
