# Working rules for this project

Constraints that come from the competition (RULES.md, FAQ.md, SUBMISSION.md) and the working
practice adopted because of them. Follow these in every session.

## Hard rules from the competition

1. **Labels come from an algorithm.** No hand labels or hand corrections on this match, in any
   amount, for any purpose (not even validation). No rules or constants tied to specific frames
   of this match.
2. **No private ground truth, no human-produced data about this match** (event data, corrected
   tracking, annotations from any source). Human-labelled data about *other* matches is allowed
   and must be documented.
3. **The public 5 minutes are for checking the pipeline, not for training or tuning.**
4. **The repository must regenerate the submitted file exactly.** Keep the pipeline deterministic
   and the dependencies pinned (`solution/requirements.txt`).
5. **Do not redistribute the data or anything that reconstructs it.** `data/`, `solution/cache/`
   and `solution/output/` stay out of git. Do not paste frame-level tracking into documents.
6. **No match data to hosted LLMs.** FAQ.md: participants shall not upload or make available to
   any third-party hosted or cloud-based LLM "any videos, datasets ... or any extracts thereof".
   Consequences for assistant-driven sessions:
   - never view video frames or images rendered from the match;
   - never print raw tracking rows or per-frame positions into the conversation;
   - print only aggregates and derived statistics, and as few as the question needs;
   - whether even that is acceptable is the user's call (open decision 1 in `STATUS.md`).
7. Everything in the pipeline must be accessible to the organisers and explained in the technical
   document (`solution/README.md`), including assets that were tried and dropped.

## How to change the model

- **Start from a mechanism, not from a score.** Identify a concrete failure (a pass past an
  opponent counted as control, a stoppage found late), explain it physically, fix that.
- **Constants are round-number priors** in metres, seconds or m/s, with the reasoning in a comment
  next to them in `model.py`. Do not grid-search them.
- **Keep the scale of evidence in mind:** per-frame dead/alive evidence is ~0.1 (2.5 per second);
  transition costs are 3–25. A stoppage needs boundary events or several seconds of evidence.
- **One change at a time**, then run the checks below before the next.
- **Update `README.md`, `STATUS.md` and `HISTORY.md`** when a change is kept or dropped.

## How to judge a change without ground truth

In this order:

1. `python solution/tag_agreement.py old.csv new.csv` — H/A quality. Look mainly at which version
   the tags side with **on the frames where the two differ**. Caveat: phase tags favour smoother
   labellings, so when the possession count changes, repeat with the count matched (adjust
   `switch_cost` temporarily) before believing a gain.
2. `python solution/audit.py new.csv` — stoppages: tagged set pieces with a decoded restart near
   the tag start, set pieces with no stoppage near, kick-off timing against the two published
   kick-off frames, number of stoppages, dead share.
3. **Plausibility:** dead share around 0.45–0.53 (typical effective playing time, plus this match's
   ~2 minutes graded before the second-half kick-off and four goals); around 100 stoppages; no
   possession over a minute; long stoppages explained by `GOALS` tags.
   Also the last line of `audit.py`: referee whistles heard in the audio against decoded
   stoppages. It is independent of the tracking; do not tune the whistle detector on it.
3b. `python solution/external/calibrate.py [parameter values...]` — the same pipeline on two
   labelled other matches, scored with the official metric, under five label conventions
   (`MERGE_BRIEF_S=0`, `1.5`, `3`; `CONTROLLED_PASSES=1`, `3`). Accept a change only if it is
   good under the first three and does not lose under the last two (they follow the definition).
   Then check it **once** on the hold-out match (`EXTERNAL_GAMES=3`) under all five; drop it if
   it loses there. Never sweep a parameter on the hold-out. **Known
   bias:** the simulated labels count every brief
   recovery, so it over-rewards anything that trusts the ball more (a lower switch cost, touch
   evidence). A gain there must also make sense on the real tracking.
4. `python solution/sensitivity.py` — no single ±30 % change of a prior should move more than a
   few percent of frames; report the ones that do.
5. `python solution/inspect_public.py new.csv` and the public score — **last, and only as a
   correctness check** (alignment, label meaning, is the targeted failure gone). A public-score
   difference under ~0.06 spellF1 is one possession. Never keep or drop a change on it alone, and
   never fit a constant to it.

## Before submitting

- `python solution/run.py --name <team_name>` then
  `python evaluation/validate_submission.py solution/output/<team_name>.csv` on the exact file.
- Run it twice and `cmp` the outputs.
- Technical document named after the team; public repository URL; one form response per team.
