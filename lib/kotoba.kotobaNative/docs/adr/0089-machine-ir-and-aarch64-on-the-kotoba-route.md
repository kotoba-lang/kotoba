# ADR 0089: machine-ir and the AArch64 emitter on the Kotoba route

Status: accepted. Date: 2026-10-02.

## Context

`kotoba.native.machine-ir` (9.8k lines) and `kotoba.native.aarch64` (1.7k) are
the code generator every native artifact crosses: KIR -> GMIR -> MIR -> MC ->
bytes. Until today both were host-only; `amu check` refused them at
`constant must contain exactly one literal value`, and the selfhost analysis
(amu `docs/selfhost-efficiency-analysis-20261002.md`, track B1) named them the
largest unported block on the critical path.

Owner decisions adopted for this wave (2026-10-02), stated here because they
shape what "ported" means in this repository. All are reversible:

1. The first selfhost target is **aarch64-macos only**. x86-64, wasm,
   component, EVM, JS, uefi and the elf/pe writers are deferred.
2. A `.kexe` run by the C loader counts as the `amu` binary for milestone 1.
3. The native string/bytes value bound rises from 64 KiB to at least 8 MiB
   (amu ADR 0362).
4. The KIR interpreter is frozen beyond what `fold-def-value!` needs.
5. The JVM native-image checker is the stage-0 compiler, labelled
   bootstrap-reference.

## Decision

**Both modules read as Kotoba over `kotoba.form`.** Every host definition is
kept byte for byte under `:default`; its Kotoba reading is a typed twin beside
it (`#?(:kotoba <twin> :default <host>)`). Host maps, vectors and keywords are
`:form/r` Forms; a sequence the host walks by index is a
`[:list [:ref :form/r]]`; a vreg-keyed table is a `:vector-i64` indexed by the
vreg number.

Measured result: both files check OK on the native checker. machine_ir has 220
of its 392 definitions with a real Kotoba body (5299 of 8592 host lines), 198 of
them (5073 lines) reachable from a differentially tested entry; 46 are folded into twins
under other names (an EDN table that became a `case` predicate, a constant
inlined at its one use); 126 are deferred (the x86-64 encoders and the legacy
`pilot-expression?` gate). aarch64 has its production path real (`emit-program`
and the fuel instrumentation, 8 definitions); the 84 definitions of the legacy
per-expression emitter, which nothing outside this namespace's tests calls,
read as nil. Per-definition rows: `docs/kotoba-route-ledger.tsv`.

Specific choices, each forced by the Kotoba route as it is today:

* **Imported aborting functions are `[:result T :document]` values.** Abort
  does not cross a module boundary yet (amu track C4), so `mir/validate!`,
  `mc/validate!`, `gmir/validate!`, `string-index/lower`, `document/lower`,
  `*/augment-functions` and the machine-ir exports aarch64 calls are read with
  `result-match-of` and the caller aborts locally. Where an importer offers a
  non-aborting `-result` twin (`mir/select-target-result`,
  `mir/allocate-registers-result`, `mir/counted-self-recur-plans-result`) it is
  used. When C4 lands these wrappers become plain calls.
* **An abort may not precede a recur.** Encoders run inside loops, so an
  unsupported register (an allocator invariant) traps instead of raising
  `:unsupported-register`; the per-instruction walks that call aborting
  encoders (`instruction-tokens`, the layout passes, `nso`) are self-recursive
  functions rather than `loop`s.
* **The counted-loop entry charge is data.** On the host the fuel
  instrumentation's `:entry` is a function of the fallback label; on the Kotoba
  route it is `{:counted-bulk-counter N}` and machine-ir expands it.
* **Layout is done on Forms in machine-ir.** `kotoba.codegen.layout`'s Kotoba
  twin is `:document`-typed, and a document holds at most 32 items per
  container; a token stream is thousands. The tables and both passes are
  repeated here over Forms (the host route still uses `kotoba.codegen.layout`).
* **`signed-division-magic` runs in u64 word arithmetic** (Hacker's Delight
  10-1 with unsigned compares and a shift-subtract division); the host computes
  in bigints. On the Kotoba route it answers `[multiplier shift add? sub?]`.
* **Generated let binders have fixed names** (`option__`, `record__`, ...) where
  the host gensyms. Each binds around code whose references are to itself, user
  code never names them, and none reaches GMIR.
* **Hot lookups allocate nothing.** Every Form is seven pairs and a vector and
  the native heap is not reclaimed, so keyword lookups scan kids without
  building a key Form, op tables are `case` predicates, and the fuel
  instrumentation reads the GMIR `emit-program` already lowered
  (`entry-fuel-prefixes-of-gmir`, `counted-self-recur-plans-of-gmir`, Kotoba-only
  exports) where the host lowers the KIR again for each consumer.

## Evidence

The Kotoba side is compiled natively (aarch64 `.kexe`, run by
`tools/kexe_loader.c`) and compared with host recordings, case by case, with
`scripts/kotoba-route/` (README there). Host recordings come from compiling the
amu `.kotoba` corpus (220 programs: examples, test/nbb/fixtures,
lang-conformance, bench) and 167 aiueos programs for aarch64-macos on the JVM.

| entry | agree (bytes / data equal) | both refused | stub | arena | differ |
|---|---|---|---|---|---|
| `aarch64/emit-program`, amu corpus | 161 | 1 | 3 | 7 | 0 |
| `aarch64/emit-program`, aiueos (kernel windows, subregions, ...) | 77 | 18 | 0 | 21 | 0 |
| `lower-kir-expression` | 786 | 1 | 20 | 0 | 0 |
| `lower-kir-module` | 160 | 1 | 2 | 0 | 0 |
| `compile-gmir` / `hoist` / `coalesce` / `lower-mc` | 153 / 156 / 156 / 153 | | | | 0 |
| `encode-mc-module` | 166 | | | 1 | 0 |

"stub": the case reaches `kotoba.native.document`, `string-index` or
`string-search`, which the guest replaces by local stubs because those modules
are not natively linkable yet (they hold functions answering `:symbol`).
"arena": the guest exhausted the loader's 4M-entry vector table.

## Consequences and open walls (owners outside this repository)

* **Memory.** A 28 KB KIR program needs about 3.4M vectors and 16M pairs on the
  Kotoba route, mostly Form nodes (each leaf allocates an empty kids vector) in
  `kotoba.mir` select/allocate and the MC validators. Compiling the compiler
  itself needs memory reclamation or a lighter Form (amu track C3).
* **Native string-index holds 128 entries** and traps past that; tables keyed
  by compiler names cannot use it.
* **Not natively linkable:** `kotoba.native.document`, `string-index`,
  `string-search`, `interrupt-abi` (functions answering `:symbol`), and
  `kotoba.lang.coll` (typed keyword sets), which `aggregate-abi` requires on
  both readings although its Kotoba arms never call it.
* **Frontend defects met** (reported to the frontend owners): sibling `loop`s in
  one function can be given each other's loop-helper parameter types; an
  aborting call in a nested `let` inside a long `let` can lose the outer
  bindings in abort A-normalization; a type error in an aborting function is
  reported as `call to aborting function ... neither catches it nor aborts with
  the same error type` with no span (inference swallows the exception).
* x86-64 and the legacy aarch64 per-expression emitter stay host-only until the
  deferral is lifted.
