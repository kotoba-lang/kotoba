# ADR 0221: A `:bool` parameter at a function boundary

Status: accepted

Supersedes the `:bool`-parameter exclusion in `compiler` ADR 0219 /
superproject ADR-2608052000 ("native record parameters, murakumo cores").

## Context

ADR 0219 widened both native admission gates — `kotoba.kir`'s
`only-native-word-typed-features?` and, independently, `kotoba.verifier`'s own
re-derivation — to admit `:i64`, `:string`, `:keyword`, `[:option T]`,
`[:result T E]` and records at a function boundary. It deliberately withheld a
bare `:bool` PARAMETER, and gave a measurement as the reason:

> Measured: `kotoba.kir/execute` itself refuses one with
> `{:trap :value-type-mismatch :expected :i64 :position {:parameter b}}`. That
> gap is in the INTERPRETER, not either backend. Admitting the type while the
> oracle cannot run one would ship a boundary nothing had executed.

The refusal to admit an unexecuted type was right. The diagnosis under it was
not.

Re-measured 2026-08-05 on `a54916b`, the trap reproduces exactly — and is
reproduced permanently by `the-untyped-encoding-still-loses-a-bool-parameter`
in `kotoba.kir-bool-parameter-test`. But it is not the interpreter refusing a
`:bool` parameter. It is the interpreter correctly refusing a host boolean
where the KIR it was handed **declares `:i64`**, because that KIR carries no
`:param-types` table at all and `invoke-function` defaults an absent one to
`:i64` per parameter.

The table is absent for a reason that lives two repos away.
`kotoba.kir/lower` keeps `:param-types` only for `:kotoba.hir/v3`, and
`kotoba.compiler.frontend`'s `typed-values?` excludes `:bool` by name — its own
comment reads "`:bool` literals are plain 0/1 words, not typed values". So a
module whose ONLY typed feature is a `:bool` parameter is emitted as
`:kotoba.hir/v2` and loses its parameter types on the way down.

Where the table IS present — a `:bool` parameter alongside any other typed
feature, which is precisely the shape this gate governs — `execute` runs a
`:bool` parameter, and always could. Measured on the unmodified `a54916b`
interpreter: 9 of the 10 tests added here pass against the old gate; only the
gate test itself fails.

## Decision

`kotoba.kir/native-boundary-type?` admits `:bool`. The change is the removal of
one `(not= :bool type)` guard — `native-word-value-type?` has listed `:bool`
since it was written, and that guard was what withheld it.

It is admitted only because the oracle demonstrably executes one first.
`test/kotoba/kir_bool_parameter_test.cljk` executes a `:bool` parameter in every
position one can occupy: crossing the entry boundary, as an `if` test, through
`bool-not`, through `=`, rebound by `let`, passed into another function's
`:bool` parameter, populating a `:bool` record field, and returned as a boxed
`:bool` result. It also pins the negative — the word `1` is refused at the entry
boundary — and pins the untyped-encoding trap above, so the gap that remains is
measured rather than remembered.

The boundary convention is unchanged and now symmetric in both directions: a
host boolean is what ENTERS (the argument check requires `boolean?`), a host
boolean is what LEAVES (`box-bool`), and inside a module `:bool` stays a plain
0/1 word — both spellings decoded by the single `kotoba-false?`. This is the
convention `kotoba.wasm.core`'s export wrapper, the restricted-ESM emitter and
`kototama.native.executor` already share; nothing new is introduced.

## Consequences

- Golden digests do not move. `:kir-sha256` digests the `select-keys`'d
  program, and an admission predicate is not in it. Verified against a live
  compile: 60/60 cases, zero mismatches, and the dual-backend conformance run
  is 60/60.
- 470 assertions before, 499 after. The gate test was falsified against the
  unmodified predicate before being trusted.
- **`kotoba.verifier` is now the blocker, and this is not a no-op.** It
  re-derives the same boundary set and still excludes `:bool`, so a
  `:bool`-parameter module now passes target selection and is refused later.
  Measured end to end on `(defn label [s :string b :bool] :string …)` for
  `--target x86_64`:

  | | result |
  |---|---|
  | base `a54916b` | `:error :target` — "typed values currently require … the qualified native one-word slice" |
  | this change | `:error :verify` — "runtime KIR function shape rejected" |
  | this change + `kotoba.verifier/native-boundary-type?` widened in-process | `{:ok true :target :x86_64-kotoba-v1}`, `.kexe` written |

  So the required follow-on is one predicate in `kotoba-verifier`, dropping its
  own `(not= :bool type)`. Nothing in `kotoba-native` needs changing: with only
  the verifier patched, native codegen produced an artifact.
- Native *machine-code* execution of a `:bool` parameter is still unproven here.
  `verify-native-artifact!` re-executes through this interpreter, not through
  the emitted code, so compile success is not execution evidence. That proof
  belongs with the `kotoba-verifier` follow-on.
- The untyped-encoding gap stays open, by choice. Closing it means changing what
  `typed-values?` classifies or what `lower` keeps, and either moves
  `:kir-sha256` for every affected module on every target, including its wasm
  bytes. That is a compiler decision with its own digest accounting, not
  something to do while widening a predicate.
- Unrelated observation, recorded so it is not rediscovered as a bool problem:
  an i64 operation applied to a host boolean (`(+ b 1)` on a `:bool` parameter)
  escapes as a raw host `ClassCastException` rather than a Kotoba trap. The
  frontend's type checker makes this unreachable from source, so it is not
  gated here, but a host exception crossing the language boundary is a defect
  in its own right.
