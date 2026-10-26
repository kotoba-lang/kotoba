# ADR 0223: Validate checked HIR before lowering

**Status:** accepted
**Date:** 2026-08-09

## Context

`kotoba.kir/lower` previously trusted any map carrying an HIR format marker.
Malformed entry/export/effect relationships and private function fields could
cross the repository boundary and fail later in unrelated lowering code.

## Decision

Pin `kotoba-hir` and call `kotoba.hir/validate!` before inspecting or lowering
the module. The HIR repository owns envelope and annotation validity; this
repository continues to own HIR-to-KIR lowering and KIR semantics.

Focused test fixtures now construct the same complete checked envelope emitted
by semantic analysis. Missing format/module keys are contract errors rather
than an implicit request for legacy defaults.

## Verification

- `kotoba-hir`: 4 tests, 12 assertions
- observed compiler sample: 547 produced HIR values accepted, 0 rejected
- `kotoba-kir`: 120 tests, 524 assertions

## Consequences

Independent HIR producers fail at the boundary with `:phase :hir-validation`.
New HIR fields or annotations require an explicit contract version/change
instead of being silently ignored by KIR lowering.
