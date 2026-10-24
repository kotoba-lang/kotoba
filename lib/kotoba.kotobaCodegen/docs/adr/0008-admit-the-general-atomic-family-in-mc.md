# ADR 0008: Admit the general atomic family in MC

## Decision

MC admits six target-selected general atomic read-modify-writes:
`kernel-atomic-add-u32/u64`, `kernel-xchg-u32/u64` and
`kernel-cmpxchg-u32/u64` (kotoba-gmir ADR 0007, kotoba-mir ADR 0014).

All six carry the bounded store's keyset. Only the two compare-exchanges carry
`:mir/expected`, and the keysets are exact in both directions: a compare-
exchange without a comparand is rejected, and an add or a swap **with** one is
rejected too. A guest-supplied comparand is the whole difference between these
and the try-lock pair, so it must not become an optional field that an
encoder can silently ignore.

`:mir/dst` is the word memory held before the operation, for all six.

## Evidence

`kbb -M:test`: 23 tests, 185 assertions, 0 failures.

Deleting `:mir/expected` from the `:kernel-cmpxchg-u32` keyset made the
canonical program fail with `MC rejected: non-canonical-selected-instruction`
-- the reason this keyset exists.

## Does not decide

No bytes. The encoders own those, and the kotoba-mir ADR owns which registers
the operands arrive in.
