# ADR-0001: Own source semantic analysis outside compiler orchestration

- Status: accepted
- Date: 2026-08-09

## Decision

`kotoba-sema` owns the implementation that turns Kotoba source into checked
HIR. This includes the admitted reader, schema validation, type/effect checks,
capability elaboration, and semantic catalogs.

The compatibility namespaces under `kotoba.compiler.*` are retained during
the extraction. The canonical public entry is `kotoba.sema`; namespace renaming
is deliberately separate from repository ownership so downstream consumers do
not have to migrate atomically.

`kotoba-sema` may depend on `kotoba-hir` and the KIR value contracts used while
checking source. It must not depend on the compiler orchestrator. The compiler
depends on this repository and no longer carries duplicate semantic sources.

## Consequences

- Source semantics can evolve and test independently of orchestration.
- The dependency direction is acyclic: compiler -> sema -> KIR -> HIR.
- Grammar and capability catalogs remain language-authoritative vendored data;
  sema owns their runtime loading and enforcement.
- A future namespace cleanup can occur as a separately reviewed compatibility
  migration.
