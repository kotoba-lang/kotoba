# kotoba kernel DSL (JUN-139) — milestone 1 design

Single kernel source → GLSL/SPIR-V + MSL, replacing the hand-maintained twins
(`kdot_h2_r1.comp` / `kdot_h2_r1.msl.r4`). Scope: the kdot Q8_0 family first
(the composite's memory workhorses), then the nex ops.

## The three decisions (the issue's milestone-1 items)

1. **Placement: independent DSL here (inference), amu later.** The emitter is
   a kbb script (`emit-kernel.cljk`) — tooling goes through kbb per the repo
   rule (Python stays test-oracle-only). Once the emitters and the identity
   contract are proven over the kdot family, the DSL graduates toward
   amu/`kir` in its own issue; moving early would couple two unproven things.

2. **IR shape: a typed op catalog with the arithmetic as ordered chains.**
   The source (`kdot-q8.r4.kernel.kotoba`) declares the per-value product
   chain, the accumulation order and the reduction tree as DATA. The
   emitters are dumb syntax renderers with a shape-fixed, side-by-side
   reviewable skeleton. Everything that affects rounding lives in the source.

3. **Arithmetic identity: the source fixes it, emitters may not transform.**
   - `:conv :i8h` — the int8→half conversion, NOT the exponent trick
     (the trick measured 1.8x slower on Metal AND rounds differently;
     metal-iteration4). A future `:conv :trick` would be an explicit,
     re-verified alternative, not an emitter choice.
   - `:acc-chain` — acc0/acc1 and the thread sum in this order.
   - `:reduce` — simd_sum → lane-0 partials → thread-0 index-order sum.
   - rows-per-threadgroup is a TUNED parameter (4 chains safe / 8 spills on
     Apple GPUs — metal-iteration3's spill boundary), carried in
     `:kernel/shape` next to its tuning evidence, not a free knob.

## Acceptance (iteration 1)

1. Both emitters compile (glslangValidator → SPIR-V; Metal runtime compile).
2. Both pass `kdot_check.py` vs the CPU dequant reference (rel err ≤ 1e-2).
3. **Mutual check: the two emitted kernels agree with each other to ≤ 1 ulp**
   on the same inputs — this validates the emitters against each other, not
   against the hand twins (which remain the measurement baseline).
4. Performance within ±10% of the hand GLSL (symmetric best-of), recorded —
   the DSL is not allowed to be a silent slowdown.

## The migration series (JUN-139 items 2-4)

| # | kernel | new vocabulary | blocks |
|---|---|---|---|
| 1 | kdot Q8_0 (done) | term8 / acc-chain / reduce | — |
| 2 | qkvr (source written) | :bias-add, :rope (:neox + :identity) | the emitter's multi-binding + pair skeleton |
| 3 | atncopy | the cache-write slice, the softmax attention reduce | the op's max/exp/sum reduce order |
| 4 | nex ops (rmsnorm / add_rmsnorm / silu / add) | the wg_sum tree, elementwise chains | — |

The migration rule: every kernel lands only with the same acceptance (compile
x2, the CPU-reference gate, the mutual-in-budget check, symmetric perf within
+-10% of its hand baseline).

## Status

- [x] milestone 1 design (this file + the DSL source)
- [ ] emit-kernel.cljk (glsl + msl renderers)
- [ ] the acceptance run (compile ×2, kdot_check ×2, the mutual 1-ulp check)
- [ ] migration issues per twin family (kdot → nex ops), separate

## Baselines (the measured ground this replaces)

| kernel | backend | pure-kernel best-of | note |
|---|---|---|---|
| kdot_h2_r1 (hand GLSL) | Vulkan/MoltenVK | 43.0 µs (warm est. 27.1) | the measurement baseline |
| kdot_h2_r1.msl.r4 (hand MSL) | native Metal | 51.6 µs | adopted Metal form (r1 76.4 / r8 118.2 = the dose curve) |
