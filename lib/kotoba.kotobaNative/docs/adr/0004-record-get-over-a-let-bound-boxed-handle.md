# 0004 — `record-get` over a `let`-bound boxed handle

Status: accepted
Date: 2026-08-06
Base: `origin/main` `55ba8c3` (branched from `4a5216e`, fast-forwarded)

## Context

ADR 0001 boxed a record RESULT from any tail position, and read a result
declared by schema reference. It left one shape open, and named it precisely:

```clojure
(let [ends (partition-3-ends x)          ; a call whose result is a record
      hi0  (record-get … ends :hi0)      ; projected through the NAME
      hi1  (record-get … ends :hi1)] …)
```

The handle is ONE WORD — the same ADR 0062 pair chain a record result has
crossed on since records could cross at all — so reading a field off it is the
same chain walk a projection over a call or over a parameter already emitted.
Nothing new is encoded. What had to change is only which `env` shapes reach that
walk.

ADR 0001 implemented exactly that, measured it green on both ISAs, and
**reverted it**, because `kotoba.verifier` independently rejected the shape
(`verifier.cljc` `record-get`, "runtime KIR record projection rejected"). With
only the backend widened, the three murakumo cores stopped failing in the
backend and started failing in the verifier instead; no ISA execution row could
run, so the change would have added a code path nothing could reach and nothing
had ever executed. It recorded the two lines so the follow-up would be a
two-repo change rather than a rediscovery. This is that follow-up, landed with
kotoba-verifier ADR 0004.

## Measurement (before)

Sweep of murakumo's 33 shipped `kotoba/*_core.kotoba`, compiled through
kotoba-lang/compiler `db44180` with kotoba-kir `57cfa2b`, kotoba-native
`4a5216e` and kotoba-verifier `6433a81` supplied as pinned git SHAs — not
`:local/root`, and no `with-redefs`:

| target | pass |
|---|---|
| `:x86_64-kotoba-v1` | **30 / 33** |
| `:aarch64-kotoba-v1` | **30 / 33** (same 3, same reasons) |

All 3 failures are one reason class, identical on both ISAs:
`record-get is only supported directly over a matching record-new construction
on the native backend` — `infer_plan_core`, `infer_schedule_core`,
`task_plan_core`.

The measured sites, all the same shape (a `let`-bound name whose value is a call
whose declared result is a record):

- `infer_plan_core:476` — `ends (partition-3-ends x)`, then `:hi0` `:hi1` `:hi2`
- `infer_schedule_core:296` — `nq (apply-pick-3 …)`, then `:v0` `:v1` `:v2`
- `task_plan_core` — the same `[:ref :task/triple]` shape

Suite on unmodified `origin/main` `4a5216e`, clean worktree: **66 tests, 2,572
assertions, 0 failures, 0 errors** — no pre-existing failures to separate out.

## Decision

Both backends (`kotoba.native.x86-64`, `kotoba.native.aarch64`), identically —
one predicate each, exactly the two lines ADR 0001 recorded:

```clojure
;; was
(and (symbol? value-form) (not (map? (get env value-form)))       (contains? env value-form))
;; now
(and (symbol? value-form) (not (:record-fields (get env value-form))) (contains? env value-form))
```

`expand-binding` gives an ordinary slot `{:let-depth d}` and a FLATTENED record
binding `{:record-type T :record-fields {…}}`. Only the latter has its fields in
separate slots, and it is resolved earlier by `resolve-record-binding`. So the
question this predicate is really asking is "is this name ONE word or N words",
and `:record-fields` answers it; `map?` answered a different question and
happened to exclude a plain slot as a side effect. A parameter's bare index is a
word too, and reaches the same walk — the three routes a boxed handle can arrive
by are now spelled the same because they ARE the same word.

No new primitive, no new representation, no ABI change, no loader change, no
Rust. `pair` / `pair-first` / `pair-second` are the ADR 0062 arena contract.

## Measurement (after)

| target | before | after |
|---|---|---|
| `:x86_64-kotoba-v1` | 30 / 33 | **33 / 33** |
| `:aarch64-kotoba-v1` | 30 / 33 | **33 / 33** |

Both ISAs measured separately, not asserted from one. Newly compiling to real
machine code: `infer_plan_core`, `infer_schedule_core`, `task_plan_core`.

Suite after: **72 tests, 2,604 assertions, 0 failures, 0 errors** (+6 tests,
+32 assertions).

## Evidence

### Execution — real processes, both ISAs

The shared ISA execution table is in kotoba-lang/compiler
(`test/kotoba/compiler/isa_execution_test.clj`), driven by `tools/kexe_loader.c`.
This repo has no loader and its own tests are emission-level, as
`isa_parity_test.clj` states. Six rows were added there and run against this
branch as a `:local/root`, and are **not committed there** — the compiler repo
was out of scope and another agent was active in it. They are reproduced below.

- Baseline table, both repos at `origin/main`: **185 assertions, 0 failures,
  0 errors**, three consecutive runs.
- With this change: **209 assertions, 0 failures, 0 errors**, three consecutive
  runs. 209 − 185 = 24 = 6 rows × 2 assertions × 2 ISAs.
- **Neither ISA was skipped.** The runner's `loaders` map was resolved directly
  and both entries were real paths (`kotoba-isa-loader-x86_64.bin`,
  `kotoba-isa-loader-aarch64.bin`), and no "skipping ISAs with no
  buildable/runnable loader" line was printed. x86-64 runs under Rosetta 2 on
  this Apple-silicon host.
- **Falsified.** With both repos at `origin/main` and the new rows present, the
  first new row throws `record-get is only supported directly over a matching
  record-new construction on the native backend` (`x86_64.cljc`) after 95
  assertions of pre-existing rows pass. The rows fail without the change.

The rows (`record-type` is `[:record :t/r [[:a :i64] [:b :i64]]]`,
`option-record-type` is `[:record :t/o [[:m [:option :i64]] [:x :i64]]]`):

```
let-bound handle, first field                          => 4
let-bound handle, second field                         => 9
let-bound handle projected at two depths   (:a - :b)   => -5
handle forwarded through a function, then projected    => 9
let-bound handle over a record with an option field    => 5
… same, option none, falls back to the sibling field   => 9
```

**Field selection is the design, not decoration.** A pair chain walked to the
wrong depth still returns a plausible i64, so a row that always read the first
field passes even when the walk is wrong. 4 and 9 differ; the rows read
different fields on purpose; and the two-depth row SUBTRACTS, so reading one
slot twice (0) or the two in the wrong order (+5) is distinguishable from the
correct −5. This follows the discipline the existing record-parameter rows were
written with.

### Emission — both ISAs, committed here

`isa_parity_test.clj` gains six tests. Each asserts the projection emits
**exactly the same bytes** as the hand-written chain walk
(`pair-first` after N `pair-second`s) over the same handle — an oracle built
only from primitives both backends emitted before this change. Not "it emits":
byte equality is what makes this a rewrite into an existing shape rather than a
new encoding that happens to compile.

Rows cover: projected once at each field; projected twice at two depths (with a
`not=` against the depth-swapped walk, so the row cannot be vacuous); forwarded
through a second `let` binding; a record with an `[:option T]` field; and the
negatives — a FLATTENED `let`-bound `record-new` must still be read from its
slots and must NOT be emittable as a chain walk, and an undeclared field is
still a loud failure rather than depth zero.

**Falsified**: with the two predicates reverted and the tests kept, all six new
tests fail on both ISAs (2 failures, 22 errors across the suite). They are known
to be capable of failing.

## What was deliberately NOT done

### 1. Nothing in the compiler, kotoba-kir, kotoba-wasm, artifact or murakumo

The ISA rows were run from a throwaway compiler worktree and not committed.

### 2. No capability kit qualification flag was touched

No `:native-aot` / `:wasm-aot` / `:jit` flag changed anywhere. Every kit stays
`:native-aot :pending`. This qualifies no capability.

### 3. No KIR signature was reshaped

`:kir-sha256` digests exactly the `select-keys`'d program. Nothing here changes
what is digested. The reference spelling is still admitted BY NAME rather than
ref-expanded in `lower` — the attempt to expand it moved the digest of every
module using a schema reference on every target including its Wasm bytes, and
was reverted. That approach is preserved.

### 4. A flattened record forwarded through a second binding

`(let [r (record-new …) r2 r] (record-get … r2 :b))` is still refused: `r` is N
slots, and rebinding it would read N words as one. kotoba-verifier ADR 0004
declines to admit it for the same reason, so the two gates stay the same width.

## Residual gaps, by name

| gap | state | detail |
|---|---|---|
| a `[:ref …]` result in an ENTRY-bearing module | kotoba-kir | The verified `program` is `select-keys`-ed to the six keys `:kir-sha256` digests, which excludes `:schemas`, so the KIR oracle traps `unknown-schema-reference` on a reference in a signature. murakumo's cores are entryless libraries and never reach that path, so no core is blocked. It is why the ISA table has no by-reference row: such a program cannot be built there. Covered instead by `a-result-declared-by-schema-reference-boxes-identically` (both spellings emit the SAME BYTES, so the committed rows execute the identical machine code either way) and by the sweep. Fixing it means widening the digested key set — not this change's business. |
| match-form branch tails | open | `box-record-tails` follows `if`, `let` and `do` only; the match forms desugar inside `emit-expr`, after the rewrite. No murakumo core needs it (ADR 0001 §4). |

The three reason classes ADR 0001 listed as blocking cores — the typed-feature
gate on `:bool` parameters, the missing `string-contains?`/`string-replace-all`
lowering, and this one — are all now closed. All 33 shipped murakumo cores
compile to real machine code on both ISAs.

## Reproducing

Sweep, from a kotoba-lang/compiler checkout at `db44180`, with everything pinned
by git SHA:

```clojure
(compiler/compile-source (slurp "…/murakumo/kotoba/<name>_core.kotoba")
                         :x86_64-kotoba-v1)   ; and :aarch64-kotoba-v1
```

```
-Sdeps '{:deps {io.github.kotoba-lang/kotoba-kir      {:git/sha "57cfa2b…"}
                io.github.kotoba-lang/kotoba-native   {:git/sha "<this merge>"}
                io.github.kotoba-lang/kotoba-verifier {:git/sha "<verifier ADR 0004 merge>"}}}'
```

This repo's own suite: `kbb -M:test`.

## A note on measurement hygiene

One baseline run of the ISA table reported 43 failures on inputs that produced
185/185 on the three runs before and after it. It was not reproducible. The
table writes to fixed `/tmp/kotoba-isa-*` paths shared by every concurrent run,
which is the most likely cause on a host running many sessions. Every number in
this ADR is from a repeated run, and the anomaly is recorded rather than
discarded because a single green run of this table is not evidence.
