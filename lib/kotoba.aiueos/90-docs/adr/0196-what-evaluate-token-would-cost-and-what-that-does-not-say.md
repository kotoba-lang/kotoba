# ADR 0196: what `evaluate_token` would cost, and what that does not say

Status: accepted. Date: 2026-09-03.

## Context

ADR-0175 (QWEN-KERNELS-2) concluded:

> `evaluate_token` IS NOT FLIPPED AND ONE OBJECT CANNOT BE IT: the fuel word is
> an imm32 (ceiling 2,147,483,647) and the output projection alone is
> 248,320 × 5,120 = 1,271,398,400 MACs ≈ 27,970,764,800 fuel = 13x that
> ceiling. The available flip is C calling each object in turn.

The premise is gone (ADR 0078: the imm32 was an encoding, not the ABI; the
ceiling is now 2^53−1, and ADR 0195 spent 2,200,000,005 fuel on a CPU to show
it is a bound and not just a number). This ADR re-measures the claim so that
"the road is open" is a number rather than a feeling.

## The estimate, and it is an estimate

The projection alone was never the token. Deriving the rest from the tensor
shapes **the runtime already asserts** — `qwen35_runtime.c`'s
`dimensions_are` calls, not from anything guessed:

| part | per unit | count | MACs |
|---|---|---|---|
| FFN (`ffn_gate`, `ffn_up` 5120×17408; `ffn_down` 17408×5120) | 3 × 5120 × 17408 | 64 trunk layers | 1.711e10 |
| linear attention (`gate` 5120×6144, `qkv` 5120×10240, `output` 6144×5120, `alpha`/`beta` 5120×48) | 1.158e8 | 48 | 5.56e9 |
| full attention (`key` 5120×1024, `output` 6144×5120, `query_gate` 5120×12288) | 9.96e7 | 16 | 1.59e9 |
| **output projection** | 5120 × 248,320 | 1 | **1.271e9 — 5.0% of the token** |
| | | **total** | **2.554e10 MACs** |

At **22 fuel per MAC** — which is not a new measurement but ADR-0175's own two
numbers divided by each other, 27,970,764,800 / 1,271,398,400 = 22.0 exactly —
that is

> **≈ 5.62 × 10^11 fuel for one token.**

| against | ratio |
|---|---|
| the old imm32 ceiling, 2^31−1 | **262× over** — ADR-0175 said 13×, because it counted 5% of the token |
| the new ceiling, 2^53−1 | **16,032× headroom** |

A tier in the house style — measured, with a stated margin — would be about
**2^43 (8.8e12, 15.7×)**, or 2^41 (3.9×) at the tighter end. Every one of those
is four orders of magnitude below the ceiling.

## What this does not say

**The road is open. The object does not exist, and nothing in this stream built
it.** ADR-0175's other findings are untouched and are the actual work:

- `ffn` and `linear_attention` are not objects. What remains of `ffn` after the
  matvecs is norm mode 0, activation mode 4 and a residual add; what remains of
  `linear_attention` is the kernel-4 depthwise convolution with its three-step
  history.
- The four-lane binary64 score tree is implemented and **not verified** —
  re-associating it stayed green twice, because products are exact in binary64
  and 256 of them sum without rounding.
- The K16 image is unchanged: `matvec_range` still runs the C every token.

**And the number above is an estimate, not a measurement.** Every fuel tier in
`kotoba.native.elf64` was bisected by execution against the largest input its
callers can legitimately hand it; this one was derived from shapes and a
constant lifted out of another ADR's arithmetic. The three things it could be
wrong about, in the order they matter:

1. **The 22 is the `matvec` object's cost per MAC.** `attention`,
   `recurrent-step`, `norm` and `activation` have their own, and their measured
   tiers say so — 33,554,432 and 4,194,304 against `matvec`'s 250,000,000.
   Applying one rate to all of them is the crude step here.
2. **Attention is counted as projections only.** The QK^T and the value-weighted
   sum scale with KV positions, which the runtime caps at 8 today and which a
   real context does not.
3. **`value` is not in the asserted full-attention shapes**, so it is not in the
   table; the full-attention rows are therefore a floor.

All three push the number **up**, and it would have to move by four orders of
magnitude to reach the ceiling. That is the claim: not that 5.62e11 is right,
but that no plausible correction to it puts `evaluate_token` outside a budget a
single object can now carry.

**Measuring it properly is bisecting one object that does not exist yet**, and
that is the next step rather than this one.
