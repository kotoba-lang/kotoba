# ADR-001 — Five-axis distributed redesign (authority / ordering / availability / conflict / transport)

Status: **accepted (phased)** · 2026-06

## Context

After the journal deletion (#57) kotoba's durable substrate is the **CommitDag**
(per-graph ProllyTree commits, content-addressed, IPNS head) plus each
subsystem's own content-addressed store (signal → Shelf, realtime → block-store
snapshots). The live surface is an in-memory **LiveBus** (gossipsub-style,
ephemeral). That is coherent as a *sovereign single-writer* design, but five
distributed-systems axes were only handled implicitly. This ADR makes the target
explicit and sequences the work.

### Where we are (audited against the code)

| axis | current behaviour | gap |
|---|---|---|
| **authority** | one `owner` DID per graph (= IPNS controller); writes need owner Bearer or a CACAO/VP `datom:transact` capability whose recovered issuer == owner; IPNS head is signature-required | no independent **validation** (no "shared physics"); no multi-writer |
| **ordering** | in-graph **total order** (linear `prev` + `seq`, CAS-serialised); cross-graph order is **wall-clock `ts` (1 s)** | "CommitDag" is really a chain (single parent); cross-graph order is skew-prone, not causal |
| **availability** | content-addressed in FsBlockStore → CAR-on-B2 → kubo → DHT (opt-in); de-facto holder = owner node + B2 | no declared replication responsibility; single-holder by default |
| **conflict** | `expected_parent` CAS → `StaleParent` (**reject**) | no merge; the ProllyTree's order-independence (Fireproof-style CRDT) is unused |
| **transport** | datomic live (LiveBus) loss is recoverable from the CommitDag; **non-datomic is live-only** | non-datomic event *stream* is unrecoverable on transport loss (only the payload is, by CID) |

## Decision — the target (A + B unified)

Adopt a **multi-writer, causally-ordered, merge-on-conflict, replicated,
transport-independent** content-addressed model, while preserving the
sovereign-single-writer mode as a special case (one authorized writer ⇒ no
merges ever happen).

| axis | target | mechanism |
|---|---|---|
| **authority** | owner-rooted, **delegatable + validated** | keep CACAO `datom:transact` capability chains; add a per-graph **validation hook** (`:db.validate/*` rules + optional WASM validator) run on every transact — the "shared physics". Multiple writers = multiple capability holders. |
| **ordering** | **causal** (not wall-clock, not global-total) | **Hybrid Logical Clock (HLC)** on every commit + optional `caused_by: [commitCID]` cross-graph causal refs. Cross-graph firehose orders by HLC. In-graph stays total. |
| **availability** | **declared responsibility** | per-graph `replication = { min_replicas, pin_peers }`; the DHT NeighborhoodBlockStore enforces the replication factor (pin contract), default-on. |
| **conflict** | **merge** (CRDT), reject only on validation failure | the CommitDag becomes a **true multi-parent DAG**: concurrent writes don't `StaleParent`, they create a **merge commit** whose ProllyTree is the join of both states. Datom resolution: cardinality-one = **LWW by (HLC, writerDID)**; cardinality-many = **OR-set** (assert/retract by `(e,a,v)` with HLC tiebreak). Deterministic ⇒ same DAG ⇒ same root CID on every replica. |
| **transport** | recoverable for **all** topics | datomic already replays from the CommitDag; give each non-datomic topic a cheap **pointer-chain** (append-only CID-pointer commits — no ProllyTree rebuild) so the stream is cursor-replayable without re-introducing the heavy journal. |

### Why the ProllyTree substrate makes B cheap
ProllyTrees are history-independent: the same datom set yields the same Merkle
root regardless of insert order (this is exactly what Fireproof exploits). So a
merge is `ProllyTree::diff` + a deterministic per-`(e,a,v)` resolution, then a
rebuild — and because the result is canonical, every replica converges to an
identical root CID without coordination. The commit DAG is the Merkle clock.

### Merge semantics (the load-bearing decision)
A datom is `(e, a, v, tx, op)`. On merging two heads H1, H2 with common
ancestor A:
- compute `Δ1 = diff(A,H1)`, `Δ2 = diff(A,H2)`;
- union the asserted set, apply retracts;
- for the same `(e,a)` under a **cardinality-one** attribute, keep the datom with
  the greater `(hlc, writer_did)` (LWW, total + deterministic);
- under **cardinality-many**, keep the OR-set (an assert and a later retract of
  the same `(e,a,v)` resolve by `(hlc, writer_did)`);
- the merge commit's `parents = [H1, H2]`, `hlc = max(hlc1,hlc2)+1`.
Validation runs on the merged result; if it fails, the *later* writer's commit is
rejected (the only place "reject" survives).

## Phasing (each phase is an independently shippable, verified PR)

1. **HLC clock** — add `hlc` to commits; cross-graph firehose orders by HLC
   instead of wall-clock `ts`. Foundation for both causal ordering and the merge
   tiebreak. *(this PR)*
2. **Multi-parent DAG + Merkle-CRDT merge** — `parents: Vec<KotobaCid>`;
   `StaleParent` → auto-merge with the resolution above; convergence test
   (two writers, independent commits, identical root CID after merge).
3. **Validation hook** — `:db.validate/*` + optional WASM validator on transact
   and on merge results.
4. **Declared replication** — per-graph replication policy enforced by the DHT
   tier (pin contract); availability surfaced in `node.status`.
5. **Non-datomic pointer-chains** — cursor-replayable streams for signal /
   realtime / kse without the journal.

## Consequences
- Commit block format changes (new fields) — content-addressed CIDs change.
  Acceptable at dev stage; `#[serde(default)]` keeps old commits readable.
- Sovereign single-writer deployments are unaffected in behaviour (no concurrent
  writes ⇒ no merge commits ⇒ identical to today, just HLC-stamped).
- Multi-writer becomes possible without a global consensus/ledger — agent-centric
  like Holochain, convergent like a Merkle-CRDT like Fireproof.
