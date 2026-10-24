# ADR 0023: a quantized row is a vector of blocks, not a vector of elements

Status: accepted. Date: 2026-09-02.

## Context

ADR 0010 declared `kernel-dot-f32`: two regions, two lengths in bytes, and a
count of four-byte ELEMENTS. Both spans are `count * 4`, because both regions
hold the same thing.

A quantized weight row does not. Q8_0 carries 32 elements in 34 bytes, Q4_K
carries 256 in 144, Q6_K carries 256 in 210. The byte stride and the element
stride are different numbers, and neither is derivable from the other without
knowing the format.

## Decision

`:gmir/kernel-dequant-dot-q8-0`, `-q4-k` and `-q6-k`, one operation per format,
carrying `kernel-dot-f32`'s keyset exactly: `:gmir/base`/`:gmir/length` for the
packed row, `:gmir/second-base`/`:gmir/second-length` for the f32 activations,
`:gmir/count`, `:gmir/maximum`.

**`:gmir/count` counts BLOCKS here.** Both spans are derived from it by the
format's own strides — `count * block-bytes` against the first length,
`count * elements * 4` against the second — and nothing downstream may assume
the two regions have the same length. They never are.

The keyset is deliberately the f32 dot product's, so every pass that already
walks those keys keeps working. What differs is only the arithmetic between the
regions, which the operation NAMES rather than parameterises: a format field
would make the strides a runtime value and the bound checks would have to trust
it.

`kernel-dequant-dot-formats` is the one table of strides. `:block-bytes` is
`sizeof(block_*)` in `os/aiueos/kernel/qwen35_quant.c`, where a negative-array
typedef asserts each one; `:block-elements` is that format's QK.

`kernel-dequant-dot-block-limit` is DERIVED from both strides and the shared
65536-byte ceiling, as `min(65536/block-bytes, 65536/(4*elements))`. Bounding
the block count is what keeps either product from wrapping a 64-bit multiply
before it is compared with a length. Measured: the f32 side binds for all three
formats, so all three admit exactly 16384 elements — the same number
`kernel-dot-f32-element-limit` admits.

## Evidence

`test/kotoba/gmir_test.cljk`, four tests: the keyset is exact in both
directions, the ceiling is 65536 and nothing else, the strides are the C's, and
the limit is the derived minimum. Suite: 39 tests / 399 assertions.

Break-checked: the Q8_0 stride as 32 rather than 34 reddens
`fused-dequant-dot-strides-are-the-c-block-sizes` by name.

The emitter, the oracle and the execution evidence are kotoba-native ADR 0066.

The oracle is kotoba-kir ADR 0256 and the probe that boots it is aiueos ADR 0165.
