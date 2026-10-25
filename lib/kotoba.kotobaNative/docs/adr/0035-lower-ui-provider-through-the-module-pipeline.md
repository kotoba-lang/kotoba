# ADR-0035 — Lower the UI provider through the module pipeline

- **Status:** Accepted
- **Date:** 2026-08-26
- **Owner:** `kotoba-lang/kotoba-native`

## Decision

`typed-capability-kinds` maps the sealed ui-v1 commit pair to `:ui-commit-v1`
and the event pair to `:ui-event-v1`. UI records travel the existing
provider pair-chain path. `typed-set-*` rewrites to the vector host table,
skipping the type descriptor: a set handle is one word, the same as
`vector-i64`.

A module that calls capability 9 or 10 with those exact kinds is a
provider-boundary module. This repository still does not execute compiled
programs; process proof lives in amu's kexe loader.
