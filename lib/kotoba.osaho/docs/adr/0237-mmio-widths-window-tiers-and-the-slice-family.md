# ADR 0237: MMIO widths, window tiers, and the ADR 0285 slice family

## Status

Accepted.

## Decision

`kernel-memory-profile` becomes four widths by four window tiers by
load/store — thirty-two entries where there were seven — and a second profile,
`slice-memory-profile`, carries the element-indexed bulk carrier amu ADR 0285
decided on.

### The byte-indexed window family

`kernel-{load,store}-u{8,16,32,64}` with tiers `""`, `-4k`, `-16k`, `-64k`
(512 / 4096 / 16384 / 65536 bytes).

Nothing was decided by adding twenty-five names. What was decided is that a
**width and a tier are two independent axes**, which the seven entries did not
say:

- `kernel-load-u8` reached 16384; `kernel-store-u8` reached only 4096, because
  its own validation clause said so.
- the u32 pair reached neither: they were pinned to 512.
- there was no 16-bit access at all, which is what a PCI vendor/device ID pair
  and most legacy device registers are.
- there was no 64-bit access, which is what a descriptor ring pointer is.

65536 is admitted because `cmp r64, imm32` costs the same bytes at 65536 as at
512. The tier exists because the encoding is identical, not because a caller
asked for it.

### The checks, in the order the backends emit them

For a window access of width `w`:

1. `length > maximum` → `:length-above-profile-maximum`
2. `base == 0` → `:null-base`
3. `index >= length` (unsigned) → `:index-outside-window`
4. `length - index < w` → `:{two,four,eight}-byte-access-outside-window`
   (width 1 skips 3's sibling entirely and uses only 3)
5. `index mod w != 0` → `:misaligned-access`

**The reason literal names the width.** `:four-byte-access-outside-window` is
exactly what it was for every u32 access; widening the family must not silently
move a pinned reason under the two tests that assert it.

**Check 5 is last, deliberately.** A program that was trapping on the window
before still traps on the window. An index that is both misaligned and past the
tail reports the tail.

**Check 5 does not apply to four operations**: `kernel-load-u32`,
`kernel-store-u32`, `kernel-try-lock-u32`, `kernel-unlock-u32`. They predate the
rule, and retrofitting it would change the bytes of shipped aiueos objects.
A caller that was misaligned was already broken in a way this change is not the
place to discover. The asymmetry is named in `unaligned-window-operations` and
pinned by a test, so a later change that closes it says so out loud rather than
happening quietly.

Alignment is checked at all because a misaligned MMIO access is architecturally
undefined on AArch64 device memory and splits the bus lock on x86. The machine's
answer to one is not a value; making it a Kotoba trap is the only answer that is.

### The element-indexed slice family

`slice-{load,store}-u{8,16,32,64}`, ceiling `slice-item-limit` = 2^40 elements.

Three checks, not five, and that is the point of the carrier:

1. `length > slice-item-limit` → `:length-above-slice-limit`
2. `base == 0` → `:null-base`
3. `base mod w != 0` → `:misaligned-slice-base`
4. `index >= length` (unsigned) → `:index-outside-slice`

`index` and `length` count **elements**, so the tail check the window family
needs (`length - index >= w`) is structurally unnecessary: `index < length`
already says the whole element is inside. Alignment is proved **once on the
base** rather than per access, because a scaled index off an aligned base is
aligned. What is left per element is one unsigned compare and one scaled load.

`slice-item-limit` is an **address-space** bound, chosen so `length * 8` cannot
wrap a 64-bit address computation. It is deliberately not derived from
`vector-item-limit` (16384): ADR 0285's decision is that the bulk carrier does
not travel through the vector arena, so that arena's item bound is not its
ceiling. A million-element slice is admitted here where a vector is not.

## What this is NOT

**This is not the `[:slice T]` value.** ADR 0285 asks for a two-word (base,
length) carrier the guest binds with a `let`, passes to a function and narrows
with `slice-sub`. What lands here is the machine layer that carrier lowers to:
the operations take `base`, `length` and `index` as three separate i64 operands,
which is what the backends can express today.

The single-value surface needs a two-word value in GMIR/MIR — `pilot-expression?`
knows exactly one shape, `:scalar`, and `kotoba.native.x86-64`'s fallback path
keeps every value in one accumulator. That is a register-allocator change, not
a machine-code change, and it is deliberately not attempted here: an admission
gate that admits what nothing can lower is the defect amu ADR 0284 named.

`[:slice T]` is therefore **not** added to `native-word-value-type?` or to
`only-native-word-typed-features?`. Nothing produces a slice value, so nothing
admits one. The operations reach the native gate the way every other kernel
operation does: as plain i64 operations through the `:else` arm.

## Consequences

- The eval dispatch and `lower`'s kernel-native set are now **derived** from the
  two profile maps (`checked-memory-operations`) rather than spelled out a third
  and fourth time. Writing the members by hand is exactly how a new operation
  reaches an interpreter with no case for it — or, worse, misses `lower`'s set
  and gets constant-oracled at compile time.
- `word-byte` is not used for the new stores. ClojureScript's
  `bit-shift-left` is **thirty-two bit**: `(bit-shift-left 1 56)` is 16777216
  there, not 2^56. `word-byte` has that shape and was correct only because
  nothing had ever asked it for a byte above the fourth. u64 asks.
  `word-byte-at` and `word-load` use repeated multiply/divide by 256 instead.
- This is measured, not supposed: restoring the old shape in the `:cljs` branch
  alone makes the nbb suite write `[2 1 0 0 2 1 0 0]` where `[2 1 0 0 0 0 0 0]`
  is expected — byte 4 aliasing byte 0 because the shift wrapped — while the
  JVM suite stays green.

## Evidence

`kbb -M:test` — 205 tests, 831 assertions, 0 failures.
`kbb --backend sci run-tests.cljk` — 57 tests, 153 assertions, 0 failures.

Deliberate breaks, each red for its own reason and then restored:

| break | red for |
|---|---|
| the alignment check made unreachable | `:misaligned-access` missing, 4 failures |
| the slice index not scaled by width | `[0 4 3 2 1 0 0 0]` where `[0 0 0 0 4 3 2 1]` is expected |
| `slice-item-limit` set to 16384 | the million-element slice refused |
| `word-byte-at`'s `:cljs` branch back to a 32-bit shift | nbb only: byte 4 aliases byte 0 |

## Upstream

Follows kotoba-gmir `cb935ce`, kotoba-mir `37345aa` and kotoba-codegen
`c024b11`, which carry the same two families through the IR and MC contracts.
kotoba-sema and kotoba-native follow.
