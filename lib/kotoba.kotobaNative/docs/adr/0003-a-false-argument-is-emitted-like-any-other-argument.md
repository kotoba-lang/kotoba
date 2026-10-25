# 0003 — a call argument that is the literal `false` is emitted like any other argument

Status: accepted
Date: 2026-08-05
Base: `origin/main` `8e7c0530b18b7c4d9ea3b3b28dc40c989ea03470`

## Context

`kotoba.native.x86-64` had three copies of the same argument walk — one per
call shape — and all three were written as

```clojure
(loop [remaining args depth temp-depth out []]
  (if-let [arg (first remaining)] …))
```

`if-let` tests the **bound value**, not the sequence. A boolean literal is an
ordinary value on this backend (`emit-expr` encodes `true`/`false` as the i64
word 1/0, through the same `le64` path an integer literal uses), so an argument
whose KIR form is `false` made the loop take its else branch — terminating
early. **That argument and every argument after it was never emitted**, while
the surrounding code still built its `pops` sequence from the full `argc`. Each
missing argument is exactly eleven bytes: `movabs rax,imm64` (ten) + `push rax`
(one).

`kotoba.native.aarch64` walks arguments with `mapcat` and has no truthiness
test, so it was never affected. **This was never a `:bool` representation
problem** — both backends carry a `:bool` as an i64 word, and that is correct.
It was a difference in how one loop was written.

## The three sites, and which of them were reachable

| site (at `8e7c053`) | function | reachable from source? |
|---|---|---|
| `x86_64.cljc:189` | `emit-tail-self-call` | only behind the held `:bool`-boundary widening |
| `x86_64.cljc:242` | `emit-call` | only behind the held `:bool`-boundary widening |
| `x86_64.cljc:342` | `emit-heap-call` | **reachable today, on unmodified `main`, with nothing relaxed** |

The third row is the correction this ADR exists to record. The defect was
reported as latent — gated behind a `:bool` **function-boundary** type, which
`kotoba.kir/native-boundary-type?` and `kotoba.verifier/native-boundary-type?`
both still exclude (the widening that admits it is written and green but held
unmerged on kotoba-verifier `agent/verifier-bool-boundary-widening`
`b5a88cd`, `DO NOT MERGE YET`, because of this defect).

But `emit-heap-call` does not take function arguments. It takes the arguments
of a **host context callback**, and `option-some-of` / `result-ok-of` lower to
`(pair 1 payload)` — so a `:bool` payload is a boolean literal in the second of
two host-call argument slots, and it never crosses a function boundary at all.
`kotoba.compiler.frontend`'s `infer-call-type` types the payload of
`(option-some-of [:option :bool] …)` against the declared element type, so

```clojure
(defn main []
  (if (option-value-of [:option :bool] (option-some-of [:option :bool] false) true) 6 7))
```

compiles on unmodified `main` with no redefinition of anything, and produces
**159 bytes where the `true` form produces 170** — one dropped push. Run, it is
a SIGBUS on x86-64 and returns 7 correctly on AArch64. That is a shipping
miscompilation, not a latent one.

That verdict is not inferred from the byte count. It is isolated: with the fix
applied at `emit-tail-self-call` and `emit-call` but **reverted only at
`emit-heap-call`**, exactly the two `option`/`result` rows fail and the other
fourteen pass.

`(pair false 1)` and `(vector-conj v false)`, by contrast, are rejected by the
frontend (`expected i64, got bool`, `:phase :subset`) — `same-expression-type?`
is exact, so `:bool` is not an `:i64`. It is specifically the parametric
`[:option :bool]` / `[:result :bool …]` constructors that carry a boolean into
a host-call argument slot.

## Decision

The three copies become one `emit-pushed-arguments`, whose loop condition is
`(seq remaining)`. Nothing ever depended on the truthiness test to terminate:
KIR has no `nil` argument form, so the empty sequence was always the only
terminating case, and `(seq remaining)` says that.

One function rather than three fixed copies, because three copies of a loop are
what let one mistake be three bugs, and what let two of them be found while the
third was left unverified.

The emitted bytes are unchanged for every program that does not pass a boolean
literal: the whole existing suite passes byte-identically.

## Measurement

kotoba-native's own suite, clean worktree:

| | tests | assertions | failures |
|---|---|---|---|
| baseline, unmodified `origin/main` `8e7c053` | 64 | 2,506 | 0 |
| after this change | 66 | 2,572 | 0 |

The shared ISA execution table in kotoba-lang/compiler
(`test/kotoba/compiler/isa_execution_test.clj`, as committed there at
`36bedf8`, kotoba-native supplied as `:local/root`): **2 tests, 185 assertions,
0 failures** — identical before and after. Both ISAs ran; neither was skipped.

### Real-process execution, both ISAs

Sixteen rows driven through the compiler's own loader harness — `cc -arch
x86_64` under Rosetta 2 and `cc -arch arm64` natively, `tools/kexe_loader.c`,
`KEXE_STRUCTURED_REPORT=1`. Rows A–E need the held boundary widening, relaxed
**in process** with `with-redefs` on `kotoba.verifier/native-boundary-type?`
and `kotoba.kir/native-boundary-type?` for measurement only; nothing in those
repositories was edited, and nothing of the sort exists in landed code. Rows
F–G need nothing relaxed.

Rows A–E each carry a second, non-`:bool` typed parameter (a `:string`). That
is not decoration: `kotoba.kir`'s lowering only carries `:param-types` into KIR
when the HIR is typed (`:kotoba.hir/v3`), and without them the reference
interpreter validates every parameter as `:i64` and traps
`{:trap :value-type-mismatch :expected :i64}` — the interpreter gap
`kotoba.kir/native-boundary-type?`'s own comment describes. The `:string`
parameter is what keeps the row out of that unrelated gap. It also gives the
boxing-order coverage the rows needed anyway.

| row | argument position | `false` | `true` |
|---|---|---|---|
| A | the only argument | 2 | 3 |
| B | first of three | 8 | 5 |
| C | last of three | 8 | 5 |
| D | two booleans, at opposite ends | 223 / 213 / 123 / 113 for the four combinations |
| E | inside a self tail call | 5 | 100 |
| F | `[:option :bool]` payload, host call | 7 | 6 |
| G | `[:result :bool :i64]` payload, host call | 7 | 6 |

Every row's `true` and `false` forms produce **different** results, so a row
cannot pass by returning the same value either way.

- **After this change: 32 / 32 pass** (16 rows × 2 ISAs), every one a real
  process.
- **Before it: all 16 AArch64 executions pass; 10 of the 16 x86-64 executions
  trap.** `emit-call` and `emit-heap-call` rows die with `KEXE_TRAP {:kind
  :signal :signal :SIGBUS}` (loader exit 120); the `emit-tail-self-call` row
  dies as `{:kind :supervisor :reason :unhandled-child-signal}` (exit 123),
  since that site stores the wrong words into live parameter slots and jumps
  back into the body. The six x86-64 rows that pass before the fix are the ones
  whose arguments are all `true`.

### Falsification

The new rows were run against a copy with the fix removed, twice, before being
trusted:

1. Against the pristine pre-fix source: **all nine x86-64 rows of
   `a-false-argument-emits-exactly-what-a-true-argument-emits` fail**, short by
   11, 33, 11, 33, 51, 11, 11, 11 and 11 bytes; **all nine AArch64 rows pass**.
2. Against the fix with `emit-pushed-arguments`'s condition changed back to
   `if-let`: those nine fail again *and* the walk test fails, reporting
   `(not (= 33 0 11 22))` for `[1 2 3]` / `[false 2 3]` / `[1 false 3]` /
   `[1 2 false]` — 0, 11 and 22 bytes for three-argument lists, which is the
   truncation stated directly.

## Consequences

- The `:bool`-boundary widening held on kotoba-verifier
  `agent/verifier-bool-boundary-widening` is unblocked. Landing it is a
  separate change with its own evidence; this one does not touch that
  repository, nor kotoba-kir, nor any capability kit qualification flag —
  nothing here qualifies anything.
- A residual gap this ADR does **not** close: a function whose only typed
  parameter is `:bool` still traps in the reference interpreter at `:phase :ir`
  as an `:i64`, because `:param-types` is not carried into KIR unless the HIR
  is typed. That is in kotoba-kir, it is the gap that namespace's own comment
  already names, and it is why every row here carries a `:string` parameter
  alongside its boolean.
- The byte-count assertions are the load-bearing ones, and are what the new
  tests assert first. A corrupted stack does not reliably fault — a one-slot
  displacement often reads a plausible word and returns a plausible answer — so
  a runtime-only test can pass by luck. Eleven bytes per dropped argument
  cannot.
