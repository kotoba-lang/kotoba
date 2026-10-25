# `@etzhayyim/pregel` — Pregel BSP runtime

Minimal Pregel (Bulk Synchronous Parallel) super-step runtime for the
etzhayyim open agent fleet. Extracted from the LangGraph patterns used by
the open-UNSPSC 18,343-agent fleet and the IEC 61499 microgrid demo.

## Status

Tranche F Phase 2 scaffolding (skeleton package shell only). Per
ADR-2605172400, the Pregel runtime moves from vendor to etzhayyim because
it is pure compute primitive — no PII custody, no operator liability, no
fiat settlement. The unispsc agent fleet already migrated in commit
`f8358383`; the runtime itself follows here.

Phase 3 (content copy) will bring in:

- `cell_loader.py` / `pregel_runner.py` patterns (currently in vendor
  `60-apps/etzhayyim-project-open-ot/orchestrator/`)
- LangGraph integration glue
- atproto MST / IPFS / Base L2 checkpointer adapter (per ADR-2605171800
  anchor pipeline)

## kotoba constraint

Per ADR-2605172000, this package MUST NOT import `risingwave`, `kysely`,
`pg`, or open SQL connections directly. Checkpointer state goes to:

- atproto MST (durable, federated via PDS firehose)
- IPFS pin (CAR shard, content-addressable)
- Base L2 anchor (Merkle root, immutable batch)

If a Pregel computation needs a centralized index, the consumer (vendor
side) provides it externally.

## See also

- [ADR-2605171800 LangGraph Pregel → MST → IPFS → Base L2 anchor pipeline](https://github.com/etzhayyim/root/blob/main/90-docs/adr/2605171800-langgraph-mst-ipfs-l2-anchor-pipeline.md)
- [ADR-2605171300 Open-UNSPSC Generative Agent Fleet](https://github.com/etzhayyim/root/blob/main/90-docs/adr/2605171300-open-unispsc-generative-agent-fleet.md)
- [ADR-2605172000 etzhayyim kotoba substrate](https://github.com/etzhayyim/root/blob/main/90-docs/adr/2605172000-etzhayyim-kotoba-substrate.md)
- [ADR-2605172400 etzhayyim/vendor 3-axis split rule](https://github.com/etzhayyim/etzhayyim-root/blob/main/90-docs/adr/2605172400-etzhayyim-vendor-three-axis-split-rule.md) (vendor canonical)
