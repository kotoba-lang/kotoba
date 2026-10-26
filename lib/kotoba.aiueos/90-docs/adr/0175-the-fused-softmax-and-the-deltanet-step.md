# ADR-0175 — The fused softmax and the DeltaNet step

Status: accepted
Date: 2026-09-03
Relates to: ADR-0147 (the forward pass's first three objects), ADR-0148 (the
scalar functions between the matvecs), ADR-0155 (a boot harness must say which
kernel it ran), kotoba-native ADR 0070.

## Decision

Two more of the Qwen3.5 forward pass becomes Kotoba kernel objects:

| object | export | bytes | fuel tier |
|---|---|---|---|
| `qwen35-attention.kotoba` | `kotoba_aiueos_qwen35_attention` | 17,872 | 33,554,432 |
| `qwen35-recurrent-step.kotoba` | `kotoba_aiueos_qwen35_recurrent_step` | 6,808 | 4,194,304 |

`attention` is `full_attention`'s query/gate de-interleave (`qwen35_infer.c:707`),
its **fused softmax** over the KV cache (:733) and its position-zero reduction
(:791). `recurrent-step` is the gated DeltaNet update of one linear-attention
head's `d*d` state (:493).

Both take `[arena arena-bytes plan plan-bytes]` and a 96-byte plan, the shape
`aiueos-qwen35-matvec` established: each needs six or more regions against a
five-argument ABI, and `kernel-subregion` requires a base to be a parameter, a
literal or `kernel-boot-info`, so regions arrive as **offsets** into one arena
that a plan may compute. The offsets are 64-bit because `decode->recurrent` is
**150,994,944 bytes** — 48 linear slots × 48 heads × 128 × 128 × 4 — and sits
above the model mapping.

## What is NOT ported, and why neither reason is schedule

**`rope_heads` (:476) cannot be ported.** On x86-64 the C's sine and cosine are
the x87 `fsincos` **instruction**; Amu emits no x87 and there is no polynomial
to transcribe because the C is not using one. A Kotoba rope could not be
bit-compatible by construction (ADR-0148 made the same finding and it has not
moved).

**The KV cache write, its FNV hash and `resolved_cached_key` (:542) stay in C**
for a different reason: they are custody, not arithmetic — a hash, a shadow
copy and a repair. The object reads the cache the C has already resolved, which
is what that function returns on every path that does not fail.

**`ffn` (:530) and `linear_attention` (:561) are not done.** Both are dominated
by `matvec` calls, and `matvec` is already an object; what is left of `ffn`
after them is `rms_norm` (`aiueos-qwen35-norm` mode 0), the silu-gate
(`aiueos-qwen35-activation` mode 4) and a residual add. See "What this does not
claim".

## The reduction trees are different in the two objects, and that is the port

`stable_attention_score` (:115) widens each binary32 factor to **binary64** and
reduces in **four accumulators**, `(sum0 + sum1) + (sum2 + sum3)` — that is
`dot_scalar`'s tree, not `dot_avx2`'s left-to-right one, the same fork
ADR-0147 had to choose in. The softmax exponent and the denominator then stay
binary32.

`recurrent_step` does the opposite: both of its inner products accumulate **one
element at a time, left to right, in binary32**. Using the four-accumulator
tree there would disagree with the C on most inputs.

## Two things the objects do differently from the C, both proved rather than assumed

**The decay multiply is hoisted.** The C decays a cell inside the `remembered`
accumulation. Over the whole `v` loop every cell is reached exactly once and
always before it is read, so doing all `d*d` multiplies first is the same
sequence of roundings over the same values — a loop split, not a reordering of
an arithmetic expression. It is done because `[state r v k acc]` already spends
the five parameters this dialect admits.

**The gate temporary is dropped.** The C stages each head's gate through
`scratch_b[FULL_GATE_TEMP_OFFSET..]` before applying it. It stages it *after*
the output is written, so it was already reading the same bytes the object
reads; and head `h`'s output occupies `[h*D, (h+1)*D)` while its gate begins at
`h*2D + D`, and `h*2D + D >= (h+1)*D` for every `h >= 0`. The copy moved a
float without rounding it.

## The reference half of the self-test is the code the model path runs

`full_attention`'s three blocks are lifted into `attention_deinterleave`,
`attention_softmax_heads` and `attention_zero_position`, and `full_attention`
calls them. No loop body changed; the geometry arrives as arguments so the
self-test can drive a smaller one. One consequence is stated in the source: the
causal prefix is now resolved **once per prior** instead of once per (head,
prior), which repairs the same rows — `resolved_cached_key` reads the whole
1,024-float row, does not depend on the KV head, and is idempotent.

Without this the reference would have been a second transcription of the C, and
a port and its transcription can be wrong together.

## THE CPU RUN FOUND A DEFECT THE INTERPRETER COULD NOT — again

`recurrent-step`'s two inner loops each need a row and a column, which is six
parameters against five, so the first draft packed them as `v * 128 + k` with
the dimension ceiling as the radix. At `d = 128` — **the only dimension K16
ever passes** — the decoded `k` is `vk mod 128`, which is never 128, so the
termination test `k >= d` never fired.

Every interpreter vector passed. They had to: the `kotoba.kir` interpreter
recurses once per Kotoba call with no tail-call elimination, so it cannot run
`d = 128` at all, and every dimension below the ceiling terminates correctly.
QEMU said `AIUEOS_EXCEPTION_FAIL unexpected-vector vector=6` — the fuel guard's
`ud2` on an infinite loop.

The repair removes the radix rather than widening it: a column walk starts at
`v` and steps by `d`, so `c >= d*d` is the end and `k` is `c / d`; the rank-one
update touches every cell exactly once, so it is one flat loop over `c`.
Neither depends on a ceiling. The object went from 7,432 to 6,808 bytes and the
interpreter vectors are unchanged, which is what a repair that changes no
arithmetic should look like.

This is the second time in this series (ADR-0148 was the first) that the CPU
run caught something the contract could not, and the two have the same shape:
**a contract's builder and its object agree by construction about the thing the
contract is not varying.**

## THE FIRST RED DID NOT DISCRIMINATE, AND THAT FOUND A SECOND DEFECT

Changing `shifted`'s upper clamp from `0.0f` to `1.0f` — a wrong constant of
exactly the kind a port gets wrong — left the comparison **green**. The cause
was the self-test's own inputs: `qwen_parity_value` spreads magnitudes over
`2^-7..2^15`, so a 256-term dot product is around 1e9 and a score around 1e8.
Every difference is then far below `local_exp`'s `-87` clamp, every weight but
the largest underflows to zero, and **the softmax degenerates to picking one
prior with weight one** — `w_max / denominator` is one whatever the clamp says.

In the model the query and the key have both been through
`rms_norm_heads_weighted`, so `q·k/16` is O(1..10) and every prior contributes.
`qwen_att_fill_narrow` halves the synthetic query and key sixteen times, which
is an exact power of two, so no value is rounded on the way in. With that fill
the same one-constant break reports `QWEN-PARITY attention mismatch`.

A break that fails to discriminate is not a failed experiment; it is the only
thing that would have told us the test was not testing the softmax.

## WHAT IS STILL NOT COVERED: the four-lane binary64 tree

`stable_attention_score`'s `(sum0 + sum1) + (sum2 + sum3)` is implemented as
the C has it, and **no evidence here discriminates it.** Re-associating it to
`((s0 + s1) + s2) + s3` was measured twice — once with the wide fill and once
with the narrow one — and both runs reported `QWEN-PARITY attention ok`.

The reason is structural rather than a gap in the vectors. Each product is a
binary32 times a binary32, which is exact in binary64 (24 + 24 ≤ 53), and 256
such products from this generator sum without rounding, so association cannot
change the answer for any input it produces. The interpreter contract cannot
cover it either: its oracle reduces in the same four lanes by construction.

Covering it needs an input whose partial sums span more than 2^53 **while** the
resulting scores stay within about 87 of each other, so the difference survives
into the softmax — the two requirements pull against each other and designing
one is a piece of work this ADR does not claim to have done. Until then the
tree is implemented, not verified.

## Every parity profile was already unbuildable, and `--gc-sections` is why they build now

Measured 2026-09-03 at aiueos main `f11967e`, against
`ASSERT(aiueos_low_end <= 0x1f4000)`:

| profile | objects linked | over the limit by |
|---|---|---|
| 1 (dequant, dot, matvec) | 23,320 B | 45,056 |
| 2 (activation, norm) | 16,120 B | 40,960 |
| 3 (attention) | 17,872 B | 40,960 |
| 4 (recurrent-step) | 6,808 B | 28,672 |

Profiles 1 and 2 landed working and the tree grew past them; `ld.lld` produces
nothing and the stage-0..4 evidence could not be reproduced at main. So the
parity build now compiles the three Qwen C files with
`-ffunction-sections -fdata-sections` and links with `--gc-sections`, which
gives profile 3 **110,260 bytes of headroom** instead of −40,960. What the
collector removes is the model path — `aiueos_qwen35_generate`, the GGUF
parser, the IQ codebook grids — which no self-test stage calls, and it removes
it from the **reference** half: a stage whose reference had been collected
would not agree with the object, it would fail to link.

**The collector took the ring-3 payload the first time.** `.user.text`,
`.user.data` and `.bss.stack` are reached through linker-script symbols and a
section attribute, never through a relocation, and the image booted as far as
`AIUEOS_RING3_FAIL tss-or-mapping`. `linker.ld` now `KEEP`s all three, which is
a no-op for every build that does not pass `--gc-sections`. With that, the
serial log of a parity image is **identical to the baseline's apart from the
`QWEN-PARITY` line**.

Splitting the two objects across two profiles is likewise measured, not
stylistic: 17,872 + 6,808 together still overflowed before `--gc-sections`
existed, and a stage a profile did not compile is REFUSED rather than reported
ok.

## Evidence

**On the CPU** (`smoke-qemu-uefi.sh`, OVMF + q35, with ADR-0155's freshness
receipt so the log cannot belong to a kernel that is not in the tree):

```
IMAGE-FRESH artifacts=3 head=4a7ddcf tree=96f956798b1f
QWEN-PARITY attention ok
AIUEOS_RING3_OK processes=2 preemptive roots=2 domains=2,3 kernel-stacks=2 syscall-sysret
AIUEOS_UEFI_SMOKE_OK
```

`head=4a7ddcf` is the commit the objects and the self-test were at. The same
two lines were re-observed after the merge that carried them onto today's main,
at `head=e36c5b8 tree=cf2536b80401` — a later ADR edit moves the tree hash and
not the kernel, so no quote of a freshness receipt can name the commit that
contains the quote.

```
IMAGE-FRESH artifacts=3 head=4a7ddcf tree=67f1a502ce1f
QWEN-PARITY recurrent ok
```

Shown red, one constant each: `shifted`'s upper clamp `0.0f` → `1.0f` gives
`QWEN-PARITY attention mismatch`; `INV_SQRT_LINEAR_HEAD_DIM` moved by **one
ULP** (1035273459 → 1035273460) gives `QWEN-PARITY recurrent mismatch`. Neither
break can reach the other profile, which links only its own object.

`attention` runs all three modes at 8 heads / 256 wide / group 2 / position 5,
against `attention_deinterleave`, `attention_softmax_heads` and
`attention_zero_position` on the same buffers, comparing every binary32 bit
pattern — plus a refusal (`mode 3` → `-5`), so a run that never saw the object
say no is not counted as a pass. `recurrent` runs at the production
`LINEAR_HEAD_DIM = 128` against `recurrent_step` itself and compares **both**
halves of the answer: the 65,536-byte state the next token reads and the
512-byte activation this token emits. A port that got the rank-one update wrong
but the read-out right passes the second check alone.

**In the interpreter.** `contracts/qwen35-{attention,recurrent-step}-v1.edn`
through `verify-admissions.cljs`: 29 vectors, 7 memory assertions, reasons
`-10..0` and `-7..0` observed. `attention`'s `-11`, `-12` and `-13` need a
non-finite input or a softmax whose weights all underflow, and are declared
**unobserved, not unreachable** — they are reachable and the C reaches them.
Both contracts state `:node-stack-size 60000`, which is measured: at 4,000 the
runner refuses with `:host-stack-exhausted true` rather than reporting a pass.

**Fuel** was bisected in the interpreter and extrapolated to the ceiling each
object **admits**, not to the geometry K16 passes, because a tier is a per-call
budget and a caller may legally ask for the ceiling. attention: 29,991 at 2
heads / position 1 and 47,539 at position 3, so 4,387 per head-prior and 6,221
fixed per head; head scaling is linear and was **measured** rather than argued
— 4 heads at position 3 is 95,604, a ratio of 2.011 — so 64 heads × 8 priors is
2,644,288 and the tier is 12.7× that. recurrent-step: 1,762 at d=8, 6,721 at
d=16, 25,414 at d=32, fitting `22.85 d² + 71.5 d − 272`, which predicts 55,806
at d=48 against **56,312 measured** and gives 383,254 at d=128; the tier is
10.9× that.

## What this does not claim

- **Nothing is flipped and no C is deleted.** `full_attention` still runs its
  own C every token; the objects are compared against it, not substituted for
  it. `qwen35_infer.c` went from 1,528 lines to 1,821: **production 1,118 →
  1,161** (+43, the three extracted signatures and the hoisted resolve loop, of
  which 11 lines are the plan writers moved out of a self-test guard so two
  profiles can share them) and **self-test-guarded 411 → 661** (+250).
- **`evaluate_token` is untouched, and one object cannot replace it.** This is
  measured, not deferred. A kernel object exports one symbol and cannot call
  another (ADR-0030), so an `aiueos-qwen35-evaluate-token` would have to inline
  the whole forward pass, and the packager writes the fuel word as the
  immediate of `mov qword [r9+8], imm32` — a ceiling of 2,147,483,647. The
  output projection alone is 248,320 vocabulary rows of 5,120, which is
  1,271,398,400 multiply-accumulates and, at the 22 fuel per element measured
  for `aiueos-qwen35-matvec`, **27,970,764,800 fuel: thirteen times the largest
  tier that can be written**. One `ffn_gate` matvec is 1,960,837,120, which
  fits only by 9% — and `aiueos-qwen35-matvec` already caps a call at 2,097,152
  elements for exactly this reason, so `ffn_gate` is 43 chunks. The
  orchestration therefore stays in C, and the flip that is actually available
  is C calling each object in turn. That is a different change from the one
  "stage 4" names, and it wants `ffn` and `linear_attention` decided first.
- **`ffn` and `linear_attention` are not objects.** What is left of them after
  the matvecs is already covered by `aiueos-qwen35-norm` and
  `aiueos-qwen35-activation` plus a residual add; an object that restated those
  two would be duplication with a new fuel tier and a new allowlist row, and
  the residual add alone does not earn a symbol. The decision to make is
  whether `ffn` becomes a phased object or whether the C calls the three
  existing objects in sequence — and that decision belongs with the flip, not
  before it.
- **The interpreter never ran either object at its production geometry.**
  `attention` was verified at 2 heads and `recurrent-step` at d ≤ 32; the CPU
  is the only place the real sizes ran, and it is where the one real defect
  showed.
- **Fuel was fitted from three points and executed once.** One execution at one
  size is not a bound.
