# ADR 0037: four more rows and no new operand

Status: accepted. Date: 2026-09-03.

## Context

ADR 0033 gave the fused dequantize-and-dot family the f32 dot product's keyset
and its register tier. `kotoba.gmir` ADR 0027 declared four more members —
IQ4_XS, IQ2_S, IQ3_XXS, IQ3_S, 306 of the Qwen3.5 model's 866 tensors — in
which a code is an INDEX INTO A TABLE rather than a number.

A table is data an instruction reads. This repository's business is which
operands an instruction HAS.

## Decision

Four more rows in `mir-operand-keys`, and four more entries in the set of
operations that produce a value. **No new operand key**, and no change to the
ceiling check, the register tier or the x86-only rule.

The codebook belongs to the FORMAT and not to the caller: it is read-only data
the compiler places beside the code, not a region a caller passes in. So there
is no third base whose provenance to walk and no third length to check. If it
were an operand, every caller of a codebook format would have to obtain and
declare a region it does not own, and the family's operand shape would fork
into two.

## Consequences

- Seven formats, one keyset, one ceiling. `kernel-dequant-dot-operations` is
  still derived from GMIR's own set, so the rows here cannot drift from the
  declaration.
- A backend with no arms for one of these refuses it by name. That refusal
  happens after this layer and is not this layer's business — which is why
  four rows are added here for formats no backend emits.
