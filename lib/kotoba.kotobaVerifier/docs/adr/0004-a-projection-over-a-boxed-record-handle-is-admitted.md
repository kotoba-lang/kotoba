# 0004 — A projection over a boxed record handle is admitted

Status: accepted
Date: 2026-08-06
Base: `origin/main` `6433a81bd23b5328e3da3cfb22be0187dfc41d06`

## Context

A record that crosses a function boundary is boxed into a one-word pair chain
(kotoba-native ADR 0062). Reading a field back off that word is one chain walk,
and the backends do not care which route the word arrived by: straight off the
call, as a parameter, or named by a `let` first. This file did care, in two
independent places, and neither distinction had a reason behind it.

**1. A `let`-bound handle.** `verify-bindings!` remembered a binding's schema
only when its value was a directly-nested `record-new`, so

```clojure
(let [ends (partition-3-ends x)
      hi0  (record-get … ends :hi0)] …)
```

bound `ends` to `nil`, `record-schema-of` returned `nil`, and the projection was
refused with "runtime KIR record projection rejected". This is how murakumo's
`infer_plan_core`, `infer_schedule_core` and `task_plan_core` read a multi-field
result, and it was the last shape in the 33 shipped cores with no native path.

kotoba-native ADR 0001 implemented the backend half of this, measured it green on
both ISAs, and **reverted it** — with only the backend widened, those cores moved
their failure from the backend into this file, so no ISA execution row could run
and the change would have shipped a path nothing could reach. It recorded the
two lines and named this repo as the blocker. This is the other half.

**2. A result declared by SCHEMA REFERENCE.** `record-schema-of` resolved a
call's declared result and then required `native-scalar-record-type?`. A
`[:ref :t/r]` is not one, so it returned `nil` and `(record-get … (mk) :b)` was
refused — while the identical program with `mk`'s result written inline was
admitted. `lower` leaves a reference unexpanded in a SIGNATURE on purpose
(expanding it moved the `:kir-sha256` of every module using one, on every target
including its Wasm bytes, and was reverted), so the reference is the spelling the
murakumo cores actually carry. The backends never distinguished the two — pinned
by kotoba-native's `a-result-declared-by-schema-reference-boxes-identically` —
only this resolver did.

The two turned out to be the same blocker in practice: the cores' let-bound
values are calls whose results are declared by reference
(`apply-pick-3 → [:ref :schedule/triple]`), so closing either alone closed
nothing.

## Decision

1. **`call-record-schema`** resolves a call's declared result in EITHER spelling,
   and returns a reference **as the reference** rather than expanding it. The
   verified `program` is `select-keys`-ed to the exact set `:kir-sha256` digests
   and carries no schema table; widening that set would move the digest of every
   module using a schema reference. `record-schema-of`'s call case now uses it.

2. **`binding-record-schema`** — a `let` binding remembers a `record-new`'s
   schema (as before) **or** a call's, via `call-record-schema`.

Admitting a reference is **not** taking the record on trust. `record-get`'s
existing identity check requires the projected `type` to be a well-formed
`native-scalar-record-type?` whose own NAME equals the reference — the same
by-name discipline a record PARAMETER declared by reference has always been held
to. Projecting schema A through a value declared as a reference to B is still
rejected, and that is the property that matters.

### Deliberately not widened to `record-schema-of`

`binding-record-schema` is not the general resolver, which also resolves a bare
SYMBOL. Using it would admit

```clojure
(let [r (record-new …) r2 r] (record-get … r2 :b))
```

and a flattened `let`-bound record is N SLOTS, not a word — rebinding it reads N
words as one, which both backends refuse. This gate must be exactly as wide as
the emitter it re-derives, not merely "also narrow". kotoba-native ADR 0004
declines the same shape for the same reason.

## Evidence

Suite: **18 tests, 123 assertions** on unmodified `origin/main` (clean worktree,
0 failures, 0 errors — no pre-existing failures to separate out) →
**25 tests, 142 assertions**, 0 failures, 0 errors.

### Falsified, each half separately

Reverting one half at a time, with the tests kept:

| reverted | failures | which rows |
|---|---|---|
| the `let`-binding half only | **6** | `a-let-bound-boxed-handle-may-be-projected` (4), `a-handle-projected-twice-at-different-depths-is-admitted` (2) |
| the `[:ref …]` result half only | **5** | `…-may-be-projected` (2), `a-handle-projected-straight-off-the-call-may-be-declared-by-reference` (2), `…-twice-at-different-depths` (1) |

Neither half is redundant, and neither row set passes without its change.

**Stated honestly:** the four negative tests
(`projecting-the-wrong-schema-through-a-handle-is-still-rejected`,
`a-let-bound-non-record-is-still-not-projectable`,
`a-flattened-record-forwarded-through-a-second-binding-is-still-rejected`,
`an-undeclared-field-is-still-rejected-through-a-handle`) pass BEFORE the change
as well as after. They are regression guards on the widening, not proof of it,
and they are not counted above. They matter because the widening is exactly the
kind that could have relaxed them by accident — but a guard that was already
true is not evidence that anything was fixed, and this effort has already had
one agent mistake the two.

Every rejection is asserted by MESSAGE, not by a boolean, so a row cannot go
green because some other check refused the input first — the specific false-green
this area has produced before.

### Execution — real processes, both ISAs

This gate is admission only; what justifies it is execution, and this repo has no
loader. Six rows were added to the shared ISA execution table in
kotoba-lang/compiler (`test/kotoba/compiler/isa_execution_test.clj`, driven by
`tools/kexe_loader.c`) and run against this branch and kotoba-native `f35a8ee`
as `:local/root`s. They are **not committed there** — the compiler was out of
scope and another agent was active in it. Reproduced verbatim in kotoba-native
ADR 0004.

- **209 assertions, 0 failures, 0 errors**, three consecutive runs, on BOTH ISAs.
- **Neither ISA was skipped**: the runner's `loaders` map was resolved directly
  and both entries were real binaries; no "skipping ISAs" line was printed.
  x86-64 runs under Rosetta 2 on this Apple-silicon host.
- Baseline (both repos at `origin/main`, same table): 185 assertions, 0 failures,
  three consecutive runs. 209 − 185 = 24 = 6 rows × 2 assertions × 2 ISAs.
- **Falsified**: with both repos at `origin/main`, the first new row throws in
  the backend after 95 assertions of pre-existing rows pass.

Rows select DIFFERENT fields on purpose (4 vs 9) and one SUBTRACTS two depths,
because a chain walked to the wrong depth still returns a plausible i64 and a
row that always read the first field passes even when the walk is wrong.

### Sweep

murakumo's 33 shipped `kotoba/*_core.kotoba`, through kotoba-lang/compiler
`db44180`, everything pinned by git SHA — no `:local/root`, no `with-redefs`:

| target | before | after |
|---|---|---|
| `:x86_64-kotoba-v1` | 30 / 33 | **33 / 33** |
| `:aarch64-kotoba-v1` | 30 / 33 | **33 / 33** |

Measured separately per ISA, not asserted from one.

## The `kotoba-native` pin moves in this commit

`deps.edn` advances kotoba-native `f6f29e9` → `f35a8ee` (ADR 0004, fast-forward,
6 ahead / 0 behind, confirmed server-side). This repo CALLS the backend —
`native-targets` holds `x86-64/emit-program` — so admitting a projection while
pinned to a backend that still throws on it would put the disagreement inside
this repo's own closure. Same reasoning as ADR 0003's pin advance.

## What was deliberately NOT done

- **No capability kit qualification flag.** No `:native-aot` / `:wasm-aot` /
  `:jit` changed anywhere; every kit stays `:native-aot :pending`. This qualifies
  no capability.
- **No KIR signature reshaped, no digested key set widened.** A reference is
  admitted by NAME. Ref-expanding in `lower` was tried elsewhere, moved every
  affected module's digest on every target including its Wasm bytes, and was
  reverted; that approach is preserved here deliberately.
- **Nothing committed in the compiler, kotoba-kir, kotoba-wasm, artifact or
  murakumo.**

## Residual gap

A `[:ref …]` result in an **entry-bearing** module still cannot be
oracle-evaluated: `verify-runtime!` hands `kotoba.kir` the `select-keys`-ed
program, which excludes `:schemas`, so `native-boundary-type?` traps
`unknown-schema-reference` on a reference in a signature. murakumo's cores are
entryless libraries and never reach that path, so no core is blocked — but it is
why the shared ISA table carries no by-reference row: such a program cannot be
built there at all. It is kotoba-kir's, and closing it means widening the
digested key set.
