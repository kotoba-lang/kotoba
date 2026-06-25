# ADR — ENGI mutual-credit on the Source Chain (mesh-distributed EN)

Status: **accepted (R0 core types + R1 net receive + R2 verified outbound publish landed)**
Supersedes the node-local-only ledger posture of `engi.rs` (ADR-2606013400).

## Context

`ENGI` (縁起) is kotoba's internal **mutual-credit** unit, **EN (縁)**: net-zero,
non-minted, agent-centric — value exists only as a *relation between two agents*
(exactly HoloFuel's model). The R0 ledger (`kotoba-server/src/engi.rs`) was
correct as accounting but **node-local**: balances lived in an in-memory
`HashMap` persisted to a single `engi-ledger.json`. It was not on the per-DID
Source Chains, not gossiped, and not validated by neighborhoods — so EN did not
actually live "in the mesh."

This ADR puts EN movement onto the agent-centric integrity layer kotoba already
has (`kotoba-dht`: `SourceChain` + `Warrant` + neighborhood validation), so that:

- a balance is **derived** by replaying signed chains (no global ledger), and
- double-spend / overspend is caught by **neighborhood validators**, not a
  central authority or a global total order.

## Decision

### 1. The transfer is a countersigned chain entry

A spend is a **`MutualCreditTransfer`** (`kotoba-dht/src/engi_chain.rs`): a
`TransferBody { spender, receiver, amount, spender_prev, receiver_prev, nonce,
ts }` that **both** parties sign over its canonical CBOR (`transfer_id =
CID(body)`). The same transfer is appended to **both** chains via a new
`ChainContent::Transfer` — the spender records a debit, the receiver a credit.
Net-zero by construction.

```
spender chain:  … → Transfer{spender:A, receiver:B, amount:n, spender_prev:headA} (prev = headA)
receiver chain: … → (same Transfer)                                               (prev = headB)
balance(A) = Σ over A's chain (received − spent)
```

### 2. Balance is a projection, not the source of truth

The canonical record is the chain. `replay_balance(entries, did)` folds the
`Transfer` entries into a balance. `Engi` (server) is demoted to a **materialized
cache**: `Engi::project_transfer(t)` applies one chain-validated transfer
(unconditionally — it mirrors a committed fact), and
`Engi::rebuild_from_transfers(set)` reconstructs the cache from a complete
transfer set at boot. The JSON file is a fast read surface, not the ledger of
record. Per-agent credit limits stay (reputation state, not EN).

### 3. Double-spend prevention — no global order

`TransferBody::spender_prev` pins the transfer to the spender's chain head at
signing; the appended entry's `prev` **must** equal it. A `SourceChain` is linear
(one entry per `seq`; `append` enforces seq+prev), so spending the same EN twice
forces a **fork** — two entries sharing one `prev`/`seq`. This is detected two
ways:

- `detect_fork(a, b)` — same agent + same `seq` + different CID = the structural
  proof of a double-spend (a validator holding both raises a warrant).
- `audit_peer_chain(entries, did, credit_limit, resolve)` — a neighborhood
  validator replays a peer's chain, verifies both countersignatures (resolving
  DIDs → Ed25519 keys), checks prev-binding, and replays running solvency against
  the credit limit. Returns **every** violation as a `TransferAccusation`.

Each accusation maps to a `Warrant`:

- `ValidationRule::MutualCreditViolation = 10` — bad/forged counter-signature,
  non-positive amount, self-transfer, or unbound `prev`.
- `ValidationRule::DoubleSpend = 11` — overspend past the credit limit, or a fork.

`mutual_credit_warrant(...)` signs the accusation; it propagates on the existing
warrant gossip (K/2 warrants → eviction), identical to every other KDHT misbehaviour.

### 4. Finality

Countersigning gives **bilateral** finality (both agreed). The neighborhood gives
**fraud detection**, not instant global finality — acceptable because the scarce,
irreversibly-settled asset lives across the boundary (**USDC on Base L2**,
etzhayyim-exclusive). EN is internal contribution accounting only.

## Invariants (CI-greppable)

- ❌ minting/burning EN (only `transfer`/`project`/replay; Σ balances ≡ 0).
- ❌ a transfer entry whose `prev` ≠ `spender_prev` (fork / unbound spend).
- ❌ a spend that drives the replayed balance below `−credit_limit`.
- ❌ a transfer with one signature (must be countersigned by both parties).
- ❌ treating `Engi`'s JSON as canonical — it is a projection of the chains.

## Wire / gossip

- `ENGI_TRANSFER_TOPIC` is the bare KSE-topic name `engi/transfer` (like
  `firehose` / `rekey/revoke`); the net layer maps it to the wire topic
  `kotoba/engi/transfer` via `gossipsub_topic`. It carries countersigned transfers
  for projection across the mesh.
- `SeenTransfers` (bounded ring+set keyed by `transfer_id`, cap
  `SEEN_TRANSFERS_CAP = 8192`) dedups re-gossiped transfers — mirrors the
  firehose `FirehoseSeen` guard.
- `net_actor` (feature `p2p`) subscribes the topic and, on each inbound message,
  runs `handle_engi_transfer` → decode `MutualCreditTransfer` → `SeenTransfers`
  dedup → `Engi::project_transfer`. Outbound publish uses the existing generic
  gossip channel (`(ENGI_TRANSFER_TOPIC, cbor)`).

## Status & follow-ups

**Landed (R0, this ADR):** `engi_chain.rs` — `TransferBody`,
`MutualCreditTransfer` (countersign/verify), `EngiChain` (record_spend/receive
with prev-pin + credit-limit), `replay_balance`, `validate_chain_transfers`,
`audit_peer_chain`, `detect_fork`, `mutual_credit_warrant`, `SeenTransfers`;
`ChainContent::Transfer`; `ValidationRule::{MutualCreditViolation, DoubleSpend}`;
`Engi::{project_transfer, rebuild_from_transfers}`. 20 `engi_chain` unit tests +
6 `Engi` projection tests, all green.

**Landed (R1, net wiring):** `net_actor` (feature `p2p`) subscribes
`ENGI_TRANSFER_TOPIC`, holds a `SeenTransfers` guard, and projects inbound
transfers via `handle_engi_transfer` → `Engi::project_transfer`. `Engi` is
threaded into `net_actor::run`. 1 handler unit test (project / dedup / skip
garbage) green under `--features p2p`. Topic const corrected to the bare KSE name
`engi/transfer` (the net layer adds the `kotoba/` prefix).

**Landed (R2, outbound publish + verified boundary + DID resolution):**
- `engi::resolve_did_pubkey(did)` resolves `did:key` → Ed25519 pubkey
  (`kotoba_auth::parse_ed25519_did_key`); the resolver `audit_peer_chain` and the
  receive path both use.
- **Inbound gossip is now verified**: `handle_engi_transfer` resolves both DIDs
  and verifies BOTH countersignatures before projecting — a forged or
  single-signed transfer is rejected at the gossip edge, never entering the cache.
- **Outbound publish**: the `engi.transfer` XRPC endpoint (`NSID_ENGI_TRANSFER`,
  self-authorizing — the two signatures ARE the auth) verifies, projects locally,
  and gossips the CBOR transfer on `ENGI_TRANSFER_TOPIC` to the mesh.
- Tests: net_actor verify/project/dedup/reject-forgery (p2p) + `resolve_did_pubkey`
  round-trip, green.

**Deferred (need new subsystems — not faked):**

1. **durable transfer store + boot replay** — there is no durable, queryable log
   of transfers yet (the balance JSON is a derived cache, not the canonical
   record). Persisting `ChainContent::Transfer` entries (journal / QuadStore) is
   the prerequisite; once present, boot calls `Engi::rebuild_from_transfers`.
2. **full neighborhood validator deployment** — sync a peer's *whole* Source
   Chain (bitswap `want_since`), run `audit_peer_chain` over it, and gossip
   `mutual_credit_warrant`s. Needs the peer-chain sync + a per-agent chain store
   (the R2 boundary check verifies single transfers, not full-chain solvency).
3. **fold fees onto transfers** — making `charge` / `batch_credit` countersigned
   transfers is a write-path + economics change (the operator must co-sign every
   write fee, and the writer's signature must enter the fee path); deferred as a
   deliberate protocol change, not a mechanical edit.
