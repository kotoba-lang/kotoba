# ADR 0003: A `:bool` parameter at a function boundary is admitted

Status: accepted

Supersedes [ADR 0001](0001-a-bool-parameter-at-a-function-boundary-was-blocked-on-x86-64.md),
which withheld this widening.

## Context

ADR 0001 withheld one guard removal in `kotoba.verifier/native-boundary-type?`
— the `(not= :bool type)` that was the entire exclusion — because opening the
boundary made a latent x86-64 defect **reachable**. `kotoba.native.x86-64`
walked a call's argument list with `(if-let [arg (first remaining)] …)`, and
`if-let` tests the *bound value*, so an argument whose KIR form IS the literal
`false` ended the loop and was never emitted, along with every argument after
it, while the pop sequence still popped the full arity.

That defect is fixed. `kotoba-native`
`f6f29e9ff682d227c9d0556f66fd6b274070a746` (its ADR 0003) collapsed all three
copies of that walk into one `emit-pushed-arguments` keyed on `(seq remaining)`.

ADR 0001's condition for landing was explicit: re-run the 17 rows against the
fixed backend, on both ISAs, as real processes. This ADR is that re-run.

## The 17 rows, re-measured

Measured 2026-08-05 against **`kotoba-native` `f6f29e9`**, `kotoba-kir`
`57cfa2b`, `compiler` `db44180`, with the widened verifier supplied as
`:local/root`. Rows were run from a throwaway `compiler` worktree — **not
committed there** — as real processes through `tools/kexe_loader.c`: x86-64
natively, aarch64 natively, both loaders built and probe-verified on the same
host.

**Neither ISA was skipped.** The harness prints its availability set and
asserts it equals `#{"x86_64" "aarch64"}`, because a skipped ISA reads exactly
like a passing one in the summary line. Observed:
`available: ["aarch64" "x86_64"] / missing (SKIPPED): []`.

Every row is a `true`/`false` pair returning **different** values, so a backend
that dropped the argument, passed a constant, or read the wrong register cannot
pass by luck.

| row | expected | x86-64 | aarch64 |
|---|---|---|---|
| bool parameter as an `if` test, `true` | 4 | **4** | **4** |
| bool parameter as an `if` test, `false` | 0 | **0** | **0** |
| bool parameter before a string parameter, `true` | 4 | **4** | **4** |
| bool parameter before a string parameter, `false` | 99 | **99** | **99** |
| bool parameter through `bool-not`, `true` | 99 | **99** | **99** |
| bool parameter through `bool-not`, `false` | 4 | **4** | **4** |
| bool parameter through `=`, `true` | 4 | **4** | **4** |
| bool parameter through `=`, `false` | 99 | **99** | **99** |
| bool parameter forwarded into another bool parameter, `true` | 10 | **10** | **10** |
| bool parameter forwarded into another bool parameter, `false` | 11 | **11** | **11** |
| two bool parameters, `true false` | 4 | **4** | **4** |
| two bool parameters, `false true` | 5 | **5** | **5** |
| bool parameter with a string result, `true` | 3 | **3** | **3** |
| bool parameter with a string result, `false` | 2 | **2** | **2** |
| bool parameter returned as a bool result, `true` | 7 | **7** | **7** |
| bool parameter returned as a bool result, `false` | 6 | **6** | **6** |
| tail self-call passing a literal `false` | 6 | **6** | **6** |

**17/17 on both ISAs.** 35 assertions (34 rows plus the both-ISAs-present
assertion), 0 failures.

Each row carries a `:string` parameter alongside its boolean. That is
**load-bearing, not decoration**: `kotoba-kir` carries `:param-types` into KIR
only when the HIR is typed, so a function whose *only* typed feature is a
`:bool` parameter loses its table and traps at `:phase :ir` as `:i64`. That is
a kotoba-kir gap (its ADR 0221) and is deliberately not worked around here.

The row sources are reproduced verbatim below, because they are still not
committed to `compiler` — that repo was out of scope, as it was for the three
previous agents to run this table.

```clojure
;; each entry: [name source expected]
["bool parameter as an `if` test, `true`"
 "(defn f [s :string b :bool] (if b (string-byte-length s) 0))
  (defn main [] (f \"abcd\" true))" 4]
["bool parameter as an `if` test, `false`"
 "(defn f [s :string b :bool] (if b (string-byte-length s) 0))
  (defn main [] (f \"abcd\" false))" 0]
["bool parameter before a string parameter, `true`"
 "(defn f [b :bool s :string] (if b (string-byte-length s) 99))
  (defn main [] (f true \"abcd\"))" 4]
["bool parameter before a string parameter, `false`"
 "(defn f [b :bool s :string] (if b (string-byte-length s) 99))
  (defn main [] (f false \"abcd\"))" 99]
["bool parameter through `bool-not`, `true`"
 "(defn f [s :string b :bool] (if (bool-not b) (string-byte-length s) 99))
  (defn main [] (f \"abcd\" true))" 99]
["bool parameter through `bool-not`, `false`"
 "(defn f [s :string b :bool] (if (bool-not b) (string-byte-length s) 99))
  (defn main [] (f \"abcd\" false))" 4]
["bool parameter through `=`, `true`"
 "(defn f [s :string b :bool] (if (= b true) (string-byte-length s) 99))
  (defn main [] (f \"abcd\" true))" 4]
["bool parameter through `=`, `false`"
 "(defn f [s :string b :bool] (if (= b true) (string-byte-length s) 99))
  (defn main [] (f \"abcd\" false))" 99]
["bool parameter forwarded into another bool parameter, `true`"
 "(defn g [s :string b :bool] (if b 10 11))
  (defn f [s :string b :bool] (g s b))
  (defn main [] (f \"abcd\" true))" 10]
["bool parameter forwarded into another bool parameter, `false`"
 "(defn g [s :string b :bool] (if b 10 11))
  (defn f [s :string b :bool] (g s b))
  (defn main [] (f \"abcd\" false))" 11]
["two bool parameters, `true false`"
 "(defn f [s :string a :bool b :bool] (if a (if b 3 4) (if b 5 6)))
  (defn main [] (f \"abcd\" true false))" 4]
["two bool parameters, `false true`"
 "(defn f [s :string a :bool b :bool] (if a (if b 3 4) (if b 5 6)))
  (defn main [] (f \"abcd\" false true))" 5]
["bool parameter with a string result, `true`"
 "(defn f [s :string b :bool] :string (if b \"abc\" \"ab\"))
  (defn main [] (string-byte-length (f \"x\" true)))" 3]
["bool parameter with a string result, `false`"
 "(defn f [s :string b :bool] :string (if b \"abc\" \"ab\"))
  (defn main [] (string-byte-length (f \"x\" false)))" 2]
["bool parameter returned as a bool result, `true`"
 "(defn f [s :string b :bool] :bool b)
  (defn main [] (if (f \"x\" true) 7 6))" 7]
["bool parameter returned as a bool result, `false`"
 "(defn f [s :string b :bool] :bool b)
  (defn main [] (if (f \"x\" false) 7 6))" 6]
["tail self-call passing a literal `false`"
 "(defn f [s :string b :bool] (if b (f s false) 6))
  (defn main [] (f \"abcd\" true))" 6]
```

## Falsification

A green table proves nothing unless the table can go red. Both halves were
falsified in the same session.

**The rows can fail.** The identical 17 rows were re-run with `kotoba-native`
pinned back to `8e7c053` — the pre-fix commit, and the pin `compiler` still
carries — with everything else unchanged. Result: **10 failures, all on x86-64,
all traps** (`{:status :trap :exit 120}`, a hardware signal via the loader, not
a Kotoba trap), on exactly the ten rows whose bool argument is written as the
literal `false`. aarch64 was correct on all 17. That reproduces ADR 0001's
table row for row — 9 SIGILL plus the SIGSEGV on the tail self-call — so the
rows detect the defect they were written for.

**The verifier change is what admits them.** With the predicate reverted to
`main`'s (`a64956a`, guard present) and the fixed backend left in place, every
row is refused before it can execute: `runtime KIR function shape rejected
{:function f, :phase :verify}`, on **both** targets. The rows are therefore
gated by this repo's change, not merely coincident with it.

**The unit gate can fail.** Restoring `(not= :bool type)` in the widened tree
turns 8 assertions red, and only those 8: the seven bare-`:bool` parameter rows
plus the kotoba-kir agreement flip.

That count is worth stating precisely, because it corrects an impression the
test could otherwise leave. The wrapped rows (`[:option :bool]`,
`[:result :bool :i64]`, `[:result :i64 :bool]`) and the record-field row **do
not move** — they reach admission by recursion through
`native-word-value-type?` and passed before the change too. They are
documentation, not gates, and the test comment now says so. The negative half
(`:f64`, `:f32`, `:bytes`, `:vector-i64`, `:map`, a malformed table) also does
not move, which is the point: widening one type must not widen the set.

## Decision

`kotoba.verifier/native-boundary-type?` drops its `(not= :bool type)` guard. A
bare `:bool` is admitted as a parameter type, and this verifier now agrees with
`kotoba.kir`'s independently derived boundary set on every type.

The gate that pinned the *divergence* is flipped to pin the *agreement*
(`the-native-boundary-set-agrees-with-kotoba-kirs`). It still fails if either
side moves in either direction.

`deps.edn` advances `kotoba-native` `470fd94` -> `f6f29e9` (a fast-forward).
This is not housekeeping. This repo does not merely depend on that backend, it
**calls** it — `native-targets` holds `x86-64/emit-program` — so admitting a
`:bool` parameter while pinned to a backend that miscompiles one would put the
defect inside this repo's own closure.

## Murakumo sweep, re-measured

All 33 shipped `kotoba/*_core.kotoba`, compiled for both native targets, **no
`with-redefs` anywhere**, same script for both columns:

| | x86-64 | aarch64 |
|---|---|---|
| verifier `a64956a` (guard present) | 24/33 | 24/33 |
| this change | **30/33** | **30/33** |

Both measured against **`kotoba-native` `f6f29e9`**, `kotoba-kir` `57cfa2b`,
`compiler` `db44180`. The two ISAs admit the *same set*, not merely the same
count — checked explicitly, since equal totals could hide a divergence.

The six unblocked are exactly the six ADR 0001 predicted: `connect_core`,
`dash_state_core`, `infer_waste_core`, `overlay_stream_core`,
`reconcile_plan_core`, `report_core`. All six failed at `:phase :verify` with
`runtime KIR function shape rejected` and now compile.

The three remaining failures are identical on both ISAs and share one reason
class, which is neither `:bool` nor this verifier:

| module | reason |
|---|---|
| `infer_plan_core` | `record-get is only supported directly over a matching record-new construction on the native backend` |
| `infer_schedule_core` | same |
| `task_plan_core` | same |

That is a `kotoba-native` backend limitation, surfaced at `:phase :x86-64` /
`:phase :aarch64`. It is out of scope here and is left open, named.

**These figures are not comparable to ADR 0001's 14/33 -> 19/33.** That
baseline was a different `kotoba-native`, and other agents have landed record
and string work since. A bare `N/33` carries no meaning without the backend SHA
beside it — a same-day 14/33 versus 16/33 discrepancy in this effort turned out
to be exactly that. Quote the SHA or do not quote the number.

Note also what the sweep does and does not say: it is a **compile** figure.
These modules are entryless libraries with no `main`, so they are not executed
by the sweep. Execution evidence for the widened boundary is the 17-row table
above, not this one.

## Consequences

- Tests: **16 tests / 101 assertions** on `a64956a` -> **18 tests / 123
  assertions** here, 0 failures at both ends.
- **No capability qualification flag is touched.** This qualifies no
  capability; `:native-aot` / `:wasm-aot` / `:jit` are untouched.
- **Golden digests did not move.** Verified, not assumed: the single
  conformance vector in `resources/conformance/dual-surface-v1.edn`
  (`:scalar-capability-call`, 1 case) hashes to
  `3c08f7ce6d50ca2cce27a0c583d9428d3cac1e93d3def8a41b3f94a9c758a304` under both
  the baseline and the widened predicate, and the file itself is untouched.
  This is expected — an admission predicate decides accept/reject and never
  rewrites the program that `:kir-sha256` digests — but it was measured rather
  than argued.
- The held branch `agent/verifier-bool-boundary-widening` was brought forward by
  **cherry-pick onto current `origin/main`**, not by rebase. Its commit
  `b5a88cd` is unmodified upstream; no history was rewritten anywhere.
- **Left open, named**: (1) the three `record-get`-over-`record-new` modules
  above, a `kotoba-native` limitation; (2) the untyped-encoding gap from
  kotoba-kir ADR 0221 — a module whose only typed feature is a `:bool`
  parameter is emitted as `:kotoba.hir/v2` and loses `:param-types` — which is
  why every row carries a `:string` parameter, and which is still that repo's;
  (3) the 17 ISA rows are still **not committed** to `compiler`, reproduced
  verbatim above instead, as they were by the three previous agents to run them;
  (4) this repo has no loader of its own, so nothing here executes native code —
  the execution proof necessarily lives in a throwaway `compiler` worktree and
  is not re-run by `kbb -M:test`.
