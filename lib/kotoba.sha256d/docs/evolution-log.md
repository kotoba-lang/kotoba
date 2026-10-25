# Evolution log

Append-only. Each entry is the Meta-review output of one `(sha256d.evolve/run-tournament)`
call (or `kbb -M:evolve`), left mostly unedited so this log reflects what the harness
actually measured, not a cleaned-up narrative.

## Summary — the whole search at a glance (rounds 1-16, complete)

Every lever the co-scientist tournament tried, and what the measurement said. "Verdict" is
KEPT (in the shipped repo), REJECTED (measured dead end), or SCOPED (bounded, deferred).

| # | Lever tried | Measured result | Verdict |
|---|---|---|---|
| 1-3 | Ch/Maj round-primitive formula (naive/alt/or) | within noise on JVM & V8, boxed & unboxed | REJECTED (noise) |
| 4 | Schedule `:rolling` (16-word window) | ~7-10% slower (subvec/conj alloc + interleave) | REJECTED |
| 5 | Schedule `:precompute-transient` | ties / slightly worse than precompute | REJECTED |
| 6 | Schedule `:mutable` (zero-alloc `long-array`) | ties precompute — schedule was never the cost | REJECTED |
| 7 | **Unboxed round loop** (`compress-primitive`, JVM) | **~2.3x** | **KEPT** |
| 8 | V8 cross-platform tournament | portable verdicts reproduce on V8 | (validated) |
| 9 | **V8 `Int32Array` fast path** (`compress-v8`) | **~3.5x** | **KEPT** |
| 10 | **Inline ch/maj** into the fast paths | JVM **~13%** (→~2.7x total), V8 ~2.4% (→~3.6x) | **KEPT** (best paths) |
| 11 | Software 2-way multi-buffer interleave | ~6% slower (register spills > ILP gain) | REJECTED |
| 12 | **midstate + fast compress** (`search-nonce`) | **~4.4x** mining, 1.59×2.78 stacking | **KEPT** |
| 13 | **Parallel nonce search** (across cores) | **~4.6x on 10 cores** (not linear) | **KEPT** |
| 14 | Diagnose the parallel plateau | it's turbo frequency scaling, **not** GC/alloc | (allocation-free path REJECTED unbuilt) |
| 15 | Validate vs the **real Bitcoin genesis block** | reproduces block 0 + Satoshi's nonce | (grounded) |
| 16 | Hardware-SIMD multi-buffer (JVM Vector API) | 4 NEON lanes exist; naive Clojure port ~6300x slower | SCOPED (needs a Java hot loop) |

**One-line conclusion:** the only lever that ever moved single-hash throughput was removing
per-operation runtime overhead (boxing/IFn on the JVM, arg-seq-alloc/persistent-indexing on V8);
neither the Ch/Maj *formula* nor the schedule *data structure* ever mattered, and allocation never
mattered anywhere (single-thread or parallel). Mining throughput composes three axes — structural
(midstate 1.6x) × per-op-overhead (fast compress ~2.7x/core) × across-core (threads ~4.6x, hardware-
frequency-bounded) — reaching ~272k nonce/s on 10 cores, all bit-identical and validated against the
real genesis block. Sole remaining frontier: a **Java** SIMD hot loop (outside this repo's idiomatic-
Clojure setting). **Shipped API:** `compress` (portable reference) · `compress-primitive-inline`
(JVM ~2.7x) · `compress-v8-inline` (V8 ~3.6x) · `midstate`/`header-hash`/`search-nonce`/
`search-nonce-parallel`.

**Pivot to the inverse problem (2026-07-02).** After the forward-optimization tournament closed,
the owner redirected to the *cryptanalytic* question: can the co-scientist approach design an
algorithm to invert SHA-256 (find a preimage) *below* 2²⁵⁶ brute force? Answer, honestly: yes for
reduced rounds (real MITM/splice-and-cut attacks), no by any meaningful margin for full 64 rounds.
This is a separate track from the forward tournament above — see `sha256d.mitm` and
`docs/preimage-mitm-cosci.md`. The search designs genuine 2¹²⁸ preimages on 16-20 rounds and locates
the wall at ~24 rounds (word granularity); the message expansion that made forward inversion hard is
exactly what collapses the attack's neutral sets. Full SHA-256 stays unbroken — the search
demonstrates the wall, it does not cross it.

## 2026-07-01 — initial run, JVM (OpenJDK 24, Temurin), Apple Silicon

Three consecutive `kbb -M:evolve` runs (default settings: 3 generations, elite-n 2,
200 iters x 7 reps per benchmark) over the current 2x2 gene pool (`sha256d.ops/ch-naive`
vs `ch-alt`, `maj-naive` vs `maj-alt`):

```
run 1: champion {:ch :alt,   :maj :naive} (51748.75 ns/hash) -- clusters: [1, 1] (NOT tied)
run 2: champion {:ch :alt,   :maj :alt}   (61070.84 ns/hash) -- clusters: [2]    (tied)
run 3: champion {:ch :naive, :maj :alt}   (61386.67 ns/hash) -- clusters: [2]    (tied)
```

**Findings:**

1. **No stable champion.** The "winner" changes between runs and 2 of 3 runs land in a
   single proximity cluster (i.e. Ranking itself found no significant difference). At
   this payload size, on this JIT, `ch-alt`/`maj-alt`'s one-fewer-gate savings are
   *below the noise floor* of a wall-clock micro-benchmark that also pays for the full
   padding/schedule/compression pipeline around the primitive call. This is a real,
   useful negative result, not a bug: it says the Ch/Maj formula choice alone isn't
   where meaningful throughput is hiding for this repo's current gene pool -- the
   Bitcoin midstate optimization (sha256d.midstate, ~2x fewer compression rounds per
   mining attempt) is a structural win of a completely different order, and the next
   genes worth adding (loop unrolling degree, schedule-buffer reuse, batch/lane-
   parallel hashing) are likely to matter more than further round-primitive rewrites.
2. **Generation-over-generation diversity loss.** By generation 3 the leaderboard only
   ever contains 2 distinct candidates, both sharing one gene value (e.g. both
   `:maj :naive`, or both `:maj :alt`). `evolve-round`'s recombination step only
   recombines gene *values already present among the current elites* -- once both
   elites happen to agree on a gene (a coin-flip after generation 1, given the Ranking
   noise above), that gene's other variant is gone for the rest of the run. There's no
   mutation/reintroduction step, so this is effectively genetic drift with no
   selective pressure behind it (since the "selection" driving convergence is largely
   benchmark noise per finding 1). **Follow-up:** either add a small random-
   reintroduction step to `evolve-round`, or don't treat convergence as meaningful
   until the gene pool is large enough / the payload is large enough that Ranking's
   pairwise comparisons are reliably outside the 1% proximity tolerance.

**Not yet done (explicitly out of scope for this initial pass, left for follow-up):**
ClojureScript/node benchmarking (only JVM was measured here -- `now-ns`'s cljs branch
via `js/performance.now` is implemented and the *correctness* of core/ops/midstate is
proven under cljs in `test/sha256d/cljs_verify.cljk`, but the evolve tournament itself
has only been run on the JVM so far); growing the gene pool beyond Ch/Maj.

## 2026-07-01 (round 2) — grew the gene pool to 3x3, JVM only

Added `sha256d.ops/ch-or` and `maj-or`: the same pairwise terms as `ch-naive`/
`maj-naive` but OR'd instead of XOR'd, valid because the terms being combined are
pairwise-disjoint (Ch) or never exactly-two-1 (Maj) -- see their doc-comments for the
proofs, and `test/sha256d/ops_test.cljk`'s exhaustive truth-table + randomized checks.
Gene pool is now 3x3 = 9 candidates. `kbb -M:test` (14 tests, 5154 assertions) and
the cljs proof (5/5) both still pass.

Three more `kbb -M:evolve` runs, same defaults:

```
run 1: champion {:ch :alt, :maj :alt} (51511.88 ns/hash) -- runner-up {:ch :alt, :maj :or}
run 2: champion {:ch :or,  :maj :alt} (45749.79 ns/hash) -- runner-up {:ch :alt, :maj :alt}
run 3: champion {:ch :alt, :maj :alt} (46046.88 ns/hash) -- runner-up {:ch :alt, :maj :or}
```

**Findings:**

3. **[⚠ LARGELY SUPERSEDED by round 3, finding 6 — this "signal" turned out to be
   substantially an artifact of the diversity-loss bug in finding 5, not a real speed
   difference.]** The `*-naive` variants are consistently eliminated by generation 3, in
   all 3 runs, for both genes. Unlike round 1's inconclusive Ch-alt-vs-naive comparison (which was
   only ever a 2-way fight), with `or` in the pool as a second same-cost-as-`alt`
   competitor, `naive` (one more gate than either) loses often enough in early-generation
   pairwise comparisons that `evolve-round`'s elitism drops it for good. This is
   reasonably strong evidence -- across 3 independent runs, not just one -- that the
   well-known "one-fewer-gate" reformulation is a real, measurable win here, not just
   noise as round 1's smaller pool made it look. It's still not a *novel* discovery
   (`ch-alt`/`maj-alt` are already how OpenSSL/Bitcoin Core write this), but it's the
   tournament's first result where Ranking's signal clearly exceeds its own noise floor.
4. **`alt` vs `or` (same gate count, different data-dependency shape) remain a genuine
   toss-up**: the champion alternates between them across runs, and each run's top-2
   still lands in 2 separate (not tied) clusters rather than 1 -- so there IS a
   measurable gap between whichever wins and whichever loses each specific run, it just
   isn't the *same* one twice. Distinguishing `alt` from `or` reliably would need either
   a larger reps/iters budget or a payload where the primitive call is a bigger fraction
   of total work.
5. **Diversity loss (finding 2, round 1) still reproduces**: every run's final
   leaderboard still has exactly 2 entries, not 9 or even 3+ -- confirms it's a property
   of `evolve-round`'s recombination-among-elites-only design, not something the larger
   pool alone fixes. Still an open follow-up.

**Still not done:** node/cljs benchmarking of the tournament itself; the diversity-loss
fix; genes beyond Ch/Maj (loop-unrolling degree, schedule-buffer reuse, batch/lane-
parallel hashing).

## 2026-07-01 (round 3) — fixed the harness, and it dissolved round 2's "finding"

Fixed the two flaws the earlier rounds documented, in `sha256d.evolve`:

- **Mutation (fixes finding 5, the premature convergence):** `evolve-round` now, in
  addition to elitism + crossover, reintroduces every pool variant the elites have
  dropped (grafted onto the top elite). The population no longer collapses to 2 -- it's
  a stable 5 every run now (`population size (diversity): 5` in all 3 runs below).
- **Persistent Elo (makes generations cumulative):** `rank` seeds each generation's Elo
  from the previous generation's ratings (newcomers at 1000) instead of resetting to
  1000 every round, so 3 generations over a stable diverse field pool ~3x as many
  pairwise games into each rating. Elo spread widened from the old artificial ±16 to
  ~120 points (≈971–1090), i.e. the ratings now carry real accumulated evidence.

`kbb -M:test` (16 tests, 5167 assertions, incl. new `evolve-round-mutation-test` and
`rank-persistent-ratings-test`) and the cljs proof (5/5) both pass. Three runs:

```
run 1: champion {:ch :naive, :maj :alt} (45442 ns/hash), pop 5, clusters [1,1,3]
run 2: champion {:ch :alt,   :maj :alt} (45845 ns/hash), pop 5, clusters [1,2,1,1]
run 3: champion {:ch :alt,   :maj :alt} (46471 ns/hash), pop 5, clusters [3,1,1]
```

**Findings:**

6. **Fixing the harness dissolved round 2's headline result — an important, humbling
   meta-finding.** Round 2 (finding 3) reported that the `*-naive` forms were
   "consistently eliminated," read as real evidence the one-fewer-gate `alt`/`or` forms
   are faster. Round 3 shows that was **largely an artifact of the diversity-loss bug
   itself**: round 2's `evolve-round` *dropped* `naive` from the population early (on
   noise) and then never re-benchmarked it, so of course it never appeared in the final
   leaderboard — that's not the same as `naive` losing on speed. With mutation now
   keeping `naive` in the field and re-measured every generation, **`{:ch :naive, :maj
   :alt}` actually wins run 1 outright.** All candidates now sit within ~3% of each other
   (45.4k–47.0k ns/hash) with heavy proximity-clustering (ties). So the honest verdict
   reverts to round 1's: at this payload and measurement budget, the Ch/Maj *formula*
   choice is within noise. The lesson is the general one — don't trust a search harness's
   "discoveries" until its own convergence behavior is sound; a premature-convergence bug
   manufactures crisp-looking signals out of noise.
7. **The only weak surviving lean:** `:maj :alt` is the champion's Maj in all 3 runs, and
   `:ch :alt` is in the top two in all 3. It's suggestive but NOT decisive — the gaps are
   inside the proximity tolerance and `:ch :naive` still won once. Not claimed as a result.
8. **Diversity fix confirmed end-to-end** (finding 5 closed): population is a stable 5,
   and `run-tournament-smoke-test` now asserts `population-size >= 3` so a regression back
   to collapse would fail CI.

**Still not done:** node/cljs benchmarking of the tournament itself (evolve.cljc's cljs
branches compile but the loop has still only been *run* on the JVM); a payload/'budget
where the primitive is a bigger fraction of total work, to actually resolve alt-vs-or if
it's resolvable at all; genes beyond Ch/Maj (loop-unrolling degree, schedule-buffer
reuse, batch/lane-parallel hashing) — the real efficiency frontier, per round 1 finding 1.

## 2026-07-01 (round 4) — added a real implementation-strategy gene; got the first signal that clears the noise

Acting on round 3's conclusion (the efficiency frontier is *structural*, not the
round-primitive formula), added the first non-formula gene: `:schedule`, selecting the
message-schedule strategy.

- `sha256d.core/compress-rolling`: computes the 64-word schedule in a 16-word rolling
  window just-in-time inside the round loop, instead of `compress`'s full-precompute
  `extend-schedule` — the "schedule-buffer reuse" idea. Proven bit-identical to the
  reference across 260 input sizes + FIPS vectors (`compress-rolling-equivalence-test`)
  and under cljs.
- Pool is now `:ch (3) x :maj (3) x :schedule (2) = 18` candidates; `rank`/`reflect`
  route through the new injectable `sha256-bytes-with`. `kbb -M:test` (17 tests,
  5449 assertions) and the cljs proof (6/6) pass.

Three runs (leaderboards trimmed to top + the surviving `:rolling` entry):

```
run 1: champion {:ch :or, :maj :or,    :schedule :precompute} 45948 ns/hash, elo 1222
       ...(4 more :precompute, elo 1102-1196)...
       LAST {:ch :or, :maj :or,  :schedule :rolling}  49351 ns/hash, elo 927
run 2: champion {:ch :or, :maj :naive, :schedule :precompute} 46489 ns/hash, elo 1165
       LAST {:ch :or, :maj :alt, :schedule :rolling}  50031 ns/hash, elo 946
run 3: champion {:ch :or, :maj :naive, :schedule :precompute} 45325 ns/hash, elo 1170
       LAST {:ch :or, :maj :alt, :schedule :rolling}  48946 ns/hash, elo 943
```

**Findings:**

9. **First signal that clearly exceeds the noise floor — and it's a negative result about
   the optimization I just added.** In all 3 runs `:schedule :precompute` wins and the
   sole surviving `:rolling` candidate is *last*, in its own low-Elo cluster (~927-946,
   well below the ~1100-1220 precompute pack), consistently ~7-10% slower in ns/hash
   (~49-50k vs ~45-47k). Unlike Ch/Maj (rounds 1-3, all within ~3%/tolerance), this gap
   is stable across runs and outside the proximity tolerance. The persistent-Elo spread
   widened to ~295 points (vs round 3's ~120 on pure noise), i.e. the round-3 harness
   correctly *amplifies* a real signal — good confirmation it now separates signal from
   noise rather than manufacturing it.
10. **Why: the C-level "schedule-buffer reuse" win does NOT transfer to idiomatic
    persistent-vector Clojure.** In C, rolling uses an in-place 16-word `int[]` with zero
    allocation, beating a 64-word buffer. Here, sliding the window with
    `(conj (subvec win 1 16) wt)` allocates a new (sub)vector every one of the 48
    extension steps per block — *more* churn than `extend-schedule`'s single flat 64-word
    vector that the JIT indexes cheaply with `(w t)`. So the "optimization" is a
    pessimization on this platform. A mutable `int-array` + `aset` rolling window would
    likely win on the JVM (it's how OpenSSL does it) but breaks `.cljc` portability
    (JVM/JS array semantics diverge) — deliberately not done; noted as a platform-specific
    follow-up, not a portable gene.
11. **Within `:precompute`, Ch/Maj is still noise** (consistent with round 3): `:ch :or`
    happens to top all 3 runs but `:maj` alternates (`:or`/`:naive`/`:naive`) and the
    intra-precompute gaps sit inside tolerance. Not claimed as a result.

**Net so far:** three rounds of Ch/Maj formula search found nothing above noise; the first
implementation-strategy gene immediately produced a clear (negative) signal. That is
itself the headline — *for this workload the lever is allocation/implementation strategy,
not bit-level formula* — and it re-confirms round 3's thesis. The genuine wins remain
structural and already in the repo (`sha256d.midstate`'s ~2x fewer compression rounds per
mining nonce), or would require a mutable-buffer, platform-specific (non-`.cljc`) rolling
schedule that this repo's portability constraint rules out.

**Still not done:** node/cljs *benchmarking* of the tournament (correctness under cljs is
proven; speed there — where V8's allocation behavior differs and rolling might fare
differently — is not measured); a mutable-array JVM-only schedule as a separate,
explicitly-non-portable experiment; genes for batch/lane-parallel hashing.

## 2026-07-01 (round 5) — tested round 4's "it's the allocation" hypothesis; it failed

Round 4 concluded rolling loses *because* per-step `subvec`/`conj` allocates. That's a
causal claim, and the portable, idiomatic way to test it is transients — the standard
Clojure tool for cutting allocation without leaving persistent-data-structure land. So:

- `sha256d.core/extend-schedule-transient` + `compress-transient`: same full 64-word
  precompute as `compress`, but the schedule is grown in a transient vector (`conj!`,
  one `persistent!` before `run-rounds` reads it). Extracted the shared 64-round body
  into a private `run-rounds` so `compress`/`compress-transient` differ *only* in how the
  schedule is built. Proven bit-identical across 260 sizes + FIPS vectors, **including a
  cljs check that transient-vector `nth` reads work under ClojureScript** (they do — the
  round-3 "verify portability under node" reflex paid off again; this could have been a
  cljs-only break and wasn't). Pool is now `:ch(3) x :maj(3) x :schedule(3) = 27`.
  17 tests / 5729 assertions JVM + 6/6 cljs green.

Three runs (top of each leaderboard + the transient and rolling entries):

```
run 1: champ {:ch :or,  :maj :alt, :precompute} 45659 (elo 1264); transient(or,alt) 46343 (elo 1017); rolling 49786 (elo 929)
run 2: champ {:ch :or,  :maj :alt, :precompute} 46175 (elo 1242); transient(or,naive) 46961 (elo 999); rolling 50048 (elo 939)
run 3: champ {:ch :alt, :maj :alt, :precompute} 45561 (elo 1259); transient(alt,alt) 49020 (elo 1069); rolling 50255 (elo 845)
```

**Findings:**

12. **Hypothesis NOT supported: cutting schedule-build allocation (transient) did not
    speed anything up.** A plain-`:precompute` candidate takes every champion slot across
    all 3 runs; `:precompute-transient` never wins — it lands in the same noise band as
    plain precompute, and in run 3 it's clearly *slower* (49020 vs the precompute pack's
    45.4–47.8k). So reducing the persistent-`conj` allocation of the schedule build is a
    wash-to-slightly-negative, not the hoped-for first positive result. Likely because
    (a) `conj` onto a <64-element persistent vector is already cheap (small tries, JIT
    escape-analysis), so there's little to save, and (b) `transient`/`persistent!` + the
    transient `nth` path carry their own fixed overhead that 48 steps don't amortize.
13. **This refines round 4's finding 10.** Rolling's ~7-10% penalty (re-confirmed here —
    rolling is dead-last again in all 3 runs) is therefore *not* simply "allocation," or
    the transient precompute would have helped. It's more specifically rolling's per-step
    `subvec`-view-plus-`conj` (a larger, differently-shaped allocation than one trie node)
    together with interleaving the schedule into the round loop, which stops the JIT from
    optimizing a tight separable schedule pass. Cutting *precompute's* allocation, by
    contrast, changes nothing measurable.
14. **Conclusion for the schedule axis (3 strategies now tested):** plain `compress`
    (persistent-vector precompute) is the best portable schedule strategy; both
    alternatives are equal-or-worse. The schedule build/representation is a dead end for a
    *portable* speedup — the reference was already near-optimal. Efficiency wins remain
    structural (`sha256d.midstate`) or non-portable (mutable `int-array`, out of scope).

**Meta (rounds 1-5):** five rounds, zero portable speedups found — every Ch/Maj formula is
within noise, and both schedule alternatives are ties-or-losses. That is itself the honest
result: **in portable persistent-Clojure the reference implementation is already at the
efficient frontier for a single-stream hash; the only real levers are algorithmic/structural
(midstate, already in the repo) or require abandoning `.cljc` (mutable buffers, SIMD/lane
parallelism).** The co-scientist harness earned its keep less by finding a faster SHA-256
than by *rejecting* three plausible "optimizations" (naive-elimination, rolling, transient)
that don't survive an honest, convergence-sound tournament.

**Still not done:** node/cljs *benchmarking* (V8 allocation differs — transient/rolling
might rank differently there); a deliberately non-`.cljc` JVM-only mutable-`int-array`
schedule to confirm the "leaving persistent structures is the only way" claim; a
batch/lane-parallel (multi-message) gene, the one axis that could plausibly beat the
reference and hasn't been tried.

## 2026-07-01 (round 6) — the mutable-buffer test that was supposed to confirm the claim; it refuted it

Round 5 teed this up: build the C-style in-place mutable schedule and confirm rounds 4-5's
standing claim that *the only way to beat the persistent-vector precompute is to leave
persistent structures*.

- `sha256d.core/compress-mutable` (JVM-only, `#?(:clj ...)`): one 64-slot `long-array`
  (not `int-array` — SHA-256 words are unsigned 32-bit and don't fit a Java `int`), filled
  with `aset`, read with `aget` — **zero per-step allocation**, exactly the C approach.
  Excluded from the ClojureScript gene pool (portability preserved: cljs proof still 6/6).
  Proven bit-identical on the JVM across 260 sizes (`compress-mutable-equivalence-test`).
  JVM pool is now `:ch(3) x :maj(3) x :schedule(4) = 36`; 18 tests / 6007 assertions.

Three runs (top few + transient/rolling tails):

```
run 1: champ {alt,alt,:mutable} 45914 (elo 1270); {alt,naive,:mutable} 45848 (1260);
       {alt,alt,:precompute} 45836 (1061); ...; transient 46922 (967); rolling 48726 (919)
run 2: champ {alt,alt,:precompute} 45810 (elo 1290); {alt,naive,:mutable} 45983 (1288);
       {alt,alt,:mutable} 46064 (1226); ...; transient 46645 (1065); rolling 48765 (761)
run 3: champ {alt,alt,:precompute} 46295 (elo 1310); {alt,alt,:mutable} 46488 (1257);
       ...; transient 46900 (1015); rolling 49332 (928)
```

**Findings:**

15. **The claim is REFUTED: even a zero-allocation mutable `long-array` schedule does NOT
    beat the persistent-vector precompute.** `:mutable` and `:precompute` are statistically
    tied — they alternate the championship (mutable wins run 1, precompute wins runs 2-3),
    and all their top ns/hash values sit within ~0.5% (45.8-46.5k). So "leaving persistent
    structures" was NOT the missing lever; the schedule container and its allocation were
    never the bottleneck. (`:rolling` is dead-last for the *sixth* round running; `:precompute-
    transient` again mid-pack.)
16. **So the real bottleneck is the boxed arithmetic in the round function**, which every
    schedule strategy shares: `add32`'s `(apply + xs)` varargs boxing, bit-ops on boxed
    `Long`s, boxed `ch`/`maj` return values, and the `(K t)`/`(w t)` vector lookups — ~128
    rounds of it per 2-block hash, dwarfing the ~48-step schedule build that the schedule
    genes vary. That's why *every* schedule strategy ties or loses: they all pay the same
    dominant boxed-round cost. It also explains rolling's persistent last place cleanly —
    rolling doesn't reduce that cost, and it *adds* per-step `subvec`/`conj` allocation while
    interleaving the schedule into the round loop (defeating a tight, separable, JIT-friendly
    round pass). Mutable and precompute both keep the schedule build separate and the round
    loop tight, so they tie.
17. **This overturns the round-5 "meta" conclusion's framing.** Rounds 4-5 concluded the
    reference was "at the efficient frontier" and further wins needed non-`.cljc` mutable
    buffers. Round 6 shows the mutable buffer *doesn't* help — so the frontier isn't the data
    structure at all; it's the **unboxed-vs-boxed arithmetic** of the round function, a lever
    none of rounds 1-6 has touched (all variants reuse the same boxed `add32`/bit-ops).

**Clear next experiment (round 7):** a primitive/unboxed round function — `^long` type hints,
`unchecked-add`, a fixed-arity (non-varargs) add, primitive `ch`/`maj`, and avoiding the
boxed vector lookups. On the JVM this is the classic 2-5x Clojure numeric win and is the
first thing that should actually move ns/hash (and might finally make the Ch/Maj formula
differences visible above the noise, since boxing currently swamps them). `^long` hints are
valid `.cljc` (cljs ignores them), so a portable primitive round function is plausible —
that would be the first genuine, portable positive result if it lands.

## 2026-07-01 (round 7) — THE FIRST POSITIVE RESULT: unboxing the round loop is ~2.3x

Round 6's diagnosis (bottleneck = boxed round arithmetic, not the schedule) made a sharp,
falsifiable prediction. Round 7 tested it:

- `sha256d.core/compress-primitive` (JVM-only, `#?(:clj ...)`): the *same* mutable
  `long-array` schedule as `compress-mutable` (so the schedule is held constant vs round 6),
  but the 64-round loop is UNBOXED — `^long` loop locals, `unchecked-add`, primitive
  `rotr*`/`bsig0*`/`bsig1*` (return-hint on the arg vector — the first cut mis-placed it on
  the fn name and threw `AbstractMethodError: invokePrim(J)…is abstract`; fixed), and a
  primitive `long-array` K. Confirmed **zero reflection warnings** (genuinely unboxed) and
  bit-identical across 260 sizes AND all 9 ch/maj gene combinations. Still calls injected
  `ch-fn`/`maj-fn` (a residual boxing island), so it composes with the :ch/:maj genes.
  Excluded from the cljs pool; JVM pool now `:ch(3) x :maj(3) x :schedule(5) = 45`.
  18 tests / 6294 assertions; cljs proof still 6/6.

Three runs (champion + a boxed reference row + rolling tail):

```
run 1: champ {alt,alt,:primitive} 20692 ns/hash (elo 1370); ...all :primitive ~20.2-21.0k...
       {alt,alt,:mutable} 47123; {alt,alt,:precompute} 46741; {alt,alt,:rolling} 49835
run 2: champ {naive,alt,:primitive} 20074; ...:primitive ~20.1-20.6k...; :precompute 46637; :rolling 49572
run 3: champ {alt,alt,:primitive} 20450; ...:primitive ~20.0-20.4k...; :precompute 46893; :rolling 49464
```

**Findings:**

18. **First positive result, and it's decisive: unboxing the round loop is ~2.3x.** Every
    `:primitive` candidate lands at ~20-21k ns/hash; every boxed schedule variant
    (precompute/mutable/transient) at ~46.6-47.5k; rolling ~49.5k. That's 46.7k/20.4k ≈
    **2.29x**, consistent across all 3 runs, with a clean, huge Elo gap (primitives
    ~1090-1388, boxed ~815-1130). This exactly confirms round 6's prediction: `:mutable`
    (mutable schedule, *boxed* round) ties precompute at ~47k, and adding unboxing to that
    *same* schedule drops it to ~20k — so the lever was the round arithmetic's boxing, full
    stop, isolated cleanly because the schedule was held constant between :mutable and
    :primitive.
19. **Ch/Maj is STILL noise, even unboxed** (round 3 survives): among the primitives,
    `{:ch :naive}` even wins run 2, and all 9 primitive candidates sit within a few % of each
    other. Removing boxing did not make the formula choice matter — it genuinely doesn't for
    throughput (the round is dominated by the σ/add chain and memory, not the one ch/maj gate
    difference; and ch/maj here are still the residual boxed calls anyway).
20. **The win is JVM-only, not portable — stated honestly.** `compress-primitive` uses
    `long-array` + `^long` and is `#?(:clj ...)`; ClojureScript never sees it. On V8 there is
    no boxed-`Long` problem to fix (JS numbers are unboxed doubles natively), so this specific
    ~2.3x does not transfer, and the cljs performance question remains unmeasured. The
    portable reference `compress` stays the default; `compress-primitive` is an opt-in JVM
    fast path (`sha256-bytes-with compress-primitive …`).

**Meta (rounds 1-7):** the optimization arc is now essentially complete and, crucially,
*correctly ordered by the harness*: Ch/Maj formula (rounds 1-3) = noise; schedule data
structure (rounds 4-6, incl. a zero-alloc mutable buffer) = no help / rolling hurts; unboxed
round arithmetic (round 7) = the one real lever, ~2.3x on the JVM. The co-scientist loop
rejected four plausible dead-ends and, by elimination, drove straight to the actual
bottleneck — which is exactly what a diagnosis-by-tournament is supposed to do. The single
biggest correctness catch along the way (the JS shift-count bug, round 3) and the biggest
speed lever (round 7) both came from *taking the mechanism seriously*, not from guessing.

**Still open:** whether *any* restructuring helps on cljs/V8 (needs a node benchmark harness —
the tournament has only ever been run on the JVM); fully inlining ch/maj to remove the last
boxing island (likely small, given finding 19); and batch/lane-parallel (multi-message)
hashing, which needs real SIMD (JVM Vector API / WASM SIMD) to beat the reference and is
therefore also non-portable.

## 2026-07-02 (round 8) — ran the tournament on V8: the portable rankings hold cross-platform

Rounds 1-7 measured *speed* only on the JVM. Since the repo's whole premise is portable
`.cljc`, that's a real gap: are "rolling is worst / transient ties-or-loses / Ch/Maj is
noise" genuine properties, or JVM-JIT artifacts? Round 8 finally runs `run-tournament` under
ClojureScript/node — the first time the harness's `now-ns` cljs branch (`js/performance.now`,
written back in round 3) has ever executed. New `sha256d.cljs-bench` ns + `:cljs-bench` deps
alias; the cljs pool is the 27 portable candidates (JVM-only `:mutable`/`:primitive` excluded).

Three node/V8 runs, same default methodology as the JVM (200 iters x 7 reps, 3 gens):

```
run 1: champ {alt,alt,:precompute} 135142 ns/hash; ...5 :precompute 134.3-137.0k...;
       transient 141036; rolling 145118 (last)
run 2: champ {or,naive,:precompute} 136003; transient 144005; rolling 147953 (last)
run 3: champ {or,or,:precompute}   137045; transient 142988; rolling 147141 (last)
```

**Findings:**

21. **The portable performance conclusions transfer JVM -> V8 — they were not JIT artifacts.**
    All 4 qualitative verdicts reproduce on V8: `:precompute` is best (champion in all 3 runs),
    `:precompute-transient` is clearly worse (~142-144k vs ~135-137k), `:rolling` is dead-last
    (all 3 runs — now confirmed on *both* runtimes across 7+3 = 10 tournament runs total), and
    Ch/Maj is noise (the champion's ch/maj varies run-to-run: alt/alt, or/naive, or/or, all
    within ~2%). Same ordering as the JVM; the co-scientist harness gives the same scientific
    answer on two independent runtimes.
22. **Absolute speed and the unboxing win are, as expected, NOT portable.** V8 runs at ~135k
    ns/hash — ~3x slower than the JVM boxed variants (~47k) and ~7x slower than the JVM unboxed
    `:primitive` (~20k). There is no V8 analog to `:primitive`: it's excluded from the cljs pool,
    and V8 has no boxed-`Long` problem for `^long`/`unchecked-add` to fix (JS numbers are unboxed
    doubles). So round 7's ~2.3x is correctly scoped as a JVM-only lever, and V8's floor for a
    single-stream persistent-vector hash is simply higher.
23. **Nuance — transient/rolling penalties are slightly *larger* on V8.** `:precompute-transient`
    is ~5% slower than `:precompute` on V8 vs within-noise on the JVM, and rolling's gap is
    likewise a touch wider. Consistent mechanism: V8 lacks the JVM's JIT escape-analysis that
    makes short-lived persistent `conj` nodes nearly free, so transient's fixed overhead and
    rolling's per-step `subvec`/`conj` show up a bit more starkly. Direction identical, magnitude
    modestly amplified — which, if anything, *strengthens* the JVM findings.

**Meta (rounds 1-8):** the investigation is now complete on both runtimes. Portable verdicts
(precompute is the best portable strategy; transient/rolling don't help; Ch/Maj is noise) hold
on JVM *and* V8. The one non-portable win (unboxed round arithmetic, ~2.3x) is JVM-only and
labeled as such. The harness did its job: correct rankings, reproduced cross-platform, with
every claim scoped to where it was actually measured.

**Genuinely still open (all non-portable or infrastructural):** fully inlining ch/maj (small,
per finding 19); a WASM/`wgpu` or JVM-Vector-API SIMD batch-of-N-messages hasher (the only path
that could beat the reference, for the mining use case specifically); and — if ever wanted — a
V8-specific fast path (e.g. `Int32Array` with explicit `>>> 0` unsigned coercion), the cljs
analog of the JVM `long-array` path, which round 8's numbers suggest is where V8 headroom
would be, if anywhere.

## 2026-07-02 (round 9) — built the V8 fast path round 8 predicted: ~3.5x, the first cljs win

Round 8 called the shot: V8's headroom is a typed-array fast path, the cljs analog of round 7's
JVM `long-array` unboxing. Round 9 built it and it landed.

- `sha256d.core/compress-v8` (cljs-only, `#?(:cljs ...)`): `Int32Array` schedule + K, fixed-arity
  int32 `+` with a `| 0` (`bit-or 0`) truncation, and no persistent-vector lookups or varargs
  `add32`. Values are signed int32 throughout — already how the reference behaves on cljs
  (`bit-and x 0xffffffff` == `x & -1` == ToInt32) and bit-correct because `words->bytes` extracts
  with `>>>`. Bit-identical to the reference across 130 sizes AND all 9 ch/maj combinations
  (cljs-verify now 7/7). Still calls injected ch/maj, so it composes with the genes. Excluded
  from the JVM pool; cljs pool is now `:ch(3) x :maj(3) x :schedule(4) = 36` (precompute/rolling/
  transient/v8). JVM suite unchanged (18 tests / 6294 assertions).

One node/V8 run, full leaderboard (all in the same run for a clean side-by-side):

```
{or,alt,:v8}                  37811 ns/hash  elo 1348
{or,naive,:v8}                37755         1332
{or,or,:v8}                   38357         1225
{alt,alt,:v8}                 38445         1056
{naive,alt,:v8}               38830         1017
{or,alt,:precompute}         135211          986
{or,alt,:precompute-transient} 142122        958
{or,alt,:rolling}            145442          924   (last)
```

**Findings:**

24. **First cljs positive result: the V8 fast path is ~3.5x.** `:v8` candidates run at ~37.8-38.8k
    ns/hash vs the reference `:precompute` at ~135k — 135211/37811 ≈ **3.58x** — consistent across
    3+ runs with a clean, huge Elo gap. Symmetric to round 7's JVM `compress-primitive` (~2.3x):
    same underlying insight, each via its platform's native numeric mechanism.
25. **The V8 win (~3.5x) is even bigger than the JVM win (~2.3x).** On V8 the reference's varargs
    `add32` (`(apply + xs)` allocates an arg-seq every call) plus persistent-vector schedule/K
    lookups cost proportionally *more* than JVM boxing does, so removing them (Int32Array +
    fixed-arity `+` + `| 0`) buys more. The reference ordering among the portable strategies is
    unchanged (precompute 135k > transient 142k > rolling 145k), exactly as round 8.
26. **Unifying result (rounds 7 + 9): the bottleneck was per-operation runtime overhead, not the
    algorithm or the data structure.** JVM: boxed `Long` arithmetic. cljs/V8: arg-seq allocation
    (varargs `add32`) + persistent-vector indexing. Each platform's fast path removes its own
    overhead with that platform's primitive-numeric tool (`long-array`+`^long`+`unchecked-add` on
    the JVM; `Int32Array`+fixed-arity+`| 0` on V8). Neither is portable, so the portable `.cljc`
    reference stays the default and each fast path is opt-in via `sha256-bytes-with`.
27. **Ch/Maj is STILL noise even in the V8 fast path** (round 3 survives a third time): the
    champion's ch/maj varies run-to-run (or/alt, or/or, alt/naive), all `:v8` within ~4%. The
    formula genuinely does not matter for throughput on either runtime, boxed or fast.

**Meta (rounds 1-9):** the arc is complete and symmetric. The harness ordered the search by
elimination (formula = noise; schedule data structure = no help; per-operation overhead = the
lever), then delivered a platform-optimal fast path on *both* runtimes — ~2.3x JVM, ~3.5x V8 —
while keeping one portable reference whose *relative* verdicts hold identically on JVM and V8.
The repo now offers: `compress` (portable default), `compress-primitive` (JVM ~2.3x),
`compress-v8` (V8 ~3.5x), all bit-identical, plus `midstate` for mining. Nine rounds, driven
purely by taking the measured mechanism seriously each time.

**Still open (non-portable / bigger):** SIMD batch-of-N-messages hashing (JVM Vector API / WASM
SIMD) for the mining throughput case — the only remaining path that could beat *these* fast
paths; and fully inlining ch/maj (finding 19 says small). Both are larger, non-portable efforts.

## 2026-07-02 (round 10) — inlined ch/maj: finding 19 was wrong on the JVM, right on V8

Finding 19 (round 7) *predicted* that inlining ch/maj — removing the last boxed-call island in
the fast paths — would be small. Round 10 measured it on both runtimes instead of guessing.

- `sha256d.core/compress-primitive-inline` (JVM) and `compress-v8-inline` (cljs): the round-7/9
  fast paths with the reference ch/maj INLINED as primitive/int32 bit-expressions
  (`(e&f)^(~e&g)` and `(a&b)^(a&c)^(b&c)`) instead of injected fn calls. They hardcode the
  reference ch/maj (Ch/Maj is noise, so nothing is lost) and so don't compose with the :ch/:maj
  genes — kept out of the gene pool, used only for head-to-head benchmarks. Bit-identical across
  260 sizes (JVM) / 130 sizes (cljs); no reflection warnings on the JVM. 18 tests / 6554
  assertions; cljs-verify 7/7.

High-iteration alternating A/B (4000 iters x 15 reps, warmed):

```
JVM:  compress-primitive-inline / compress-primitive  = 0.867, 0.868, 0.868, 0.872   (~13% faster)
V8:   compress-v8-inline        / compress-v8         = 0.979, 0.976, 0.975, 0.975   (~2.4% faster)
```

**Findings:**

28. **Finding 19 was WRONG on the JVM (~13%) and RIGHT on V8 (~2.4%) — a platform split with a
    clear mechanism.** On the JVM the injected `ch-fn`/`maj-fn` are boxed Clojure `IFn` calls
    (Object args + return) reached through a higher-order-function seam the JIT can't inline
    through, so each call boxes 3 args + a result — ~13% of the round, real and consistent
    (ratios 0.867-0.872, extremely tight). On V8 the injected ch/maj are small monomorphic JS
    functions that TurboFan already inlines, over values that are already unboxed SMIs, so
    removing the call syntactically saves almost nothing (~2.4%). Same source change, 5x
    different payoff, because of whether the runtime can see through the injection seam.
29. **New best JVM fast path.** `compress-primitive-inline` is ~13% over `compress-primitive`,
    i.e. roughly ~2.6-2.8x over the portable reference (vs ~2.3x). On V8 `compress-v8-inline` is
    a marginal ~2.4% over `compress-v8` (~3.6x over reference) — take-it-or-leave-it. Since
    Ch/Maj is noise, the inline variants lose nothing by hardcoding the reference formula, so
    they are the recommended opt-in fast paths.
30. **Methodological note:** the direct high-iter A/B (JVM primitive ~19.5k, inline ~16.9k; V8
    v8 ~34.7k, inline ~33.9k) reads a bit faster than the tournament figures (which use the
    default 200x7 bench with more warmup noise). The tournament is for *ranking* many candidates;
    a focused warmed A/B is the right tool for resolving a single ~few-percent delta — using the
    tournament for that would have hidden the V8 result inside its proximity tolerance.

**Meta (rounds 1-10):** the optimization space is now exhausted for a single-stream hash on both
runtimes. Final picture: `compress` (portable reference, identical *relative* verdicts on JVM &
V8), `compress-primitive-inline` (JVM, ~2.7x), `compress-v8-inline` (V8, ~3.6x), all bit-
identical; `midstate` for mining. Ch/Maj formula never mattered (4 rounds of noise); schedule
data structure never mattered (rolling hurt, transient/mutable tied); the entire win was
removing per-operation runtime overhead — boxing/IFn-calls on the JVM, and (much less) on V8.

**Only genuinely-open frontier:** SIMD batch-of-N-messages hashing (JVM Vector API / WASM SIMD)
for mining throughput — a materially larger, non-portable effort that changes the API shape
(hash N nonces at once). Everything cheaper than that has now been tried and measured.

## 2026-07-02 (round 11) — software 2-way multi-buffer interleave: refuted (~6% slower)

Before reaching for real (non-portable, big) SIMD, round 11 tested the *portable* version of the
batch idea. Hypothesis: SHA-256's round function has a long per-round dependency chain (each round
needs the previous a/e), leaving superscalar pipeline bubbles — so manually interleaving 2
independent hash lanes in one loop should fill them and raise throughput per hash, no SIMD needed
(the software analog of hardware multi-buffer SHA). It's genuinely open (ILP gain vs register
pressure), portable, and it's the mining workload (batch nonce search).

- `sha256d.core/compress-primitive-2way` (JVM-only): two independent (state, block) lanes in one
  interleaved unboxed round loop (a1..h1 + a2..h2), each lane exactly `compress-primitive-inline`.
  Bit-identical per lane across 300 random (state, block) pairs (`compress-2way-equivalence-test`,
  600 assertions); no reflection warnings. 19 tests / 7154 assertions.

High-iter head-to-head (ns per single compression: 2-way total/2 vs two sequential inline calls,
result-folded to defeat dead-code elimination):

```
run 0  seq=4136  2way=4384  2way/seq=1.060
run 1  seq=4153  2way=4406  2way/seq=1.061
run 2  seq=4163  2way=4418  2way/seq=1.061
run 3  seq=4177  2way=4400  2way/seq=1.053
run 4  seq=4144  2way=4401  2way/seq=1.062
```

**Findings:**

31. **Hypothesis REFUTED: software 2-way interleave is ~6% SLOWER, not faster** (ratio 1.053-1.062,
    tight across 5 runs). Manually filling the dependency-chain bubbles with a second lane does not
    pay off on this JVM/CPU.
32. **Why: register pressure beats the ILP gain.** Interleaving two lanes doubles the live state to
    16 state longs (+ loop counter, two array refs), which exceeds the x86-64 general-purpose
    register file, forcing spills to the stack every round. The spill/reload cost outweighs any
    bubble-filling benefit — and the single-stream loop was already getting enough ILP from the
    out-of-order window overlapping adjacent rounds. Hardware multi-buffer SHA wins precisely
    because wide SIMD registers (AVX2/AVX-512, or the Vector API's `IntVector`) hold N lanes with
    no spilling; a pure-Clojure/`long`-local interleave cannot replicate that and pays the pressure
    without the benefit.
33. **This closes the last *portable* avenue.** Every optimization reachable without leaving portable
    Clojure or single-thread scalar execution has now been tried and measured: formula (noise),
    schedule data structure (no help), per-operation overhead (the fast paths, the real win), and
    now software multi-buffer (backfires). Genuine batch/lane throughput requires actual hardware
    SIMD — confirmed empirically now, not just asserted. `compress-primitive-2way` is kept as a
    documented negative result, explicitly not a fast path.

**Meta (rounds 1-11):** the search is complete. The one thing that ever moved single-hash
throughput was removing per-operation runtime overhead (rounds 7/9/10: boxing/IFn on JVM →
~2.7x, arg-seq-alloc/persistent-indexing on V8 → ~3.6x). Formula, schedule structure, and
software multi-buffer are all measured dead-ends. The only path left that could beat the fast
paths is hardware SIMD multi-buffer (Vector API / WASM SIMD) — materially larger, non-portable,
and changes the API to hash-N-nonces-at-once; deferred as the sole remaining frontier, now with
the empirical result that its *software imitation doesn't work*, so the SIMD registers are the
actual mechanism, not the interleaving idea per se.

## 2026-07-02 (round 12) — composed the two big wins into a mining nonce search: ~4.4x, multiplicative

The single-hash optimization search is closed (rounds 1-11). But the repo's two biggest wins had
never actually been combined: `sha256d.midstate` (the structural mining win, built early) still
used the *reference* `compress`, and there was no nonce-search primitive. Round 12 ties them
together — the concrete Bitcoin payoff — and tests whether they stack.

- `sha256d.midstate/header-hash-with` (injectable compress-fn for BOTH the inner chunk2 and the
  outer 32-byte SHA-256) + `search-nonce` (scan nonces through a chosen compress strategy for a
  simplified leading-zero-bits target). `header-hash` now delegates to `header-hash-with` +
  reference `compress`. Bit-identical: `header-hash-with compress-primitive-inline` matches the
  reference on 300 random headers, and `search-nonce` finds the *identical* winning nonce with the
  reference and the JVM fast path. 21 tests / 7457 assertions; cljs proof 7/7.

Per-nonce throughput (JVM, ns/nonce, result-folded vs DCE):

```
naive (full 80-byte header sha256d, reference compress)  76584 ns/nonce   1.00x
midstate + reference compress                            48142 ns/nonce   1.59x
midstate + fast compress (compress-primitive-inline)     17304 ns/nonce   4.43x  (2.78x over midstate-ref)
```

**Findings:**

34. **The two wins stack multiplicatively: ~4.4x combined mining throughput over naive.**
    1.59 (midstate) x 2.78 (fast compress) = 4.42 ≈ the measured 4.43x. No interaction, no
    surprise — which is exactly the confirmation: two independent, independently-validated
    optimizations compose cleanly.
35. **Precise accounting of the midstate factor: 1.59x, not 2x.** Per nonce, naive does 3
    compressions (2 inner blocks over the 128-byte padded header + 1 outer block over the 32-byte
    inner digest); midstate does 2 (1 inner chunk2 + 1 outer), since chunk1 is cached. 3/2 = 1.5x
    expected; 1.59x measured (the cached chunk1 also saves its schedule build). The earlier
    "roughly halving the *inner* SHA-256" phrasing was right about the inner hash but the *total*
    per-nonce win is 1.5-1.6x because the outer block is unavoidable. The fast-compress factor
    (2.78x) matches round 10's ~2.7x head-to-head exactly.
36. **All bit-identical — the fast mining path mines the same chain.** Because every compress
    strategy is bit-identical (the hard correctness gate held across all 12 rounds), swapping in
    the fast path changes only speed, never which nonce wins. `search-nonce` is portable (pass
    `core/compress`); the ~4.4x is the JVM opt-in (`compress-primitive-inline`), ~similar stacking
    would hold on V8 with `compress-v8-inline` (untested throughput, but the same composition).

**Meta (rounds 1-12):** the arc that began as "efficiently derive Bitcoin's SHA-256" ends with a
concrete, bit-identical **~4.4x mining nonce search** (`search-nonce`), built by composing the two
wins the co-scientist search actually validated: the structural midstate reuse and the
per-operation-overhead fast path. Everything the tournament *rejected* (Ch/Maj formula, schedule
data structure, software multi-buffer) correctly stayed out. The only frontier beyond this remains
hardware-SIMD multi-buffer (non-portable, N-nonces-at-once) — deferred, and now with the whole
rest of the space mapped and measured beneath it.

## 2026-07-02 (round 13) — parallelize the nonce search across cores: plateaus at ~4.6x on 10, not linear

Every round so far was single-thread. Mining is embarrassingly parallel across nonces, so the
across-core axis (orthogonal to the per-core fast compress, and to the still-deferred per-core
SIMD) is the natural next lever. The non-obvious question: near-linear scaling, or capped by the
per-nonce allocation churn hitting a shared allocator/GC?

- `sha256d.midstate/search-nonce-parallel` (JVM-only): `search-nonce` split across N `future`s over
  contiguous nonce sub-ranges, returning the globally-lowest winning nonce — identical to the
  single-thread result (deterministic, testable, not first-to-return). Bit-identical to
  `search-nonce` on the cross-strategy test. 21 tests / 7458 assertions.

Scaling (fast compress `compress-primitive-inline`, 200k-nonce no-hit range so every thread fully
scans; 10-core Apple Silicon; min-of-3):

```
 1 thread   58239 nonce/s   1.00x   (= 17.2k ns/nonce, matches round 12's fast path)
 2 threads 114121 nonce/s   1.94x   97% efficiency
 4 threads 194555 nonce/s   3.31x   83%
 8 threads 258114 nonce/s   4.39x   55%
10 threads 272374 nonce/s   4.63x   46%
```

**Findings:**

37. **Parallel nonce search does NOT scale linearly — it plateaus at ~4.6x on 10 cores (46%
    efficiency).** Near-linear to 2 cores (97%), degrades gradually through 4 (83%) and 8 (55%).
    Peak ~272k nonce/s.
38. **Two honest, not-fully-disentangled causes.** (a) Allocation/GC contention: the per-nonce path
    allocates two `long-array`s + several vectors per hash; under 10-way parallelism the aggregate
    allocation rate drives frequent young-gen GCs whose stop-the-world pauses stall *all* threads —
    the classic ceiling on allocation-heavy parallel workloads, and the gradual (not cliff-shaped)
    degradation fits this. (b) Apple Silicon heterogeneity: the 10 cores are a performance/efficiency
    mix, so cores added past the P-core count contribute less. Disentangling them (GC logs, core
    pinning, `-Xmn` tuning) is a follow-up; the *plateau* itself is solid and measured.
39. **[⚠ REFUTED by round 14 — both causes above were wrong. GC is negligible (0.1%→0.8%); the
    plateau is all-core turbo frequency scaling, a hardware effect no code change addresses.]**
    This retroactively re-frames rounds 5-6 — the most interesting finding of the round. Reducing
    schedule allocation (transient/mutable) was a measured DEAD END *single-thread* (rounds 5-6:
    allocation was never the single-thread bottleneck — boxing/overhead was, per round 7). But round
    13's cause (a) says allocation becomes a real bottleneck *under parallelism*, because the
    allocator and GC are shared across cores. So an optimization that is noise on one thread can
    govern the scaling ceiling on ten. Concrete round-14 hypothesis: an allocation-free per-nonce
    path (thread-local *reused* `long-array` schedule + preallocated state, zero per-compress
    allocation) should push efficiency back up — the payoff the transient/mutable rounds never had
    single-thread may finally appear in the parallel regime.

**Meta (rounds 1-13):** three composing throughput axes now measured: structural (midstate, 1.6x),
per-operation-overhead (fast compress, 2.7x/core), and across-core (threads, ~4.6x here). The
mining artifact (`search-nonce`/`search-nonce-parallel`) reaches ~272k nonce/s on this 10-core
machine (~21x a naive single-thread reference at 13k nonce/s), all bit-identical. The remaining
frontiers are now two, both about *allocation and lanes*: an allocation-free per-nonce path (round
14, to lift the parallel ceiling — newly motivated) and hardware-SIMD multi-buffer (still the big
non-portable one).

## 2026-07-02 (round 14) — diagnosed the parallel plateau: it's turbo frequency scaling, not allocation

Round 13 proposed building an allocation-free per-nonce path to lift the ~4.6x parallel ceiling,
blaming GC/allocation contention (cause a) or Apple Silicon P/E cores (cause b). Before building
anything, round 14 ran two cheap diagnostics — and they refuted the whole premise.

**Diagnostic 1 — GC (via `GarbageCollectorMXBean`), scanning 400k nonces:**
```
 1 thread : wall=6721ms  gc-collections=14  gc-pause=10ms (0.1% of wall)   59512 nonce/s
10 threads: wall=1431ms  gc-collections=16  gc-pause=11ms (0.8% of wall)  279526 nonce/s
```
GC is negligible at BOTH — 14 vs 16 collections, <1% pause. The JVM's thread-local allocation
buffers (TLABs) absorb the per-nonce `long-array`/vector churn without contention.

**Diagnostic 2 — isolate frequency scaling (single-thread scan, alone vs all cores hot):**
```
single-thread ALONE:          57855 nonce/s
single-thread, ALL CORES HOT:  26682 nonce/s  (46% of alone; 9 background busy-spinners)
per-thread rate at 10 threads: ~27900 nonce/s (279k/10)
```
A single scanning thread drops to 46% of its solo rate the moment all cores are busy — and that
26682 matches the ~27900 per-thread rate under real 10-way parallelism. That is the smoking gun.

**Findings:**

40. **Round 13's cause (a) is REFUTED: GC/allocation is NOT the parallel cap** (0.1% -> 0.8% pause,
    +2 collections). Eliminating all allocation could gain at most ~0.8%, so the round-13
    allocation-free-path hypothesis (finding 39) is not worth building — and the cheap diagnostic
    is exactly what stopped me from building it. Finding 39's "allocation matters under parallelism,
    re-framing rounds 5-6" is wrong: allocation matters neither single-thread NOR in parallel.
41. **The plateau is entirely all-core turbo frequency scaling.** One active core boosts to a high
    turbo clock (~57.9k nonce/s); with all cores busy each runs at the lower all-core base clock
    (~26.7k, 46%). 46% x 10 cores = 4.6 -> exactly the measured 4.63x plateau, and single-thread-
    all-cores-hot (26.7k) == per-thread-at-10 (27.9k) confirms it directly. This is the CPU's
    power/thermal governor, not software: no code change (allocation-free path, different pool,
    core pinning) can raise it, because the physical per-core clock is what drops.
42. **Reframe: `search-nonce-parallel` is NOT inefficient — it scales as well as the hardware
    allows.** The "46% efficiency" is not overhead or contention; it's the correct all-core-vs-
    single-core frequency ratio. Measured against the *all-core* per-thread rate the scaling is
    essentially perfect (10 cores each doing their all-core-clock share). The only reason "10x"
    looked achievable was that the 1-thread baseline was measured at boosted clock — an
    apples-to-oranges baseline the diagnostic corrected.

**Meta (rounds 1-14):** the cheapest round produced one of the clearest results — two ~30-line
diagnostics refuted an expensive-to-build hypothesis and quantitatively nailed the true cause
(46% x 10 = 4.6x). This is the measure-first discipline's sharpest payoff in the whole series:
rounds 4-6, 10, 13 all *guessed* that allocation mattered somewhere, and it never did — not in the
schedule build, not single-thread, not in parallel. The one true single-hash lever was always
per-operation overhead (boxing/IFn), and the one true parallel limit is the CPU's frequency
governor. No code artifact this round — the right outcome, since the diagnostic showed the
proposed optimization would not help. The sole remaining frontier is unchanged: hardware-SIMD
multi-buffer (non-portable), which raises *per-core* lane throughput and is orthogonal to the
all-core frequency ceiling measured here.

## 2026-07-02 (round 15) — validated the whole stack against the REAL Bitcoin genesis block

Fifteen rounds of correctness gates, and every one used *synthetic* fixtures (random headers,
Python-hashlib cross-checks). For a repo whose premise is "efficiently derive Bitcoin's SHA-256",
that's a real credibility gap: it had never reproduced a single real Bitcoin block. Round 15 is
the strongest possible Reflection-against-ground-truth — validate the entire stack against block 0.

Fixtures independently verified via Python `hashlib` before use (per the repo's never-hand-
transcribe-crypto-constants rule): constructed the genesis header from its real field values
(version 1, prev-hash 0, merkle root 4a5e1e4b…, time 1231006505, bits 0x1d00ffff, nonce
2083236893) and confirmed its sha256d equals the canonical genesis hash
`000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f` (display leading-zero bits: 43).

**Findings:**

43. **The whole stack reproduces the real genesis block on BOTH runtimes.** `sha256d-bytes`, the
    `midstate` mining path, and (JVM) the `compress-primitive-inline` fast path all yield the exact
    canonical genesis hash in block-explorer display order — verified on the JVM
    (`genesis-block-test`, 22 tests / 7464 assertions) and on V8 (cljs-verify now 8/8, genesis via
    the midstate path). First non-synthetic validation in the series.
44. **`search-nonce` recovers Satoshi's actual genesis nonce (2083236893).** Searching an 11-nonce
    window around it at a 40-leading-zero-bit target (below the genesis hash's 43, so only the
    genesis nonce qualifies), the reference AND the JVM fast path both return exactly
    `[2083236893, <genesis hash>]`. The mining primitive works against real Bitcoin difficulty, not
    just synthetic leading-zero checks — a real known-answer test with the answer being a famous
    constant of the actual blockchain.
45. **This grounds every prior round.** Because all six compress strategies + midstate + both nonce
    searches are bit-identical (the hard correctness gate held all 15 rounds), the ~4.4x single-
    thread and ~4.6x parallel fast mining paths provably mine the *real* chain — now demonstrated
    against block 0, not asserted. The optimization work was never at the expense of correctness.

**Meta (rounds 1-15):** the arc is complete and anchored to reality. What began as "efficiently
derive Bitcoin's SHA-256" is: a portable `.cljc` reference verified against NIST vectors and the
real genesis block on JVM+V8; per-platform fast paths (~2.7x JVM / ~3.6x V8) reached by removing
per-operation overhead — the one lever the tournament found real, after rejecting Ch/Maj formula,
schedule data structure, and software multi-buffer; a ~4.4x mining nonce search composing midstate
+ fast path; ~4.6x across 10 cores (hardware-frequency-limited, not software); and a real-Bitcoin
known-answer proof tying it all to the chain. The single remaining, deliberately-deferred frontier
is hardware-SIMD multi-buffer (JVM Vector API / WASM SIMD) — large, non-portable, per-core lane
throughput, orthogonal to everything measured. Every cheaper avenue has been tried, measured, and
either kept (midstate, fast paths, threads) or honestly rejected (formula, schedule structure,
software multi-buffer, allocation-free path).

## 2026-07-02 (round 16) — probed the SIMD frontier: viable API, but needs a Java hot loop (not portable Clojure)

Having deferred hardware-SIMD multi-buffer seven times, round 16 engaged it — with a feasibility
probe first (scout before building ~100 lines of Vector API interop blind).

**What the probe established:**

46. **The JVM Vector API is available and correct here.** `jdk.incubator.vector` loads on JDK 24
    (`--add-modules jdk.incubator.vector`); `IntVector.SPECIES_PREFERRED` = **4 lanes** (Apple
    Silicon ARM NEON, `S_128_BIT`); broadcast / add / xor / shift / or produce correct lane values.
    So the raw capability for a 4-way multi-buffer (theoretical ~4x per core) exists.
47. **But a performant *Clojure* port is blocked — two compounding issues the probe surfaced:**
    (a) **Reflection, confirmed.** Vector API calls (`.lanewise`/`.lane`/`broadcast`) cannot be
    type-resolved through Clojure `loop`/`recur` locals — `*warn-on-reflection*` flags every one
    ("call to method lanewise can't be resolved (target class is unknown)"). Every op reflects, so
    even a tight 25M-iteration register-resident loop would not complete in 80s. (b) **Allocation.**
    The immutable-`IntVector` style returns a fresh heap vector per op (~48 per schedule extension);
    the naive `IntVector[64]` schedule is allocation-bound on top of the reflection cost. Removing
    (a) needs pervasive `^IntVector` hinting on every intermediate — impractical through the 16-to-64-
    vector schedule/state loops SHA-256 requires; the clean fix is to write the hot loop in Java.
    **Measured (the probe finished when left to run longer):** the naive 4-lane array-of-`IntVector`
    schedule extension clocked **~1,448,000 ns/msg vs 229 ns/msg scalar — ~6,300x SLOWER**, not 4x
    faster. That single number is the whole finding: reflection + per-op heap allocation utterly
    dominate, so the naive Clojure Vector API port is a non-starter, full stop.
48. **And still unverified:** whether HotSpot C2 actually *intrinsifies* the Vector API on aarch64
    (NEON) as well as it does x86 AVX — historically less mature. The reflection issue dominated
    before this could even be measured.
49. **Conclusion — the frontier is real but out of scope for this project's setting.** A SIMD
    multi-buffer would be a dedicated **Java** hot-loop effort (leaving not just `.cljc` portability
    but idiomatic Clojure entirely) plus aarch64 intrinsics validation. That is a qualitatively
    bigger step than the per-platform fast paths were: those stayed within idiomatic Clojure/cljs
    (`long-array`/`^long`; `Int32Array`/`| 0`). SIMD is the one avenue that requires dropping out of
    the language the whole repo is written in. It stays open, now *scoped* (4 lanes, Java hot loop,
    NEON intrinsics TBD) rather than hand-waved.

**Meta (rounds 1-16):** the co-scientist search is complete for everything reachable in idiomatic
portable Clojure. Sixteen rounds mapped the space: one real single-hash lever (per-operation
overhead → ~2.7x/~3.6x fast paths), one structural mining win (midstate, 1.6x), one across-core
axis (threads, ~4.6x, hardware-frequency-bounded), all bit-identical and grounded against the real
genesis block — and a long list of measured, honestly-rejected dead ends (Ch/Maj formula, schedule
data structure, software multi-buffer, allocation-free path). The last frontier (hardware SIMD)
was probed and bounded: viable in principle, but a Java effort outside this repo's Clojure setting.
No code artifact this round — the probe's finding was that the naive Clojure approach is the wrong
tool, so nothing broken was committed. That is itself the measure-first discipline holding to the
end: don't ship a slow/reflective SIMD port just to have "done SIMD."
