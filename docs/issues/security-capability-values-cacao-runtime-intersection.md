# Security: implement capability values and dynamic CACAO/runtime intersection

Architecture review finding: `F-003`
Severity: High
Owner: runtime/compiler implementation

## Problem

Static per-CID checks are strong for literal graph/model resources, but dynamic
resource arguments still need first-class capability values and runtime grant
intersection. `ADR-safe-capability-language.md` tracks this as S4b.

## Risk

Dynamic resource ids can force broad wildcard grants. That weakens least
privilege and makes runtime receipts less precise.

## Required work

- Add first-class `GraphReadCap`, `GraphWriteCap`, `InferCap`, and future host
  capability value concepts.
- Ensure effect rows are consistent with capability parameters.
- Compute CACAO/grant/local-policy intersection at host-call time.
- Record the concrete capability object in runtime receipts.

## Acceptance criteria

- Dynamic graph/model resource calls can be scoped without wildcard grants.
- Least-privilege policy generation avoids `*` for capability-valued flows.
- Runtime receipt records the concrete capability object used.
- `kotoba-lang/security` risk `R-007` has implementation evidence.

## References

- `kotoba-lang/security/docs/architecture-review-2026-07-01.md` finding `F-003`
- `kotoba-lang/kotoba-lang/docs/adr/ADR-safe-capability-language.md`
