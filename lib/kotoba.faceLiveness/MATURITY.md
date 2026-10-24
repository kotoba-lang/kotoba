# Maturity

**Level: R1 experimental (real algorithm, no bundled detector)**

Implemented:
- `face-liveness.model` — challenge lifecycle (issue/expire), named-point
  landmark frame shape, result records (`:non-adjudicating true` always,
  mirroring ekyc/aml/watchlist-screen's own convention).
- `face-liveness.geometry` — Eye Aspect Ratio (the real, published
  Soukupová & Čech 2016 formula), Mouth Aspect Ratio (the same geometric
  shape applied to a mouth contour, a documented simplification not itself
  independently cited), and a yaw proxy (an explicitly-labeled
  dimensionless nose/eye-symmetry heuristic, NOT a real 3D pose estimate).
  All three propagate `nil` on missing points rather than guessing.
- `face-liveness.core` — per-challenge-type detection: dip-then-recover EAR
  curve for `:blink`, below-then-above MAR transition for `:smile`,
  centered-then-committed yaw transition for `:turn-left`/`:turn-right`.
  Confidence is reported as a clean 1.0/0.0 boolean match, not a fabricated
  fractional score.
- `face-liveness.ports/ILandmarkTracker` — the camera/CV seam, protocol
  only.
- `face-liveness.datom` — audit emitters mirroring `ekyc.datom`'s shape.
- Contract tests: EAR/MAR formula correctness against hand-computed
  synthetic open/closed eye and mouth geometry, yaw-proxy sign/symmetry,
  every challenge type's positive AND negative detection path (a real
  motion pattern verifies; noise, a static pose, or turning the wrong
  direction fails), expiry vs. empty-frames as distinct outcomes. 24 tests,
  40 assertions, 0 failures. `clj-kondo`: 0 errors, 0 warnings.

Not yet R1 (i.e., explicitly absent, not a rounding-down):
- **No `ILandmarkTracker` implementation ships in this repo.** This is the
  hard CV dependency this repo does not attempt: a real face-landmark
  detection model. `kotoba-lang/inference`'s stated ML stance rejects
  ONNX/TF.js/WebNN in favor of `torch`+`num`, which has no vision-workload
  precedent today (LLM-shaped only) — building one is out of scope here,
  a real follow-up if the org accepts a `torch`/`num` vision-extension
  design.
- **No adversarial-robustness testing** — no attempt to detect or defend
  against video replay, 3D mask, or deepfake/video-injection attacks. See
  README.md's explicit "does not defend against" list.
- **No liveness accuracy number of any kind** (false-accept rate,
  false-reject rate) against real human faces/real cameras — none exists
  in this workspace, and none is fabricated here.
- **Yaw-proxy left/right calibration is unverified** against any real
  capture pipeline (camera mirroring conventions vary) — documented as a
  known risk in `face-liveness.core`'s module doc and README.md, not
  silently assumed correct.
- **No liveness spec citation for the MAR formula** specifically (the EAR
  formula IS a cited, published algorithm; MAR here is the same shape
  applied by analogy, a common but not independently-peer-reviewed
  simplification).
- **Single-signal challenges only** — no combined multi-signal challenge
  (e.g. requiring blink AND turn in one session) or randomized
  challenge-ordering anti-replay design.

## Downstream consumers

None yet in production. Designed as the `:liveness` check behind a future
`kotoba-lang/ekyc-native-provider` (per ADR-2607198200's Phase E), once
`kotoba-lang/mrz` and this repo are both stable.
