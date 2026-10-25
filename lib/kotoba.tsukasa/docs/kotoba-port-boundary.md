# kotoba port — measured boundary (JUN-197, 2026-10-21)

amu main `6c474c81` (origin/main worktree — the shared checkout carries another
session's WIP with a stale deps-lock, so all measurements ran from
`~/github/wt/hermes/tsukasa-amu` with the shared `node_modules` symlinked).

## Final state — green

```text
amu check kotoba/tsukasa/ledger_core.kotoba --jvm-free
  → {:ok true, :effects #{}, :admitted? true}
amu test  kotoba/tsukasa/ledger_core.kotoba --jvm-free
  → 18/18 passed, tests=[test-registration test-duplicates test-transitions
     test-retired-terminal test-ledger test-audit]
     targets=[:jvm-kir :js :wasm]
```

The `.cljk` host wrapper, its kbb suite and deps.edn are retired: the guest is
the whole component (registration verdicts + lifecycle + audit).

## The wasm-self-validation bug — bisected and avoided

`amu test` failed with `:error :wasm-self-validation` ("emitted Wasm module
does not validate", kotoba/internal-error) until the trigger was isolated
(m1–m18 probes):

- **`(= <bool-returning-module-fn-call> false)`** in a test body breaks wasm
  codegen — the emitted module fails self-validation before any test runs.
  `(= b true)` with a bool result is fine; **`(not (f …))` is fine on all
  targets** and is what the suite uses now.
- Not keyword-specific: the failure survived a full keyword→string rewrite.
  Keywords are excluded for a separate reason (below).

Minimal repro (check green, `amu test` module-invalid on :js/:wasm):

```kotoba
(defn h [ds :vector-i64] :bool (= (doms ds) 1))
(defn test-h [] (if (and (h [2 2 2]) (= (h [1 1 2]) false)) true false))  ; ← breaks
(defn test-h [] (if (and (h [2 2 2]) (not (h [1 1 2]))) true false))     ; ← 3/3 green
```

Compiler bug worth reporting upstream: an admitted source emits a wasm module
that does not validate.

## Port constraints found by measurement

- **keyword VALUES are refused by the amu test profile**
  (`value-type-outside-profile`) — `check` admits them, `test` does not.
  Reason pins are therefore **string literals** (`"tsukasa/missing-id"`), the
  same text the old `:tsukasa/missing-id` keyword carried.
- params need **type annotations** (`:string :i64 :bool :vector-i64`) when a
  symbol is used at more than one type; unannotated mixed use is refused.
- `cond->` refused (unbound threading symbol); `not=` absent; `not` is fine.
- `string-starts-with?` absent; prefix test is `(= (string-index-of s p) 0)`.
- vector literals are **`:vector-i64` only** (string vectors refused) and
  `vector-at` **traps** on out-of-range — every access is bounds-guarded.
- `vals` / `count` need canonical typed maps / bounded vectors; the map
  accumulator ledger does not port. The ledger is 8 slots of i64 state codes
  (`-1` = absent), domain codes are caller-assigned i64 in 0..7.
- `bit-shift-left` / `i64-or` are not builtins (`i64-shift-left` is) — not
  needed in the final shape; the audit counts over the code range instead.
- `(:export [...])` must name declared public fns exactly; `amu test` runs
  exported zero-arity `test-*` returning true on :jvm-kir :js :wasm.

## Amu selfhost seed constraints (2026-10-22)

Measured with the pinned selfhost root compiler (amu `f5b11a08`,
`seed/HEADS`), which is stricter than the Node-hosted `bin/amu`:

- a `fn` literal may capture only `:i64` locals (E2104 otherwise). The
  `(reduce (fn ..) [] [0 .. 7])` slot rebuilds captured the ledger vector, so
  they are self-recursive defns (`set-slot`, `domains-from`, `largest-from`).
- `fn` parameters are bare symbols; an annotation is E2139. Their types come
  from the context (the accumulator and item types of `reduce`).
- `loop` bindings are i64 / bool / string only, so a vector accumulator
  recurs through a defn, not a `loop`.
- the `ns` form is `(ns NAME (:export [..]))` with no docstring, and an
  exported fn takes only `:i64` and returns `:i64` / `:bool`. The component
  keeps its API; the selfhost gate builds a driver that exports `main` only.
- defns need a declared result type, so the zero-arity `test-*` declare
  `:bool`.

## Parity with the retired .cljk suite (12 tests / 38 assertions)

Same reason literal texts and precedence (id → did → failure-domain →
availability), same lifecycle legality incl. retired-terminal and
typo-is-not-a-policy-hit, same audit fixture numbers ([1 1 2] → 3 nodes /
2 domains / largest 2 / not single; [4 4 4] → single-domain trap; [] → all
zero and NOT single-domain). One deliberate delta: availability and
failure-domain arrive as **strings** (closed set `"always-on"` /
`"intermittent"`), because the test profile refuses keyword values; the
semantic contract is unchanged.
