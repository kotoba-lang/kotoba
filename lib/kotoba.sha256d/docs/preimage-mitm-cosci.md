# Below-brute-force SHA-256 preimage, designed by a co-scientist search

This is the *inverse* problem: given a digest, find a preimage faster than the 2²⁵⁶ brute-force
bound. It is the honest realization of "design an algorithm that inverts SHA-256 below brute force,
using the co-scientist approach." Implemented in `sha256d.mitm`, tested in `test/sha256d/mitm_test.cljk`.

## The one honest boundary, stated once

- **Below-brute-force preimage algorithms are real** — the meet-in-the-middle (MITM) /
  splice-and-cut / biclique family (Aoki & Sasaki 2009; Khovratovich–Rechberger–Savelieva 2012).
- On **reduced rounds** they give large, genuine speedups (this repo's search reproduces them).
- On **full 64 rounds** the best published record is ≈ **2²⁵⁵·⁵** (biclique, ~45 rounds), a margin of
  ~0.5 bits — real but cryptographically meaningless. **No algorithm with a meaningful margin below
  2²⁵⁶ is known for full SHA-256, and none is believed to exist.** This search does not cross that
  wall; it *demonstrates* it. Anything claiming to break full SHA-256 would be fabrication.

## Why a preimage is a search over the message schedule (recap)

From `docs/…` / the round-15/16 analysis: undoing the Davies–Meyer feedforward is O(1) (the post-64
state is `digest ⊟ IV`), and each compression round is invertible *given* its schedule word `W_t`.
So a preimage is any solution of `F(W₀..₁₅) = IV`, where the 48 expanded words
`W_t = σ₁(W_{t-2}) ⊞ W_{t-7} ⊞ σ₀(W_{t-15}) ⊞ W_{t-16}` (t≥16) are determined by the 16 free words.
**The message expansion is the sole source of hardness** — without it, inversion is polynomial.

## The algorithm: meet-in-the-middle / splice-and-cut

Split the R-round cycle (closed by the feedforward) into two chunks A and B at a cut point.
Compute A forward from the (spliced) start and B backward from the target, and match in the middle.
The attack is below brute force when each chunk has **neutral message words** — base words in
`{W₀..W₁₅}` used by *one* chunk only, so they can be varied without disturbing the other:

- `N1 = used(A) \ used(B)` (neutral for B), `N2 = used(B) \ used(A)` (neutral for A);
  `d1 = 32·|N1|`, `d2 = 32·|N2|` bits of independent freedom per side.
- MITM finds `F1(x1) = F2(x2)` on the n=256-bit mid-state: build a 2^d1 table, probe with 2^d2,
  match on n. Cheapest balanced attack is 2^(n/2); with short freedom (`d1+d2 < n`) the shared bits
  are iterated, giving **2^(n − min(d1,d2))**. So the pseudo-preimage cost is
  `2^max(128, 256 − 32·min(|N1|,|N2|))` — below 2²⁵⁶ whenever both neutral sets are non-empty.
  (A pseudo-preimage converts to a full preimage with modest standard overhead.)

## The co-scientist search that *designs* it

The valuable, tractable problem is not running the attack (2¹²⁸ is infeasible) but **finding the
configuration that minimizes complexity** — exactly what automated cryptanalysis does. Mapped onto
the co-scientist agents (`sha256d.mitm`):

- **Generation** — enumerate splice-and-cut configs: every contiguous cyclic arc split `(start, len)`.
- **Reflection (hard gate)** — verify neutrality *exactly* against the schedule dependency graph
  (`schedule-deps`): a config is valid only if BOTH neutral sets are non-empty. A one-sided split is
  not a below-brute-force attack and is rejected — the analog of the forward work's bit-identical gate.
- **Ranking** — order valid configs by pseudo-preimage complexity (lower = better).
- **Meta-review** — report the best attack per round count, and the decay curve.

At word granularity the config space is small enough to search exhaustively (so it is — honesty:
the evolutionary/tournament machinery only becomes *necessary* at the finer bit-level/biclique
granularity, see below). The dependency graph is the crux: `schedule-deps` computes, for each round,
which base words its `W_t` transitively depends on.

## Measured result (this repo's search, word granularity)

`kbb -M -e "(require 'sha256d.mitm)(println (sha256d.mitm/report))"`

| rounds | best cost | saved bits | neutral \|N1\|/\|N2\| | below 2²⁵⁶? |
|---|---|---|---|---|
| 16 | 2¹²⁸ | 128 | 4/12 | yes |
| 18 | 2¹²⁸ | 128 | 4/9 | yes |
| 20 | 2¹²⁸ | 128 | 4/7 | yes |
| 22 | 2¹⁶⁰ | 96 | 3/3 | yes |
| 24 | 2²²⁴ | 32 | 2/1 | yes |
| 26+ | (none) | 0 | — | **no** |

So the search **designs genuine below-brute-force preimage attacks**: e.g. *20-round SHA-256 has a
2¹²⁸ preimage via a 4-word / 7-word neutral split* — a real ~2¹²⁸× speedup over brute force. And it
**locates the wall precisely**: past ~24 rounds the message-expansion fan-out makes every base word
feed both chunks (the dependency graph saturates to all 16 base words by round ~23), so no neutral
split exists and the word-granularity attack vanishes. This is the empirical signature of SHA-256's
preimage resistance — the same mechanism, message expansion, that makes forward inversion hard.

## (B) RUNNING the attack — a measured below-brute-force preimage on the real round function

The full-state MITM is 2¹²⁸ (unrunnable), so `sha256d.mitm/run-mitm` demonstrates its ENGINE at a
runnable scale — a partial preimage matching on `m` mid-state bits of REAL 32-bit reduced-round
SHA-256 (real Ch/Maj/Σ/σ/K; free-schedule model so the forward/backward neutral split is exact),
counting compression-chunk evaluations. It plants a solution, recovers it, and verifies the recovered
pair genuinely collides. `(sha256d.mitm/run-mitm {})` (8 rounds, cut 4, d=11 freedom bits/side, m=26,
seed 42), deterministic:

```
MITM:  2,049 chunk-evals        (≈ 2·2^d, builds a 2^11 table + probes)
brute: 2,325,617 chunk-evals    (same 2^d × 2^d space, no table)
speedup: 1135×                  verified: true  (recovered pair really collides on the 26 bits)
```

This is a real, running, verified below-brute-force attack primitive on the actual SHA-256 round
function — the meet-in-the-middle square root (2^(m/2) vs 2^m) that makes the whole preimage attack
sub-brute-force, measured in genuine operation counts. It scales as √: doubling d roughly squares the
brute-force gap while ~doubling the MITM cost. `test/sha256d/mitm_test.cljk` pins these numbers.

## (A) Pushing further — the honest ceiling: bit-level buys nothing, bicliques are the real gap

The `(A)` request was: extend to bit-level neutral bits + bicliques with a true evolutionary search,
toward the ~45-round record. The honest, tested result:

- **Bit-level neutrality reduces to word-level under sound analysis — bit-granularity gives NO gain.**
  `bit-neutral-for-chunk?` (using the *real* message expansion) shows: a single bit of base word W_i
  is neutral for a chunk **iff the whole word W_i is unused** by it. If W_i is used, even a one-bit
  flip perturbs the chunk (σ-diffusion + carries), so no bit of it is neutral; if unused, every bit
  is. `bit-level-equals-word-level-test` verifies this across all 16 words for a 24-round chunk. So a
  bit-level neutral-set search bottoms out at exactly the word-level result (~24 rounds) — the
  evolutionary/Elo machinery adds nothing here, and the config space is small enough that the
  exhaustive `best-attack` already returns the optimum.
- **The real gap to ~45 rounds / 2²⁵⁵·⁵ is bicliques**, not finer neutral sets: initial structures that
  manufacture extra rounds of independence via *differential trails*, plus probabilistic partial
  matching. These relax soundness in controlled, differential-verified ways — they are a different
  technique, not a neutral-set search, and this repo **does not fabricate their complexity**. That
  larger, genuinely-intractable space (which biclique dimensions, which trails) is the one place a true
  evolutionary / MILP / SAT search becomes *necessary*; building and *verifying* it correctly is a
  research effort, and claiming a 45-round result without that verification would be fabrication.
- **Full 64-round SHA-256 stays unbroken by any meaningful margin** — the correct, honest endpoint,
  and the honest answer to "invert it below brute force": yes for reduced rounds (demonstrably, and
  runnably per (B)), no for the real thing.
