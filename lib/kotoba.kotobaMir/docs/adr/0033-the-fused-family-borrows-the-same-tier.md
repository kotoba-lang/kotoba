# ADR 0033: the fused family borrows the same tier, and is refused for the same reason

Status: accepted. Date: 2026-09-02.

## Context

ADR 0015 selected `kernel-dot-f32` for one target and gave the reason: its two
arms are AVX2 and legacy SSE and the claim that binds them is that they agree
BIT FOR BIT, which is a claim about one accumulation tree rather than about a
dot product. An AArch64 spelling would have to decide whether to keep that tree
at whatever NEON costs, or answer a different number.

kotoba-gmir ADR 0023 adds three operations of exactly that shape.

## Decision

`:mir/kernel-dequant-dot-q8-0`, `-q4-k` and `-q6-k` carry
`:mir/kernel-dot-f32`'s keyset, join `value-ops`, share its single ceiling, and
join its spill arm — five operands loaded into the call-argument tier
immediately before the instruction and dead immediately after, so nothing lives
across it.

They are refused for every target but x86-64, as `:x86-simd-target-mismatch`,
and the refusal now reports the operations it actually found rather than the
literal `[:gmir/kernel-dot-f32]`. A NEON arm would be a third answer nothing
has compared with the other two.

`:mir/count` counts BLOCKS in this family. Nothing in MIR depends on which,
because the ceiling check that does lives in the emitter and in `kotoba.kir`.

## Evidence

Suite: 103 tests / 1984 assertions. The refusal is asserted per format in
kotoba-native's `isa_parity_test.clj`, where the x86-only table lives.
