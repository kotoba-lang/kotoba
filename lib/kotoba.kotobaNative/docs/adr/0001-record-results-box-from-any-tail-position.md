# 0001 — A record result is boxed from any tail position, and from a result declared by schema reference

Status: accepted
Date: 2026-08-05
Base: `origin/main` `78f3111b9067ace491eac540842581caebc95d7f`

## Context

ADR 0062 (kotoba-lang/compiler) gave the native backends a record with **no
runtime representation**. A `let`-bound record flattens into one stack slot per
field. A record that has to CROSS a function boundary cannot flatten — a record
is N slots and the ABI has one word — so it is boxed into a `pair` chain,
`pair(f0, pair(f1, … pair(fN-1, 0)))`. kotoba-native `9b33db5` extended the same
chain to record PARAMETERS. No new representation, no new primitive, no ABI
change, no loader change; both directions are source rewrites into forms the
backends already emit.

Boxing a record RESULT, however, required two things at once that nothing
guarantees about a real module:

1. the `record-new` had to be the **outermost form of the body**, and
2. the declared result had to be the **expanded `[:record …]` spelling**.

Neither is how murakumo's cores are written. A schema reference survives into a
KIR **signature** unexpanded on purpose — expanding it in `lower` moved the
`:kir-sha256` of every module that used one, on every target including its Wasm
bytes, which is why the compiler reverted that attempt — so `[:ref :t/r]` is the
spelling the cores actually carry, while `record-new`/`record-get` **expressions**
always carry the expanded `[:record …]`. And a body is normally
`(let [...] (if guard (record-new …) (let [...] (record-new …))))`.

## Measurement (before)

Sweep of murakumo's 33 shipped `kotoba/*_core.kotoba` against `origin/main`
`78f3111`, compiled through kotoba-lang/compiler `origin/main` `36bedf8` with
kotoba-native supplied as a `:local/root`:

| target | pass |
|---|---|
| `:x86_64-kotoba-v1` | **14 / 33** |
| `:aarch64-kotoba-v1` | **14 / 33** (same 19, same reasons) |

Failure classes, before:

- **16** — the typed-feature admission gate (`kotoba.kir/only-native-word-typed-features?`).
- **3** — `record-new is only supported as the direct operand of a matching record-get on the native backend`:
  `infer_credits_core`, `infer_plan_core`, `infer_rebalance_core`.

kotoba-native suite on unmodified `origin/main`, measured in a clean detached
worktree: **49 tests, 2,152 assertions, 0 failures, 0 errors** — no pre-existing
failures to separate out.

## Decision

Both backends (`kotoba.native.x86-64`, `kotoba.native.aarch64`), identically:

1. **`record-result-name`** reads the declared result in either spelling —
   `[:record :t/r [...]]` or `[:ref :t/r]` — and yields the record's NAME.
2. **`box-record-tails`** boxes a `record-new` that is in TAIL position of a
   function declared to return that record. Tail position propagates into both
   branches of an `if`, into the body (never a binding's value) of a `let`, and
   into the last subexpression of a `do` — exactly the positions `emit-expr`
   hands its own `:tail?` down to, so the rewrite and the codegen agree about
   where a function's value is produced.

The construction's own name must equal the declared result's, because a
`[:ref :t/r]` result carries no field list to compare against and the name is
the only local evidence that this is the record the signature promised. A
mismatch is left unrewritten and fails loudly rather than being boxed into a
shape the caller will walk with the wrong field count.

Boxing still uses `boxed-record-chain` — the same ADR 0062 pair chain. Nothing
new is encoded: the only thing added is REACHING the construction.

## Measurement (after)

| target | before | after |
|---|---|---|
| `:x86_64-kotoba-v1` | 14 / 33 | **16 / 33** |
| `:aarch64-kotoba-v1` | 14 / 33 | **16 / 33** |

Both ISAs move together and fail on the identical set — measured separately, not
asserted from one.

Newly compiling to real machine code:

- `infer_credits_core` — 3,337 code bytes, 21 exports
- `infer_rebalance_core` — 18,671 code bytes, 44 exports

kotoba-native suite after: **53 tests, 2,218 assertions, 0 failures, 0 errors**
(+4 tests, +66 assertions).

## What was deliberately NOT done

### 0. Nothing in kotoba-kir, kotoba-verifier or the compiler

This change is confined to `kotoba-native`. Two of the residual gaps below sit
in those repos; both were measured and reported rather than reached into.

### 1. A projection over a `let`-bound boxed handle — reverted, not shipped

`infer_plan_core` is the third of the three, and it needs a DIFFERENT shape:

```clojure
(let [ends (partition-3-ends x)          ; a call whose result is a record
      hi0  (record-get … ends :hi0)      ; projected through the NAME
      hi1  (record-get … ends :hi1)] …)
```

`env` binds a parameter to its bare index and a `let` slot to `{:let-depth d}`,
and only the flattened record binding is `{:record-fields …}` — so admitting
this is one predicate: `(not (:record-fields (get env value-form)))` in place of
`(not (map? (get env value-form)))`, in `emit-record-get-of-new` on both
backends. That was implemented, tested green on both ISAs, and then **reverted**.

`kotoba.verifier` independently requires a projection's operand to be a
directly-nested `record-new` or a parameter, and rejects this shape with
`{:operation record-get, :phase :verify}` — "runtime KIR record projection
rejected" (`verifier.cljc:513`). Measured: with the backend widened,
`infer_plan_core` stopped failing in the backend and started failing in the
verifier instead, and the shared ISA execution table could not run a single row
of it, because `compile-source` never reaches emission.

Widening `kotoba-verifier` was out of scope for this change. Shipping the
backend half alone would have added a code path that no program can reach and
that nothing has ever executed — which is exactly the claim this repo's
execution table exists to refuse. The two lines are recorded here so the
follow-up is a two-repo change, not a rediscovery.

### 2. No capability kit descriptor was touched

No `:native-aot` / `:wasm-aot` / `:jit` qualification flag was changed anywhere.
Those mean end-to-end real-provider semantics; nothing here earns one.

### 3. No new value representation

No new primitive, no ABI change, no loader change, no Rust. `pair` /
`pair-first` / `pair-second` are the arena contract ADR 0062 already
established.

### 4. `option-match` / `result-match` / `variant-match` branch tails

`box-record-tails` follows `if`, `let` and `do` only. The match forms desugar
into `let`/`if` INSIDE `emit-expr`, after this rewrite has run, so a `record-new`
in a match branch's tail is still refused. No murakumo core needs it (none of
the 33 uses a match form around a record construction), so admitting it would
have been an untested path.

## Evidence

- **Execution, both ISAs, real processes.** The shared ISA execution table is in
  kotoba-lang/compiler (`test/kotoba/compiler/isa_execution_test.clj`), not in
  this repo — this repo has no loader (`tools/kexe_loader.c` belongs to the
  compiler) and its own tests are emission-level, as `isa_parity_test.clj`
  states ("Kernel targets are linkable ELF objects rather than runnable
  processes, so there is no execute-and-observe available here"). The new
  placements were executed there against this branch supplied as a
  `:local/root`, and are NOT committed there, because the compiler repo was out
  of scope for this change. The rows are reproduced in `Reproducing` below.

  - With this change: **205 assertions, 0 failures, 0 errors**, on BOTH ISAs —
    no ISA was skipped, so both loaders were built and both ran (x86-64 under
    Rosetta 2 on this Apple-silicon host). 205 = the table's previous 185 plus
    5 new rows × 2 assertions × 2 ISAs.
  - Against unmodified `origin/main` `78f3111`, same table: the first new row
    throws `record-new is only supported as the direct operand of a matching
    record-get on the native backend` (`x86_64.cljc` `emit-expr`, reached
    through `emit-let`) after 47 assertions of pre-existing rows pass. The rows
    fail without the change and pass with it — they are not decoration.
- **Emission, both ISAs, committed here.** `isa_parity_test.clj` gains four
  tests. Each placement is asserted to emit **exactly the same bytes** as the
  body whose construction was already written out as the pair chain — not merely
  "it emits" — which is what makes this a rewrite into a shape both backends
  already executed rather than a new encoding that happens to compile. Rows
  select `:a` and `:b` on purpose: a chain walked to the wrong depth still
  returns a plausible i64, and `:a` is the one field a broken walk gets right by
  accident.
- Negative tests pin that boxing reaches tail positions ONLY (an arithmetic
  operand and a bare record binding are still refused) and that a `record-new`
  whose name disagrees with the declared result is still refused.

## Residual gaps, by name

| gap | state | detail |
|---|---|---|
| `infer_plan_core` | blocked on kotoba-verifier | Needs `record-get` over a `let`-bound boxed handle. The backend predicate is one line per ISA (above); `kotoba.verifier`'s `record-get` case must admit the same shape first. |
| projecting a call result declared by schema reference | blocked on kotoba-verifier | `(record-get (mk) :b)` where `mk`'s result is `[:ref :t/r]` is rejected: `record-schema-of` (`verifier.cljc:321`) resolves a call's result and then requires `native-scalar-record-type?`, which a `[:ref …]` is not, so it returns `nil` and the projection is refused. Measured directly — the KIR is well-formed and expanded (`(record-get [:record :t/r [[:a :i64] [:b :i64]]] (mk) :b)`), and the identical program with `mk`'s result written inline compiles and runs. The backends do not distinguish the two spellings (pinned by `a-result-declared-by-schema-reference-boxes-identically`); the verifier does. No murakumo core hits this today — the cores that declare a record result by reference either pass it on as an argument or project it through a parameter. |
| `:bool` PARAMETER | blocked on kotoba-kir | `native-boundary-type?` excludes `:bool` outright (`kir.cljc:244`), because `kotoba.kir/execute` validates a `:bool` argument as an i64 word. 8 cores: `connect_core`, `dash_state_core`, `infer_schedule_core`, `infer_waste_core`, `overlay_stream_core`, `reconcile_plan_core`, `report_core`, `task_plan_core`. Interpreter-side, not backend-side. |
| `string-contains?` / `string-replace-all` | no native lowering | 9 cores: `deploy_plan_core`, `fleet_inventory_core`, `kekkai_gate_core`, `overlay_crypto_core`, `persist_core`, `provision_plan_core`, `reconcile_plan_core`, `secret_core`, `tunnel_core`. Both are string SEARCH operations; the backends implement `string=?`, `string-concat`, `string-byte-length`, `string-code-point-at` and `string-substring` over an ASCII literal only. |
| match-form branch tails | open | See "What was deliberately NOT done" 4. |

`reconcile_plan_core` appears twice: it needs both.

Counting each core once, the 16 that fail the typed-feature gate are 7 on a
`:bool` parameter alone, 8 on a string search operation alone, and 1 on both.

## Reproducing

Sweep (from a kotoba-lang/compiler checkout, with this branch as `:local/root`):

```clojure
(compiler/compile-source (slurp "…/murakumo/kotoba/<name>_core.kotoba")
                         :x86_64-kotoba-v1)   ; and :aarch64-kotoba-v1
```

Execution rows added to the compiler's `isa_execution_test.clj` `cases` table
(uncommitted there; `record-type` is `[:record :t/r [[:a :i64] [:b :i64]]]`):

```
record result built under a let, first field                      => 4
record result built under a let, second field                     => 9
record result built in the then branch, second field              => 9
record result built in the else branch under a nested let, first  => 4
record result built in the else branch under a nested let, second => 9
```

The `[:ref :t/r]` result spelling is proved end-to-end by the sweep instead —
`infer_credits_core` and `infer_rebalance_core` declare every record result by
reference and now compile — because a row that ALSO projects the call's result
is blocked in the verifier (see the residual gaps table).

This repo's own suite: `kbb -M:test`.
