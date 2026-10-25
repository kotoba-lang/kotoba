# ADR-0001: arXiv organism actor

- **Status**: Accepted
- **Date**: 2026-06-28
- **Parent ADR**: `orgs/kawasakijun/docs/adr/0023-organism-actor-first-service-app-yorishiro.md`

## Decision

`org-arxiv-kotoba` represents arXiv-facing work as an organism actor with two
interfaces:

- dialogue: consultation, explanation, categorization advice, state summaries
- functional: capability dispatch with risk policy, approval, route selection,
  and receipt logging

Concrete UI/API automation remains below the actor as skill recipes executed
through yorishiro surfaces.

