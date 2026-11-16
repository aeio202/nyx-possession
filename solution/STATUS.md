# Project status

Read this first. It is the working context for anyone (human or assistant) picking the project up.
Companion files:

- `HANDOVER.md` — self-contained brief for a new team member taking the project over
  (setup, state, method, what is left, freeze, and a prompt for their AI assistant).
- `README.md` — the **technical document deliverable** (approach, assets, external data,
  limitations). Keep it accurate whenever the model changes; it is what gets submitted.
- `PLAN.md` — the improvement plan written after two external LLM reviews, with the result of
  each finished step and, in **section 6, the current priorities**.
- `HISTORY.md` — what was tried, in order, what worked, what was dropped and why. Check it before
  trying an idea: several plausible ones have already been tried and reverted.
- `WORKING_RULES.md` — the competition rules that constrain how we work, and how to judge a
  change without ground truth.
- `LLMs/brief_v2.md` — the current brief for asking other LLMs for ideas (2026-11-12, written
  from this file; aggregates only). The user is sending it to other frontier models; put their
  answers next to it and assess them against `HISTORY.md` before trying anything.
  `LLMs/brief.md` is the first round (2026-11-11) with its two answers; outdated in places.

## Next session: start here

1. Read this file, then `WORKING_RULES.md`. Skim the last four entries of `HISTORY.md`.
2. **The upload file is ready:** `solution/output/NYX.csv` (team NYX), byte-identical to
   `solution/output/submission.csv`, valid, sha256 starts `0de7e99bc0f3cd2a`. Regenerate with
   `python solution/run.py --name NYX`. If nothing else gets done, upload it as is.
3. **Everything is committed** on branch `nyx-solution` (latest `854b522`; nothing pushed).
   Data, cache and outputs are gitignored. The working tree was clean at the end of the session.
4. **One optional modelling idea left (about half a day), proposed 2026-11-12, not started:**
   extend the restart owner to restarts **without** a team tag (throw-ins; corners and goal kicks
   the tagging missed). At a restart the ball rests and the taker stands at it: the player
   nearest the resting ball just before the decoded restart kick is the taker, and that team has
   the ball until the other team's net evidence reaches 0.5 (same rule as `restart_owner`).
   Steps, as for every change:
   1. count the opportunity on the real match (restarts with no teamed tag where the first
      decoded spell is not the geometric taker's team);
   2. matches 1–2 under all five labellings (`MERGE_BRIEF_S=0|1.5|3`, `CONTROLLED_PASSES=1|3`),
      also with `INTERP=1`;
   3. match 3 once (`EXTERNAL_GAMES=3`);
   4. real-match checks (`tag_agreement.py`, `audit.py`, reversal on added/removed changes);
   5. **ask the user before changing the submitted file.**
   On the practice matches the tagged version gained +0.003 with tags on 60 % of restarts;
   expect a similar, small gain at best.
5. **Then the freeze (keep the last day, 16 November, for it):**
   1. rename the technical document: `README.md` → `NYX.md` (or a PDF);
   2. make the repository public without `data/`, `solution/cache/`, `solution/output/`,
      `solution/external/data/`; decide whether `STATUS.md`, `HISTORY.md`, `PLAN.md`,
      `WORKING_RULES.md` and `LLMs/` go public (internal notes);
   3. `WORKING_RULES.md`, "Before submitting": regenerate twice, `cmp`, validate;
   4. one form response per team.
6. **Still open with the organisers:** decision 2 (the public window was read after changes as
   a correctness check, never to fit a constant). Worth one question.
7. **Not worth doing in the time left** (assessed 2026-11-12): a learned classifier on the
   practice matches; ball detection in the video (multi-day, local only); the second-half
   kick-off timing; the four artefact stoppages; dead-ball refinements; importing IDSSE matches.

### What was done on 2026-11-12 (details in `HISTORY.md`)

| step | outcome |
|---|---|
| collective-reversal test (`reversal.py`) | instrument kept; cannot place the switch cost |
| definition-following external labels (`CONTROLLED_PASSES`) | kept as two more labellings; they favour cost 16–24 |
| evidence-dependent switch cost | failed its test; switch cost stays 12 |
| hold-out match 3 (`EXTERNAL_GAMES=3`) | confirms the model; now a validation match (consulted several times) |
| receptions held (`reception_weight` 8) | **adopted** |
| broadcast synchronisation pilot (`broadcast.py`) | aligns to the frame; its evidence hurt; dropped |
| second LLM round (`LLMs/brief_v2.md`, two answers) | assessed; three ideas tested |
| restart owner (`restart_owner` 1) | **adopted**; wrong-team restarts 6 → 1 of 21 |
| IDSSE provider possession flag | exists; very fine-grained (like our raw labels); no import |
| straight-line simulator (`INTERP=1`) | kept as a tool; confirms passes and receptions |
| corner-based contact detector | stopped by its stop test; removed |
| team size, LLM use | closed: 3 members; organisers said LLM use is fine |

Last updated: 2026-11-12, end of session (modelling finished except one optional idea; next:
optional restart-owner extension, then the freeze).

## The task in one paragraph

More than a Hack 2027, Phase 1 (Metrica Sports / FC Barcelona). For each of the 199,319 frames of
the tactical video of BAR–ATH, output `H`, `A`, `D` or `X`. Ranked on `spellF1` (whole possessions
matched by temporal IoU, averaged over thresholds 0.3–0.7); `macroF1` breaks ties. Published floor:
`baseline_smooth50`, spellF1 0.2433 on the full match. The full-match ground truth is private; only
5 minutes (17 possessions) are public. **Deadline: 17 November 2026.** Details in the repository
root: `CHALLENGE.md`, `DATA.md`, `EVALUATION.md`, `RULES.md`, `SUBMISSION.md`, `FAQ.md`.

## Current state

- A complete, validated, reproducible submission exists: `solution/output/submission.csv`
  (gitignored; regenerate with `python solution/run.py`). Deleting `solution/cache/` and running
  again gives a byte-identical file.
- Model: three-state (H/A/D) Viterbi decoder over hand-set evidence scores. Team evidence is
  "control" (ball close to a player and moving with them), completed passes and receptions
  held; after decoding, the team named by a set-piece tag gets the matching restart ("restart
  owner"). Dead-ball evidence comes from player speed, ball visibility, strikes, line
  crossings, set-piece tags and the **referee's whistle detected in the audio** (`audio.py`,
  needs ffmpeg once). No training.
- A labelled test bench on three other matches exists in `external/` (Metrica public sample
  matches, degraded to resemble our tracking; five labellings; optional straight-line ball,
  `INTERP=1`). Choices are made on matches 1–2 and checked once on match 3 (`EXTERNAL_GAMES=3`).
- Committed on branch `nyx-solution` (not pushed); `main` is untouched.

### Numbers for the current submission

| quantity | value |
|---|---|
| possessions (full match) | 223, mean 14.6 s, median 9.8 s |
| graded frames H / A / D | 50,496 / 30,625 / 77,736 (dead share 0.489) |
| stoppages | 97, of which 52 have the same team on both sides |
| agreement with Smart Tagging team tags (live frames) | 0.786 |
| teamed set pieces whose decoded restart goes to the other team | 1 of 21 (was 6) |
| tagged set pieces with a decoded restart near the tag start | 47 of 58 (1 with no stoppage near) |
| referee whistles in live play with the decoder dead within 3 s | 10 of 15 |
| same pipeline on external matches 1–2 | spellF1 0.47–0.65 depending on label convention (five labellings), macroF1 0.84–0.86 |
| hold-out external match 3 | spellF1 0.49–0.65, macroF1 0.87 — no worse than on 1–2 |
| public 5 min: spellF1 / macroF1 | 0.61 / 0.90 — **17 possessions, noise; not a selection criterion** |
| full-match spellF1 | **unknown** |
| sha256 of `submission.csv` and `NYX.csv` | starts `0de7e99bc0f3cd2a` |

## What we now know (the four findings that set the priorities)

1. **The metric rewards getting the set of events right, not their timing** (`metric_cases.py`).
   A missed event and a false one cost the same. Timing errors of 1–3 s cost little. A missed
   stoppage only costs when the same team has the ball on both sides.
2. **Dead-ball detection is close to its ceiling; the error is in the team.** On the external
   matches: true dead/alive with our teams scores 0.51–0.65; our dead/alive with the true teams
   scores 0.83–0.87. Half of the possessions under 4 s show no control evidence at all
   (interceptions, clearances, first-time passes never have the ball travelling with a player);
   possessions of 4–8 s are right only about 60 % of the time.
3. **A single touch is not possession; a completed pass is.** Lowering the switch cost
   (12 → 8) and crediting single touches both gained on the external matches under fragmented
   labels, gained nothing under the least fragmented labelling, and added false possessions on
   the competition's public window (an away deflection of a long home pass; a 1 s away touch).
   Both were reverted. Two consecutive touches by the same team gained under every labelling
   and are in the model (`pass_weight`).
4. **The ATD ball is interpolated between contacts** (paths between touches are straight and
   bow to neither side). An earlier belief that airborne balls are mis-projected was tested and
   is wrong.

## Open decisions for the user (raised, not yet answered)

1. ~~Data and cloud LLMs.~~ **Closed 2026-11-12:** the user asked the organisers, who said using
   LLMs is fine. The working practice of printing only aggregates is kept anyway (it costs
   nothing).
2. **Use of the public ground truth.** Public segments and the public score were read after each
   change while developing. No constant was fitted to them, and `README.md` says exactly what
   was done. RULES.md says the window is "not a tuning set"; ask the organisers if in doubt.
3. ~~Team size.~~ **Closed 2026-11-12:** the team has 3 members (RULES.md requires 3–5).
4. **Before uploading:** rename the CSV and the technical document to `<team_name>.csv` /
   `<team_name>.pdf|md`; the code repository must be public and must not contain `data/`,
   `solution/cache/`, `solution/output/` or `solution/external/data/`. Decide whether
   `STATUS.md`, `HISTORY.md`, `PLAN.md`, `WORKING_RULES.md` and `LLMs/` belong in the
   public repository (they are internal working notes). The organisers need **ffmpeg** to
   regenerate the file (version noted in `README.md`).
5. ~~Switch cost 12 or 16?~~ **Closed 2026-11-12: 12.** An evidence-dependent cost did not get
   the best of both (`HISTORY.md`).
6. ~~Adopt "receptions held" (`reception_weight` 8)?~~ **Closed 2026-11-12: adopted.**
7. ~~Adopt the restart owner (`restart_owner` 1)?~~ **Closed 2026-11-12: adopted.**

## Work in progress

All items of the team-evidence work agreed on 2026-11-11 are finished (see the table in "Next
session"). The only proposed item left is the restart-owner extension ("Next session", item 4).
Any further idea: test it with `external/calibrate.py` under the five labellings (and
`INTERP=1`), check it once on match 3, judge added / removed changes with `reversal.py`, and ask
the user before changing the submission.

## Deferred — come back to these if there is time or the above stalls

| item | what it is | why deferred | where it is described |
|---|---|---|---|
| Broadcast as dead-ball evidence | Cuts and replays (frames whose broadcast picture is not live-consistent, `broadcast.py`) as stoppage evidence or a validation signal. | The pilot (2026-11-12) aligned the broadcast and showed its team evidence does not help; dead-ball detection is near its ceiling, so this use is low value. | `HISTORY.md`, `broadcast.py` |
| Restart geometry | Kick-off half-plane rule; throw-in entry when the ball is lost heading over a touchline; taker on the touchline. | Dead ball is near its ceiling; the missed stoppages are about 4 s long. Could still find a few same-team stoppages. | `PLAN.md` step 4 |
| Second-half kick-off timing | Decoded 32 frames late (a kick-off tap is too gentle for the restart-kick detector). | One event; timing is cheap under the metric. | `README.md`, `HISTORY.md` |
| Four artefact stoppages of 0.7–2.2 s | Ball tracked beyond a line and straight back. | Two fixes tried, both deleted real stoppages. | `HISTORY.md`, `PLAN.md` step 0 |
| Ball-free team evidence from team shape | Infer the team from player movement when the ball is unseen. | Only 7 % of live frames have no ball. | `PLAN.md` section 2 (i, j) |
| Phase tags as a prior | `Progression` and `Creating Chances` agree with the decode 95–96 % in their first 4 s. | Little unseen live play to help, and using them costs a validation signal. | `PLAN.md` step 0 |
| Whistle as dead evidence | Add dead-ball evidence after a whistle, not only a cheap boundary. | Four whistles have no stoppage near them; too few to judge. | `HISTORY.md` |
| Ball detection on the video | Fill the ball gaps from the pictures. | Heavy; must run locally. | — |

## How to run things

```bash
python solution/run.py --name submission                # regenerate the submission
python solution/run.py --name x --no-audio              # without ffmpeg / whistle evidence
python evaluation/validate_submission.py solution/output/submission.csv
python solution/audit.py solution/output/submission.csv # stoppages, structure, whistles
python solution/tag_agreement.py old.csv new.csv        # compare two versions, H/A quality
python solution/tag_reliability.py solution/output/submission.csv
python solution/sensitivity.py                          # +-30 % on every prior
python solution/test_decoder.py                         # synthetic decoder checks
python solution/metric_cases.py                         # what the metric rewards
python solution/audio.py --stability                    # whistle detector robustness
python solution/external/calibrate.py                   # pipeline on the external matches
python solution/external/calibrate.py switch_cost 8 12 16     # sweep one parameter there
INTERP=1 python solution/external/calibrate.py                # ball straight between contacts
CONTROLLED_PASSES=1 python solution/external/calibrate.py     # definition-following labels (also =3)
EXTERNAL_GAMES=3 python solution/external/calibrate.py        # hold-out match: check a choice once
MERGE_BRIEF_S=3 PARAMS_BASE="touch_weight=3" python solution/external/calibrate.py
python solution/reversal.py external                 # reversal instrument on the external matches
python solution/reversal.py match 6 8 12 16          # changes added/removed vs switch_cost
python solution/inspect_public.py solution/output/submission.csv   # debugging only
```

To score against the public window, copy a CSV into `evaluation/results/`, run
`python evaluation/run_evaluation.py`, then delete the copy (that folder is for baselines).
Editing these notes from a script on Windows: open files with `encoding="utf-8"`.
