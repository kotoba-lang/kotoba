# ADR 0031: a trit is a code with three values

Status: accepted. Date: 2026-09-26.

## Context

The Ternary Bonsai 2 27B artifact AIUEOS is admitting (aiueos ADR-0222) has
851 tensors, and **402 of them are PTQ1_0** (ggml type 143): Prism's
group-128 ternary. None of the seven fused dequantize-and-dot formats (ADR
0023, 0027) is PTQ1_0, so the live matvec materialises every PTQ1_0 row as
f32 in memory and then dots it -- the round trip ADR 0023 exists to remove.

## Decision

Declare `:gmir/kernel-dequant-dot-ptq1-0` with the family's keyset and
ceiling.

| operation | `sizeof(block_ptq1_0)` | QK |
|---|---|---|
| `:gmir/kernel-dequant-dot-ptq1-0` | 28 | 128 |

`qs[24]` (five base-3 digits per byte, 120 values), `qh[2]` (four per byte,
8 values), then `d` as fp16 -- `PrismML-Eng/llama.cpp` @9a9394a8,
`ggml/src/ggml-quants.c:2255`. 28 is distinct from the other seven strides.

The derived block limit is 128: the f32 side binds (65536 / 512), so the
family still admits exactly 16384 elements per call, and the FFN dimension
17408 is still two calls and therefore a different accumulation tree.

## Consequences

The operand shape is unchanged, so no consumer needs a new operand; each
consumer adds one row.
