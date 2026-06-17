# ADR-002 — Stake-to-replicate: a bonded, reputation-weighted replica membrane

Status: **proposed** · 2026-06-17
Extends: ADR-001 (five-axis, **availability** axis / phase 4 declared replication)
Realises: `docs/GROWTH-DECENTRALIZATION.edn` phase **p6**
Boundary: subject to the **Mishmar read+verify-only invariant** (`docs/MISHMAR-OBSERVATION.md`) — kotoba never signs an on-chain tx, custodies a bond, or settles. It *observes, verifies, gates, and challenges*.

## Context

ADR-001 made availability a **declared responsibility** (per-graph
`replication = { min_replicas, pin_peers }`, enforced by the DHT tier). That
answers *"how many replicas and where."* It does **not** answer the two
questions that decide whether decentralisation is real rather than nominal:

1. **Who is allowed to hold a replica responsibility?** Today neighbourhood
   membership is pure XOR proximity (`node_id::k_nearest`, `neighborhood::K = 7`).
   Anyone can mint a `NodeId` from a fresh pubkey (`NodeId::from_pubkey`) and
   sit next to any CID address → trivial Sybil over the replica set.
2. **What backs the promise to keep serving the block?** A replica that drops
   data pays nothing. `availability_proof::VerificationResult` already exposes
   `eligible_for_reward()` and `trigger_slash()`, but nothing is staked, so a
   slash is a no-op and a reward is unfunded.

The mechanism layer to fix this **already exists** and is the point of this ADR
— wire it, don't reinvent it:

| existing primitive | crate / symbol | role here |
|---|---|---|
| neighbourhood responsibility | `kotoba-dht` `Neighborhood::responsible_for`, `node_id::k_nearest`, `K=7` | candidate replica set per CID |
| replica accounting | `kotoba-dht` `NeighborhoodBlockStore::{with_min_replicas, replica_count, respond_to_challenge}` | declared-replication enforcement (ADR-001 p4) |
| availability challenge/proof | `kotoba-dht` `AvailabilityChallenge`, `proof_from_store`, `verify_proof → VerificationResult{eligible_for_reward, trigger_slash}` | the audit that earns reward or triggers slash |
| reward settlement (off-chain compute) | `kotoba-dht` `SettlementSchedule`, `SettlementBatch::from_intents` | retainer math (units → USDC micros) |
| **bond / slash (on-chain, kotoba reads only)** | `MishmarBondEscrow{Pinned, Challenged, Proven, Slashed}` on the anchor chain; `kotoba-runtime bind_evm` `eth_getLogs`; projected to `:mishmar/pin/*` | the collateral and the punishment |
| reputation (internal, non-transferable) | `SOCIAL-CAPITAL-LEDGER.edn` `social/capital/<epoch>`; `ReputationSBT` observed → `:social/reputation/<DID>` | who to prefer, *not* whether to admit |
| witness quorum | `hash(rootCid) % N` 5-cell, ≥3 attestations (reused from datomic membrane) | who adjudicates a challenge |

So this ADR is a **membrane + a closed incentive loop** over existing parts.

## Decision

Admission to a CID's replica responsibility is gated by an **on-chain bond**;
*preference* among admitted replicas is weighted by **non-transferable
reputation**. These are two different ledgers and must never collapse into one.

> **The load-bearing separation:** *collateral* (slashable, external/anchor-chain
> asset, the thing you lose) is **not** *reputation* (non-transferable, decaying,
> earned, the thing that ranks you). Bitcoin/Ethereum fuse stake and standing
> into one token; kotoba keeps them orthogonal so that buying in cannot buy
> standing, and standing cannot be cashed out. This preserves the
> SOCIAL-CAPITAL-LEDGER invariants (non-transferable, no-yield, decaying) while
> still giving Sybil resistance its teeth.

### 1. Replica membrane — admission (bond), not reputation

A node `D` is an **eligible replica** for graph `g` iff kotoba *observes* (read
+ verify only) on the anchor chain:

```
bond(D, g) ≥ replication.min_bond_mkoto      ; MishmarBondEscrow.Pinned(pinId, rootCid=head(g), pinner=D, bond, dur)
∧ pin.duration covers the contract window
∧ AnchorBridge three-way root match holds     ; geth-private ↔ Base anchor ↔ local CommitDag head (MISHMAR §1)
```

The candidate set for a CID becomes:

```
candidates(cid) = k_nearest( cid_address(cid),
                             { D ∈ neighborhood | eligible_replica(D, graph_of(cid)) },
                             K )
```

i.e. **filter by bond first, then take K-nearest** — XOR proximity still decides
*placement*, but only bonded DIDs are in the pool. A fresh-keypair Sybil with no
observed `Pinned` bond is simply not a candidate. `min_bond_mkoto` is a per-graph
field added to the ADR-001 `replication` policy (default `0` ⇒ today's open
behaviour, so this is opt-in and backward compatible).

### 2. The closed loop — challenge → verify → reward | slash

Per epoch, for each `(cid, replica)` under contract:

```
challenge  = AvailabilityChallenge { cid, nonce }            ; verifier-issued, fresh nonce
proof      = replica.respond_to_challenge(challenge)         ; NeighborhoodBlockStore (proof_from_store)
result     = verify_proof(challenge, proof, witnesses≥3)     ; quorum = hash(cid)%N 5-cell, ≥3 attest
```

- `result.eligible_for_reward()` → append a `SettlementIntent` (retainer); a
  batch is periodically materialised by `SettlementBatch::from_intents` and
  routed **on the anchor chain by the operating entity** (`TitheRouter`
  `purpose="retainer"`). kotoba computes the line items; it does not pay.
- `result.trigger_slash()` → kotoba **emits a warrant** (signed observation,
  same shape as `kotoba-custody` `CustodyUnreceiptedRelease`, ADR-sealed-cold-tier
  R3d) + pinned evidence (the failed challenge/proof). A relayer presents it to
  `MishmarBondEscrow` which moves the pin `Challenged → Slashed`; kotoba then
  *verifies* the `Slashed` event landed with the `TitheRouter.Routed(
  purpose="storage-slash")` 90/10 split intact (MISHMAR §3). **kotoba accuses
  with evidence; the chain punishes.**

Determinism: the witness quorum is derived (`hash(cid) % N`), the proof is over a
verifier nonce, and `verify_proof` is pure — so any observer recomputes the same
verdict. No coordinator.

### 3. Reputation — preference and earn-rate, never admission

`:social/reputation/<DID>` (observed `ReputationSBT`) and
`social/capital/<epoch>` (internal MV) weight, among *already-bonded* replicas:

- **placement preference** when more eligible candidates exist than `min_replicas`
  (prefer higher-reputation cells → better expected liveness);
- **witness-selection weighting** (already the SOCIAL-CAPITAL-LEDGER consumer);
- **retainer earn-rate multiplier** within a Council-bounded band (a *flow*
  adjustment, never a transfer).

Reputation **cannot** admit an unbonded node and **cannot** be spent to avoid a
slash. Bond is necessary; reputation is ordering.

## Phasing (each an independently shippable, verified PR — ADR-001 style)

1. **`min_bond_mkoto` in the replication policy** + `eligible_replica(D,g)` as a
   pure predicate over already-projected `:mishmar/pin/*` datoms. No network
   change; default `0` = current behaviour. *(foundation)* — **done**:
   `kotoba-query` `social::eligible_replica` + `PinIndex::bond_of` /
   `PIN_BOND_PRED`; `kotoba-server` `mishmar_observe` now projects the `Pinned`
   bond into `mishmar/pin/bond`.
2. **Bonded candidate filter** — `candidates(cid)` filters the neighbourhood by
   `eligible_replica` before `k_nearest`. Behind `KOTOBA_STAKE_TO_REPLICATE`
   until p4 (declared replication) integration test is green; default off. —
   **done**: `kotoba-dht` `membrane::bonded_candidates` (+ `stake_to_replicate_enabled`
   env gate); membrane-off path is byte-for-byte today's open `k_nearest`.
3. **Reward intents** — wire `eligible_for_reward()` → `SettlementIntent` →
   `SettlementBatch`; surface unpaid/owed retainer in `node.status`. (Routing
   stays operator-side; kotoba only emits the batch.)
4. **Slash warrants** — `trigger_slash()` → signed warrant + pinned evidence;
   `mishmar.verifySlash` confirms the on-chain `Slashed` + `TitheRouter` split.
   Reuse the custody warrant/evidence path verbatim.
5. **Reputation weighting** — placement preference + earn-rate multiplier over
   the bonded set; Council-bounded band; property test that reputation never
   changes the *admission* boolean.

## Consequences

- Sybil over the replica set now costs an **observable, slashable bond** per
  graph — the "credible-neutrality / unforgeable-cost" borrow from Bitcoin,
  expressed without PoW or a base-layer coin.
- The SOCIAL-CAPITAL-LEDGER invariants survive intact: reputation stays
  non-transferable, decaying, no-yield; it never gates admission and is never
  cashed out.
- The Mishmar boundary survives intact: every on-chain action (bond, slash,
  retainer routing) is performed by the operating entity; kotoba's surface is
  read + verify + accuse-with-evidence.
- `replication` block format gains `min_bond_mkoto` (`#[serde(default)]` keeps
  old policies readable; default `0`).
- Single-owner / sovereign deployments are unaffected (`min_bond_mkoto = 0` ⇒
  open neighbourhood, identical to today).

## Non-goals (explicit)

- **No transferable L0 token, no staking-for-yield.** The bond is collateral
  under contract, not a yield instrument; reputation is a flow, not a stake.
- **No on-chain signing/custody/settlement inside kotoba.** (Mishmar invariant.)
- **No global consensus / total order** for replica selection — it stays
  derived (XOR proximity + observed bond + recomputable quorum).
- **No reputation-buys-admission and no bond-buys-standing.** The two ledgers
  are orthogonal by construction; collapsing them is the failure mode this ADR
  exists to prevent.

## Open questions

- `min_bond_mkoto` denomination & calibration vs. graph size / duration (defer to
  a Council param blob like `social/capital/params/active`).
- Bond *top-up / partial-slash* curve: full slash on first miss is brittle;
  prefer graduated slash on repeated `Challenged` misses within an epoch.
- Challenge issuance authority & frequency (verifier = any witness-quorum member?
  rate-limited by reputation to bound challenge spam).
