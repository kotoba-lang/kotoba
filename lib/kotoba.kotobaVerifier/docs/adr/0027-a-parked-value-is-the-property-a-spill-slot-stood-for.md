# ADR-0027: A parked value is the property a spill slot stood for

- Status: accepted
- Date: 2026-09-02

## Context

This repository's `kotoba-native` pin sat at `a2023fed` while kotoba-native's
main advanced **302 commits** past it. Two earlier ADRs recorded why and
neither could get further than "someone else's change":

- ADR 0025: "bumping the `kotoba-native` pin far enough to carry the newer gmir
  imports **22 failures** in `pinned-producer-*`, which pin allocator output
  shapes across an allocator change this stream does not own."
- ADR 0026: "Bumping here would land a red suite for someone else's reason, so
  the pin stays and this paragraph exists instead of silence."

A pin that cannot advance is not a small cost here. This repository does not
merely depend on the backend, it **calls** it: `verify-native-artifact!`
re-emits with the exact producer. A stuck pin means every operation landed
since — the memory widths, the slice family, the atomics, the interrupt entry,
the dot product, the store result — is verified against a backend that does
not have it, or not verified at all.

## What the 22 failures actually were

All 22 were in three tests, and none of them was a value failing to survive a
call. They were assertions about *where* it survived:

```clojure
(is (= 1 (:mc/frame-slots caller)))
(is (= 1 (count (filter #{:x86-64/spill-store} encodings))))
(is (= [{... :mc/encoding :x86-64/spill-store :mir/src :x86-64/r8 :mir/slot 0}]
       stores))
```

kotoba-native `7b25376` ("Encode the wider register pool, and a frame that pays
for it") gave the allocator a **preserved tier** — RBX/R12–R15 on x86-64,
X19–X26 on AArch64 — and a frame that saves exactly the ones a body names. A
value that must outlive a call now goes into a callee-saved register instead of
onto the stack, so these programs spill nothing at all. Measured at
kotoba-native `70984ea`: the fifth argument is parked in `rbx` / `x19`, and
`live` in `(let [live 10] (+ live (inc-one x)))` likewise.

That is strictly better, and it made the literals false. The tests were pinning
one allocator's answer, not the question.

## Decision

The three tests pin the property the literals stood for:

> A value a call cannot be trusted with is **materialised exactly once**, in a
> home the call cannot clobber. A function that makes no call materialises
> nothing.

`materialised-homes` = frame slots + the callee-saved registers
`kotoba.mir/saved-registers` reports for the emitted stream. A slot home still
costs exactly one `spill-store` and one `spill-load`; a register home costs
neither, and the assertion is `(= frame-slots (count spill-stores))` rather
than a literal. `pinned-producer-lazily-spills-only-the-fifth-entry-argument`
is renamed `-parks-only-the-fifth-entry-argument`, because "spills" was the
thing that stopped being true.

The pin advances to kotoba-native `70984ea` (main).

`kotoba.mir` is read from the **transitive** closure the pinned backend brings,
deliberately not as a top-level dependency: the question is which registers
*this* backend's frame saves, not which ones some other pin would.

## Evidence

| measurement | result |
|---|---|
| old tests, pin `a2023fed` | 71 tests / 460 assertions, 0 failures |
| old tests, pin `70984ea` (main) | **22 failures**, all in the three tests |
| new tests, pin `70984ea` | 71 / 464, 0 failures |
| whole suite, pin `70984ea` | 88 tests / 622 assertions, 0 failures; nbb 8 / 91 |

The new property discriminates rather than describing today's allocator —
measured directly at the new pin, on both ISAs:

| program | callee homes | caller homes |
|---|---|---|
| four arguments, tail call | 0 | **0** |
| five arguments, tail call | 0 | **1** |
| a value live across a call | 0 | **1** |
| nothing live across a call | 0 | **0** |

It cannot be run at the old pin at all: `kotoba.mir/saved-registers` does not
exist there, which is itself the shape of the change.

## Consequences

- The pin can move again, so every operation that lands in kotoba-native is
  once more re-emitted by the producer this repository verifies against.
- ADR 0025 and ADR 0026 are amended in place rather than superseded: their
  decisions stand (a literal is verified where it is decoded; the second gate
  is opened here), and only the retired paragraph about the stuck pin is
  marked.
- The top-level `kotoba-gmir` dependency stays. Its first reason — a top-level
  git dependency wins over a transitive one, so the decoder does not depend on
  which gmir the backend pin carries — was never about the pin.
