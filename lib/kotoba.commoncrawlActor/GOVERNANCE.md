# Governance

`kotobase-commoncrawl-actor` is an OSS ingestion actor for net-kotobase
(`kotobase.net`). Governance covers both code and operational scope.

## Maintainers

Maintainers may merge changes that preserve these invariants:

- The LLM extraction step (`commoncrawl.llm`) cannot directly commit to
  net-kotobase — every proposal passes through `commoncrawl.policy`
  first.
- A domain outside the configured seed list, or on the exclude list, can
  never be fetched/ingested regardless of what any other code path
  computes — this is enforced in `commoncrawl.policy`, not by convention.
- The per-tick fetch budget is enforced both by the outer loop
  (`commoncrawl.loop`) and, defense-in-depth, by the Governor itself.
- Every graph run leaves exactly one append-only ledger fact (commit or
  hold) — no silent no-op.
- The actor's CACAO identity seed never leaves the process/`.commoncrawl/`
  file it's persisted in.

## Decision Records

Architecture decisions live in `docs/adr/`. The parent-workspace ADR is
`90-docs/adr/2607192200-net-kotobase-commoncrawl-web-search-integration.edn`
in the `com-junkawasaki/root` superproject; this repo's own ADRs are local
implementation decisions, related to (not superseding) that one.

## Scope Governance

Growing the seed list (`resources/seeds.edn`) is a data change anyone can
propose via PR, but merging one is a scope decision, not just a code
review — reviewers should confirm the added domain is real, has a
legitimate reason to be ingested, and doesn't turn this actor into a bulk/
automated crawler (explicitly out of scope, see the parent ADR).
