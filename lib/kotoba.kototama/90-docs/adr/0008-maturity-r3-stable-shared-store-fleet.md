# ADR-0008: R3 stable — shared-store multi-tenant fleet (not Raft)

**Status**: superseded (2026-09-07) — R3 is retired from this repo's ladder. The
shared-store fleet implementation and its `fleet-gate` moved to
[`kotoba-lang/fleet`](https://github.com/kotoba-lang/fleet) (T6 placement,
external to this tender). `kototama.guest/maturity-levels` has no `:r3` and
`kototama.guest-test/maturity-report-shape` asserts its absence, so the
"Doctor reports `:current :r3`" consequence below no longer holds; doctor
reports `:current :r2` with the status derived from
`kototama.browser/parity-score`. Kept for history; do not cite as current.  
**Date**: 2026-07-10  
**Landed on main**: `3b24afa` (merge `feat/r3-advanced-partial`)

## Decision

Declare **R3 (Fleet multi-tenant tender) = stable** under this honest definition:

> Ops-ready **local / shared-store** multi-tenant fleet: lease, budget, tick,
> governor, fence-gated claim, disk/B2 checkpoint, bounded daemon, tick audit,
> fleet-gate CI, and non-root staging-smoke.

Explicitly **out of scope** for this stable label:

- Raft / Paxos / multi-datacenter consensus
- Full aiueos fleet broker for every `actor:host` import kind

## Evidence

- `kbb -M:cli fleet-gate` (11 acceptance checks)
- `bash deploy/staging-smoke.sh` (packaging + gate + daemon + status/audit)
- CI: fleet-gate, daemon dry-run, packaging validate, staging-smoke
- aiueos GRANT/DENY E2E through `fleet-exec` + tender

## Consequences

- Doctor reports `:current :r3` with `:status :stable`
- Further work is optional hardening (broker surface, real multi-node ops),
  not a maturity-ladder promotion to invent consensus
