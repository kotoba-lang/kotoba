# ADR-0148 — The scalar functions between the matvecs

Status: accepted
Date: 2026-09-02
Relates to: ADR-0147 (the forward pass's first three objects), ADR-0138 (the
AVX2 arm runs), kotoba-native #123, kotoba-kir ADR 0238.

## Decision

The scalar functions `matvec_range` sits between become two Kotoba kernel
objects:

| object | export | bytes | fuel tier |
|---|---|---|---|
| `qwen35-activation.kotoba` | `kotoba_aiueos_qwen35_activation` | 7,736 | 16,777,216 |
| `qwen35-norm.kotoba` | `kotoba_aiueos_qwen35_norm` | 8,384 | 250,000,000 |

`activation` is `silu` / `sigmoid` / `softplus` / `local_exp` elementwise, plus
`ffn`'s `scratch_a[i] = silu(scratch_a[i]) * scratch_b[i]` as one statement.
`norm` is `rms_norm`, `l2_norm_heads` and `rms_norm_heads_weighted`.

Two objects rather than one because they split on **what they reduce over** —
the activations are elementwise and stateless, the normalisations carry a
whole-vector sum — and a mode selector across both would put an elementwise
`silu` under a fuel bound whose worst case is a two-pass `rms_norm`.

## The integer truncation the C gets from a cast

`local_exp` computes `(int32_t)(scaled + 0.5f)`. **This dialect has no
float-to-int operation**: `f32-to-i64-truncating` and `f32-to-i64-checked` are
both refused for native, because x86 yields `INT64_MIN` out of domain, AArch64
saturates and the KIR oracle traps — three answers, so there is nothing to
admit. The object truncates from the binary32 pattern instead, which is exact
over the only range that reaches it: the C clamps `value` to `[-87, 88]` first,
so `scaled + 0.5` is inside `(-127, 128)` and the exponent is at most 6.

## The accumulator is f64 and the product is f32

All three normalisations reduce `sum += (double)(v[i] * v[i])`: the **square is
binary32** and is then widened. Squaring in f64 would be more accurate and
would disagree with the C on most inputs. The two reductions then narrow at
different points, and that is a difference in the answer rather than the
spelling:

```
rms_norm        (float)(sum / (double)count) + EPSILON   divide, then cast
l2_norm_heads   (float)sum + EPSILON                     cast, then add
```

## What is NOT here: rope_heads

`rope_heads` (`qwen35_infer.c:476`) is the fourth thing in this tranche and it
is **not ported, for a reason that is not schedule**. Its frequencies come from
`local_exp`, which this object now has, but its rotation comes from
`local_sincos`, and on x86-64 that is the **x87 `fsincos` instruction**:

```c
__asm__ volatile("fsincos" : "=t"(c), "=u"(s) : "0"(value));
```

Amu emits no x87. There is no polynomial to transcribe, because the C is not
using one — so a Kotoba `rope_heads` would have to compute sine and cosine some
*other* way, and it would not be bit-compatible with the C by construction.
That is a decision about the model's numerics, not a port, and it needs the C
to change first. Two ways out, both requiring a decision this ADR does not
make: give the C a polynomial `sincos` both sides can share, or add an x87
primitive to the backend.

## Evidence

**On the CPU**, in two profiles. `aiueos_low_end <= 0x1f4000` leaves 999,424
bytes for the low region, and since the tokenizer objects landed there is less
headroom than these five objects need at once — measured: adding 16,120 bytes
to a link that already carries the other three overflows it. So the comparison
runs in halves, each linking only the objects its stages call, and **a stage a
profile did not compile is refused rather than reported ok**:

```
AIUEOS_QWEN35_KOTOBA_PARITY=1   QWEN-PARITY dequant ok / dot ok / matvec ok
AIUEOS_QWEN35_KOTOBA_PARITY=2   QWEN-PARITY activation ok / norm ok
                                AIUEOS_UEFI_SMOKE_OK
```

Shown red, one deliberate break per stage: `local_exp`'s upper clamp moved from
88.0f to 89.0f gives `QWEN-PARITY activation mismatch`; `scale-mul-w`
reassociated from `(v*scale)*w` to `(v*w)*scale` gives `QWEN-PARITY activation
ok` followed by `QWEN-PARITY norm mismatch` — the right stage, and the stage
before it still green.

**The CPU run found a defect the interpreter could not.** The first `norm` run
came back `mismatch`, and the cause was the *self-test's own harness*: mode 0's
arguments are `[mode input weights count output]` and the harness passed the
output buffer where the input goes. Every bound still held; it normalised the
wrong vector into the wrong place. The KIR contract could not have caught it,
because the contract's builder and the object agree on the order by
construction.

**In the interpreter.** `contracts/qwen35-{activation,norm}-v1.edn` through
`verify-admissions.cljs`: 27 vectors, 11 memory assertions. The activation
vectors carry every clamp boundary — ±87, ±88, ±89, ±20, ±20.5 — because a port
that got a clamp wrong agrees everywhere else. `norm` observes `-5..0`; `-6`,
`-7` and `-8` need a non-finite input or an overflowing scale and are declared
**unobserved, not unreachable** — they are reachable and the C reaches them.

**Bytes.** `qualification/jvm-free-object-parity-qwen35-scalars.edn`:
`SCANNED 2 MATCH 2 DIFFERS 0 COULD-NOT-RUN 0 FAILED 0 REACHED-A-JVM 0`.

## What this does not claim

- **The C is unchanged.** `qwen35_infer.c` gained the self-test; `rms_norm`,
  `silu` and their neighbours still run every token. Nothing is flipped.
- **The fuel tiers were fitted, then executed once each.** ~20 per element for
  the activations, ~66 (ordinary) / ~106 (fallback) for the norms. One
  execution at one size is not a bound.
- **`rope_heads`, softmax, and everything downstream are not started.** Softmax
  is fused into `full_attention` rather than standing alone, so it belongs to
  the attention stage, not to this one.
