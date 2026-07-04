# Historical Rust architecture, crates & performance

> This document is a **design-vocabulary reference**, not current source. It
> describes the pre-migration Rust implementation of the kotoba database —
> `*.rs` file references below are historical pointers into the Rust
> workspace removed from this repository (`604896171b`, 2026-07-01), not
> paths that exist here today. The design itself is still the target for the
> CLJC-native rebuild tracked in
> [ADR-2607022600](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607022600-kotoba-database-crates-cljc-migration-roadmap.md).
>
> Per [ADR-2607032500](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607032500-kotoba-kotobase-clojure-datomic-relationship.md)
> (`kotoba : kotobase = Clojure : Datomic`), the persistent, distributed,
> Datalog-queryable database this document describes is not this repository's
> identity — that lives in [`kotoba-lang/kotobase`](https://github.com/kotoba-lang/kotobase)
> and its umbrella of sibling repos (`prolly-tree`, `commit-dag`,
> `quad-store`, `kqe`, `kotobase-engine`, `kotobase-client`,
> `kotobase-cljc-worker`). This repository (`kotoba-lang/kotoba`) is the
> language. The content below is kept because the same crate names, roles,
> and numbers are referenced throughout other ADRs as a shared vocabulary,
> and because the benchmark numbers remain the best available evidence of
> what the CLJC rebuild needs to match.

## Crates (historical Rust design record)

| Crate              | Role                                                                       |
|--------------------|----------------------------------------------------------------------------|
| `kotoba-core`      | CIDv1 dag-cbor sha2-256, KAIS 8-bit frame, Prolly Tree                     |
| `kotoba-kse`       | Journal (Merkle WAL), Vault (CDC chunker), Topic, Shelf, AgentIdentity     |
| `kotoba-query`       | Datalog engine, Arrangement (EAVT/AEVT/AVET/VAET), Delta, MV               |
| `kotoba-dht`       | Source Chain, Warrant, Neighborhood (DHT)                                  |
| `kotoba-net`       | libp2p QUIC/Noise/GossipSub                                                |
| `kotoba-auth`      | CACAO chain (depth-2), multi-graph grants, EdDSA verify, did:key, Passkey  |
| `kotoba-graph`     | Datom projection API, SPARQL 1.1 (BGP/Filter/Union/Optional/Group/Path/Service/…), Datalog cold, CID-MV cache, Commit DAG, N-hop DESCRIBE |
| `kotoba-vm`        | Invoke/Result ChainEntry, CALL_FOREIGN bridge                              |
| `kotoba-llm`       | Weight blob (FP8), LoRA Delta, KV-cache, WebGPU train + infer (Gemma 4)     |
| `kotoba-runtime`   | WASM Component Model host: WasmExecutor + UdfExecutor + WIT bindings       |
| `kotoba-store`     | BlockStore: Memory, Kubo HTTP, BudgetedBlockStore LRU, TieredBlockStore, DistributedBlockStore multi-peer |
| `kotoba-store-web` | Browser IndexedDB block store (wasm32)                                     |
| `kotoba-crypto`    | AEAD (AES-256-GCM), HKDF, key wrap                                         |
| `kotoba-signal`    | Signal Protocol (X3DH + Double Ratchet + MLS)                              |
| `kotoba-ingest`    | Gmail OAuth2 poll + RFC 2822 parse + E2E encrypt → Datom projection        |
| `kotoba-server`    | XRPC / MCP endpoints (kg.ingest / kg.ingest_batch / kg.query / kg.sparql)  |
| `kotoba-cli`       | `kotoba` binary (init, serve, demo, bench, sparql, …)                      |
| `kotoba-guest`     | WASM guest SDK (WIT bindings for kotoba nodes)                             |
| `kotoba-edn`       | SSoT EDN reader (Clojure/Datomic wire format) — the shared data/source reader |

## Architecture

The canonical spine is one content-addressed chain — **Datom log → ProllyTree
indexes → CommitDag → blocks** — with IPFS and B2 as export tiers, not the
system of record:

![kotoba Datomic-over-IPFS architecture](kotoba-datomic-architecture.svg)

**① Canonical write path** — `kg.ingest`/`transact` →
`QuadStore::assert_datom` (`kotoba-graph/src/quad_store.rs`) records the exact
5-tuple `Datom{e,a,v,t,added}` in `pending_datoms`; a short window later
`commit()` builds the EAVT/AEVT/AVET/VAET (+ `datom_*` + append-only **TEA**)
**ProllyTrees** (`kotoba-core/src/prolly.rs`) — probabilistic chunking
(`blake3(key)&0xFF==0`) + path-copy so each commit writes only the delta; nodes
are **DAG-CBOR/IPLD** (`Internal [(k, child-CID)]` tag-42 links) addressed by
`sha2-256(dag-cbor) → CIDv1`. Blocks pack into one **CARv1** bundle and a
`Commit{root,index_roots,prev,seq}` block is appended to the **CommitDag**.
**The CommitDag is the write-ahead log** — an immutable, parent-linked,
content-addressed chain whose durability boundary is the atomic head-ref update
(git / Datomic semantics); restart loads the head + checkpoint and walks commits
since, no second-log replay.
> Pruned (per [ADR-2606041151](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2606041151-kotoba-commitdag-as-wal-and-incremental-query-tier.md)):
> the old per-assert **Journal WAL** (4-topic double-write) and **Kubo-as-durable-tier**
> — the CommitDag already is the WAL; the Journal was a redundant double-write and the
> ~30 s startup-replay bottleneck.

**② Query — Datomic first-tier** — the 4-index model is tier-1: BGP routing does
direct index scans (EAVT point lookup ~180 ns, AVET, VAET reverse) over the
ProllyTree, and an incremental **MaterializedView** (`kotoba-query/src/mv.rs`,
maintained per commit Δ) serves recurring/Datalog queries without re-evaluating
from scratch. `kg.sparql` (SELECT/ASK/DESCRIBE/CONSTRUCT/UPDATE/SERVICE) is the
auxiliary RDF surface over the same indexes; `db_before`/TEA give Datomic-style
`as-of` time travel. All queries run over the IPFS-backed substrate — the hot
Arrangement is only an optimisation (cache).

**③ Block store — kotoba is its own IPFS block store + pinner** — the durable hot
tier is an embedded, in-process store (direct disk, µs–ms) and kotoba holds pins
itself (a flag in its own store, no `pin/add` RPC), removing the HTTP-RPC hop
(~35× ingest). Sealed commits **export asynchronously**, off the hot path:
**Kubo IPFS** (bitswap + DHT; optionally a networked pin service for the donated
mesh) and an **off-host cold pin to Backblaze B2**
(`50-infra/kotoba-b2-pin`, DataLad + git-annex S3 — mirrors every block,
`restore` re-imports via `ipfs block put`,
[ADR-2606041130](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2606041130-kotoba-b2-blockstore-cold-pin.md)).

**④ Anchors** — the **Datom log is the canonical state**
([ADR-2605312345](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2605312345-kotoba-datom-first-class-canonical-state.md));
IPNS signed heads pin per-graph roots (durable across restart), Base L2 anchors
the commit-DAG root for tamper-evidence, and AT-Proto MST is the ingress/interop
wire that materializes the log.

## Query Surfaces

Primary query/write semantics are Datomic-style Datom APIs and Datalog over
the immutable `(E,A,V,T,Added)` history. SPARQL is intentionally a secondary
RDF-compatible query surface over that Datomic/IPLD head, not a competing
source of truth.

Server endpoint: `POST /xrpc/com.etzhayyim.apps.kotoba.graph.sparql`

Auto-detects the form from the leading keyword and dispatches to the
matching Datom-backed cold-path method:

- `SELECT` — BGP / Filter / Union / Optional / Sub-SELECT / VALUES / GROUP BY / HAVING / ORDER BY / LIMIT / OFFSET / Property paths `+ * ? ^ |` / Sequence
- `DESCRIBE` — explicit IRIs and `?var WHERE { … }` forms; parallel per-subject fetch
- `CONSTRUCT` — template instantiation from any WHERE pattern
- `ASK` — constant-time short-circuit on first match
- `UPDATE` — `INSERT DATA` / `DELETE DATA` / `INSERT/DELETE WHERE`
- `SERVICE <cid:remote-graph>` — federated query across content-addressed graphs

Every form has a CACAO-authed variant — pass `cacaoB64` in the request body.

## Performance

Measurements taken on M4 Mac, release build, `KOTOBA_IPFS=off`,
`kotoba bench` against `kotoba serve` — **on the pre-migration Rust
implementation** (see the disclaimer above). Not yet re-benchmarked on the
CLJC rebuild.

### Ingest

| path                                | rate                       |
|-------------------------------------|----------------------------|
| `kg.ingest`        (single, HTTP)   | 28 entities/sec            |
| `kg.ingest_batch`  (1 batch × 1000) | **3981 entities/sec** (142×) |
| `kg.ingest_batch`  (10 × 1000)      | **5222 entities/sec** sustained |

### Query (unauthed, 2000-entity graph)

| query                                  | result_n | seq p50 | seq QPS | c=16 QPS |
|----------------------------------------|----------|---------|---------|----------|
| `ASK     ?s <role> "admin"`            | true     | 0.32 ms | 2586    | —        |
| `SELECT  ?s <role> "admin"`            | 666      | 11.3 ms | 21      | 398      |
| 2-triple JOIN role+score               | 1332     | 18.5 ms | 51      | —        |
| `GROUP BY role COUNT(*)`               | 2 grp    | 5.1 ms  | 183     | —        |
| `CONSTRUCT … WHERE role=admin`         | 666      | 5.9 ms  | 135     | —        |

### CACAO-gated (5000 entities, fresh CACAO per request, 100% success)

| query                          | result_n | seq p50 | seq QPS |
|--------------------------------|----------|---------|---------|
| `ASK`                          | true     | 0.68 ms | 1212    |
| `SELECT role=admin`            | 1667     | 11.5 ms | 71      |
| 2-triple JOIN role+dept        | 3334     | 41.0 ms | 23      |
| `GROUP BY role COUNT(*)`       | 2 grp    | 4.5 ms  | 189     |

### CACAO concurrency sweep (3000-entity graph)

| concurrency | QPS         | p50      |
|-------------|-------------|----------|
| 1           | 3916        | 0.20 ms  |
| 8           | 10113       | 0.52 ms  |
| 16          | 10140       | 1.27 ms  |
| 32          | **12753**   | 2.15 ms  |

Trust-boundary throughput **12.8K QPS** at c=32, 100% replay-protected.
