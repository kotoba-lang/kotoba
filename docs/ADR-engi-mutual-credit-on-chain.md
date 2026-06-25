# ADR — ENGI mutual-credit on the Source Chain (mesh-distributed EN)

Status: **accepted (R0 core · R1 net receive · R2 verified outbound · R3 durable log/boot replay · R4 insolvency audit · R5 fork detection — landed)**
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

**Landed (R3, durable transfer log + boot replay):** `Engi` now keeps a durable
append-only **transfer log** (`${KOTOBA_STORE_PATH}/engi-transfers.jsonl`, one
countersigned `MutualCreditTransfer` per line): `project_transfer` appends to it,
`transfers()` / `transfer_count()` expose the record, and at boot `load` reads it
into the in-memory record. The transfer log is the **canonical** mutual-credit
history — if the balance cache JSON is lost or corrupt, boot **rebuilds the
transfer-derived balances by replaying the log**. A torn trailing line (crash
mid-append) is skipped, never fatal. 3 unit tests (restart round-trip / rebuild
from log when cache lost / torn-line tolerance), green. (Fee balances are not yet
in the log — recovering those is item 2 below.)

**Landed (R4, insolvency audit):** `kotoba_dht::audit_transfers(transfers,
credit_limit_fn) -> Vec<InsolvencyFinding>` replays a flat transfer record per
agent and flags every spend that breaches the spender's credit limit — the
solvency check the *unconditional* projection needs (it applies transfers without
re-judging them). `Engi::audit_solvency()` runs it over the R3 durable record with
each agent's effective limit; the operator-gated `engi.audit` XRPC exposes the
findings (`insolvent` + per-finding did/transfer_id/balance/limit). Catches
overspend / double-spend-by-accumulation. 2 dht + 1 server unit tests, green.

**Landed (R5, double-spend fork detection):**
`kotoba_dht::detect_transfer_forks(transfers) -> Vec<TransferFork>` groups spend
transfers by `(spender, spender_prev)` and reports any position from which a
spender signed two *distinct* transfers — the double-spend fingerprint, detectable
from the **gossip-accumulated transfer record alone** (every transfer carries the
spender's pinned head, so no separate per-DID chain sync is needed). It is the
transfer-level analog of `detect_fork` (which compares `ChainEntry` `seq`).
`Engi::detect_forks()` runs it over the durable record and `engi.audit` now also
returns `forked` + per-fork `{spender, spender_prev, transfer_ids}`. Dups
(same `transfer_id`) and advancing positions are not forks. 2 dht + 1 server
tests, green.

**Deferred (need new subsystems / a design decision — not faked):**

1. **auto-emit warrants on detection** — `audit_solvency` / `detect_forks` are
   pull-only (via `engi.audit`). Wiring them to *push* a signed
   `mutual_credit_warrant` onto the warrant gossip on detection (so the
   neighborhood evicts the offender automatically) is the remaining validator
   step. Catching forks across **non-EN** chain content (full `SourceChain` with
   `seq`-based entries) still needs the per-DID chain sync (bitswap `want_since`).
2. **fold fees onto transfers** — making `charge` / `batch_credit` countersigned
   transfers is a write-path + economics change (the operator must co-sign every
   write fee, and the writer's signature must enter the fee path); deferred as a
   deliberate protocol change, not a mechanical edit. Also folds fee balances into
   the durable log so a lost cache recovers them too.
