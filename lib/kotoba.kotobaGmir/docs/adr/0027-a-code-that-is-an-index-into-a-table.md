# ADR 0027: a code that is an index into a table

Status: accepted. Date: 2026-09-03.

## Context

ADR 0023 declared the fused dequantize-and-dot family with three members —
Q8_0, Q4_K, Q6_K — and fixed its operand shape: two regions, a BLOCK count,
and both spans derived from that count by the format's own strides.

Those three are 490 of the Qwen3.5 model AIUEOS runs' 866 tensors. **306 more
carry one of four codebook formats — IQ4_XS, IQ2_S, IQ3_XXS, IQ3_S — and they
are the model's dominant types.** Nothing in this repository knew their names,
so no consumer could declare one, admit one, or refuse one.

## Decision

Declare all four, with the same keyset and the same ceiling.

| operation | `sizeof(block_*)` | QK |
|---|---|---|
| `:gmir/kernel-dequant-dot-iq4-xs` | 136 | 256 |
| `:gmir/kernel-dequant-dot-iq2-s` | 82 | 256 |
| `:gmir/kernel-dequant-dot-iq3-xxs` | 98 | 256 |
| `:gmir/kernel-dequant-dot-iq3-s` | 110 | 256 |

Each is the size a negative-array typedef asserts in
`os/aiueos/kernel/qwen35_quant.c`, and each is DISTINCT from the other six —
the suite asserts that, because two formats with the same stride would derive
the same span from the same count and one of them would read the wrong bytes
without tripping any length check.

**Nothing about the operand shape changes.** ADR 0023's reasoning still holds
and holds for the same reason: a quantized row is a vector of blocks, the byte
stride and the element stride are different numbers, and both spans are
derived from one block count.

**What is different about these four is not visible here.** In Q8_0, Q4_K and
Q6_K a code IS a number: sign-extend it, mask a nibble out of it, assemble it
from two fields, and multiply. In the IQ formats a code is an INDEX INTO A
TABLE that belongs to the format and not to the block — 256, 512 or 1024
entries of a codebook that llama.cpp ships as static data, plus a sign table
for three of them. That difference decides how a backend can emit them and
what an oracle must carry, and it is recorded in those repositories. It does
not change what an instruction IS, which is what this repository declares.

## Consequences

- Seven formats, all bounded by their f32 side, all admitting exactly 16384
  elements. **The Qwen FFN dimension is 17408.** Splitting a row into two
  calls is a different accumulation tree, not a size workaround; that was true
  with three formats and is not made truer or falser by four more.
- Declaring an operation is not implementing it. A backend that has no arms
  for one of these must refuse it BY NAME — ADR 0023's reasoning about a
  `case` falling through to `nil` applies unchanged, and more sharply here,
  because a codebook lookup that returned zeros would answer +0.0 for every
  row on every machine.
- `kernel-dequant-dot-block-limit` needed no change: it derives from the
  strides, so four new rows are four new limits with no second place to be
  wrong.
