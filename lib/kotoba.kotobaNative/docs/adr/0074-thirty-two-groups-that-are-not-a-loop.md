# ADR 0074: thirty-two groups that are not a loop

Status: accepted. Date: 2026-09-03.

## Context

ADR 0066 landed the fused dequantize-and-dot family and emitted exactly one of
its three formats. Q4_K and Q6_K were declared in `kotoba.gmir`, admitted by
the frontend and the verifier, and implemented in the oracle — `kotoba.kir`
dequantizes both and is checked element by element against an independent port
of `os/aiueos/kernel/qwen35_quant.c` — and the backend refused them by name
with `:dequant-format-not-emitted`.

The stated reason was a property of the formats and not an oversight:

> a Q4_K or Q6_K block's dequantization parameters change every 32 and every
> 16 elements respectively, so its thirty-two eight-element groups are not a
> loop — each one takes a different scale field, a different nibble half and a
> different bit shift, and the sequence has to be unrolled thirty-two times
> per arm. Q8_0's four groups are one loop.

That reason still holds. This ADR does the unrolling.

Together the two K-quants are 184 of the Qwen3.5 model's 866 tensors, and
until now every one of their matvecs ran the C in `qwen35_infer.c`.

## Decision

**Unroll, and address the whole block from one pointer.**

Q8_0 walks a block with a group loop that advances `r10` by 8 and `r11` by 32
per iteration. The K-quants do not: their thirty-two groups are emitted in
line, every displacement is a constant computed at emit time, and the two
pointers move ONCE per block — `add r10, 144` / `add r11, 1024` for Q4_K,
`add r10, 210` / `add r11, 1024` for Q6_K. `[r10+disp]` and `[r11+disp]` reach
the whole of a block, so a group needs no pointer arithmetic at all.

**Where each group reads is a table, not arithmetic buried in an emitter.**

`x86-dequant-q4-k-groups` and `x86-dequant-q6-k-groups` are thirty-two-entry
vectors of constants. They exist as data so they can be compared with a
transcription of the C that computes them a different way:
`kotoba.native.dequant-kquant-test` walks `dequantize_row_q4_K` and
`dequantize_row_q6_K` with the C's own `y++`/`q += 32` pointer walk and
compares the two element by element — `SCANNED 256 DISAGREEMENTS 0` for each
format — then perturbs the table two ways (the nibble half swapped, the scale
index shifted) and asserts both DISAGREE, so the comparison is not vacuous.

**The accumulation tree does not change.** Four lane accumulators, the lower
half of each group before its upper, `(s0+s1)+(s2+s3)`, no `vfmadd231ps`. What
differs between the formats is only how a code becomes a float.

**Nibble masks are shift pairs, not a broadcast constant.** On a value
`vpmovzxbd` has zero-extended from a byte, `(v << 28) >>> 28` is `v & 0xF`. It
costs an instruction rather than a register, and the register is the scarce
one: Q4_K's vector arm holds an accumulator, two temporaries, two broadcasts,
`d`, the fp16 work register and 2^112 — all eight of xmm0..xmm7 — and the
legacy arm additionally holds `d`, `d1` and `min1` in xmm8..xmm10.

**2^112 is re-made once per Q4_K block.** Q4_K converts two halves per block,
`d` and `dmin`, and `dmin` then takes the register 2^112 was in. Re-materialising
the constant costs two instructions per block; keeping a ninth vector register
live across the arm costs a register the arm does not have.

**Q6_K's bias is applied to the integer.** `code = (nibble | bits<<4) - 32` is
a `vpsubd` against a broadcast -32 in the vector arm and a `sub rax, 32` in the
legacy one, both BEFORE the conversion, so the two arms round in the same
place. The broadcast is built once per call, in the arm's prologue.

**`:emitted?` stays in `x86-dequant-formats`** even though every row is now
true. The refusal it guards is the one a `case` with a missing arm cannot
make: a group emitter that returned `nil` would emit a loop with an empty
body, which is a working instruction that answers +0.0 for every row, on every
machine, agreeing with itself. The next format to arrive needs that row.

## Consequences

- Q4_K emits 14,392 bytes and Q6_K 21,208, against Q8_0's 916. That is what
  unrolling thirty-two groups into two arms costs, and it is per instruction
  site, not per call.
- Q8_0's emitted bytes are UNCHANGED: sha256
  `47eeea1fa13cdcd2ae713c862787d792e00d8a74ed7b3e0206821f829cbe167c`, 916
  bytes, before and after this change.
- Two AVX forms were added: `:vpslld-imm8` (`/6` on the opcode `:vpsrld-imm8`
  already used) and `:vpor`. A K-quant code is assembled from FIELDS, which
  Q8_0's whole-byte codes never needed.
- Static guest-instruction counts per group of eight elements, counted by
  `llvm-mc --disassemble` over the byte ranges the suite pins:

  | format | vector arm | legacy arm | ratio |
  |---|---|---|---|
  | Q8_0 (ADR 0066) | 13 | 53 | 4.08 |
  | Q4_K low half | 11 | 64 | 5.82 |
  | Q4_K high half | 10 | 64 | 6.40 |
  | Q6_K strip 0 | 21 | 99 | 4.71 |
  | Q6_K strip 1 | 21 | 99 | 4.71 |
  | Q6_K strip 2 | 20 | 91 | 4.55 |
  | Q6_K strip 3 | 20 | 99 | 4.95 |

  Q6_K's vector group carries its own scale — a `movsx`, a `vmovd`, a
  `vcvtdq2ps`, a `vmulss` and a `vbroadcastss`, five of its twenty-one — where
  Q4_K's is amortised over four groups. Strip 2 is the only strip whose
  two-bit field needs no shift (`(qh >> 4) & 3` moved to bits 4..5 is
  `qh & 0x30` and nothing else), which is why its legacy group is 91 where the
  other three are 99. Neither is a per-block figure: both arms also pay the
  half-precision conversion of the header, and Q4_K the eight (scale, min)
  pairs.

  A FIRST VERSION OF THIS TABLE WAS WRONG. It said 15 and 14 for Q6_K's vector
  strips against a true 21 and 20, and the suite was green because its
  assertions were ratio floors written from the same wrong numbers. The counts
  are now tied to byte ranges the suite extracts from the emitted code, so a
  count that no longer matches its arm is a red rather than a stale table.

  These are COUNTS and not speedups. The only machine on this workstation with
  AVX2 is QEMU TCG, whose `rdtsc` without `icount` reads host time and whose
  cost is dominated by translating instructions rather than executing them;
  ADR 0066 measured 1.46 there for Q8_0 and explained why that number means
  nothing.
- The ceiling is unchanged and still binds: every format admits 16384
  elements, and the Qwen FFN dimension is 17408. Splitting a row into two
  calls is a DIFFERENT ACCUMULATION TREE, not a size workaround, so it is not
  a thing this ADR permits anyone to do quietly.
- What is still not done: the IQ family (IQ3_XXS, IQ3_S, IQ4_XS, IQ2_S — 306
  of 866 tensors and the dominant types) needs a codebook grid reachable from
  a kernel object before it can be declared at all, and nothing in
  `qwen35_infer.c` calls any of these instructions yet.

## Evidence

- `kbb -M:test` in kotoba-native: 348 tests, 4758 assertions, 0 failures.
- `kotoba.native.dequant-kquant-test`: 11 tests, 72 assertions.
- Break/unbreak, 2026-09-03, each red for the reason named:
  - `:pair (quot g 4)` → `(quot g 8)`: `q4-k-unrolled-groups-read-what-the-c-reads`
    reports 224 disagreeing elements and `{0 64, 1 64, 2 64, 3 64}` where eight
    pairs of 32 are required.
  - the two `vaddps` swapped: the pinned low and high group bodies stop
    matching.
  - `lane = (quot e 2)` instead of `(mod e 4)`: the ordered `addss` ModRM
    sequence reports `[196 196 204 204 212 212 220 220]` where
    `[196 204 212 220 196 204 212 220]` is required. This is the defect ADR
    0066 recorded a golden passing for, and it is caught here.
- Both arms of both formats executed under QEMU and agreeing with
  `kotoba.kir`: `os/aiueos/scripts/smoke-qemu-dequant-kquant.cljs` (aiueos).
