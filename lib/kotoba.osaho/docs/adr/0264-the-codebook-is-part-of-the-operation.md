# ADR 0264: the codebook is part of the operation

Status: accepted. Date: 2026-09-03.

## Context

ADR 0256 made the dequantization equations this oracle's answer for Q8_0,
Q4_K and Q6_K. In those three a code IS a number: sign-extend a byte, mask a
nibble, assemble six bits from two fields, multiply.

`kotoba.gmir` ADR 0027 declared four more — IQ4_XS, IQ2_S, IQ3_XXS, IQ3_S —
which are 306 of the Qwen3.5 model's 866 tensors, more than any other family.
In these a code is an **index into a table**: a grid of 256, 512 or 1024
entries that llama.cpp ships as static data and that belongs to the FORMAT,
not to the block. Three of the four also carry a per-element sign that the
table does not.

So the equation alone does not determine the answer, and an oracle that
carries only the equation cannot answer.

## Decision

**The tables are in this repository, as byte images.**
`kotoba.kir.iq-codebook` carries all six —`kmask_iq2xs`, `ksigns_iq2xs`,
`kvalues_iq4nl`, `iq3xxs_grid`, `iq3s_grid`, `iq2s_grid`, 11,416 bytes in all
— vendored from llama.cpp @3173a564 (MIT) through
`os/aiueos/kernel/qwen35_quant_tables.inc`.

**As LITTLE-ENDIAN BYTE IMAGES, not as vectors of the declared element type.**
That is what every consumer wants: the C itself casts every grid to
`const uint8_t *` before indexing it, and a backend that reaches these bytes
reaches them as a run of bytes in a read-only pool. Storing `iq2s_grid` as
1024 unsigned 64-bit values and unpacking them at each use would put a second
endianness decision in every reader.

**Each image is pinned by a positional digest.** `digests` records FNV-1a/32
over each byte image and its length. That exists so a SECOND transcription of
the same table — a backend's read-only pool, say — can be compared with this
one BY A TEST rather than only by an execution. FNV-1a is used rather than a
sum because a sum cannot see a permutation, and the suite asserts exactly
that: swapping the first and last bytes of `iq3xxs_grid` leaves the sum
identical and changes the digest.

It is written without a 32-bit `bit-xor` and without a 32-bit multiply,
because neither is portable — 0x811c9dc5 exceeds 2^31 so ClojureScript's
`bit-xor` returns a negative, and `h * 0x01000193` exceeds 2^53 so a double
loses the low bits. Only the accumulator's low byte changes under the xor, and
the prime splits as 2^24 + 403.

## What the suite says, and what it cannot

`kotoba.kir-dequant-iq-test` compares each format's oracle with a
transcription of `dequantize_row_iq*` written in the C's own pointer-walk
style — `qs += 4`, `signs += 4`, `y += 8`, `qh += 2`, mutable cursors — where
the oracle is written with `reduce` over derived indices. Element by element,
through the public `execute` with a one-hot activation vector:

```
SCANNED 256 DISAGREEMENTS 0  kernel-dequant-dot-iq4-xs
SCANNED 256 DISAGREEMENTS 0  kernel-dequant-dot-iq2-s
SCANNED 256 DISAGREEMENTS 0  kernel-dequant-dot-iq3-xxs
SCANNED 256 DISAGREEMENTS 0  kernel-dequant-dot-iq3-s
```

**The TABLES are not independent between the two sides.** Both read
`kotoba.kir.iq-codebook`, because a second hand transcription of 8192 bytes
would be a second copy of the same typing rather than a second opinion. What
guards the table is the digest above plus six entries read out of the `.inc`
by hand and asserted — the first and last entry of every grid, all sixteen
`kvalues_iq4nl` levels, and the first four `ksigns_iq2xs` bytes.

**The blocks are synthesised** (this host carries no GGUF, measured
2026-09-02), and the suite asserts they are not degenerate: more than sixteen
distinct weights per format, with both signs present. A fixture of equal
weights cannot show a wrong index, because every wrong answer is the right
one.

**Break/unbreak, 2026-09-03.** The oracle's IQ4_XS scale bias `ls - 32`
changed to `ls - 31`: 256 of 256 elements disagree. The oracle's IQ2_S quarter
scale `db[l/2]` changed to `db[l mod 2]`: 112 of 256 disagree — not 256,
because the two scales coincide wherever a byte's two nibbles are equal, and
that is what makes the count informative rather than the failure.

## Consequences

- Seven formats have oracles; three of the seven have machine code. Declaring
  and answering are separate from emitting, and a backend that cannot emit one
  of these must refuse it by name (gmir ADR 0027).
- `kotoba.kir.iq-codebook` is 11,416 bytes of table in a repository that had
  none. It is required by `kotoba.kir` at load, so every consumer of this
  namespace now carries it.
- The IQ3_S transcription keeps the C's `ib32 += 2` outer loop rather than
  flattening it, because one `qh` byte serves two 32-element groups and one
  scale byte serves both. Flattening it is exactly the kind of index
  arithmetic the reference exists not to share with the oracle.
- Registered in `run-tests.cljk`, so it runs on both runtimes. Being required
  is not being run — the suite that established that (`kir-rodata-literal`)
  is three entries above it in the same list.
