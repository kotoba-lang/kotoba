# ADR 0026: Open the second gate for the extended state enable

## Status

Accepted.

## Decision

Admit `kernel-read-cr4` (arity 0), `kernel-write-cr4` (1) and `kernel-xsetbv`
(2) at all four places this file states a privileged operation:

1. the membership set in `verify-expr!` — otherwise they fall to the terminal
   `:else` with `"runtime KIR operation rejected"`;
2. the **independently re-derived** arity map beside it;
3. `kernel-native-operations`, which decides whether the oracle re-executes an
   entry;
4. the set that requires the aiueos kernel target, so no other target can name
   them.

## Why all four, when three would compile

ADR 0023 recorded that `kernel-xgetbv` had been landed in kotoba-gmir,
kotoba-kir, kotoba-sema and kotoba-native and **not here**, and that nothing
found it until a `.kotoba` program called it. The write half of the same feature
check arriving late for the same reason would be a pattern rather than an
accident, so it is opened here in the same change.

Each of the four is a different failure:

- missing from (1): every call is refused with a message that names nothing;
- wrong in (2): a wrong arity **does not crash**. A one-argument
  `kernel-xsetbv` takes the VALUE as the XCR index and writes EDX:EAX from
  whatever the register happened to hold — into the register that governs
  whether the machine saves its vector state across a context switch;
- missing from (3): the disagreement with `kotoba.kir/lower` surfaces in
  neither side's terms. The compiler correctly seals no value, this side
  re-executes the entry, gets `:kernel-privileged-unavailable`, and refuses the
  artifact as an oracle mismatch it never had;
- missing from (4): a non-aiueos target could name x86 machine state.

## The arity map is re-derived, not imported

That is the whole point of this table, and `kernel-xsetbv` is the clearest case
it has: `2` here is arrived at independently of kotoba-sema's `2`. If the two
ever disagree, the negative rows in the test say so in this repository's own
words.

## There is no `kernel-write-cr2`

CR2 is written by the CPU when a page fault is taken. The test asserts that
`(kernel-write-cr2 p0)` is refused with `"runtime KIR operation rejected"` —
the terminal `:else` — rather than leaving the absence implicit.

## The kotoba-native pin was NOT bumped, and that is measured

This repository's `deps.edn` comment says a pin that refuses what the verifier
admits "would put the disagreement inside this repo's own closure", so bumping
to kotoba-native `da3593b5` (which carries the encodings) was attempted.

It imports **22 failing assertions in two tests** —
`pinned-producer-lazily-spills-only-the-fifth-entry-argument` and
`pinned-producer-materializes-only-the-live-across-call-value` — that have
nothing to do with these operators. Measured three ways:

| kotoba-native pin | result |
|---|---|
| `a2023fed` (this repo's pin, kept) | 68 tests / 440 assertions, **0 failures** |
| `24f43e2` (kotoba-native main *before* the xsave change) | 22 failures, same two tests |
| `da3593b5` (kotoba-native main *with* it) | 22 failures, same two tests |

The middle row is the answer: the failures are a register-allocator change
already on kotoba-native main, not this one. They belong to whoever made that
change. Bumping here would land a red suite for someone else's reason, so the
pin stays and this paragraph exists instead of silence.

*(Amended 2026-09-02, ADR 0027. The pin was bumped, to kotoba-native main.
"Someone else's reason" turned out to be kotoba-native `7b25376`, which gave
the allocator a callee-saved tier: those two tests pinned SPILL SLOTS as
literals and the programs now park in registers instead. They pin the property
those literals stood for and the suite is green at main.)*

**What the stale pin does and does not cost.** It is inert for the compiler:
amu pins kotoba-native itself, and tools.deps resolves one version per
classpath, so `verify-native-artifact!` re-emits with amu's newer backend. It
costs exactly one thing — this repository cannot, on its own classpath, verify
an artifact that uses these operators. Nothing here tries to.

## Evidence

`kotoba.verifier-test/the-extended-state-enable-is-admitted-at-its-three-arities`
— five positive rows (including literal operands, the shape a real enable has),
six negative rows pinning
`"runtime KIR kernel privileged operation arity rejected"`, three
oracle-suppression assertions, and the CR2 negative.

Shown to discriminate twice, with different messages:

| break | failure |
|---|---|
| remove the three from the membership set | `"runtime KIR operation rejected"` — the terminal `:else`, which is exactly the shape ADR 0023 describes |
| change `kernel-xsetbv` arity to 1 | the two-argument positives fail with the arity message, and the one-argument negative stops being negative (`nil`) |

Restored: 68 tests / 440 assertions, 0 failures.

Nothing here executes.
