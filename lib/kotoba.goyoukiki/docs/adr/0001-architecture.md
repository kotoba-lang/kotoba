# 0001: goyoukiki architecture

**Status**: accepted
**Date**: 2026-07-06

## Context

See the superproject ADR
`90-docs/adr/2607070200-kotoba-lang-goyoukiki-procurement-signal-actor.md`
(the authoritative record — Context/Decision/Consequences in full) and
`../DESIGN.md` (the detailed design write-up). This file is the repo-local
pointer other kotoba-lang actors (kekkai/teian/koyomi/tayori) also keep at
this path, so a reader inside this checkout doesn't have to go find the
superproject to get oriented.

## Decision

match-LLM ⊣ ProcurementGovernor, propose-only, two-flow langgraph-clj
StateGraph (`ingest` / `assess`), Phase 0→3, CACAO self-mint identity. See
`../DESIGN.md` §1-5 for the full contract and `../../README.md` for the file
layout table.

## Consequences

Same charter shape as `../../teian` and `../../koyomi` — see those repos'
own `docs/adr/0001-architecture.md` for the shared precedent this follows.
