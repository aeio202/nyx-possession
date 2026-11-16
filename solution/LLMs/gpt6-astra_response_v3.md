I reviewed only [brief_v2.md](/C:/projects/Barcelona/first/solution/LLMs/brief_v2.md).

**My strongest recommendation is to investigate information discarded by the touch detector, then train a small classifier on candidate events.** I would keep switch cost 12 as the default. The brief supports “little evidence under the current features”; it does not yet establish that the tracking contains little recoverable evidence.

There are also two material qualifications to your reasoning: timing matters greatly for short spells, and your external degradation may reproduce aggregate statistics without reproducing the errors that determine possession accuracy.

The ranges below are **speculative numbers of possession episodes corrected**, not measured forecasts. They could be zero, overlap, and should not be added together.

| Rank | Experiment | Weakness targeted | Plausible reach | Effort | Confidence in useful gain |
|---|---|---|---|---|---|
| 1 | Recover weaker contacts and retain uncertain team attribution | Short possessions, first-time passes, some aerial endpoints | 0–15 episodes | About 1 day | Medium |
| 2 | Use set-piece ownership at already detected restarts | Wrong team immediately after a restart | 0–5 episodes | A few hours | Medium–low |
| 3 | Train a small classifier over candidate possession episodes | Brief control versus touches; pressing ambiguity | 0–10 additional episodes | About 1 day | Medium–low |
| 4 | Select local edits by expected spellF1 | Uncertain insertions and short-spell boundaries | 0–5 episodes | Half a day | Medium, conditional on useful confidence estimates |
| 5 | Repair uniquely identifiable tracklet breaks and team flips | Missing or mislabelled carrier | 0–5 episodes | Half to one day | Medium–low |

**Before comparing those experiments, I would strengthen the external test.**

Your degradation description mentions smoothing the ball over one second, but does not explicitly mention replacing its trajectory with straight paths between retained contacts. If you already do that, this concern is addressed. Otherwise, it is a substantial mismatch: smoothing a real trajectory preserves information that interpolation can erase.

I would test a small, fixed family of degradations that includes:

- Straight interpolation between retained contact anchors, with some contacts omitted.
- Carrier dropout concentrated around crowded interactions, alongside ordinary tracklet losses.
- Short team-label errors and tracklet exchanges.
- Ball losses conditioned on difficult situations, alongside your existing long-gap process.

Matching strike rate, speed quartiles and control share is useful, but the decisive quantities are **contact recall and team-attribution accuracy conditional on possession duration and event type**. A degradation can match all three aggregate statistics while making interceptions much easier than yours.

Avoid making every annotated contact an interpolation anchor. That would give the synthetic tracking unusually reliable evidence at precisely the events you are trying to detect.

There is also an additional allowed dataset worth considering: **IDSSE provides seven Bundesliga/Bundesliga 2 matches with synchronized tracking and events, under CC BY 4.0.** This offers fresh external matches beyond the repeatedly inspected Metrica set. [Dataset publication](https://www.nature.com/articles/s41597-025-04505-y). The documented reader exposes home/away possession and dead/alive codes from the tracking files; their provenance and definitions need checking before treating them as an independent possession reference. [Reader documentation](https://floodlight.readthedocs.io/en/develop/modules/io/dfl.html).

Time-box importing one match to half a day. Its main value would be a fresh test of a frozen candidate, not another source of repeatedly consulted validation scores.

**1. Recover contacts that your current detector cannot credit.**

Your contact pipeline has three gates: a velocity change exceeding 6 m/s, a nearby player, and a one-metre team separation. A first-time pass in a crowded area can fail any of them despite leaving useful geometric evidence.

I would separate two questions:

- Did a contact probably occur?
- Which team probably made it?

For contact detection, fit the incoming and outgoing trajectory over windows extending beyond the smoothing ramp. Measure the improvement from allowing a change in direction or speed at a candidate time. Compare that improvement with local tracking residuals, rather than relying exclusively on one absolute velocity-change threshold.

This is particularly appropriate for your piecewise-straight ball paths: **the joins may retain information even when the local derivative test misses them.** Trajectory simplification has also been used to generate candidate ball touches in published football work, although that does not establish its accuracy on your feed. [PathCRF, data preparation](https://arxiv.org/html/2602.12080v1#S3.SS1).

Then retain ambiguous attribution instead of discarding it. Useful features are:

- Distances of the closest two players from each team around the candidate.
- Whether each player approaches the contact location before it and separates afterwards.
- How well each player’s motion explains the incoming-to-outgoing transition.
- Whether the outgoing segment reaches a plausible teammate at its arrival time.
- Whether the candidate coincides with a track discontinuity.

A player merely crossed by the interpolated ball path should lack the trajectory change and subsequent action. A first-time passer may have both despite never satisfying your co-motion control feature.

This is different from adding weight to your existing single touches: it changes which contacts are observable and how much information survives attribution.

**First stop test:** on degraded external matches, measure how many currently missed possessions acquire a plausible correctly attributed contact under this detector. Use the external labels only to measure this coverage, not to generate the candidates. If coverage barely improves, stop before building a more complicated decoder.

On the target match, count the newly supported candidate episodes automatically. That count gives a real upper bound on opportunity. No candidate coverage means no plausible gain.

There remains an irreducible limit: if interpolation removes the contact and the observed player movements are compatible with either outcome, tracking alone cannot determine the winner of that header or duel.

**2. Use restart-team information where it has a narrow, meaningful role.**

The rejected phase prior does not settle the usefulness of **set-piece ownership at a detected restart**. Those are different claims: a broad phase can span several possessions; a correctly identified restart specifies the team performing one action.

Where a set-piece tag has a team:

- Associate it with an independently detected restart.
- Combine its team with the first kicker or initial outgoing contact.
- Apply the evidence at the start of the live spell, rather than throughout the tag interval.

This could correct a restart assigned to an opponent who happens to be closer to the ball during its initial flight. It does not require using the tag’s opening time as the restart time.

The opportunity count is straightforward: how many existing restarts have disagreement between the decoded team and mutually supporting tag/kicker evidence? If there are only two, this is a two-event opportunity.

The external test must include tag-team mistakes. Synthetic tags copied perfectly from event labels would exaggerate the benefit.

**3. A learned model is worth trying at the event level.**

I would not start with a replacement frame classifier. With three matches, thousands of adjacent frames do not provide thousands of independent examples, and long easy possessions can dominate training.

Instead, train a regularized logistic model or a shallow boosted tree on **candidate possession episodes**.

Generate candidates from inputs alone: the new contacts, ambiguous existing switches, and brief opposing-team evidence bursts. Include negative candidates such as passes crossing opponents, apparent control by pressing players, and tracklet failures.

Use a compact feature set:

- Existing integrated control evidence.
- New contact-fit strength and team-attribution uncertainty.
- Incoming/outgoing ball geometry.
- Local player approach, deceleration and separation.
- Evidence of an outgoing action reaching a teammate.
- Local tracking completeness.
- Duration and distance from the nearest stoppage.

Train the target separately under each external labelling convention: **does this candidate correspond to an opposing-team possession?** Also evaluate contact-team prediction separately, so you can distinguish better physical attribution from a change in what counts as possession.

Use whole-match splits. Keep every degraded version of a source match in the same split. Normalize attacking direction and use team-relative features; persistent identities and track-slot numbers should not be inputs.

Evaluate:

- Precision and recall of newly introduced episodes.
- SpellF1, including damage or repair to neighbouring spells.
- Results separately for under 4 s, 4–8 s and longer spells.
- Stability across degradation families and labelling conventions.

My confidence is higher in learning **which ambiguous contacts are credible** than in learning an entire possession system. Three matches might support that small classification problem. They cannot establish reliable transfer to this match.

If the model’s gain comes entirely from counting more isolated touches and disappears under the definition-following labels, it has reproduced your rejected experiment.

**4. Expected spellF1 gives a principled decision rule, but requires uncertainty estimates.**

Your description that a false change “destroys” a long possession is sometimes true, but depends on where the inserted spell falls.

Suppose the truth is one 40-second home spell:

- Insert a two-second away spell in the middle: the remaining home spells are each 19 seconds, with IoU \(19/40=0.475\).
- Insert it near the beginning, leaving a 36-second home spell: that fragment still has IoU \(36/40=0.9\).

The second error preserves a home match at all your thresholds. The first loses it at the higher thresholds. Conversely, a genuine central away spell can repair more missed matches when inserted correctly.

For one IoU threshold,

\[
F_1=\frac{2M}{P+G},
\]

where \(M\) is matched spells, \(P\) predicted spells and \(G\) true spells. For a fixed hypothetical truth, an edit improves the score exactly when

\[
\Delta M > \frac{F_1}{2}\Delta P.
\]

Inserting `A` inside `H` adds two predicted spells. Thus, identifying one additional real event is not sufficient by itself: the edit’s effect on neighbouring matches matters.

For uncertainty, let \(p\) be the probability the proposed brief possession exists, \(g\) its expected score gain when real, and \(\ell\) its expected score loss when false. Insert when

\[
p\,g>(1-p)\,\ell.
\]

There is no universal confidence threshold. Flanking durations, boundary uncertainty and nearby stoppages change \(g\) and \(\ell\).

Practically, compare a small set of local hypotheses—keep the current output, insert the candidate, or adjust supported boundaries—using the official scorer on external examples. Learn or tabulate which combinations of confidence and geometry have positive utility. Score interacting edits together.

Do not obtain \(p\) by exponentiating the hand-set Viterbi scores: they are not calibrated probabilities.

**Timing needs more attention specifically for the short spells you want to recover.** For a true and predicted interval of equal duration \(d\), displaced by \(\delta\),

\[
\operatorname{IoU}=\frac{d-|\delta|}{d+|\delta|}.
\]

At IoU 0.7, a two-second spell tolerates only about **0.35 seconds** of displacement. Your “1–3 seconds costs little” conclusion is reasonable for many long spells, but not for short ones.

This supports estimating boundaries from contact geometry. It does not support moving an uncertain event to an arbitrary, less damaging location.

**5. Repair tracklets only where continuity makes the answer identifiable.**

A small useful intervention is to link tracklet endings and beginnings using position and velocity continuity **without initially enforcing team agreement**.

Where the continuation is unique and the surrounding observations consistently indicate one team, a brief conflicting team label can be repaired. Likewise, a very short gap may be bridged where there is no competing plausible trajectory.

The distinction matters:

- A unique continuation with a temporary team flip is potentially recoverable.
- A whole continuously mislabelled track is not recoverable from continuity alone.
- Two players crossing in a duel may make the continuation ambiguous.

Also test whether possession switches cluster at incumbent-carrier disappearance. Losing that track should weaken confidence; it should not by itself establish opposing control.

Validate this by injecting track breaks and label flips into external matches, then measuring both repair accuracy and downstream spellF1. A continuity repair that is occasionally wrong in duels can be more damaging than leaving the gap.

**The labelling convention is not identifiable from the available statistics.**

The wording, 17 public possessions and their mean duration do not determine whether a particular first-time clearance counts. Different conventions and different match styles can produce the same mean.

The shortest public spell rules out a universal minimum-duration interpretation. It does not imply that every brief recovery counts. The organisers’ duration and pass-count examples are described as proxies, so I would not interpret them as mandatory conditions.

Choosing the external convention closest to the public mean is both weak statistically and a form of tuning if it influences the system choice.

A defensible approach is to:

- Keep several plausible conventions.
- Prefer improvements that survive across them.
- Retain 12 where performance is flat.
- Use externally measured worst-case regret if you must choose between trade-offs.

A general clarification from the organisers about intentional first-time passes and clearances would be more informative than further analysis of the public mean.

**There is no label-free check that reliably resolves “controlled possession” in all these cases.**

Your reversal test detects a physical response to a change of interaction. It cannot determine the organiser’s semantic treatment of that interaction.

The strongest additional check I would try is a **withheld downstream-action check**. For candidates proposed using ball geometry, separately assess evidence that the proposed team subsequently receives, directs or deliberately plays the ball. Calibrate the check on external controlled possessions versus isolated touches, conditioning on candidate duration.

This is only a partly independent check if that evidence was withheld from candidate selection. Once the final model consumes it, agreement becomes a diagnostic, not validation.

Pair it with:

- Stability under small, plausible tracking perturbations.
- Checks that improvements do not concentrate at track births/deaths.
- Agreement across genuinely different feature families.

A stable or mutually agreeing prediction can still be wrong. Unlabelled target distributions cannot, without additional assumptions, establish that source-domain accuracy transfers. [Domain-adaptation limitations](https://proceedings.mlr.press/v9/david10a.html).

**Several validation claims deserve narrower wording.**

- **“Match 3 is checked once per choice” does not preserve a hold-out** if those checks influence later choices. It then functions as validation data. Repeated model selection can overfit the evaluation criterion. [Cawley and Talbot](https://jmlr.org/papers/v11/cawley10a.html).
- **The public window must not decide between variants.** Reporting that a variant added two false possessions is not itself the problem; rejecting it because of those public labels would be tuning.
- **Dead-ball detection is near its ceiling on your external construction.** That is useful evidence, but does not demonstrate the same ceiling on this match.
- **The reversal test’s estimated “real share” needs transportable class-conditional behaviour.** Its weaker target signal makes that numerical interpretation less secure, even if it remains a useful diagnostic.
- **A possession longer than one minute is not inherently implausible.** Treat duration as a diagnostic distribution, not a correctness constraint.
- **Uncertainty should reflect temporal dependence and match variation.** Independent-frame bootstraps and many degradation seeds cannot replace independent matches.

For the four days, I would spend the first half-day checking the degradation and contact-coverage opportunity, then about a day on contact reconstruction. Proceed to the small classifier only if it exposes useful candidates. Use the remaining time for external spell-level comparisons, limited metric-aware selection and a frozen final run. Restart ownership is the inexpensive side experiment; tracklet repair is conditional on finding enough uniquely repairable cases.

The decision to stop should be explicit: **if the new detector exposes almost no additional credible events, retain the current system.** Changing the decoder cannot recover short possessions whose distinguishing information is absent.
