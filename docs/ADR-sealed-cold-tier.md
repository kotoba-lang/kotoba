# ADR-2606112200 — Sealed cold tier: AES-256-GCM block envelopes for everything that leaves the node

Status: **Accepted** (R0 implemented)
Date: 2026-06-11
Relates to: ADR-2606091500 (kotobase.net default remote pin), ADR-2606014000 (AEAD AAD binding), ADR-2606112000 (DNA integrity)

## Context

Kotoba's cold tier is public IPFS: `KuboBlockStore` writes plaintext blocks to a
Kubo node, from where they replicate via bitswap/DHT, and — since
ADR-2606091500 — every pin fans out to kotobase.net **by default**. Anyone who
learns a CID can fetch the block from any IPFS gateway or peer, completely
bypassing the CACAO/`graph_auth` layer, which only guards the XRPC surface.

The target architecture (Estonia/X-Road-shaped accountability, 2026-06-11
design discussion) is: *ciphertext may replicate anywhere; the only path to
meaningful reads is a key request that is authenticated, purpose-declared, and
receipt-logged.* This ADR lands the storage half of that statement (R0). The
key-broker / receipt protocol (`/kotoba/key/1`) is the follow-up stage.

## Decision

### R0 (this change)

1. **`SealedBlockStore<C>`** (`kotoba-store/src/sealed_store.rs`) wraps the
   cold tier. Envelope: `b"KSB1" || nonce || AES-256-GCM(plaintext, aad)`,
   stored under `sealed_cid = KotobaCid::from_bytes(envelope)` — Kubo's
   recompute-the-CID `block/put` works unchanged, and pins (local + kotobase
   fanout) translate to the sealed CID.
2. **Deterministic nonces, safely**: `nonce = HKDF(block_key, "kotoba/sealed-
   block/nonce/v1")` expanded over the plaintext CID. `cid = sha2-256(pt)`, so
   a `(key, nonce)` collision implies an identical plaintext — GCM nonce reuse
   across distinct plaintexts is impossible by construction. Determinism gives
   idempotent re-puts (no cold-tier duplicates) and index rebuildability.
   `kotoba_crypto::seal_with_aad_nonce` is the new primitive; its doc states
   the contract (content-derived nonces only).
3. **AAD is the constant `kotoba/sealed-block/v1`**, deliberately NOT the
   plaintext CID: a key holder can decrypt any sealed block blind and recover
   its plaintext CID by re-hashing, so the full index is reconstructible from
   cold bytes alone (disaster recovery). Slot integrity is enforced instead by
   the post-decrypt `sha2(pt) == cid` check in `open_envelope`.
4. **Index**: append-only sidecar `$KOTOBA_STORE_PATH/sealed_index.bin`
   (72-byte records: plain CID || sealed CID), loaded at startup, torn tail
   tolerated. It is routing state, not a trust root.
5. **Config**: `KOTOBA_BLOCK_KEY` (64 hex chars) or `KOTOBA_BLOCK_KEY_FILE`.
   Unset → wrapper not installed (plaintext, fully backward compatible) and
   the server logs a loud `cold tier UNSEALED` warning, because the kotobase
   pin fanout is on by default.
6. **Legacy blocks**: reads fall back to a plaintext fetch by plaintext CID on
   index miss, so pre-sealing data keeps serving. New writes are sealed.

### Known limitations (follow-ups)

- **CAR-on-B2 export** (`CarExportQueue`) and **KOTOBA_DURABILITY_DHT
  NeighborhoodBlockStore** peer replication sit at other seams and still move
  plaintext. B2 is an operator-private bucket (lower exposure); DHT durability
  + sealing should not be combined yet.
- **Cross-node fetch by plaintext CID** (KOTOBA_PEERS /
  DistributedBlockStore): peers cannot translate plain → sealed CIDs without
  the index. Resolution lands with the `/kotoba/key/1` protocol (stage 2),
  which carries the translation alongside the key grant.
- **Key rotation / per-graph keys**: single node key in R0. Per-graph keys
  arrive with the key broker, where graph granularity is the unit of grant;
  MLS-epoch rotation is the planned revocation mechanism.

## Roadmap (from the 2026-06-11 design)

R0 ✅ sealed cold tier (this ADR) → R1 `/kotoba/key/1` request-response +
single key broker (CACAO + purpose, receipt datoms) → R2 per-DID signed
Journal chains + receipt anchoring via `AnchorBridge.commitRoot` (kotoba-EVM
R3) → R3 t-of-N custodians (VSS + MLS) + warrants/slashing via
MishmarBondEscrow + read-side DNA policy.

---

## R1 — Access receipts (2026-06-11, same day)

Status: **Accepted** (implemented)

The accountability half of the X-Road statement. Instrumented read seams —
`require_datomic_read{,_any_operation,_tx_range}` (covers every `datomic.*`
read XRPC) and the four `kotobase.kg.*` read endpoints — now emit an
**access receipt** for every authorized Authenticated/Private read:

- Receipt datoms in the named graph `kotoba/audit/access-receipts/v1`
  (`access/graph`, `access/accessor-did`, `access/operation`,
  `access/purpose`, `access/ts-unix`) — immutable, time-travel queryable,
  and on the same distributed-commit path as all data (R2 anchors them).
- **Accessor identity**: presented CACAO's leaf `iss` (the delegate), else
  Bearer JWT `sub`. Public reads are not receipted (no identity; Estonia's
  tracker covers personal data, not open data).
- **Purpose**: the `x-kotoba-purpose` request header (≤256 chars). Recorded
  always; REQUIRED for Private-graph reads only when `KOTOBA_REQUIRE_PURPOSE`
  is truthy — observe-first rollout so existing CACAO clients don't break.
- **Write path**: handlers enqueue on an unbounded channel; one background
  writer batches (`KOTOBA_RECEIPT_FLUSH_MS`, default 1000 ms, max 256/batch)
  into a single `commit_protocol_datoms` tx per flush. Keeps the read hot
  path at a channel send, serialises audit-graph commits (no IPNS head
  races), and amortises commit cost — the lesson from the request-fingerprint
  middleware's per-request commit pileup.
- **Query surface**: `GET /xrpc/com.etzhayyim.apps.kotoba.audit.listReceipts`
  (`graph` / `accessor` filters, `limit`), operator-gated in R1. The
  owner-facing CACAO gate (citizen Data Tracker analog) lands with per-graph
  keys, where owner ≠ operator becomes the common case.

R1 limitations (follow-ups): receipts are best-effort (fire-and-forget batch;
fail-closed "no receipt, no read" arrives with the R2 signed journal);
firehose / realtime / git-http read gates not yet instrumented; purpose is
free text (Estonia-style coded purposes + legal-basis references when
enforcement turns on).
