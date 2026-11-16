Four structural blind spots in your current design—and in how you are reading the data and metric—account for most of your remaining error. Addressing those first will clarify why the ranked mechanisms below work.

## 1. What You Have Overlooked or Misunderstood (Question 7)

### 1A. The "Same-Team Merge" Trap in `spellF1` (Why Weakness #8 Is Doubly Fatal)

Your sensitivity analysis treats the switch cost as a trade-off between precision and recall on short possessions. Under `spellF1`, missing a short possession of $0.8\text{ s}$ to $1.5\text{ s}$ is far worse than a single false negative.

Suppose the ground truth is `H (18 s) → A (1.0 s) → H (18 s)` (three possessions: two long `H` spells separated by a brief `A` interception/clearance). Because your switch cost (12) suppresses sub-second spells, your decoder outputs a single merged `H (37 s)` spell:

- You lose the $1.0\text{ s}$ `A` spell (**1 False Negative**).
- Because matching is strictly **one-to-one**, your single $37\text{ s}$ `H` spell can only match *one* of the two $18\text{ s}$ true `H` spells—Leaving the other $18\text{ s}$ `H` spell completely unmatched (**a second False Negative**).
- Even for the one $18\text{ s}$ `H` spell it *does* match, the temporal IoU is $18 / 37 = 0.486$, which **fails the 0.5, 0.6, and 0.7 IoU thresholds**.
- By contrast, if you insert a $1.0\text{ s}$ `A` spell that is slightly mistimed by $0.5\text{ s}$, both $18\text{ s}$ `H` spells score $\text{IoU} \approx 0.97$ (passing all five thresholds), and only the brief `A` spell risks low IoU.

The same math applies to missed short stoppages (`H → D (3 s) → H`): missing the stoppage merges two adjacent `H` spells into one double-length spell, destroying both. **Under `spellF1`, false merges between two spells of the same team are catastrophic, whereas a slightly mistimed split preserves both surrounding spells.**

### 1B. Broadcast Tracking Can Be Synchronised Without Video—and Its Replays Are a Dead-Ball Oracle

You have ignored the broadcast file because it is unsynchronised, has cuts/replays, and only has valid homography on $66\%$ of frames. You do not need video processing to synchronise it:

- On the $66\%$ of broadcast frames with valid homography, player positions are already in **pitch coordinates**.
- At any live frame $t$, the spatial constellation of players—or simply the 4D vector of team centroids $(\bar{X}_H, \bar{Y}_H, \bar{X}_A, \bar{Y}_A)$—is a unique temporal fingerprint.
- Sliding a 5-to-10-second window of each continuous broadcast camera shot across the tactical timeline via 1D cross-correlation locks the exact frame offset within $\pm 1\text{ frame}$ in milliseconds of numpy compute.
- **Payoff 1 (Ball gap filling):** Whenever a broadcast segment aligns with the tactical timeline (a live shot), you can project its tracked ball directly onto your tactical timeline. Because the broadcast camera zooms in on the ball carrier during crowded attacks—precisely when the wide-angle tactical tracker loses the ball—this alone will cut your $41\%$ missing-ball rate significantly during live play.
- **Payoff 2 (The Replay / Cut Oracle for `D`):** Why does the broadcast homography fail on $34\%$ of frames, or why does a broadcast segment match a tactical constellation from 30 seconds *earlier*? Because the broadcast director switched to a **close-up (foul, yellow card, throw-in preparation) or a replay**! Directors almost never cut away from live play for more than $2\text{ s}$. Any window of tactical time where the synchronised broadcast feed is showing a replay or has $>2.5\text{ s}$ of invalid homography is a massive, velocity-independent signal for `D`—solving foul stoppages where players keep jogging (Weakness #6).

### 1C. Airborne Ball Parallax Is Geometrically Predictable (Weakness #10)

You noted that airborne balls are projected onto the ground at the wrong place, placing the apparent ball $7\text{–}8\text{ m}$ away from the true possessor. Because the tactical camera is fixed in the main stand (say at pitch coordinates $(X_{\text{cam}}, Y_{\text{cam}}, Z_{\text{cam}})$, which you can read directly by decomposing the homography matrix $H$), the ground-projection error is not random noise—it is strictly **radial away from the camera**:

$$\vec{r}_{\text{apparent}}(t) - \vec{r}_{\text{true}}(t) = \frac{Z_{\text{ball}}(t)}{Z_{\text{cam}} - Z_{\text{ball}}(t)} \left(\vec{r}_{\text{true}}(t) - \vec{r}_{\text{cam}}\right)$$

When a ball is kicked into the air ($Z_{\text{ball}}(t)$ follows a parabola), its apparent 2D pitch trajectory between the kick and the bounce bows **outward away from the camera** and accelerates/decelerates non-linearly, whereas a true ground pass travels in a straight line in 2D pitch coordinates. Whenever an inter-strike trajectory exhibits lateral curvature away from the camera position, the ball is airborne: **all intermediate proximity/control scores near the apparent ground track are phantom intersections and must be zeroed out**, except at the takeoff and landing vertices.

### 1D. Goalkeepers Are Trivially Identifiable from Anonymous Slots

You noted there is no goalkeeper role tag. However, in each half, the team defending the left goal ($X \approx -52.5\text{ m}$) has a negative median team $X$, and the team defending the right goal ($X \approx +52.5\text{ m}$) has a positive median team $X$. At any frame $t$, the slot of each team closest to its own goal Center $(\pm 52.5, 0)$—provided it is within $22\text{ m}$ of the goal line—is that team's goalkeeper with $>98\%$ accuracy.

- Knowing which slot is the goalkeeper fixes two systematic errors: (1) when a goalkeeper holds the ball in their hands or waits at their feet for $6\text{–}12\text{ s}$ while all 20 outfield players walk below $1.4\text{ m/s}$, your current model risks flipping to `D`; (2) during a Goal Kick, ball proximity to the goalkeeper slot inside the 6-yard box pins the exact restart readiness.

## 2. Ranked Mechanisms to Improve the System

### Summary Ranking Table

| Rank | Mechanism | Target Weaknesses | Expected Benefit | Effort (Laptop / 1 Wk) | Confidence |
| --- | --- | --- | --- | --- | --- |
| **1** | **Broadcast-to-Tactical Constellation Sync & Replay/Ball Fusion** | #2, #3, #5, #6, #9 | Very High (+0.05 to +0.10 spellF1) | Low–Medium (~1 day, numpy only) | High |
| **2** | **Spatial Set-Piece Templates & "Taker Isolation" Release Detector** | #2, #5, #6, #7 | Very High (+0.05 to +0.08 spellF1) | Medium (~1.5 days) | Very High |
| **3** | **Impulse-Vertex Back-Dating & Look-Ahead Trajectory Ownership** | #4, #8, #10 | High (+0.04 to +0.07 spellF1) | Low (~0.5 days) | High |
| **4** | **Collective Kinematics & Pressing-Ray Intersection ("Phantom Ball")** | #3, #9, #10 | High (+0.03 to +0.06 spellF1) | Medium (~1 day) | High |
| **5** | **Synthetic ATD Corruptor on Open Datasets for Hyperparameter Calibration** | #1, #2, #8 | High (+0.03 to +0.06 spellF1) | Medium (~1 day) | High |
| **6** | **Camera-Ray Airborne Ball Gate** | #4, #10 | Medium (+0.02 to +0.04 spellF1) | Low (~0.5 days) | High |
| **7** | **Anchor-Calibrated Log-Likelihood Ratios & Bridge-Split Post-Processing** | #1, #2, #8 | Medium (+0.02 to +0.04 spellF1) | Low (~0.5 days) | Medium–High |
| **8** | **Targeted Crop Frame-Differencing on Set-Piece & Boundary Windows** | #3, #5, #7 | Medium (+0.02 to +0.04 spellF1) | Medium–High (~1.5 days) | Medium |

### Rank 1: Broadcast-to-Tactical Constellation Sync & Replay/Ball Fusion

- **Mechanism:**
  1. Partition the broadcast tracking into continuous segments wherever homography is valid for at least $1.5\text{ s}$ and team centroids do not jump discontinuously.
  2. For each segment, compute the 4-channel time series of median team coordinates $(\tilde{X}_H(t), \tilde{Y}_H(t), \tilde{X}_A(t), \tilde{Y}_A(t))$ and find the lag $\Delta t$ that minimises the $L_1$ distance against the tactical median team coordinates (allowing for a small linear clock drift across the match).
  3. If the minimum average $L_1$ distance exceeds $3\text{ m}$, or if the matched tactical timestamp $\tau = t + \Delta t$ falls *earlier* than the previous live shot's timestamp, classify that broadcast segment as a **Replay**.
  4. On aligned live segments where the tactical ball is missing (or airborne) and the broadcast ball is present, transform the broadcast ball into tactical pitch coordinates (applying a minor local offset corrected by matching the nearest broadcast player slot to the nearest tactical player slot).
  5. Define a new dead-ball feature `broadcast_cut_or_replay`: whenever the tactical timeline is not covered by a valid live broadcast shot for $>2.5\text{ s}$, emit strong `D` evidence.
- **Weaknesses Addressed:** #2 (removes sole dependence on walking speed for `D`), #3 (fills missing ball during live play), #5 & #6 (catches foul stoppages and quick stoppages where players keep moving but broadcast cuts to the fouled player/referee), #9 (broadcast tracking provides a second independent detector when the tactical ball-carrier slot is missing).
- **Label-Free Validation:**
  - Check synchronization accuracy on frames where *both* feeds track the ball: median ball-to-ball distance after alignment should be $<1.0\text{ m}$.
  - Check that $>90\%$ of detected broadcast replays fall inside intervals between your detected tactical ball strikes or inside tagged set-piece lead-in windows.

### Rank 2: Spatial Set-Piece Templates & "Taker Isolation" Release Detector

- **Mechanism:** Instead of relying on ball speed ($>7\text{ m/s}$, which fails on short throw-ins, kick-off taps, and short free kicks) and global player speed ($<1.4\text{ m/s}$, which lags after fouls), detect the **geometric formation of each dead-ball state** and trigger `D → Alive` on the **kinematic break of that formation**:
  - **Throw-in Signature & Release:** A throw-in requires **one isolated slot pinned within $1.2\text{ m}$ of the touchline ($\vert{}Y\vert{} \ge 33.0\text{ m}$)** with speed $<0.8\text{ m/s}$, while the median $Y$ of the remaining ~19 players is shifted toward that touchline ($\vert{}\bar{Y}\vert{} > 12\text{ m}$) and zero players are within $15\text{ m}$ of the *opposite* touchline. Even when the ball is unseen, the **team of the touchline-pinned slot tells you who owns the throw-in** (which Smart Tagging omits!). The exact restart frame (`D → Alive`) is the earlier of: (a) the ball appearing and accelerating, or (b) the touchline-pinned taker stepping back onto the pitch / accelerating above $1.5\text{ m/s}$ while a nearby receiver ($3\text{–}12\text{ m}$ away) simultaneously accelerates to receive or shield.
  - **Kick-off Half-Plane Constraint:** Before a kick-off (opening half or after a goal), all tracked slots of one team must have $X \le +0.5\text{ m}$ and all tracked slots of the other team must have $X \ge -0.5\text{ m}$ (except the 1–2 centre-circle takers). **The ball is mathematically forbidden from being alive while all 20 players satisfy this half-plane separation and one slot is stationary within $1.5\text{ m}$ of $(0,0)$.** The exact restart frame is the frame where the centre-circle slot moves the ball *or* the first non-taker crosses the halfway line $X=0$ at $>2\text{ m/s}$. This will immediately fix your second-half kick-off being decoded $3\text{ s}$ early (Weakness #7).
  - **Goal Kick & Corner Box-Exclusion Constraints:** During a Goal Kick preparation, zero opponent slots are inside the penalty area ($\vert{}X\vert{} > 36\text{ m}, \vert{}Y\vert{} < 20.16\text{ m}$) while the goalkeeper (or a single defender) stands stationary near the 6-yard line ($\vert{}X\vert{} \approx 47\text{ m}$). During a Corner, 1 slot is stationary within $2\text{ m}$ of $(\vert{}X\vert{}=52.5, \vert{}Y\vert{}=34)$ while $>8$ players are inside the penalty box with mean speed $<1.2\text{ m/s}$. In both cases, if the restart is played short (gentle kick $<7\text{ m/s}$), detect the restart at the exact frame the stationary corner/6-yard taker accelerates away from the spot and the defending box players surge outward (mean radial velocity away from goal exceeds $+1.5\text{ m/s}$).
  - **Foul / Free-Kick Stoppage Start (`Alive → D`):** When a foul occurs, players often jog for $3\text{–}5\text{ s}$ toward the referee or into position, fooling your $1.4\text{ m/s}$ threshold. Instead, detect the **divergence of velocity alignment**: during live play, players' velocity vectors are highly correlated (high magnitude of mean velocity vector $\Vert{}\frac{1}{N}\sum \vec{v}_i\Vert{}$ divided by mean scalar speed $\frac{1}{N}\sum \Vert{}\vec{v}_i\Vert{}$, i.e., **polarisation order parameter** $\Phi \in [0, 1]$). Immediately at a whistle, players stop running in a coordinated tactical direction and scatter/mill around ($\Phi$ drops below $0.25$ within $1\text{ s}$ even if scalar speed $\frac{1}{N}\sum \Vert{}\vec{v}_i\Vert{}$ remains $1.8\text{ m/s}$!). Replace raw scalar speed with **directed collective speed** $\Vert{}\frac{1}{N}\sum \vec{v}_i\Vert{}$ and polarisation $\Phi$ for `Alive → D`.
- **Weaknesses Addressed:** #2, #5, #6, #7.
- **Label-Free Validation:**
  - Run your Set-Piece Audit (Section 6): all 58 tagged set pieces should now have a decoded restart within $[0\text{ s}, +12\text{ s}]$ of the tag start (eliminating the $[-2\text{ s}, 0\text{ s}]$ premature restarts like your second-half kick-off and catching the 1 missed stoppage).
  - For the 26 untagged-team Throw-ins, verify that the team of the isolated touchline taker matches the team that gains control $2\text{–}4\text{ s}$ after the restart on $>90\%$ of throw-ins.

### Rank 3: Impulse-Vertex Back-Dating & Look-Ahead Trajectory Ownership

- **Mechanism:** Because the ball track is smoothed over $\sim 1\text{ s}$, a kick or one-touch pass does not show up as a speed jump, nor does a one-touch pass show low relative velocity ($\vert{}\vec{v}_{\text{ball}} - \vec{v}_{\text{player}}\vert{}$ stays high). However, smoothing a piecewise-linear trajectory preserves the **peak of the second derivative (curvature / acceleration vector $\Vert{}\vec{a}_{\text{ball}}(t)\Vert{} = \Vert{}\vec{v}_{\text{ball}}(t+0.5\text{s}) - \vec{v}_{\text{ball}}(t-0.5\text{s})\Vert{}$) right at the true frame of contact**!
  1. Detect **Contact Vertices** $t_k$ as local maxima of $\|\vec{a}_{\text{ball}}(t)\|$ (which catches both speed ramps from rest *and* sharp directional changes $\Delta \theta > 25^\circ$ at constant speed, such as a first-time redirect or interception).
  2. Segment live play into **Ball Flight Tubes** $[t_k, t_{k+1}]$ between consecutive contact vertices.
  3. **Look-Ahead Trajectory Ownership (Fixing First-Time Passes & Duels):** Who actually controlled the ball at contact vertex $t_k$? Not necessarily the player moving slowest relative to the ball at $t_k$, but the player within $2.5\text{ m}$ of $\vec{r}_{\text{ball}}(t_k)$ whose team **receives controlled possession at $t_{k+1}$** (or whose kick direction $\vec{v}_{\text{ball}}(t_k + 0.5\text{s})$ points within $15^\circ$ of a teammate at $t_{k+1}$)!
  4. When Team A clearly controls the ball at reception $t_{k+1}$, check vertex $t_k$: if an `A` slot was within $2.5\text{ m}$ of the ball at $t_k$ and the ball vector changed toward the `A` receiver at $t_{k+1}$, **back-date the `A` control emission spike all the way across $[t_k, t_{k+1}]$**.
  5. Conversely, in a **Duel** (both `H` and `A` slots within $2\text{ m}$ of the ball with low relative velocity), suppress the challenger's control score at frame $t$ unless the *subsequent* ball displacement vector $\vec{r}_{\text{ball}}(t+0.8\text{s}) - \vec{r}_{\text{ball}}(t)$ moves toward an open space or teammate controlled by the challenger's team.
- **Weaknesses Addressed:** #4 (fixes the $1\text{–}2\text{ s}$ lag on first-time passes and premature flipping on pressing duels), #8 (allows a $0.8\text{ s}$ one-touch pass-and-lose sequence `H → A (pass to A) → H` to accumulate full emission across the flight tube), #10.
- **Label-Free Validation:**
  - Measure the distribution of ball acceleration $\Vert{}\vec{a}_{\text{ball}}(t)\Vert{}$ at your decoded `H ↔ A` transition frames: transitions should snap sharply onto local maxima of $\Vert{}\vec{a}_{\text{ball}}(t)\Vert{}$ rather than lagging $0.8\text{–}1.5\text{ s}$ after them when the ball slows down at the receiver.

### Rank 4: Collective Kinematics & Pressing-Ray Intersection ("Phantom Ball") When Ball Is Unseen

- **Mechanism:** During the $41\%$ of frames where the ball is unseen, the 20 tracked players act as 20 human sensors responding to the ball's true location and ownership. Extract three ball-free signals per frame:
  1. **Team Width/Length Ratio (In-Possession Expansion):** In professional football, the team in possession stretches the pitch laterally (inter-quartile or 10th-to-90th percentile $Y$-span is typically $38\text{–}50\text{ m}$), whereas the out-of-possession team contracts into a compact defensive block ($Y$-span $22\text{–}32\text{ m}$) shifted toward the ball side. Define `expansion_diff = (Y_span_H - Z_score_mean_H) - (Y_span_A - Z_score_mean_A)`.
  2. **Defensive-Line Retreat vs. Advance:** Compute the longitudinal velocity $v_{X,\text{back4}}$ of the 4 deepest outfield players of each team. When the ball moves toward Team A's goal ($+X$), both teams' defensive lines move toward $+X$, *and* the attacking team's forward line has higher sprint share ($v > 5\text{ m/s}$) toward $+X$ than the defending team's forwards.
  3. **Pressing-Ray Triangulation ("Phantom Ball" Position):** At any instant of live play, the 2–3 defending players closest to the ball accelerate *directly toward* the ball carrier. For each player $i$ with speed $>2.5\text{ m/s}$ and positive tangential acceleration, cast a ray from $\vec{r}_i(t)$ in direction $\vec{v}_i(t)$ (truncated to $[2\text{ m}, 15\text{ m}]$). The spatial mode (2D Gaussian kernel density peak) of where these rays intersect—weighted by local player density—estimates the **Phantom Ball position** $\hat{r}_{\text{ball}}(t)$ to within $\sim 4\text{–}6\text{ m}$!
  4. Combine these three features (plus individual high-purity Smart Tagging indicators like `Build Up` and the first $4\text{ s}$ of `Attacking Transition`) into a lightweight Logistic Regression or Linear Discriminant trained **self-supervised** on the $59\%$ of frames where the ball *is* visible and control is unambiguous ($\vert{}\text{control}\vert{} > 0.6$). Use its predicted log-odds as the `H` vs. `A` emission whenever the ball is unseen!
- **Weaknesses Addressed:** #3 (eliminates blindness during unseen-ball intervals and dates turnovers inside gaps to the moment collective kinematics and width flip), #9 (guards against a single mis-assigned or untracked ball-carrier slot), #10 (guards against airborne ball parallax).
- **Label-Free Validation:**
  - **Held-out Masked-Ball Evaluation:** Take the $59\%$ of live frames where the ball *is* visible and your current model has high confidence. Artificially mask the ball for $6\text{ s}$ across 100 visible turnovers, and measure how accurately the ball-free model predicts (a) the team in possession (target $>78\%$ frame accuracy) and (b) the turnover frame error (target median error $<1.2\text{ s}$ vs. complete blindness).

### Rank 5: Synthetic ATD Corruptor on Open Datasets for Principled Calibration

- **Mechanism:** You noted in Section 10 that open tracking+event datasets (such as the 3 public **Metrica Sports** matches, **SkillCorner** open tracking, or **DFL / Bundesliga** public tracking-and-event data) have clean tracking and a complete ball, creating a domain gap. **Bridge the domain gap by corrupting the open datasets to match your exact ATD sensor profile:**
  1. Derive exact frame-level `H`, `A`, `D` ground truth on the open matches using the organisers' rules (dead during stoppages; team of last controlled touch during live play).
  2. Apply a deterministic **ATD Corruptor** to the open tracking data:
     - Convolve the ground-truth ball $(X, Y)$ with a $1.0\text{ s}$ triangular/Gaussian kernel so kicks ramp over $1\text{ s}$ (matching your measured strike profile).
     - On long passes ($>18\text{ m}$), add synthetic camera-ray parallax proportional to $t(T-t)$ to simulate airborne ground-projection error.
     - Mask out $41\%$ of ball frames using a 2-state Markov chain whose gap lengths match your empirical ATD gap distribution (minimum gap $3\text{ s}$, higher dropout probability near touchlines, inside crowded boxes, and when the ball goes out of bounds).
     - Drop $8\%$ of player slots randomly in $5\text{–}20\text{ s}$ chunks and strip player IDs/roles.
  3. Now run your exact pipeline on these synthetically corrupted matches and **directly optimise `spellF1`** over your 4 sensitive parameters (`H ↔ A` switch cost, control radius, relative-velocity gate, and dead-ball thresholds).
- **Weaknesses Addressed:** #1 (pins the number of possessions), #2 (pins the dead share), #8 (tells you the exact switch cost where `spellF1` peaks by trading off short-spell recall against long-spell fragmentation).
- **Label-Free Validation:**
  - Check that the corrupted open matches produce the same sensitivity curves (e.g., $\times 0.7 / \times 1.3$ scaling effects on possession count and dead share) as Table 7 on your target match.

### Rank 6: Camera-Ray Airborne Ball Gate

- **Mechanism:**
  1. Estimate the fixed camera pitch coordinates $(X_{\text{cam}}, Y_{\text{cam}}, Z_{\text{cam}})$ by decomposing the median tactical homography matrix $H$ (or simply noting that $X_{\text{cam}} \approx 0$ and $Y_{\text{cam}}$ lies ~$20\text{–}40\text{ m}$ outside the near touchline).
  2. For every inter-strike flight tube $[t_k, t_{k+1}]$ of duration $>0.8\text{ s}$ and displacement $>10\text{ m}$, compute the signed perpendicular distance $d_\perp(t)$ of the tracked ball from the straight chord connecting $\vec{r}_{\text{ball}}(t_k)$ and $\vec{r}_{\text{ball}}(t_{k+1})$.
  3. If $\max_t d_\perp(t) > 1.2\text{ m}$ in the direction pointing **away from the camera** (the geometric signature of an airborne arc projected onto $Z=0$), or while ball speed exceeds $9\text{ m/s}$, mark the interior frames $(t_k + 0.2\text{s}, t_{k+1} - 0.2\text{s})$ as **Airborne**.
  4. On Airborne frames, multiply all player `control` emissions by $0$. Possession simply coasts from $t_k$ until the landing/reception vertex $t_{k+1}$.
- **Weaknesses Addressed:** #4, #10 (completely eliminates false mid-flight turnovers caused by an airborne pass flying "over" an opponent whose ground coordinates happen to match the ball's projected shadow).
- **Label-Free Validation:**
  - Inspect the frames where your model previously flipped `H ↔ A` mid-pass (when the nearest player to the tracked ball was $7\text{–}8\text{ m}$ away or when a long ball was tagged by Smart Tagging): verify that spurious mid-flight switches during tagged `Long Ball` intervals drop to zero.

### Rank 7: Anchor-Calibrated Log-Likelihood Ratios & "Bridge-Split" Post-Processing

- **Mechanism:** Your Viterbi decoder adds heuristic scores ($\pm 0.1$, $[-1, 1]$) and compares them to heuristic transition costs (12, 20, 25). You can make this probabilistically self-calibrating *on this match alone*:
  1. **Anchor-Set Calibration:** Identify ~20,000 "Gold Anchor" frames on this match where the state is virtually certain without tuning:
     - *Pure `H` / Pure `A` anchors:* Ball is tracked inside the pitch, speed $<5\text{ m/s}$, one team has a player within $1.2\text{ m}$ moving within $1.5\text{ m/s}$ of the ball, zero opponents are within $6\text{ m}$, and the Smart Tagging phase agrees.
     - *Pure `D` anchors:* Frames inside $[-2\text{ s}, 0\text{ s}]$ prior to a detected set-piece taker release, or where the ball is $>2\text{ m}$ out of bounds, or $60\text{ s}$ after a tagged Goal.
  2. Fit the empirical class-conditional density $p(\mathbf{f}_t \mid S_t)$ of your feature vector $\mathbf{f}_t$ on these anchor sets (e.g., via histograms or a diagonal Gaussian/Laplace mixture).
  3. Account for temporal autocorrelation: because tracking frames at $25\text{ fps}$ are heavily correlated over a window of $\tau_{\text{corr}} \approx 12\text{ frames}$ ($0.5\text{ s}$), divide per-frame log-likelihoods by $\tau_{\text{corr}}$ so that emissions represent **effective independent bits of evidence per second**. Then the theoretical Bayes-optimal transition cost is simply $-\log P(\text{transition per effective step}) \approx \log(\text{mean spell duration in effective steps}) \approx \log(14\text{ s} / 0.5\text{ s}) = \log(28) \approx 3.33$.
  4. **Metric-Specific "Bridge-Split" Rule (Answering Question 6):** After Viterbi decoding, scan every long spell of a single team (duration $>20\text{ s}$) for candidate short interruptions ($0.6\text{ s}$ to $2.0\text{ s}$) where the cumulative log-likelihood ratio strongly favoured the opposing team (or `D`) and coincided with a **Contact Vertex** (for `H ↔ A`) or a **Touchline/Foul signature** (for `D`), but fell just short of the global switch cost (e.g., reaching $65\text{–}95\%$ of the threshold). Because missing a true split in the middle of a $35\text{ s}$ `H` spell destroys *two* spells in `spellF1` (Section 1A), lower the required switch threshold by $30\%$ specifically for candidate splits situated near the middle ($25\text{–}75\%$ duration) of any spell longer than $25\text{ s}$, **and raise the threshold by $30\%$** for candidate splits that would merely chop off a $<3\text{ s}$ tail at the start or end of a spell next to a stoppage!
- **Weaknesses Addressed:** #1, #2, #8 (replaces arbitrary hand-tuned weights with empirical log-likelihood ratios and exploits the exact asymmetry of `spellF1`).
- **Label-Free Validation:**
  - Check that the decoded spell-length distribution matches the theoretical negative-binomial / log-normal football possession duration distribution (mode around $6\text{–}9\text{ s}$, mean $13\text{–}15\text{ s}$, rare tail above $45\text{ s}$—any decoded spell $>50\text{ s}$ in modern football is almost certainly a missed turnover or missed quick stoppage!).

### Rank 8: Targeted Crop Frame-Differencing on Set-Piece & Boundary Windows

- **Mechanism:** You do not need a heavy deep-learning detector on 199,319 full HD frames to use the tactical video.
  1. Identify the ~300 critical uncertain windows (each $8\text{ s}$ long, totaling ~60,000 frames, downsampled to $5\text{ fps}$ = **12,000 frames**): specifically the $[-2\text{ s}, +12\text{ s}]$ window around the 59 set-piece tags and any unseen-ball interval where collective kinematics indicate a potential stoppage or turnover.
  2. Use the per-frame homography $H_t$ to warp a small $250 \times 250$ pixel crop only around the **expected locus of action** (e.g., the touchline throw-in taker, the corner spot, the penalty spot/6-yard box, or the Phantom Ball position).
  3. Apply fast numpy background subtraction (median of $\pm 1\text{ s}$ warped crops) + white/bright-blob thresholding for a moving $6\text{–}12\text{ pixel}$ object moving faster than any player slot.
- **Weaknesses Addressed:** #3, #5, #7 (pinpoints the exact frame the ball leaves the throw-in taker's hands or moves on a short free kick when ATD lost the ball).
- **Label-Free Validation:**
  - Run the crop detector on set-piece windows where ATD *did* track the ball, and verify that the detected optical motion spike agrees with the ATD restart frame within $\pm 5\text{ frames}$ ($0.2\text{ s}$).

## 3. Direct Answers to Your Remaining Questions (Section 11)

### Question 3 & 4: How to Pin Possession Count & Dead Share, and Better Label-Free Validation Signals

Beyond the Synthetic ATD Corruptor (Rank 5) and Anchor Calibration (Rank 7), use these four **structural conservation checks** on this match:

1. **The "Max-Spell-Length" Tail Audit:** In LaLiga, uninterrupted single-team possessions longer than $45\text{ s}$ occur fewer than 3–5 times per match. Count how many of your 202 possessions exceed $40\text{ s}$. If you have 10+ possessions over $40\text{ s}$, your switch cost is too high (or you are missing quick throw-ins/fouls inside unseen-ball windows).
2. **Co-Training View Agreement (Micro vs. Macro Inflection Alignment):** Split your features into **View A (Ball-Local: position, speed, 2m proximity)** and **View B (Ball-Blind Collective: 20-player widths, centroids, defensive line velocity, pressing rays)**. On frames where the ball is visible, every true change of possession `H ↔ A` causes a sharp inflection (sign reversal) in View B's collective team velocity $\bar{v}_{X}(t)$ roughly $1.2\text{ to } 2.0\text{ s}$ *after* the turnover. Plot the average View B collective acceleration triggered at your decoded `H ↔ A` transitions as a function of the switch cost:
   - When the switch cost is too low, you decode false turnovers (deflections/duels where the original team keeps the ball), so the post-transition View B velocity reversal washes out toward zero.
   - The optimal switch cost is the **elbow where the marginal transitions added no longer produce a post-transition collective velocity reversal in View B**.
3. **Phase-Internal Homogeneity vs. Boundary Alignment:** Instead of pooling all Smart Tagging phases (which only agree $70\text{–}80\%$ of the time), stratify by tag purity:
   - `Build Up` and `Goal Kick` (first $5\text{ s}$ after restart) are $>92\%$ pure for the tagged team.
   - `Attacking Transition` is defined as a turnover followed by rapid forward progression: the exact start of an `Attacking Transition` tag (or $[-2\text{ s}, +1\text{ s}]$ around it) *must* coincide with a decoded `A → H` or `H → A` switch into the tagged team! Measuring what fraction of `Attacking Transition` tags have a matching decoded turnover within $\pm 2\text{ s}$ directly calibrates your turnover recall without favouring over-smoothed outputs.
4. **Conservation of Restarts:** A LaLiga match has $\sim 54$ boundary restarts (your 26 throw-ins + 12 corners + 10 goal kicks + 6 kick-offs) plus $\sim 22\text{–}30$ free kicks/offsides = **$76\text{ to } 86$ true stoppages**. Your current count of **93 stoppages** suggests you have roughly $10\text{–}15$ false-positive stoppages (likely caused by slow live buildup phases or goalkeeper ball-holding dipping below your $1.4\text{ m/s}$ player speed threshold), while simultaneously missing a few short $<5\text{ s}$ throw-ins/fouls. Replacing the global $1.4\text{ m/s}$ walking threshold with (a) broadcast replay/cut detection, (b) polarisation drop $\Phi$, and (c) goalkeeper-holding immunity should bring stoppages into the $78\text{–}85$ range and dead share from $49\%$ down to the typical LaLiga $45\text{–}47\%$.

### Question 5: Is a Hand-Scored Viterbi Decoder the Right Architecture?

Your 3-state Viterbi backbone is a strong choice for a 1-week, single-laptop constraint, **provided you make two architectural upgrades**:

1. **Move from Frame-Level Emissions to Contact-Segment + Boundary-Event Features:** A frame-level Markov model cannot naturally express *"a player touched the ball at $t_k$ and their teammate caught it at $t_{k+1}$"* or *"a stationary throw-in taker just stepped onto the pitch."* Keep the 25 fps Viterbi lattice, but compute emissions at the **inter-strike tube level** (Rank 3) and inject sharp **boundary transition-cost discounts** at detected set-piece formation breaks (Rank 2) and contact vertices.
2. **Calibrate Emissions via Self-Supervised / Synthetic-Match Likelihoods rather than Hand Constants:** Rather than replacing Viterbi with a black-box neural network (which risks overfitting to synthetic assumptions without a validation set), use a simple Logistic Regression / Naïve Bayes log-likelihood ratio fitted on your high-confidence Gold Anchors (Rank 7) and tuned on synthetically corrupted open matches (Rank 5).

### Question 6: Decoding & Post-Processing Strategies for `spellF1` Under Uncertainty

1. **Never Output `X` (Abstain):** Because `X` is deterministically forward-filled with the previous label before `spellF1` evaluation, outputting `X` gives zero benefit on `spellF1` and cannot improve over explicitly choosing the optimal continuation state.
2. **Where to Place an Uncertain Boundary (Expected IoU Midpoint Rule):** Suppose you know a transition `D → H` (or `H → A`) occurred somewhere inside an uncertain window $[t_1, t_2]$ of length $\Delta$ (for example, during a $4\text{ s}$ unseen-ball window), with uniform or unimodal probability over $[t_1, t_2]$. Because temporal IoU $\frac{\min(e, \hat{e}) - \max(s, \hat{s})}{\max(e, \hat{e}) - \min(s, \hat{s})}$ penalises boundary errors symmetrically relative to spell length, placing the boundary at the **posterior median** of the transition time within $[t_1, t_2]$ maximises expected IoU across all thresholds $\{0.3, \dots, 0.7\}$. Specifically, when a turnover occurs inside an unseen-ball gap $[t_{\text{lost}}, t_{\text{found}}]$, do not place the switch at $t_{\text{found}}$ (your current behaviour, which guarantees maximum error!); place it at the frame inside $[t_{\text{lost}}, t_{\text{found}}]$ where the ball-free collective kinematics (Rank 4) cross zero, or $1.5\text{ s}$ prior to the collective velocity reversal.
3. **The "Bridge-Split vs. Tail-Prune" Post-Processor:** As derived in Section 1A and Rank 7, apply asymmetric switch persistence: aggressively split long ($>25\text{ s}$) spells when a brief ($0.8\text{–}1.5\text{ s}$) opposite-team control or dead-ball signature appears near the middle of the spell, but aggressively absorb/prune brief ($<1.5\text{ s}$) opposite-team spikes that occur within $2.5\text{ s}$ of an already-established stoppage boundary `D` (since a tiny false spell adjacent to `D` creates a pure False Positive spell without rescuing a double-length merge).
