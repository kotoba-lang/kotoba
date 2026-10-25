# ADR 0002: `string-contains?` and `string-replace-all` verify as target-independent string operations

Status: accepted

Companion: `kotoba-kir` ADR 0222, which opens the other of the two gates
described here. Neither ADR is useful without the other.

## Context

This verifier deliberately re-derives its own operation tables instead of
importing anyone else's. That independence is the reason it is worth running —
and it is also why it silently became the second of two gates refusing
`string-contains?` and `string-replace-all` before either could be emitted.

`kotoba.native.string-search` (kotoba-native `5df4d85`, its ADR 0002) gave both
operations a lowering on both native ISAs, as one shared source rewrite into
the four string context callbacks already listed in `string-operations` —
`string=?`, `string-concat`, `string-substring`, `string-code-point-at` — plus
i64 arithmetic. It cost no new callback, no context ABI bump and no new value
representation.

It moved nothing. Measured 2026-08-05 over murakumo's 33 shipped
`kotoba/*_core.kotoba` modules, identical on `x86_64-kotoba-v1` and
`aarch64-kotoba-v1`:

| kotoba-native | gates | cores compiling |
|---|---|---|
| `b65fd0d` (before the lowering) | as shipped | 16/33 |
| `5df4d85` (lowering landed) | as shipped | **16/33 — moved by zero** |
| `5df4d85` | this table opened, `kotoba-kir`'s gate still closed | **16/33** |
| `5df4d85` | `kotoba-kir`'s gate opened, this table still closed | **16/33** |
| `5df4d85` | both opened | **24/33** |

The two single-gate rows were measured, not inferred. Either gate on its own is
worth exactly as much as no lowering at all.

## Decision

Add `string-contains? 2` and `string-replace-all 3` to `string-operations`.

They belong in **that** table, and not in some native-only one, because the
stance `string-operations` already takes is the right one and is already
written down beside it: `string-substring` is admitted here "as the
target-independent operation it is", with the narrowing to what a particular
backend can emit left to that backend, because "encoding a backend restriction
here would make this verifier ratify one target's limits."

The same reading applies with more force to these two. They are not new
capabilities. `kotoba-wasm` has been their semantic oracle since long before
either had a native lowering, and `kotoba.kir/execute` runs them. What was
missing was a native *emission*. This verifier was never ratifying a native
limit on purpose — it was refusing an operation whose contract it already had,
because nobody had added the row.

The arities are the KIR arities, independently re-derived like every other
entry in this file, and they coincide with the shapes both backends dispatch on
(`x86_64.cljc` 1189/1192, `aarch64.cljc` 988/991). A different arity has no
lowering and is refused by the arity check this table drives.

## Consequences

Eight of murakumo's shipped cores now compile on both ISAs: `deploy_plan`,
`fleet_inventory`, `kekkai_gate`, `overlay_crypto`, `persist`,
`provision_plan`, `secret`, `tunnel`.

No digest moves. An operation table is not part of the `select-keys`'d program
`:kir-sha256` digests — verified rather than assumed, because an earlier
attempt in this effort to change a KIR *signature* shape did move the digest of
every module using it on every target. The 60-case `lang-conformance` golden
document reports `ok? true` with 0 mismatches over 60/60 live cases, and all 33
murakumo cores compiled to `wasm32-kotoba-v1` produce byte-identical KIR
digests before and after.

`reconcile_plan_core` is the ninth string-searching core and is **not**
unblocked. It is refused by a different check in this same file: the
function-boundary type set here still excludes a bare `:bool` parameter, which
`kotoba-kir` ADR 0221 admitted on its side. The widening that closes that gap
is written and green on the branch `agent/verifier-bool-boundary-widening`, and
is **deliberately held unmerged** pending an x86-64 codegen fix in
kotoba-native — see ADR 0001, which records that decision and the reasoning for
it. This change touches a different function in the same file and does not
disturb it.

The remaining eight failures split into two reason classes, unchanged by this
work and identical on both ISAs:

- **`runtime KIR function shape rejected`** — `connect`, `dash_state`,
  `infer_waste`, `overlay_stream`, `reconcile_plan`, `report`.
- **`record-get is only supported directly over a matching record-new
  construction on the native backend`** — `infer_plan`, `infer_schedule`,
  `task_plan`.

## Falsification

`kotoba.verifier-string-search-test` asserts on the rejection **message**, not
merely on the fact of rejection, and that distinction is the whole test.

Before this change every unlowered arity was already refused — by the terminal
`runtime KIR operation rejected`, because the symbol appeared in no table at
all. A test asserting only "this is rejected" would therefore have passed
identically with the change reverted: a false green of exactly the kind three of
the four previous agents in this effort produced. Requiring the message to be
`runtime KIR string operation arity rejected` is what makes it fail when the
entries are removed.

Confirmed by removal:

| removal | failures | deftests hit |
|---|---|---|
| both entries deleted | 6 | `both-operations-verify`, `an-unlowered-arity-is-refused-by-the-arity-check` |
| arities transposed (`string-contains? 3`, `string-replace-all 2`) | 6 | adds `the-operands-are-still-verified` |

## Alternatives considered

**A separate native-only table.** It would have encoded a backend's reach into
this verifier as if it were the contract, which is precisely what the existing
comment above `string-operations` says not to do.

**Wait for the `kotoba-kir` gate first and land these together.** They cannot
be landed together — they are separate repositories — and each is individually
green and individually inert. `kotoba-kir` ADR 0222 landed first because this
repository depends on that one; the order is recorded so that a bisect across
the pair reads correctly.
