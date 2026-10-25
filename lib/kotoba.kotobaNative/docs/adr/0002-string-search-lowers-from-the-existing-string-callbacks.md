# 0002 — `string-contains?` and `string-replace-all` lower from the four string callbacks that already exist

Status: accepted
Date: 2026-08-05
Base: `origin/main` `b65fd0d25e5a6e84ad7930c986c374bd5c1fc45a`

## Context

ADR 0001's residual-gap table named this: *"`string-contains?` /
`string-replace-all` — no native lowering. 9 cores. Both are string SEARCH
operations; the backends implement `string=?`, `string-concat`,
`string-byte-length`, `string-code-point-at` and `string-substring` over an
ASCII literal only."*

A string value on native is a one-word `pair(offset,length)` handle, and
emitted code can address neither the code/literal region nor the runtime string
pool — only the host context callbacks can read the bytes behind a handle. So a
search could have been a fifth string callback at a new context offset. It is
not, for the reason ADR 0062's pair chain was not a new representation: a new
slot is a **v4 context ABI bump**, and the loader that would have to supply it
(`tools/kexe_loader.c`) lives in kotoba-lang/compiler with its source digest
pinned by `kotoba.artifact.runtime-identity`. Search turned out to be
expressible from the four callbacks already at 112 / 120 / 136 / 144, so it was.

## Measurement (before)

Sweep of murakumo's 33 shipped `kotoba/*_core.kotoba` against `origin/main`
`b65fd0d`, compiled through kotoba-lang/compiler `origin/main` `36bedf8` with
kotoba-native supplied as a `:local/root`:

| target | pass |
|---|---|
| `:x86_64-kotoba-v1` | **16 / 33** |
| `:aarch64-kotoba-v1` | **16 / 33** (same 17, same reasons) |

kotoba-native's own suite on unmodified `origin/main`, in a clean worktree:
**53 tests, 2,218 assertions, 0 failures, 0 errors** — no pre-existing failures
to separate out. The shared ISA execution table in kotoba-lang/compiler
(`test/kotoba/compiler/isa_execution_test.clj`, as committed there): **2 tests,
185 assertions, 0 failures**. ADR 0001 quotes 205 for the same table; that
figure included ADR 0001's own five rows, which were never committed to the
compiler.

### The failure the sweep reports is not the failure that exists

All 16 typed-feature failures report `:phase :target` — the compiler's call to
`kotoba.kir/only-native-word-typed-features?`. **The backend is never reached.**
Both search operations are refused twice before emission, by two tables in two
repositories that are not this one:

1. `kotoba.kir/non-string-typed-ops` contains `string-contains?` and
   `string-replace-all`, so `only-native-word-typed-features?` rejects them at
   its `:else` clause, and `kotoba.compiler.core` turns that into
   `"typed values currently require … the qualified native one-word … slice"`.
2. `kotoba.verifier`'s `string-operations` map — `{string-byte-length 1
   string=? 2 string-concat 2 string-substring 3 string-code-point-at 2 …}` —
   has no entry for either, so `verify-expr!` falls to
   `"runtime KIR operation rejected"` `{:operation string-contains?, :phase
   :verify}`.

Isolating the backend's own contribution therefore needs the sweep run four
ways. Relaxing means only those two tables, for the duration of the run:

| kotoba-native | gates | x86_64 | aarch64 |
|---|---|---|---|
| `origin/main` `b65fd0d` | as shipped | 16 / 33 | 16 / 33 |
| this branch | as shipped | 16 / 33 | 16 / 33 |
| `origin/main` `b65fd0d` | relaxed | 16 / 33 | 16 / 33 |
| this branch | relaxed | **24 / 33** | **24 / 33** |

Row 3 is the one that isolates this change. With the gates relaxed and the
backend unmodified, **eight** cores stop failing in kotoba-kir and start
failing in the backend with `operation not implemented on this backend` —
`deploy_plan_core`, `fleet_inventory_core`, `kekkai_gate_core`,
`overlay_crypto_core`, `persist_core`, `provision_plan_core`, `secret_core`,
`tunnel_core`. The ninth string-search core, `reconcile_plan_core`, keeps
failing in kotoba-kir on its `:bool` parameter, which is a different gap.
That is what it means to say this repository was the second of three blockers,
and the only one in scope.

## Decision

A new namespace, `kotoba.native.string-search`, owns one rewrite that BOTH
backends consume. It is shared rather than restated per backend precisely
because the property under test is that one program produces one value on both
ISAs; two copies could drift and both stay green.

### The scan advances by code points, not by bytes

The obvious lowering — slide a byte cursor and compare
`(string-substring h i (+ i nlen))` against the needle — **traps on any
multi-byte haystack**. `kotoba.kir.value/utf8-substring!` requires both offsets
to be code-point boundaries, and `(+ i nlen)` is not one in general: looking for
the 2-byte needle `"ab"` in `"日本"` asks for `(string-substring h 0 2)`, and 2
splits the first code point. There is no boundary predicate to test with, and a
trap cannot be caught, so the scan may never construct an offset it has not
walked to.

`string-code-point-at`'s own docstring states the contract this stands on: the
code point's UTF-8 width is derivable from its VALUE (`< 0x80` → 1, `< 0x800` →
2, `< 0x10000` → 3, else 4), "so a single op is enough to walk a string".

- **`kotoba$string-span`** advances a haystack cursor one code point for every
  code point of the needle, establishing the END of the first candidate window.
  `-1` means the haystack cannot supply that many.
- **`kotoba$string-find`** slides both cursors together, so the window always
  spans exactly as many code points as the needle and both of its offsets are
  boundaries the walk reached. Comparison is then one `string=?` over one
  `string-substring`. Two strings are equal iff they are the same code points,
  so a same-code-point-count window is the right window even where its byte
  length differs from the needle's.
- **`kotoba$string-replace-from`** consumes the subject: it appends
  `prefix ++ replacement` to an accumulator and recurs on the SUFFIX past the
  match, so **the replacement is never rescanned**. A window that compared equal
  has the needle's byte length, so the match ends at exactly
  `k + (string-byte-length n)` and the skip is plain arithmetic.

`string-contains?` is `(< (find …) 0)` negated; `string-replace-all` is
`replace-from` seeded with the first match.

### Why the helpers are functions, and how they get there

The rewrite needs a loop and the backends have none — control flow is `if`,
`let`, `do` and calls. So the three helpers are ordinary KIR functions, appended
to `(:functions kir)` by `emit-program` on both backends when, and only when, a
body actually reaches one. `exported-names` is read from the DECLARED functions
first, so a program's public surface does not change because it searched a
string. `augment-functions` is idempotent — a second copy would put every call
displacement past the first copy at the wrong distance — and refuses a name
already declared with a *different* definition.

A program that searches nothing gets back the identical collection, so this
cannot have moved the emission of any existing program.

### Fuel is what shapes the helpers

`emit-function` charges one unit of fuel per entry and `emit-tail-self-call`
one per iteration; a host context callback charges none, and the qualification
loader starts a program with **512**. Every helper therefore spends one fuel
unit per code point examined and pushes everything else onto free callbacks.
That is why `code-point-width` is written INLINE rather than as a fourth helper
(re-reading the code point through `string-code-point-at` up to three times is
free; a call is not), and why nothing is hoisted into a `let`.

The `let` avoidance is load-bearing a second time on x86-64: `emit-call`'s
tail-self-call fast path requires `(zero? temp-depth)`, so a self-call from
inside a `let` body falls back to a real CALL and grows the stack. Every
recursive call here is in tail position at depth zero, so on x86-64 the scan is
a jump. AArch64 has no tail-self-call path and does grow its stack, one small
frame per iteration — bounded by the same fuel budget that bounds the iteration
count. **The two ISAs differ in stack use and not in results**, and the
execution table below is what makes that a measured claim.

### The empty needle traps, because the oracle traps

`kotoba.kir` traps on an empty needle (`:empty-string-search-needle` /
`:empty-string-replacement-needle`) rather than answering, so the rewrite must
not answer either — and `clojure.string/includes?` would have said `true`, so
this is a real divergence and not a theoretical one. It reaches a trap through
`(string-code-point-at n 0)`, out of bounds exactly when the needle is empty.
Native traps carry no keyword (the loader reports `KEXE_TRAP`), so the trap's
identity differs from the interpreter's while the observable behaviour — no
value is produced — agrees. No new trap encoding in either backend.

## Measurement (after)

| target | before | after (gates as shipped) | after (gates relaxed) |
|---|---|---|---|
| `:x86_64-kotoba-v1` | 16 / 33 | 16 / 33 | **24 / 33** |
| `:aarch64-kotoba-v1` | 16 / 33 | 16 / 33 | **24 / 33** |

Both ISAs move together and fail on the identical set — measured separately,
not asserted from one.

Newly compiling to real machine code, once the two out-of-scope tables admit
the operations: `deploy_plan_core`, `fleet_inventory_core`, `kekkai_gate_core`,
`overlay_crypto_core`, `persist_core`, `provision_plan_core`, `secret_core`,
`tunnel_core` — **8**, not 9. `reconcile_plan_core` is in two failure classes
and still fails on its `:bool` parameter.

**With the two tables as shipped, this change moves the sweep by zero.** The
backend half is done and proved; the operations remain unreachable from source.

kotoba-native's own suite: **64 tests, 2,494 assertions, 0 failures, 0 errors**
(from 53 / 2,218: +11 tests, +276 assertions).

Shared ISA execution table, both ISAs, real processes: **3 tests, 378
assertions, 0 failures, 0 errors** (from 2 / 185: +1 test, +193 assertions).

## Evidence

### Semantics, against the oracle, in this repository

`kotoba.native.string-search-test` runs every row TWICE through
`kotoba.kir/execute`: once as the operation itself, which the reference
interpreter implements directly, and once as the rewrite the backends emit.
**The expected value is never written down** — the oracle produces it — so no
row can be passed by an implementation and an expectation being wrong in the
same direction. 45 rows (23 `contains?`, 22 `replace-all`), plus a runtime-
operand table where the strings are parameters rather than literals.

This is possible only because the helpers are declared as complete KIR — with
`:param-types` and `:result` — rather than with the `:name`/`:params`/`:body`
the backends alone would read. Being runnable BY THE ORACLE is what turns the
comparison into a differential test.

The table is built out of near misses, because a byte search is the classic
place a wrong implementation returns a plausible answer:

| row | what it catches |
|---|---|
| needle at offset 0 / touching the last byte | a scan that starts at 1 or stops one short |
| `"abcde"` / `"cdf"` | comparing only a prefix — every window shares two bytes with it |
| `"abcd"` / `"abce"` | comparing all but the last byte |
| needle longer than the haystack, by any amount and by one | an unguarded window end |
| empty haystack | a walk that assumes at least one code point |
| `"aaa"` / `"aa"` | overlapping occurrences |
| `"日本語"` / `"ab"` | **a byte-indexed scan traps here** rather than answering |
| `"日本語"` / `"日語"` | same code-point count, different content |
| `"aé日b"` / `"é日"` | a haystack whose code points are 1, 2 and 3 bytes wide |
| `"a𝄞b"` / `"𝄞"` | the 4-byte branch of the width derivation |
| `"xax"` / `"a"` → `"aa"` | a replacement containing the needle, which must NOT be rescanned |
| `"a--b--c"` / `"--"` → `"-"` | replacement shorter than the needle |
| `"a-b"` / `"-"` → `"==="` | replacement longer than the needle |
| `"a-b"` / `"-"` → `""` | empty replacement |
| `"aaa"` / `"aa"` → `"b"` | non-overlapping, left to right: `"ba"`, not `"b"` and not `"ab"` |
| `"a-b"` / `"-"` → `"日"` | a multi-byte replacement |

The table was confirmed to FAIL on wrong implementations before being trusted.
Four mutations, each applied to a copy and reverted:

| mutation | result |
|---|---|
| the find scan steps one BYTE instead of one code point | 10 errors |
| a match is skipped by 1 instead of the needle's byte length | 4 failures, 4 errors |
| the width derivation returns 3 for a 4-byte code point | 3 errors |
| the empty-needle trap is dropped | 2 failures |

### Emission, both ISAs, committed here

Each row is emitted twice per backend: once from the operation, once from a
module with the rewrite already written out and the helpers already declared —
and the two must produce **exactly the same bytes**. That is what makes this a
rewrite into code both backends already emitted rather than a new encoding that
happens to compile, and it pins the helper PLACEMENT, which is what every call
displacement depends on.

Also pinned: the helpers are never exported; they are injected once and never
twice; a name collision with a different definition is refused; a search of the
wrong arity falls through to `emit-call` and is reported as an unimplemented
operation rather than being lowered as if an argument had been supplied; and
occurrences nested inside `if`/`let`/arithmetic, appearing twice in one body,
or feeding one another still lower on both ISAs.

### Execution, both ISAs, real processes

The shared ISA execution table is in kotoba-lang/compiler
(`test/kotoba/compiler/isa_execution_test.clj`), not here — this repository has
no loader, as `isa_parity_test.clj` states. 31 rows were added there against
this branch supplied as a `:local/root` — 14 `contains?` and 17 `replace-all`,
the latter asserted twice each, so 48 executed cases — and are **NOT committed
there**, because the compiler repository was out of scope. They are reproduced
below.

- With this change: **378 assertions, 0 failures, 0 errors**, on BOTH ISAs.
  Neither was skipped — `@loaders` resolved both `kotoba-isa-loader-x86_64.bin`
  and `kotoba-isa-loader-aarch64.bin`, so both were built and both ran (x86-64
  under Rosetta 2 on this Apple-silicon host).
- Against unmodified `origin/main` `b65fd0d`, same table, same relaxations: 187
  assertions, **1 error** — the first new row throws
  `operation not implemented on this backend`, aborting that deftest, after
  every pre-existing row has passed. **The rows fail without the change and
  pass with it.**

Each `replace-all` row is asserted BOTH ways — the exact result bytes via
`string=?`, and the exact byte length. Content alone would pass a
length-preserving slip; length alone would pass a wrong-bytes-same-length one.

Every expectation in that table was cross-checked against the same
`clojure.string/includes?` and `clojure.string/replace` calls `kotoba.kir`'s
evaluator itself makes, before the table was run.

## What was deliberately NOT done

### 1. No ABI bump, and no loader change

The context ABI stays at **v3**. No new context offset, no new host callback,
no edit to `tools/kexe_loader.c`, and therefore nothing touching the
`loader-source-sha256` constants in `kotoba.artifact.runtime-identity` or the
standing verification asymmetry on their Windows half. The lowering uses
`string=?` (112), `string-concat` (120), `string-substring` (136) and
`string-code-point-at` (144), all of which the loader already supplies.

No new value representation either: everything is the one-word
`pair(offset,length)` handle, and no new instruction encoding was added to
either backend — the rewrite reaches `emit-expr` cases that already existed.

### 2. Nothing in kotoba-kir, kotoba-verifier, kotoba-wasm or the compiler

The two tables that refuse these operations before emission were measured and
reported, not reached into. Both changes are one line each and are recorded in
the residual-gap table below with the exact site.

### 3. No capability kit descriptor was touched

No `:native-aot` / `:wasm-aot` / `:jit` qualification flag was changed
anywhere. Those denote end-to-end real-provider semantics; nothing here earns
one.

### 4. `string-split-count` and `string-fold-case`

`kotoba.kir/non-string-typed-ops` lists both alongside the two implemented
here. Neither is used by any of the 33 murakumo cores, so admitting them would
have added a path nothing had executed — the same reason ADR 0001 declined
match-form branch tails.

### 5. No Rust

The native core path stays Rust-free.

## Residual gaps, by name

| gap | state | detail |
|---|---|---|
| `string-contains?` / `string-replace-all` unreachable from source | blocked on kotoba-kir | `non-string-typed-ops` (`kir.cljc:47`) contains both, so `only-native-word-typed-features?` refuses them at its `:else`. Needs a native admission clause of the same shape the `i32-operations` and `vector-*` families already have there — those are in the same set and are admitted for native by an explicit clause rather than by removal, because the CLJS gate shares the set. Both are arity-fixed: `string-contains?` 2, `string-replace-all` 3. |
| same, second gate | blocked on kotoba-verifier | `string-operations` (`verifier.cljc:79-80`) needs `string-contains? 2 string-replace-all 3`. That map is already the "target-independent operations with their KIR arities" table, and its own comment says a backend that cannot emit one reports it as not implemented — which is now exactly what would happen for a backend that has not done this work. |
| 8 cores on a `:bool` PARAMETER | blocked on kotoba-kir | Unchanged from ADR 0001. `native-boundary-type?` excludes `:bool` (`kir.cljc:244`) because `kotoba.kir/execute` validates a `:bool` argument as an i64 word. `connect_core`, `dash_state_core`, `infer_schedule_core`, `infer_waste_core`, `overlay_stream_core`, `reconcile_plan_core`, `report_core`, `task_plan_core`. |
| `infer_plan_core` | blocked on kotoba-verifier | Unchanged from ADR 0001: `record-get` over a `let`-bound boxed handle. |
| the 512-unit fuel budget bounds haystack length in the qualification host | open, and a property of the loader | One fuel unit per code point examined, so `tools/kexe_loader.c`'s `shared->context.fuel = 512` caps a single search at roughly 500 haystack code points before it traps — well short of `string-value-byte-limit` (65,536). This is a host parameter, not an ABI constant, and a host that grants more fuel scans further. No murakumo core searches anything near that long, and nothing here can raise it from this repository. |
| AArch64 grows its stack where x86-64 does not | open, and bounded | AArch64 has no tail-self-call path, so the scan recurses one frame per code point instead of jumping. The same fuel budget bounds it (~512 frames × 64 bytes ≈ 32 KB), so it is not reachable as a stack overflow at the current budget — but a host that raises fuel raises this too. Giving AArch64 a tail-self-call path is a separate change with its own evidence. |
| `string-split-count` / `string-fold-case` | open | Still refused by both backends. See "What was deliberately NOT done" 4. |
| the search is O(haystack × needle) | open, and deliberate | No Boyer-Moore/KMP skip table: a table needs a mutable array, which the one-word slice has no representation for, and the fuel budget above binds long before the asymptotics do. |

Counting each core once, the 17 that still fail are 7 on a `:bool` parameter
alone, 8 on a string search operation alone, 1 on both
(`reconcile_plan_core`), and 1 on `record-get` (`infer_plan_core`).

## Reproducing

Sweep, from a kotoba-lang/compiler checkout with this branch as a
`:local/root`:

```clojure
(compiler/compile-source (slurp "…/murakumo/kotoba/<name>_core.kotoba")
                         :x86_64-kotoba-v1)   ; and :aarch64-kotoba-v1
```

To see the eight cores reach the backend, wrap the sweep in the two
relaxations (this is a MEASUREMENT harness, not a proposed change):

```clojure
(with-redefs-fn
  {#'kotoba.kir/non-string-typed-ops
   (disj @#'kotoba.kir/non-string-typed-ops 'string-contains? 'string-replace-all)
   (ns-resolve 'kotoba.verifier 'string-operations)
   (assoc @(ns-resolve 'kotoba.verifier 'string-operations)
          'string-contains? 2 'string-replace-all 3)}
  sweep!)
```

Execution rows added to the compiler's `isa_execution_test.clj` (uncommitted
there, under the same two relaxations). `contains?` rows answer 1/0 directly;
each `replace-all` row is run twice, once comparing the result with `string=?`
against the expected text and once measuring `string-byte-length`.

```
contains?: needle at the very start                                "abcdef" "abc"  => 1
contains?: needle at the very end                                  "abcdef" "def"  => 1
contains?: needle in the middle                                    "abcdef" "cd"   => 1
contains?: needle is the whole haystack                            "abc"    "abc"  => 1
contains?: absent                                                  "abcdef" "xyz"  => 0
contains?: absent, but every window shares a prefix with it        "abcde"  "cdf"  => 0
contains?: needle longer than the haystack                         "ab"     "abcd" => 0
contains?: empty haystack                                          ""       "a"    => 0
contains?: two occurrences, first at offset 0                      "abab"   "ab"   => 1
contains?: overlapping occurrences                                 "aaa"    "aa"   => 1
contains?: multi-byte needle inside a multi-byte haystack          "日本語"  "本語"  => 1
contains?: multi-byte needle absent                                "日本語"  "日語"  => 0
contains?: 2-byte needle against a 3-byte-per-code-point haystack  "日本語"  "ab"   => 0
contains?: mixed-width haystack                                    "aé日b"  "é日"   => 1

replace-all: single occurrence in the middle          "a-b"     "-"   "+"    => "a+b"
replace-all: at the very start                        "-ab"     "-"   "+"    => "+ab"
replace-all: at the very end                          "ab-"     "-"   "+"    => "ab+"
replace-all: two occurrences                          "a,b,c"   ","   ";"    => "a;b;c"
replace-all: adjacent occurrences                     "--"      "-"   "+"    => "++"
replace-all: absent                                   "abc"     "x"   "y"    => "abc"
replace-all: needle longer than the haystack          "ab"      "abc" "z"    => "ab"
replace-all: empty haystack                           ""        "a"   "b"    => ""
replace-all: needle is the whole haystack             "abc"     "abc" "z"    => "z"
replace-all: replacement contains the needle          "xax"     "a"   "aa"   => "xaax"
replace-all: replacement is the needle doubled        "a.b"     "."   ".."   => "a..b"
replace-all: replacement shorter than the needle      "a--b--c" "--"  "-"    => "a-b-c"
replace-all: replacement longer than the needle       "a-b"     "-"   "==="  => "a===b"
replace-all: empty replacement                        "a-b"     "-"   ""     => "ab"
replace-all: overlapping candidates, left to right    "aaa"     "aa"  "b"    => "ba"
replace-all: multi-byte needle                        "日本語"   "本"  "X"    => "日X語"
replace-all: multi-byte replacement                   "a-b"     "-"   "日"    => "a日b"
```

This repository's own suite: `kbb -M:test`.
