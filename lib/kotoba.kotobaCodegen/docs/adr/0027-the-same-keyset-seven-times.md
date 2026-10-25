# ADR 0027: the same keyset, seven times

Status: accepted. Date: 2026-09-03.

## Context

ADR 0023 admitted the fused dequantize-and-dot family into MC with the f32 dot
product's keyset. `kotoba.gmir` ADR 0027 declared four more members — IQ4_XS,
IQ2_S, IQ3_XXS, IQ3_S — in which a code indexes a table that belongs to the
format.

## Decision

Four more rows, the same keyset. A codebook is not an operand: it is read-only
data the backend places beside the code, so nothing about the MC shape of
these instructions differs from the three that came before.

The rows are written out rather than generated from the family's set, for the
reason ADR 0023 gave: this table is what says an instruction is canonical, and
a table generated from another table cannot disagree with it, which is the
only thing it is for.

## Consequences

- Seven formats in `mc-operand-keys`. A format missing here is rejected as
  `:non-canonical-instruction`, which is the correct answer for one this
  repository has never been told about — and the WRONG answer for one a
  backend simply has no arms for. That difference is why the backends refuse
  by name, and it was measured on 2026-09-03: with these four declared
  everywhere except here, `kotoba-native` reported
  `:non-canonical-instruction` for all four and said nothing about codebooks.
