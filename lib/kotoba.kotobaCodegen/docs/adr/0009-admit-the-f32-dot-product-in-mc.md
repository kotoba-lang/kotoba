# ADR 0009: Admit the f32 dot product in MC

## Decision

MC admits one target-selected `kernel-dot-f32` (kotoba-gmir ADR 0010,
kotoba-mir ADR 0015).

It is the first member of the checked-memory family with **two regions**, so
it is the first whose keyset is not `base length index …`:

```clojure
:kernel-dot-f32 #{:mc/op :mc/encoding :mir/dst :mir/base :mir/length
                  :mir/second-base :mir/second-length :mir/count
                  :mir/maximum}
```

`:mir/base` and `:mir/length` stay the **first** region's names rather than
becoming `:mir/first-base`, so anything reading `:mir/base` for a base still
finds one. `:mir/count` replaces `:mir/index`, and the replacement is not
cosmetic: it names how many elements to fold rather than which one to touch,
and the operation has no single element to name.

`:mir/maximum` bounds **both** lengths, in bytes, while `:mir/count` counts
elements.

The keyset is exact in both directions, and the field that most needs it is
`:mir/second-base`. An encoder handed a four-operand instruction does not
fail — it reads whatever register happens to be in that position, which is a
pointer this layer never checked.

## Evidence

`kbb -M:test`: 25 tests, 256 assertions, 0 failures (was 23 / 185 before
the binary32 encodings and this).

Shortening the keyset to drop `:mir/second-base` and `:mir/second-length` made
the canonical program fail with `MC rejected:
non-canonical-selected-instruction` — the reason this keyset exists.

The register-profile assertions are answered by MIR rather than by MC's own
check, because `mc/validate!` re-validates the underlying MIR program and a
foreign register fails the register profile there first. Either layer refusing
is the answer; what must not happen is an AArch64 register reaching an x86
encoder.

## Does not decide

No bytes, and no target admission. kotoba-native owns the AVX2 and SSE
sequences and their accumulation tree; `kotoba.mir` owns the refusal of this
operation for every target but x86-64.
