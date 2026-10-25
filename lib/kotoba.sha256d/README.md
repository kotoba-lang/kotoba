# sha256d

The dependency-free SHA-256 `Ch` and `Maj` round primitives also have a native
`.kotoba` implementation in `sha256d.round-primitives`. Its domain is every
signed i64 bit pattern and it compiles directly to restricted JavaScript and
Wasm without a JVM runtime. Message scheduling, compression, complete digests,
benchmark evolution, and platform-specific fast paths remain in `.cljc`.

A portable **`.cljc` SHA-256 / Bitcoin SHA-256d** reference implementation, plus a
small **evolutionary benchmark tournament** over interchangeable, individually-proven
round-primitive formulations -- shaped like Google DeepMind's **[AI
co-scientist](https://research.google/blog/accelerating-scientific-breakthroughs-with-an-ai-co-scientist/)**
(Generation / Reflection / Ranking / Evolution / Proximity / Meta-review agents under a
Supervisor, an Elo-based ranking tournament, and self-play/recursive self-critique
driving iterative improvement) and **AlphaEvolve** (LLM-guided evolutionary code search
over a scored program population), but scoped down to a finite, closed, non-LLM search:
for a hash function, "close to correct" isn't a lower-scoring candidate the way a
slower matrix-multiplication algorithm is in AlphaEvolve's search -- it's simply not
SHA-256. Reflection here is therefore a hard correctness gate, applied before any
benchmarking, never one term in a fitness score, and there's no LLM-driven "debate" --
Evolution's recombination is deterministic gene-crossover over a hand-verified pool,
not self-play (see ADR-2607012300 for why: no Workflow/token cost per run).

## Why this shape

The starting reference for this repo was a case study on Google DeepMind's
AlphaProof / Gemini Deep Think / AlphaEvolve / FunSearch line of work -- LLM +
evolutionary-search systems that discover genuinely new algorithms (AlphaEvolve found a
48-multiplication algorithm for 4x4 matrix multiplication, beating Strassen's
56-year-old bound). That search methodology -- maintain a population of candidate
programs, verify/score each, keep and recombine the best -- transfers to SHA-256, but
with one absolute constraint those systems don't have: **correctness is binary, not a
score.** So this repo keeps the *shape* of that search (see `sha256d.evolve`) while
making the correctness gate (`sha256d.evolve/reflect`) a hard filter, and keeps the
"discoveries" honest and small: the gene pool starts with two well-known, individually
algebra-proven Ch/Maj reformulations (see `sha256d.ops`), plus Bitcoin mining's classic
midstate-caching optimization (`sha256d.midstate`), which is a structural ~2x win of a
completely different order than round-primitive rewrites -- see
`docs/evolution-log.md` for what the tournament actually found when run.

## Modules

- **`sha256d.core`** -- FIPS 180-4 SHA-256 + Bitcoin's SHA-256d (`sha256(sha256(x))`),
  over plain sequences of byte values (ints 0-255), no host byte-array type in the hot
  path. This is the correctness oracle everything else in the repo is checked against —
  verified against NIST known-answer vectors **and the real Bitcoin genesis block** (block 0,
  hash `000000000019d668…`) on both the JVM and V8.
  Compression strategies, all bit-identical and injectable via `sha256-bytes-with`:
  portable `compress` (full 64-word precompute), `compress-rolling` (16-word window),
  `compress-transient` (transient-built precompute); JVM-only `compress-mutable`
  (in-place `long-array`), `compress-primitive` (unboxed round loop, ~2.3x) and
  **`compress-primitive-inline`** (also inlines ch/maj, ~2.7x — the recommended JVM fast
  path); and cljs-only `compress-v8` (`Int32Array` + int32 arithmetic, ~3.5x) and
  **`compress-v8-inline`** (also inlines ch/maj, ~3.6x — the recommended V8 fast path).
- **`sha256d.ops`** -- the "gene pool", now `:ch (3) x :maj (3) x :schedule (5 on the JVM,
  4 on cljs) = 45 candidates on the JVM, 36 on cljs` (each platform includes its own fast path). The Ch/Maj variants are `*-naive` (FIPS textbook), `*-alt` (the
  OpenSSL/Bitcoin Core one-fewer-gate formulation), and `*-or` (the same pairwise terms
  as `*-naive`, OR'd instead of XOR'd -- valid because those terms are pairwise-disjoint
  / never-exactly-two-1), each proven algebraically equivalent to the FIPS textbook form
  in a doc-comment and re-checked exhaustively (all single-bit truth-table rows +
  randomized 32-bit words) in `test/sha256d/ops_test.cljk`. The `:schedule` gene is an
  implementation-strategy axis rather than a per-bit formula (`:precompute`, `:rolling`,
  `:precompute-transient`, JVM-only `:mutable` and `:primitive`, and cljs-only `:v8`).
- **`sha256d.midstate`** -- Bitcoin block-header mining: cache the compression state after a
  header's constant first 64 bytes so each nonce attempt only re-runs the second block, not
  the whole 80-byte header (`midstate`, `header-hash`). `header-hash-with` takes an injectable
  compress strategy and `search-nonce` scans nonces through it — composing the midstate reuse
  with a fast compress path gives **~4.4x mining throughput** over naive full-header hashing
  (1.59x from midstate × 2.78x from the fast path), bit-identical (finds the same winning nonce).
- **`sha256d.evolve`** -- the tournament: Generation (enumerate gene combinations) ->
  Reflection (hard correctness gate) -> Ranking (pairwise Elo benchmark tournament) ->
  Proximity (cluster results within 1% as ties) -> Evolution (recombine elites) ->
  Meta-review, for N generations under a Supervisor (`run-tournament`).
- **`sha256d.mitm`** -- the *inverse* direction: a co-scientist search that **designs
  below-brute-force preimage attacks** (meet-in-the-middle / splice-and-cut) for reduced-round
  SHA-256, by finding neutral-word splits over the message-schedule dependency graph. It produces
  genuine 2¹²⁸ preimages on 16-20 rounds and locates where the attack dies (~24 rounds, when the
  expansion fan-out collapses the neutral sets). It does **not** break full 64-round SHA-256 — it
  demonstrates the wall. See `docs/preimage-mitm-cosci.md`.

## Usage

```clojure
(require '[sha256d.core :as sha256d])

(sha256d/bytes->hex (sha256d/sha256-bytes (sha256d/str->bytes "abc")))
;; => "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

(sha256d/bytes->hex (sha256d/sha256d-bytes (sha256d/str->bytes "abc"))) ; SHA256(SHA256(x))

;; Platform fast paths (~2.7x JVM / ~3.6x V8), identical output, opt-in via sha256-bytes-with:
;;   JVM:  (sha256d/sha256-bytes-with sha256d/compress-primitive-inline bytes sha256d/ch sha256d/maj)
;;   cljs: (sha256d/sha256-bytes-with sha256d/compress-v8-inline        bytes sha256d/ch sha256d/maj)
```

```clojure
(require '[sha256d.midstate :as midstate] '[sha256d.core :as core])

;; header is a vector of 80 byte-values (version|prevhash|merkleroot|time|bits|nonce)
(let [mid (midstate/midstate header)]
  ;; re-run this per nonce attempt against the same header prefix -- `mid` is computed once
  (midstate/header-hash mid (subvec header 64 80)))

;; mining nonce search — midstate reuse + a fast compress path (~4.4x over naive on the JVM);
;; scans nonces for a simplified leading-zero-bits target, returns [nonce hash] or nil:
(midstate/search-nonce core/compress-primitive-inline mid tail-prefix-12 20 0 1000000)

;; across-core parallel nonce search (JVM); ~4.6x on 10 cores (all-core turbo-frequency-bound, not linear — round 14):
(midstate/search-nonce-parallel core/compress-primitive-inline mid tail-prefix-12 20 0 1000000 10)
```

```bash
kbb -M:test               # correctness suite (JVM) -- 6000+ assertions
kbb -M:cljs && node target/cljs-verify.js        # correctness portability proof (node)
kbb -M:evolve             # run the tournament on the JVM, print a Meta-review report
kbb -M:cljs-bench && node target/cljs-bench.js   # run the same tournament on V8 (node)
```

## Portability

The round-function primitives (`Ch`/`Maj`/`Σ0`/`Σ1`/rotr/add32) are **plain shared
`.cljc`** with no `#?(:clj :cljs)` split: every operation is either bit-position-local
(and/or/xor/not/shift/rotate, sign-representation-invariant on both platforms) or a
bounded-width add of at most 5 terms under 2^32, which double-precision `+` computes
exactly on both the JVM and V8, before a `mask32` truncation. The one place that
genuinely needs care is the padding's 64-bit big-endian length field: JS bitwise
operators are 32-bit only and silently mask any shift count to its low 5 bits (`x >>>
40` behaves as `x >>> 8`), so it's built from two 32-bit halves via `quot`/`mod` rather
than shifting past bit 31 -- see `sha256d.core/u64be-bytes` and its doc-comment for the
bug this repo actually hit and fixed (`test/sha256d/cljs_verify.cljk`, run under node,
is what caught it -- the JVM test suite alone did not, since `unsigned-bit-shift-right`
on a `long` is 64-bit-aware and masked the bug).

The two JVM-only RNG uses (`src/sha256d/mitm.cljk` `run-mitm` and the JVM test's
2-way `compress` equivalence) used to hold `java.util.Random`; they now use
**`kotoba-lang/prng`** (`kotoba.prng`), a kotoba-lang first-party deterministic
PRNG with JVM/ClojureScript bit-parity. The core stays zero THIRD-party deps;
`prng` is kotoba-lang's own portable lib.

## Status / follow-ups

See `docs/evolution-log.md` for what the tournament has actually found, kept deliberately
honest across rounds:

- **Round 1** (2x2 pool): no stable champion — Ch/Maj formula choice within benchmark noise.
- **Round 2** (grew to 3x3 with `ch-or`/`maj-or`): *appeared* to find that the `*-naive`
  forms get eliminated — but see round 3.
- **Round 3** (fixed the harness): added a **mutation** step so the population stops
  prematurely collapsing to 2 candidates, and made **Elo persist across generations** so
  the rounds accumulate evidence. Doing so **dissolved round 2's result** — that
  "elimination" was largely an artifact of the diversity-loss bug (a dropped candidate
  simply stopped being benchmarked); with `naive` kept in the field it actually wins one
  run. Honest verdict: at this payload/budget the Ch/Maj *formula* choice is within noise.
- **Round 4** (first implementation-strategy gene): added `:schedule`
  (`compress` precompute vs `compress-rolling` 16-word window). First signal clearly above
  the noise floor — but **negative**: `:rolling` is consistently ~7-10% *slower* on the
  JVM and always ranks last. The C-level "schedule-buffer reuse" win doesn't transfer to
  idiomatic persistent-vector Clojure (window-sliding via `conj`/`subvec` allocates).
- **Round 5** (tested round 4's causal claim): added `:precompute-transient`
  (`compress-transient`, schedule built in a transient vector) to test whether *cutting
  allocation* is the lever. It isn't — transient precompute is within noise of plain
  precompute and never wins.
- **Round 6** (the decisive mutable-buffer test): added JVM-only `:mutable`
  (`compress-mutable`, a C-style in-place `long-array` schedule with **zero per-step
  allocation**). It was supposed to confirm "you must leave persistent structures to win" —
  instead it **refuted** it: `:mutable` and `:precompute` are statistically tied (they
  alternate the championship, all within ~0.5%). So the schedule container was never the
  bottleneck. The real cost is the **boxed arithmetic in the round function** (varargs
  `add32`, boxed bit-ops/`ch`/`maj`, vector `(K t)`/`(w t)` lookups) — shared by every
  schedule strategy, which is why they all tie or lose. `:rolling` is dead-last for the 6th
  round running (it adds allocation + interleaving without touching the boxing).

- **Round 7** (the payoff): added JVM-only `compress-primitive` — the *same* mutable
  `long-array` schedule as round 6, but with the 64-round loop **unboxed** (`^long` locals,
  `unchecked-add`, primitive rotate/σ, `long-array` K). This is the **first positive result,
  and a big one: ~2.3x faster** (~20k vs ~47k ns/hash), consistent across runs. It confirms
  round 6's diagnosis exactly — holding the schedule constant, unboxing the round arithmetic
  is the entire win — and Ch/Maj is *still* noise even unboxed (round 3 survives). The win is
  **JVM-only** (V8 has no boxed-`Long` problem); the portable reference stays the default.

- **Round 8** (cross-platform validation): ran the *same* tournament under ClojureScript/node
  for the first time. The portable verdicts **reproduce on V8** — precompute best, transient
  worse, rolling last, Ch/Maj noise — so they weren't JVM-JIT artifacts. V8 is ~3x slower in
  absolute terms (~135k ns/hash) and has no analog to the JVM-only `:primitive` win, confirming
  that win as JVM-only — and predicting a *typed-array* V8 fast path is where the headroom is.
- **Round 9** (the V8 fast path): added cljs-only `compress-v8` (`Int32Array` schedule + K,
  fixed-arity int32 `+` with `| 0`). First cljs positive result and even bigger than the JVM's:
  **~3.5x** (~38k vs ~135k) — the reference's varargs `add32` + persistent lookups cost more on
  V8 than boxing does on the JVM.
- **Round 10** (inline ch/maj): tested round 7's prediction that inlining the last boxed
  ch/maj calls would be small. It was **wrong on the JVM (~13%) and right on V8 (~2.4%)** — the
  JVM can't inline through the higher-order-function seam (boxed `IFn` calls), while V8's
  TurboFan already inlines the small ch/maj JS functions. Added `compress-primitive-inline`
  (JVM ~2.7x) and `compress-v8-inline` (V8 ~3.6x) as the recommended fast paths.

**Net (rounds 1-10):** the bottleneck was per-operation *runtime overhead* — boxed `Long` /
boxed `IFn` calls on the JVM, arg-seq allocation + persistent-vector indexing on V8 — never the
algorithm or data structure (Ch/Maj = noise across all 10 rounds; schedule strategy = no help).
Each platform's fast path removes its own overhead with that platform's numeric tools. The repo
ships one portable reference (`compress`, whose *relative* verdicts hold identically on JVM and
V8) plus a platform-optimal opt-in fast path on each (`compress-primitive-inline` ~2.7x JVM,
`compress-v8-inline` ~3.6x V8).

- **Round 11** (software multi-buffer): tested whether interleaving 2 independent hash lanes in
  one loop fills SHA-256's per-round dependency-chain pipeline bubbles (the portable, no-SIMD
  version of hardware multi-buffer). **Refuted: ~6% slower** — interleaving doubles the live state
  past the register file and spills to stack; the register-pressure cost exceeds the ILP gain.
- **Round 12** (mining payoff): composed midstate + the fast compress into `search-nonce` —
  **~4.4x** per-nonce over naive full-header hashing (1.59x midstate × 2.78x fast path, stacking
  cleanly), bit-identical (finds the same winning nonce).
- **Round 13** (across-core): `search-nonce-parallel` splits the nonce range over cores — ~4.6x on
  10 cores (peak ~272k nonce/s), not linear.
- **Round 14** (diagnose the plateau): two cheap diagnostics showed the ~4.6x ceiling is **not**
  allocation/GC (negligible: <1% pause, 14→16 collections) but **all-core turbo frequency scaling** —
  a single thread drops to 46% of its solo rate when all cores are hot (26.7k vs 57.9k nonce/s),
  and 46% × 10 = 4.6 exactly. So `search-nonce-parallel` scales as well as the hardware allows; the
  "efficiency loss" is the CPU's frequency governor, not software. Refuted round 13's allocation
  hypothesis (and correctly avoided building the allocation-free path it proposed).
- **Round 15** (real-world grounding): validated the whole stack against the **actual Bitcoin
  genesis block** on JVM + V8 — `sha256d`, the midstate path, and the fast path all reproduce the
  canonical genesis hash, and `search-nonce` recovers Satoshi's real genesis nonce (2083236893) at
  the genesis difficulty. First non-synthetic validation; grounds every optimization in the real chain.

- **Round 16** (probe the SIMD frontier): `jdk.incubator.vector` loads on JDK 24 with **4 lanes**
  (ARM NEON) and correct ops — so a 4-way multi-buffer is possible in principle. But a performant
  *Clojure* port is blocked: the Vector API calls **reflect** through `loop`/`recur` locals
  (confirmed via `*warn-on-reflection*`) and the immutable-`IntVector` style allocates per op — the
  naive port measured **~6,300× *slower* than scalar** (1.45 ms/msg vs 229 ns/msg). A real SIMD
  hasher needs a **Java** hot loop (leaving idiomatic Clojure entirely) plus unverified aarch64 C2
  intrinsification.

Sole remaining frontier, now scoped: a **hardware-SIMD** batch-of-N-messages hasher — viable in
principle (4 NEON lanes here), but a dedicated Java effort outside this repo's portable-Clojure
setting, and orthogonal to round 14's all-core frequency ceiling. Everything reachable in idiomatic
Clojure has been tried and measured — kept (midstate, fast paths, threads) or honestly rejected
(Ch/Maj formula, schedule data structure, software multi-buffer, allocation-free path).
