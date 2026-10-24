# kotobase-engine-contract

Provider- and storage-engine-neutral contracts for Kotobase database engines.
It is the seam that lets the same Datom semantics run over a memory oracle,
Prolly snapshots, Merkle-LSM runs, or a future engine without teaching the API
layer about any physical tree.

The contract deliberately separates three identities:

- `:tx-root` commits to the canonical logical transaction;
- `:logical-checkpoint-root` commits to the visible logical Datom state at a
  checkpoint;
- `:physical-root` names an engine-specific snapshot or manifest.

Physical roots are not expected to match between engines. A Prolly root and a
Merkle-LSM manifest can represent the same logical state while having different
CIDs. Cross-engine equivalence is established by transaction/query/history
answers and the logical checkpoint root.

`kotobase.engine.canonical` fixes the versioned, domain-separated logical value
form (`kotobase.logical/v1`). It rejects host-dependent numeric and record
representations rather than inheriting JVM or JavaScript printer behaviour.
`kotobase.engine.identity` defines two separate v1 envelopes:

- `kotobase.logical-commit/v1` binds transaction, checkpoint, schema, model and
  admission-policy roots. V1 is intentionally a zero-or-one-parent chain, and
  its canonical bytes (hence CIDs) are pinned by a golden test.
- `kotobase.logical-commit/v2` is used only for merge commits: 2..16 distinct
  parents in ascending CID order plus `:merge-policy`. A linear commit can
  never be spelled as v2, so every commit has exactly one identity.
- `kotobase.physical-publication/v1` binds one logical commit to an
  engine-specific physical root. Repacking or changing engines therefore does
  not move the logical database identity.

Signers sign the domain-separated `signature-payload`; signatures are not
embedded into the value whose root they attest.

`kotobase.engine.frontier/accept-head` closes the remaining mutable-discovery
gap. A client persists `{database-id, logical-commit-root, epoch}` in secure
local storage and accepts a different discovered head only when a
CID/signature-verified, epoch-contiguous parent path reaches that last-seen
root. It distinguishes rollback, same-epoch equivocation, and a higher but
unrelated fork. The first observation is deliberately TOFU; IPNS, DNSLink, DID
documents, S3, and HTTP remain discovery/transport and never become truth.

`kotobase.engine.merge` is the pure, coordinator-free convergence rule
(`kotobase.merge/v1`, kotobase ADR-2610101200). Given the heads' verified
ancestor closure, a schema and the injected digest, `merge` returns either a
fast-forward or one v2 merge commit whose resolution transaction explicitly
retracts every cardinality-one / `:db/unique` loser and re-asserts every datom
kept against a concurrent retraction. Argument order, duplicates and ancestor
heads cannot change the result. The closure must have a single genesis at
epoch 0, exact epochs, one `:database-id` and one `:schema-root`, and is
bounded by `:max-closure` and `:max-work`. Every v2 commit in the closure is
recomputed during a single replay, so `merge`, `state` and `verify-merge`
verify nested merges recursively. Replay is linear in events for linear
history, but each merge resolves and checkpoints its full state, so the cost
is O(events + merges x (state + dots)); `:max-work` charges every such loop
and fails closed beyond the budget. `accept-head` treats a merge as an ordinary descendant
once its proof entry carries every parent (`:parent-entries`) and its epoch
is exactly 1 + max(parent epochs), so a merge naming both equivocating heads
advances either observer.

`checkpoint` and physical maintenance are deliberately different contracts.
A checkpoint computes a logical-state commitment and may leave the physical
layout unchanged. Optional `IMaintenance` performs real compaction/folding and
must report the before/after physical roots, work units, and whether work was
completed or was a no-op. Promotion tooling must never label a checkpoint
duration as compaction evidence.

## Repositories around this seam

| responsibility | owner |
|---|---|
| Datom representation | `kotoba-lang/datom` |
| Datomic-shaped logical semantics | `kotoba-lang/datom-model` |
| storage-free Datalog | `kotoba-lang/datalog` |
| engine contract, restore seam and oracle | this repository |
| immutable Prolly structure | `kotoba-lang/prolly-tree` |
| immutable sorted runs/compaction | `kotoba-lang/merkle-lsm` |
| block/ref/large-object provider contract | `kotoba-lang/kotobase-storage` |
| S3/R2/B2/Filecoin implementations | provider and archive adapters |
| tenant/auth/HTTP deployment | `cloud-kotoba/kotobase-control-plane` |

`kotobase.engine.memory` is a small zero-dependency correctness oracle, not a
production database. `kotobase.engine.conformance/verify` runs the same semantic
checks against any `IEngine` implementation. Engine operations return an
immediate value, JVM `CompletionStage`, or JavaScript `Promise`; the same
conformance runner composes all forms.

Semantic PASS alone does not select a default. `kotobase.engine.qualification`
adds independent resilience and workload-specific performance evidence gates;
root manifests must remain bounded as history grows, and metadata persisted to
an untrusted block store must not disclose logical Datom values. These are
explicit qualification gates rather than assumptions inferred from encrypted
covering indexes.
The initial candidate inventory is in `docs/qualification-matrix.edn`. The
Prolly candidate has passed manifest-only cold mutation and second-process
reopen against real R2 semantics and is ready for server shadow traffic. It is
not yet the production default: production latency distributions and restore
throughput remain required evidence. The
legacy peer Prolly path remains a compatibility baseline because it currently
stringifies every non-Link Datom position and therefore cannot yet claim typed
Datom round-trip conformance.

## Engine profiles

Profiles describe a physical strategy without making it doctrine:

- `:memory`
- `:prolly`
- `:merkle-lsm`
- `:lsm-prolly-checkpoint`

The composite profile is a third experiment, not an assertion that Prolly and
Merkle-LSM must always be deployed together.

Filecoin/FEVM are not engine profiles. `kotobase.engine.archive` models them as
asynchronous archive and anchor lifecycles outside the foreground commit/query
path.

## Operation layers

`kotobase.engine.surface` is the authoritative layer classifier for the public
surface. It distinguishes primitive engine state, storage-independent semantic
queries, provider diagnostics, projections, archives, and anchors.

In particular, `dbStats` is provider diagnostics and `view` is a projection
operation. Neither is a portable IEngine read or a cross-engine promotion
gate. A projection implementation must version its definition and source
commit barrier independently; FEVM anchoring remains asynchronous and cannot
be inserted into the foreground database path.

## Verification

```sh
kbb -M:test
kbb -M:lint
npm install
npm run test:cljs
```


## Opt-in engine source projects

Three independently selected implementations are co-located under
`implementations/`; the neutral default dependency graph does not include them.
`node scripts/engine-sources.mjs list` returns exact source IDs and preserved
repository/coordinate aliases, with no runtime admission. See
[ADR-0001](docs/adr/0001-engine-source-monorepo.md) for project boundaries,
branch/recovery decisions and reproducible JVM/SCI/compiled host gates.
