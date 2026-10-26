# ADR-0052 — One missing intrinsic holds four of the ten

Date: 2026-08-18

## Status

Accepted as a measurement. The receipt now names the form each native-slice
rejection was about. Nothing is fixed; what changed is that the remaining work
is three asks instead of an adjective.

## Context

ADR-0051 sorted the ten value-runtime failures into three classes and left the
largest one — six objects the `x86_64-aiueos-kernel-v1` slice "does not admit" —
as a sentence. Six objects needing six different things and six objects needing
one thing are the same sentence and completely different amounts of work, and
nothing distinguished them.

The compiler had already said which. `kotoba.compiler.frontend/reject!` carries
the offending form in its `ex-data` under `:form`; the runner was reading only
`ex-message`.

## Decision

**Record the form, not the adjective.** `run-one` now keeps `:rejected-form`,
`:error-code` and `:compiler-phase` from the exception's data. `:span` is
deliberately dropped — a byte offset into a file this receipt does not pin
would churn the diff on every unrelated edit.

Measured, the seven form-carrying failures are **three distinct asks**:

| form the slice refused | objects |
|---|---|
| `kernel-compare-exchange-u32` | **4** |
| `kernel-value-runtime-capability-table` | 2 |
| `(kernel-publish-current-domain domain)` | 1 |

**Four of the ten failures are one missing atomic compare-exchange.** That is a
bounded upstream ask against `kotoba-lang/amu`, not a programme, and it is the
single highest-leverage item in this series so far. The remaining three
failures are the `:per-object-export-symbol` class from ADR-0051 and carry no
form, which is correct — the compiler did not reject them, the contract did.

**A rejection with no named form now fails the ratchet.** "The slice does not
admit this" without saying what is a report nobody can act on, and it is the
exact shape that hid six asks behind one sentence for two iterations.

## Executable evidence

`aiueos.value-runtime-baseline-test`: **9 tests, 68 assertions, 0 failures**
(was 7/59). Full suite **623 tests, 9365 assertions, 19 failures** — the
baseline nineteen. `tcb-check` unchanged. Lint unchanged.

**Both directions, shown**, each mutation asserting the edit applied first: a
form histogram that disagrees with its rows fails
`the-rejected-forms-are-counted-from-the-rows` on both the equality and the
over-count assertion; blanking one row's form fails that test *and*
`a-native-slice-rejection-names-the-form-it-rejected`, which is the pair
working as intended — the derived histogram and the per-row floor catch the
same corruption from two directions.

## What this changes about the next iteration

Before: "six objects need native slice features." After: **one intrinsic
unblocks four objects**, and the other three failures split two ways. The
cheapest real move is now visible and it is upstream, in the compiler, not
here — which is a conclusion this repository can act on by filing it, and could
not have reached by reading its own messages.

## Remaining boundary

- **Still ten failing.** No object compiles; the ratchet reads ten.
- **The asks are not filed.** Nothing in `kotoba-lang/amu` knows about
  `kernel-compare-exchange-u32`; this ADR names it and stops there.
- **The intermittent twentieth suite failure is still unexplained**
  (ADR-0051), and this iteration did not attempt it — capturing it needs the
  full suite in a loop, which is a different shape of measurement than
  anything here.
