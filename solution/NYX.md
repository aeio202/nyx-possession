# Team NYX — ball possession by control evidence and restart-aware decoding

More than a Hack 2027, Phase 1 (FC Barcelona – Athletic Club). Technical document. The full
description, with every measurement behind the choices below, is `solution/README.md` in the
repository.

## 1. Approach

The ranking metric (spellF1) scores **whole possessions**, so we built a model that outputs a
realistic set of segments rather than a per-frame classifier: a **three-state (H / A / D) Viterbi
decoder** run over each half. Every frame gets a score per state from hand-built evidence, and
the path pays a cost each time it changes state, so a change of possession or a stoppage must be
supported by enough accumulated evidence to pay for itself. **Nothing is trained**: every
constant is a round-number prior in metres, seconds or m/s, written next to its reasoning in
`solution/model.py`. Why not a learned model: no labels exist for this match, and the only
labelled data available (other matches) differs from this tracking in exactly the ways that
matter (ball smoothing, gaps, untracked players).

**Which team has the ball (H vs A).**

- *Control*: a player controls the ball when it is **close to them (≈2 m) and moving with them**
  (relative velocity under ≈4 m/s). Per frame: best home control − best away control. A pass
  travelling past an opponent is close but fast relative to them and scores nothing.
- *Completed passes*: a touch is a sharp change of the ball's velocity, credited to a team whose
  player is within 3 m and clearly nearer than any opponent. Two consecutive touches by the same
  team within 5 s add evidence for that team over the pass.
- *Receptions held*: a touch after which the same team holds the ball (control on at least 0.5 s
  within 2 s) adds evidence from the touch on. This credits interceptions and tackles, which
  control alone never sees.

**Ball in or out of play (D).** Small per-frame evidence (≈0.1, so a stoppage needs seconds of
it): collective player speed below walking pace (read 2 s ahead: players react late), ball
unseen, ball at rest inside a long interval between strikes, ball beyond a line, ball resting
unattended, the start of a tagged set piece; against: frequent strikes, a carried ball, a fast
ball, the seconds after a restart. Transition costs make **stoppages events**: entering D is
cheap on the frame the ball crosses a line, when all players decelerate together, or at a
**referee's whistle detected in the audio** (two simultaneous tones near 3.8 and 4.25 kHz; 70
blasts found); leaving D is cheap only on a detected restart kick.

**Output for the full match:** 223 possessions (mean 14.6 s), 97 stoppages, 49 % of graded frames
dead. Runs in under a minute from the raw data, deterministically.

## 2. Assets used and dropped

| asset | used | how |
|---|---|---|
| tactical tracking (ATD) | yes | all evidence above |
| tactical video | **audio only** | referee whistles; the pictures are not used |
| Smart Tagging | yes, narrowly | set-piece starts as stoppage evidence; the team of a set piece at its restart; kick-off windows; label-free validation |
| tactical homography | no | the ATD is already in pitch coordinates |
| broadcast tracking | tried, dropped | aligned to the tactical timeline (one constant offset per half, exact to the frame), but its control evidence, used where ours is empty, added false changes of possession by our label-free check |
| broadcast video, homography | no | |

**Tried and dropped** (measured reasons in the README): nearest-player evidence (replaced by
control); single-touch evidence and a lower switch cost (gain only under labellings that count
every brief recovery, which the definition excludes); an evidence-dependent switch cost; Smart
Tagging phase teams as a prior (too noisy, 75–80 % agreement); a model of mis-projected aerial
balls (refuted: the ball is interpolated in straight lines between contacts); a contact detector
looking for turns in that straight path (almost no new information); dating changes back to the
new team's arrival at the ball (median shift 4 frames); several dead-ball rules that deleted real
stoppages.

## 3. Training data

**No model is trained and nothing comes from the provided game's labels.** Labelled data from
other matches was used only to check the pipeline and to choose between a few round values:

- **Metrica Sports public sample matches 1, 2 and 3** (github.com/metrica-sports/sample-data;
  three full matches, tracking at 25 fps and event data **annotated by Metrica**). We derived
  frame labels from the events with our own rules (`solution/external/sample.py`) and degraded
  the clean tracking to resemble the competition's (`external/corrupt.py`). Because the
  organisers' labelling convention cannot be observed, every check uses five labellings, from
  "every recovery is a possession" to "a change needs a completed pass or 3 s on the ball".
  Choices were made on matches 1–2 and checked on match 3. One evidence weight (completed
  passes) was chosen there; the later additions (receptions held, restart owner) were accepted
  only because they helped on all three matches.
- **IDSSE** (Bassek et al., Scientific Data 2025; Bundesliga, CC BY 4.0): inspected only. We read
  the provider's possession flag on an 11-minute slice of one match to understand how a tracking
  provider labels brief possessions. Nothing from it is used by the model.

**Public 5-minute window:** used to check frame alignment and label meaning, and to understand
failure modes. No constant was fitted to it; with 17 possessions it cannot choose between
versions.

**AI assistance.** AI assistants were used during development, as the rules allow: Claude as a
coding and analysis assistant, and other LLMs for two rounds of design ideas. The briefs we sent
them and their answers are in `solution/LLMs/`; the briefs contain descriptions and aggregate
statistics only. No LLM is part of the pipeline that produces the submission.

## 4. The possession rules we implemented

- **Ball in play:** exactly one team has possession; there is no contested state.
- **A change needs control by the new team:** control evidence, a completed pass, or a touch the
  team then holds. About half a second of sole control by the other team is the minimum (switch
  cost 12).
- **Loose balls, passes in flight, an unseen ball:** possession stays with the last team until
  the other one shows control (ties are resolved towards the latest change).
- **Simple touches and deflections:** credited to nobody. A deflection does not change
  possession unless the deflecting team then keeps the ball.
- **Challenges and duels:** no change unless the challenger comes away with the ball moving with
  them. Aerial duels give no evidence (the ball is drawn on the ground), so possession stays with
  the last team.
- **Stoppages (D):** from the moment play stops (line crossing, whistle, collective slowing) to
  the restart kick. Before each half's kick-off (released by the kick-off whistle) the state is D.
- **Restarts:** when a set-piece tag names the taking team (corners, goal kicks, free kicks),
  that team has the ball from the restart until the other team gains control. Otherwise the first
  team to show control after the restart has it.
- **Outside the halves:** X. No X is written on graded frames.

## 5. Limitations, and what we would do with more time

- **Short possessions** (interceptions, clearances, first-time passes of under ~1–4 s) are mostly
  missed: they leave almost no trace in this tracking, because the ball is interpolated between
  contacts and never travels with the player who wins it.
- **The number of possessions depends on a labelling convention we cannot observe.** Labels
  counting every brief recovery prefer more changes; labels following "controlled possession"
  prefer fewer. Our switch cost sits between the two.
- **Timing of changes** can be 1–2 s off in duels (a pressing opponent looks like control early)
  and after first-time passes.
- **Quick throw-ins with the ball unseen** and stoppages under a loud crowd (missed whistle) can
  be missed; gentle restarts can be dated 1–3 s off.
- **A mis-teamed or untracked player on the ball** cannot be corrected from the tracking alone.
- **With more time:** ball and player detection on the tactical video, to recover who played the
  ball in the moments the tracking interpolates; and a taker rule for restarts without a team tag
  (throw-ins).

## 6. Reproduction

```bash
pip install -r solution/requirements.txt              # Python 3.14.3; numpy 2.4.6, pandas 3.1.1
# ffmpeg on the PATH (used once, to read the audio track; build N-121700-g36e5576a44)
# match data unpacked into ./data (or MTAH_DATA_DIR), as described in DATA.md
python solution/run.py --name NYX                     # -> solution/output/NYX.csv
python evaluation/validate_submission.py solution/output/NYX.csv
```

Deterministic: from the raw data (no cache) it reproduces `NYX.csv` byte for byte (sha256 starts
`0de7e99bc0f3cd2a`). Derived data is cached in `solution/cache/` and never published.
