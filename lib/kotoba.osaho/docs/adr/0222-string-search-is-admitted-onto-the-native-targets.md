# ADR 0222: `string-contains?` and `string-replace-all` are admitted onto the native targets

Status: accepted

Companion: `kotoba-verifier` ADR 0006, which opens the second of the two gates
described here. Neither ADR is useful without the other.

## Context

`kotoba.native.string-search` (kotoba-native `5df4d85`, its ADR 0002) gave
`string-contains?` and `string-replace-all` a lowering on **both** native ISAs
— one shared source rewrite, not two backends — by expressing search and
replacement in terms of the four string context callbacks the native slice has
always had: `string=?` (112), `string-concat` (120), `string-substring` (136),
`string-code-point-at` (144). No new callback, no context ABI bump, no loader
change, no new value representation.

That work was commissioned on the premise that the backend was the blocker.
**The premise was wrong**, and establishing that was its main result. Both
operations are refused *twice, before anything is emitted*:

1. here, by `only-native-word-typed-features?`, because both symbols are in
   `non-string-typed-ops`; and
2. again by `kotoba.verifier/string-operations`, which re-derives its own
   operation table from scratch and listed neither.

Measured 2026-08-05 over murakumo's 33 shipped `kotoba/*_core.kotoba` modules,
identical on `x86_64-kotoba-v1` and `aarch64-kotoba-v1`:

| kotoba-native | gates | cores compiling |
|---|---|---|
| `b65fd0d` (before the lowering) | as shipped | 16/33 |
| `5df4d85` (lowering landed) | as shipped | **16/33 — moved by zero** |
| `5df4d85` | this gate opened, verifier's still closed | **16/33** |
| `5df4d85` | verifier's opened, this one still closed | **16/33** |
| `5df4d85` | both opened | **24/33** |

The middle two rows are the load-bearing ones and they were measured, not
reasoned about. A landed lowering behind two independent closed gates is worth
exactly as much as no lowering at all, and opening either gate on its own is
worth exactly as much again. Nothing in the compiler reports this: the failure
a caller saw was `typed values currently require the kotoba-script web target,
typed Wasm/CLJS target, or the qualified native one-word ... slice`, which
names a target restriction and gives no hint that the operation has a working
emitter sitting behind it.

## Decision

Admit `string-contains?` (arity 2) and `string-replace-all` (arity 3) in
`only-native-word-typed-features?`, as two clauses placed with the other
per-operation admissions.

Both symbols **stay in `non-string-typed-ops`.**
`only-cljs-provider-typed-features?` shares that set and has no lowering for
either operation; removing the symbols would silently widen the CLJS gate as a
side effect of a change about native. This is the identical arrangement
`i32-operations` and the `vector-*` families already use, and the comments at
those clauses already say why — the exception belongs to the target that can
emit it, not to the shared set.

The arities are pinned rather than left to `every? walk args`. They are the
exact shapes both backends dispatch on (`x86_64.cljc` 1189/1192,
`aarch64.cljc` 988/991); any other arity has no lowering and must keep failing
here rather than reaching a backend and being reported from further in.

The operands continue to be walked. An admitted operation must not become a
laundering channel for an operand the one-word slice cannot represent.

## Consequences

Eight of murakumo's shipped cores stop failing here and now compile on both
ISAs: `deploy_plan`, `fleet_inventory`, `kekkai_gate`, `overlay_crypto`,
`persist`, `provision_plan`, `secret`, `tunnel`. With the gates open and the
backend **unmodified**, these had moved from failing in this namespace to
`operation not implemented on this backend`; with `5df4d85`'s lowering they
emit.

**No digest moves.** `:kir-sha256` digests the `select-keys`'d program, and an
admission predicate is not part of it — but that was verified rather than
assumed, because an earlier attempt in this same effort to change a KIR
*signature* shape did move the digest of every module using it, on every
target including its wasm bytes. Two measurements:

- the 60-case `lang-conformance` golden document (`pilot-golden.edn`, KIR +
  wasm32 digests) reports `ok? true`, 0 mismatches, 60/60 live cases; and
- all 33 murakumo cores compiled to `wasm32-kotoba-v1` produce **byte-identical
  KIR digests** before and after this change — a stricter check, since it
  includes the eight modules that actually contain these operations.

`reconcile_plan_core` is the ninth string-searching core and is **not**
unblocked. It is refused later, at `verify-native-artifact!`, for an unrelated
reason: `kotoba.verifier` re-derives its own function-boundary type set and
still excludes a bare `:bool` parameter, which this repo's ADR 0221 admitted on
its side. A branch closing that exists in kotoba-verifier and is deliberately
held unmerged pending an x86-64 codegen fix in kotoba-native; it is not part of
this change.

The remaining eight failures split into two reason classes, unchanged by this
work and identical on both ISAs:

- **`runtime KIR function shape rejected`** (`:verify`) — `connect`,
  `dash_state`, `infer_waste`, `overlay_stream`, `reconcile_plan`, `report`.
- **`record-get is only supported directly over a matching record-new
  construction on the native backend`** — `infer_plan`, `infer_schedule`,
  `task_plan`.

## Falsification

Each new assertion was confirmed to fail when the thing it claims to pin is
removed — three of the four previous agents in this effort found a false green
this way, so it is done per-clause rather than once.

| removal | failures | confined to |
|---|---|---|
| both clauses deleted | 6 | `both-operations-are-admitted-on-native`, `a-let-binding-does-not-change-the-answer` |
| arity conjuncts dropped (`(= op 'string-contains?)` alone) | 4 | `an-unlowered-arity-is-still-refused` |
| both symbols deleted from `non-string-typed-ops` | 8 | adds `cljs-still-refuses-both-operations` |
| `(every? walk args)` replaced by `true` | 4 | `the-operands-are-still-walked` |

The second row is the one that mattered. An unlowered arity is refused with or
without the arity conjunct — nothing else in this predicate would have caught
it either — so an assertion that merely said "rejected" would have passed with
the change reverted. It fails only because the conjunct is what refuses it, and
that was checked by removing exactly that conjunct.

## Alternatives considered

**Delete the two symbols from `non-string-typed-ops`.** One line instead of
two clauses, and it opens this gate — but it opens the CLJS gate with it, for
operations CLJS does not lower. Rejected for the reason the `i32` and
`vector-*` clauses were written the way they were.

**Admit the operations with no arity bound.** Simpler, and every arity the
frontend can produce is one of the two. But this predicate also runs over KIR
the verifier treats as hostile, and an unbounded admission would send a shape
with no lowering into a backend to be reported from a worse place.

**Wait for the CLJS lowering so the shared set could be narrowed.** That is the
coherent end state and remains open. It is a different change, in a repo this
one does not own, and blocking eight shipped cores on it is not a trade worth
making.
