# Maturity

**Level: R0 (contract boundary only, deliberately no algorithm)**

Implemented:
- `face-match.model` — result record shape, always defaulting to
  `:review`/`:not-implemented`/`:non-adjudicating true`.
- `face-match.ports/IFaceMatcher` — the injection seam a real future
  implementation would satisfy.
- `face-match.core/match` — routes to human review with no matcher (the
  only way any caller in this org invokes it today); if a real matcher is
  injected and returns an outcome, surfaces it; if a matcher is injected
  but returns nil (couldn't attempt a comparison), still falls back to
  `:review`, never a guess.
- Contract tests covering all three paths (no matcher, matcher-returns-nil,
  matcher-returns-real-outcome). 4 tests, 10 assertions, 0 failures.
  `clj-kondo`: 0 errors, 0 warnings.

Not yet R1 (this is the whole point — not a rounding-down):
- **No embedding model of any kind.** No ONNX/TF.js/WebNN (the org's
  stated stance per `kotoba-lang/inference`'s README explicitly rejects
  these), and no `torch`+`num` vision-workload precedent exists today
  (that pairing's one working path is GGUF/Gemma LLM inference).
- **No benchmark data.** Even if a model were ported, there is no labeled
  face-pair dataset in this workspace to validate a false-accept/
  false-reject rate against, and none is fabricated here.
- **No `IFaceMatcher` implementation anywhere in this org.**

## Re-evaluation conditions

This repo should only gain a real matching algorithm if ALL of the
following become true, not as a unilateral engineering decision:

1. A genuinely open-licensed, well-known face-embedding model (e.g. in the
   FaceNet/ArcFace lineage) is identified with a license this org can
   responsibly redistribute/derive from.
2. A real evaluation dataset (or a credible proxy) exists to measure actual
   false-accept/false-reject rates before shipping, not after.
3. The org accepts a design decision to extend `kotoba-lang/torch`+`num`
   into a real vision workload (a new precedent, not assumed here).

Until then, `:review` is the correct, honest answer every time.

## Downstream consumers

None yet in production. Designed as the `:face-match` check behind a
future `kotoba-lang/ekyc-native-provider` (ADR-2607198200 Phase E) — which
will route every `:face-match` check straight to `:manual-review`, exactly
mirroring what this repo already does on its own.
