# ADR 0075: a codebook has to reach the machine before an arm can be written

Status: accepted. Date: 2026-09-03.

## Context

ADR 0074 unrolled Q4_K and Q6_K, so this backend emits three of the seven
formats `kotoba.gmir` ADR 0027 now declares. The other four — IQ4_XS, IQ2_S,
IQ3_XXS, IQ3_S — are **306 of the Qwen3.5 model's 866 tensors, more than any
other family**, and their oracle exists: `kotoba.kir` ADR 0264 answers all
four, checked element by element against an independent port of the C.

In the three that emit, a code IS a number. In these four it is an **index
into a table** of 256, 512 or 1024 entries that belongs to the FORMAT and not
to the block, and three of the four also carry a per-element sign the table
does not. So an arm cannot be written until the table can be read.

## Decision

**Carry the four through this backend's tables with `:emitted? false`, so the
refusal names them.**

Measured 2026-09-03: with the four declared in gmir, mir and the verifier but
NOT in `kotoba-codegen`'s `mc-operand-keys`, this backend answered
`:non-canonical-instruction` for all four — a true statement that says nothing
about codebooks and points at the wrong repository. With the row present it
answers `:dequant-format-not-emitted` and names the encoding.

## The route the table takes, measured

**This backend already has a read-only pool, and an MC emitter can put bytes
in it without any new operand.** The literal pool BOOT-LITERALS landed
(`resolve-program-layout`) is driven by TOKENS, not by source heads: any token
carrying `:native/rodata-content`, `:native/rodata-encoding`,
`:native/rodata-dst` and `:native/rodata-target :x86-64` becomes a pool entry
and resolves to `lea r64,[rip+disp32]` — seven bytes, one layout pass, no
relocation and no fourth PE section. The pool follows the code and the UTF-8
string pool, every entry is 8-aligned, and entries are keyed on
`[encoding content]`.

So a codebook does **not** need a seventh operand, a third region, a
provenance root or a caller that owns a table it did not write. It needs a
`:hex-bytes` literal in this file and one token per arm.

**The size, measured from `os/aiueos/kernel/qwen35_quant_tables.inc`:**

| table | entries | bytes | used by |
|---|---|---|---|
| `kvalues_iq4nl` | 16 × int8 | 16 | IQ4_XS |
| `kmask_iq2xs` | 8 × uint8 | 8 | IQ2_S, IQ3_XXS, IQ3_S |
| `ksigns_iq2xs` | 128 × uint8 | 128 | IQ3_XXS |
| `iq3xxs_grid` | 256 × uint32 | 1,024 | IQ3_XXS |
| `iq3s_grid` | 512 × uint32 | 2,048 | IQ3_S |
| `iq2s_grid` | 1024 × uint64 | 8,192 | IQ2_S |
| | | **11,416** | |

That is the whole cost, once per object rather than once per call, and
`kotoba.kir.iq-codebook` already carries every one of them as a hex byte image
with a positional digest — pinned there precisely so a copy in this repository
can be compared with it by a test rather than only by an execution.

**IQ4_XS is the near one.** Its codebook is sixteen signed bytes: it fits in
one XMM register, `vpshufb` is a sixteen-entry byte lookup, and its layout is
Q4_K's without the min or the packed six-bit scales. It needs neither the pool
nor a gather.

**The other three need a gather.** A grid entry is four or eight bytes at a
variable index, which on the vector arm is `vpgatherdd` (not in this
backend's form table) or a fall back to scalar loads that would make the AVX2
arm no wider than the legacy one for the lookup itself.

## What is NOT possible today, and it is not this repository's gate

**No `.kotoba` program can call any of these four, so no arm of theirs could be
executed even if it existed.** The frontend allowlist lives in `kotoba-sema`,
whose vendored copy of the language authority's grammar is pinned by sha256 in
four repositories at once (kotoba-lang, amu, kotoba, kotoba-sema) and is
resynced as a coordinated wave. That wave was measured IN FLIGHT on
2026-09-03: the authority on `kotoba-lang/main` hashes
`1dfb0bb5f622b43b4161bdf93824824be0b3f63bfe43c324a54c64a7dd319d5e` while
`kotoba-sema` main pins
`9f4a779cbbb1f0d459107d4594e24d3f5d9009ce3319370e82141e879f7afee4` as "the
authority of the 2026-09-03 resync wave". Adding four heads there is that
wave's business.

Landing arms that cannot be executed is what ADR 0066 declined to do for the
K-quants, and the reason has not changed: byte goldens say the sequence is the
one intended and cannot say the two arms compute the same number.

## Consequences

- Seven declared, three emitted, four refused by name. The suite counts both
  numbers, so a format that quietly stopped emitting is a red rather than a
  smaller set.
- `:emitted?` earns its keep for the second time. The refusal it guards is one
  a `case` with a missing arm cannot make.
- The resume point is short: the grammar wave, then IQ4_XS (sixteen bytes in a
  register, no pool), then the pool token for the three grids.
