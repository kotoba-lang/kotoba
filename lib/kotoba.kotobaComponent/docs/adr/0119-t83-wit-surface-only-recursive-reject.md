# ADR 0119: T8.3 — WIT recursive-schema reject is surface-only

- Status: Accepted
- Date: 2026-08-01
- Depends: component-model `:recursive-schema :reject-v1`; provider W4 record-kv ADRs 0250–0255

## Context

Ops W4 packages use recursive sealed ADTs (`:edn/node` atom|entry|pair) as
**guest-internal** values, then print `:string` EDN at the kit boundary.
`kotoba.component.wit/emit` previously called `reject-recursive-schemas!` on
**all** KIR schemas and emitted every schema into `interface types`, so any
Component twin of a W4 package failed with `recursive schema has no WIT
representation` even when exports were only `:string` / `:i64`.

WIT still cannot represent sized recursive records. The bug was scope: internal
ADTs that never cross Canonical ABI should not be forced onto WIT.

## Decision

1. Collect **WIT-surface** schemas = transitive refs from export param/result
   types and capability request/result types only.
2. `reject-recursive-schemas!` runs on the surface set alone.
3. Emit `interface types` from the surface set alone (internal recursive ADTs
   omitted).
4. Exporting a recursive type still fails closed (`:reject-v1` unchanged for
   surface).

## Evidence

- `component_wit_test`: internal recursive + string export emits; surface
  recursive still throws
- Unlocks provider Component twins of W4 record-kv string codecs

## Related

- T8.3 residual host I/O / Component packaging; provider ADR 0250–0255
