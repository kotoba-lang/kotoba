# ADR-0005: Transfer width and window tier are two axes

- Status: accepted
- Date: 2026-09-02

## Context

`kernel-memory-operations` had seven entries, and four things were true of them
that nobody had decided:

- `kernel-load-u8` could name a 16 KiB window; `kernel-store-u8` could not.
- `kernel-load-u32` and `kernel-store-u32` could name neither the 4 KiB nor the
  16 KiB tier: they were pinned to 512 bytes.
- There was no 16-bit access, which is what a PCI vendor/device ID pair and most
  legacy device registers are.
- There was no 64-bit access, which is what a descriptor ring pointer is.

None of those was written down as a judgement. Each was a consequence of the
table having been extended one caller at a time.

## Decision

The table is **four transfer widths by four window tiers by load/store** —
`kernel-{load,store}-u{8,16,32,64}` with tiers `""`, `-4k`, `-16k`, `-64k` —
plus the eight-member element-indexed slice family
`slice-{load,store}-u{8,16,32,64}` from amu ADR 0285. Forty-three entries with
`kernel-subregion` and the lock pair.

**They share one table on purpose.** `kernel-memory-op?` reads it, so a new
width inherits the region-provenance taint on its first argument without a line
being written for it. Adding a family beside it would mean the provenance walk
grew a second list, and the two lists would be free to diverge — which is the
shape the arity table itself was already in.

The slice family differs from the window family in what its `length` and `index`
**count** (elements rather than bytes) and in its ceiling (an address-space bound
rather than a window profile). Neither difference is visible in the arity or in
the provenance rule, which is precisely why they belong in the same table here
and in different profile maps in `kotoba.kir`.

## Evidence

`kbb -M:test` — 122 tests, 708 assertions, 0 failures (after merging
`kotoba-lang/main`, which brought the sysops atomics and the UEFI boundary
spellings into the same table).

The new namespace `kotoba.compiler.kernel-memory-widths-test` covers all forty
operations for arity, `:i64` typing, reserved-name status, the provenance taint
(`:tainted` = `#{0}`, `:abi-boundary` = `['base]`), and the computed-base
refusal.

It counts **per family**, not as a table total. A total was written first and
went red on the merge that brought the general atomics in — a test that fails
because a different stream did its own work correctly is measuring the wrong
thing.

Discriminated in both directions rather than asserted:

| deliberate break | result |
|---|---|
| `slice-{load,store}-u32` removed from the table | 8 failures / 3 errors — the arity assertions report `"operation has no admitted lowering"` instead, which is the *different* failure an absent operation produces |
| `kernel-load-u16-16k` given arity 4 | 3 failures / 3 errors, and the computed-base test reports `"kernel memory operation arity mismatch"` instead of its own reason |
| restored | 0 failures |

The first break is the one worth recording: an operation missing from the table
does not merely fail an arity check, it fails a *different* check. The test
pins the message rather than asserting that something threw, so the two are
distinguishable.

## Upstream

kotoba-kir `7aa6d2d` (pin bumped here), which carries the oracle semantics: the
window checks, the alignment rule, and `slice-memory-profile`. Follows
kotoba-gmir `cb935ce`, kotoba-mir `37345aa`, kotoba-codegen `c024b11`.
kotoba-native follows with the encodings.
