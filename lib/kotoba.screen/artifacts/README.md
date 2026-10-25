# artifacts — the host bridge consumes this

`screen-gate-aarch64.kexe` is the compiled judgment gate the resident host
loads. Built 2026-09-03 with amu (sema 219f14f) from `src/screen/` + this
directory's `gate.kotoba`, `--target aarch64 --jvm-free`, policy
`{:allow #{[:cap/call 31]}}`.

## What the host may call (all PURE, i64 in / i64 out)

| export | signature | semantics |
|---|---|---|
| `chronicle-keep?` | `(prev-combined, new-combined) -> {0,1}` | the chronicle dedup rule: 0 = drop the new frame (same combined digest), 1 = keep |
| `gate-frame-unchanged?` | `(prev-digest, prev-app, new-digest, new-app) -> {0,1}` | 0 = changed (keep), 1 = unchanged (drop) |
| `gate-judge-press` | `(ref-id, expect-digest, node-count) -> {0,1}` | the act shape gate: 1 = spend an act grant, 0 = refused by shape |
| `gate-version` | `() -> i64` | 1 |

## Two execution routes, one answer (measured 2026-09-03)

1. **KIR interpreter** (`kotoba.kir/execute` over the `:program` inside the
   kexe) — the css-parity route, runs on any JVM host with kotoba-kir.
2. **Native** (`kototama.native.executor/execute`, signed artifact +
   measured loader, aarch64) — same exports, same results, measured
   `:status :ok` on both routes with matching values
   (keep-same 0 / press-ok 1).

## sha256

Rebuild deterministically and compare (`host/rebuild-gate.sh`):

```
shasum -a 256 screen-gate-aarch64.kexe
```

The kexe carries its own `:sha256` over the code stream; the verifier
re-derives it before every signed execution, so a tampered artifact fails
closed at load.

## Note on `amu extract-native`

The current amu main pin refuses `extract-native` with
`native export table rejected` (kotoba-mir pin regression, upstream ADR
0288 — reproduces with no screen code at all). The signed-execute path
through kototama-native verifies the same artifact fine.
