# ADR 0001: A `:bool` parameter at a function boundary was blocked on x86-64

Status: superseded by [ADR 0003](0003-a-bool-parameter-at-a-function-boundary-is-admitted.md)

**The hold this ADR records is over.** kotoba-native `f6f29e9` fixed the defect
described below, the 17 rows were re-run against it as real processes — 17/17 on
both ISAs — and the widening is merged. ADR 0003 carries the re-measurement.

What survives here is the *diagnosis*: the row table, the byte-level evidence,
and the reason a passing compile is not evidence that a binary runs. That
reasoning is why the type was withheld for a cycle instead of being admitted on
the strength of "native codegen produced an artifact", and it is the reason this
repo re-derives the boundary set rather than importing kotoba-kir's answer.
The row table below is the **pre-fix** measurement; do not quote it as current.

## Context

`kotoba-kir` ADR 0221 (landed 2026-08-05, `8de6215`) widened that repo's
`native-boundary-type?` to admit a bare `:bool` PARAMETER, after executing one
through its own interpreter in every position a parameter can occupy. It named
the required follow-on precisely:

> So the required follow-on is one predicate in `kotoba-verifier`, dropping its
> own `(not= :bool type)`. Nothing in `kotoba-native` needs changing: with only
> the verifier patched, native codegen produced an artifact.

That is accurate as far as it goes, and it is exactly the trap this ADR is
about. `verify-native-artifact!` re-executes through the KIR **interpreter**,
not through the emitted machine code. So "native codegen produced an artifact"
is not evidence that the artifact runs. ADR 0221 said so itself, and left the
proof to this repo:

> Native *machine-code* execution of a `:bool` parameter is still unproven here.
> [...] That proof belongs with the `kotoba-verifier` follow-on.

It was attempted here. It failed.

## Measurement

Measured 2026-08-05 against `compiler` `36bedf8`, `kotoba-kir` `8de6215`,
`kotoba-native` `9b33db5` (the pin `compiler` carries), with the widened
verifier supplied as `:local/root`. Rows were added to `compiler`'s shared ISA
execution table (`test/kotoba/compiler/isa_execution_test.clj`) and run as real
processes through `tools/kexe_loader.c` on both ISAs — x86-64 natively, aarch64
natively, both loaders built and probe-verified.

Every row is a `true`/`false` pair returning **different** values, so a backend
that dropped the argument, passed a constant, or read the wrong register cannot
pass by luck.

| row | expected | x86-64 | aarch64 |
|---|---|---|---|
| bool parameter as an `if` test, `true` | 4 | **4** | **4** |
| bool parameter as an `if` test, `false` | 0 | **SIGILL** | **0** |
| bool parameter before a string parameter, `true` | 4 | **4** | **4** |
| bool parameter before a string parameter, `false` | 99 | **SIGILL** | **99** |
| bool parameter through `bool-not`, `true` | 99 | **99** | **99** |
| bool parameter through `bool-not`, `false` | 4 | **SIGILL** | **4** |
| bool parameter through `=`, `true` | 4 | **4** | **4** |
| bool parameter through `=`, `false` | 99 | **SIGILL** | **99** |
| bool parameter forwarded into another bool parameter, `true` | 10 | **10** | **10** |
| bool parameter forwarded into another bool parameter, `false` | 11 | **SIGILL** | **11** |
| two bool parameters, `true false` | 4 | **SIGILL** | **4** |
| two bool parameters, `false true` | 5 | **SIGILL** | **5** |
| bool parameter with a string result, `true` | 3 | **3** | **3** |
| bool parameter with a string result, `false` | 2 | **SIGILL** | **2** |
| bool parameter returned as a bool result, `true` | 7 | **7** | **7** |
| bool parameter returned as a bool result, `false` | 6 | **SIGILL** | **6** |
| tail self-call passing a literal `false` | 6 | **SIGSEGV** | **6** |

AArch64 is correct on all 17. x86-64 is correct on every row whose bool
argument is `true` and crashes on every row whose bool argument is written as
the literal `false`. The trap is a hardware signal (loader exit 120), not a
Kotoba trap: `KEXE_TRAP {:kind :signal :signal :SIGILL}` /`:SIGSEGV`.

## Cause

`kotoba-native`'s x86-64 backend emits a call's arguments with

```clojure
(loop [remaining args depth temp-depth out []]
  (if-let [arg (first remaining)]
    ...
    out))
```

`if-let` binds and then tests for truth. When an argument's KIR form IS the
literal `false`, `(first remaining)` is `false`, the loop takes the else branch,
and **that argument and every argument after it are silently not emitted** —
while `pops` still pops `argc` slots. The stack is left one word short, and the
function returns into whatever that leaves in the return slot.

The byte evidence is unambiguous. For the same program with `true` versus
`false`, x86-64 emits 167 versus 156 bytes — the missing 11 are exactly
`48 b8 <imm64> 50`, the `movabs rax, imm` plus `push rax` for that one argument.
The `true` program materialises `01 00 00 00 00 00 00 00`; the `false` program
materialises nothing at all.

Three sites have this shape (`x86_64.cljc` at `origin/main` `b65fd0d`, lines
189, 242, 342): `emit-tail-self-call`, `emit-call`, and the typed heap/cap-call
argument loop. Two of the three are confirmed reachable and crashing above.
AArch64 is unaffected because its `emit-call` uses `mapcat` over `args` and has
no truth test to fail.

This is not a `:bool` representation problem. `:bool` really is a plain 0/1
word, in both backends, exactly as every gate comment says. It is a Clojure
`false`-versus-`nil` conflation in an emitter loop.

## Why it was invisible until now

It is unreachable on unmodified `main`. Measured: an unannotated parameter is
typed `:i64`, so `(defn f [b] …) (defn main [] (f false))` is rejected by the
frontend with `expression type mismatch: expected i64, got bool {:phase
:subset}` — on both ISAs, for every variant tried, including the tail-self-call
shape. A literal `false` cannot reach `emit-call`'s argument loop while the
`:bool` parameter boundary is closed. **Opening the boundary is what makes the
defect reachable**, which is the entire reason ADR 0221 required an execution
proof before admitting a type, and the reason that requirement had to be
honoured with emitted code rather than with a successful compile.

## Decision (superseded 2026-08-05 by ADR 0003)

*At the time:* `kotoba.verifier/native-boundary-type?` keeps its
`(not= :bool type)` guard. The widening is held until `kotoba-native`'s x86-64
argument emission is fixed.

*Now:* the guard is removed and the divergence is closed. The gate that pinned
the divergence has been flipped to pin the **agreement**
(`the-native-boundary-set-agrees-with-kotoba-kirs`), and still fails if either
side moves in either direction.

The verifier was deliberately **stricter than `kotoba.kir`** for one cycle, and
that divergence was pinned by a test asserting the two agreed on every other
boundary type and disagreed on exactly `:bool`. Holding it in a gate rather than
in prose is what made the hold survivable: the next agent found the ADR instead
of a crash, and the flip was a one-line edit rather than an archaeology problem.

Being stricter was sound in the only direction that matters — a verifier can
only reject — but it was not free, and the cost was named: for one cycle a
`:bool`-parameter module passed `kotoba.kir`'s target selection and was refused
later here as "runtime KIR function shape rejected" instead of at target
selection. That cost is now gone.

The widening was written and green on branch
`agent/verifier-bool-boundary-widening`, and landed unchanged (cherry-picked, not
rebased) as part of ADR 0003: the same one-guard removal, plus tests that admit
`:bool` alone, alongside every other boundary type in both orders, wrapped in
`[:option T]`/`[:result T E]`, and as a record field — with the negative half
(`:f64`, `:f32`, `:bytes`, `:vector-i64`, `:map`, a malformed table) still
refused, and with the `:closure-param-indexes` /
`:i64-pair-chain-param-indexes` refinements still i64-only.

## Consequences

- **Nothing changes in this repo's behaviour.** No admission is widened, no
  capability qualification flag is touched, no digest moves.
- The `kotoba-kir` dependency advances `a54916b` -> `8de6215`, which is required
  for the divergence test to see the widened predicate and is the correct
  current pin regardless.
- The murakumo sweep quantified what was being withheld. Measured over all 33
  `kotoba/*_core.kotoba`, identically on both ISAs: **14/33** compiled, **19/33**
  with the widening. ⚠ **Those figures are stale and are not comparable to
  ADR 0003's**, which measured 24/33 -> 30/33 against a later `kotoba-native`.
  A bare `N/33` is meaningless without the backend SHA beside it; see ADR 0003.
  The observation that mattered at the time survives: none of the unblocked
  modules writes a literal `false` in argument position — every `false` in them
  is in `if`-branch position — so the defect would not have bitten them on day
  one. That is luck, not a property, and it was not a reason to ship.
- **Left open at the time, resolved since**: (1) the x86-64 `if-let`
  argument-emission defect was fixed in `kotoba-native` `f6f29e9`, which
  collapsed all three copies of the walk into one `emit-pushed-arguments` keyed
  on `(seq remaining)` — including (2) the third site (the typed heap/cap-call
  loop), which that fix covered along with the other two.
- **Left open, still**: the untyped-encoding gap from kotoba-kir ADR 0221 is
  unchanged and still pinned by that repo — a module whose only typed feature is
  a `:bool` parameter is emitted as `:kotoba.hir/v2`, loses `:param-types`, and
  traps as `{:trap :value-type-mismatch :expected :i64}`. It is why every row in
  the table carries a `:string` parameter alongside its boolean. The ISA rows
  remain uncommitted to `compiler`, reproduced verbatim here and in ADR 0003.
- **Not attempted**: making this verifier reject the specific crashing shape.
  The bug is in an emitter, the verifier has no business encoding one backend's
  defects, and a gate that admitted `:bool` except where an argument happens to
  be spelled `false` would be exactly the kind of ratification this file's
  independent re-derivation exists to prevent.
