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

---

## R2a — Receipt-root anchoring payload (2026-06-11)

Status: **Accepted** (implemented)

The KSI analog: `GET /xrpc/com.etzhayyim.apps.kotoba.audit.anchorPayload`
(operator-gated) returns `AnchorBridge.commitRoot(bytes32,bytes,uint64)`
calldata committing the audit graph's current head commit CID to Base —
`rootHash` = low 32 bytes of the head CID, `ipfsCid` = the head multibase
(anyone can fetch + replay the audit DAG and check it hashes to the anchored
root), `batchSize` = the audit graph's IPNS sequence. kotoba builds the
payload; the relayer signs + submits (same permissionless-commit +
off-chain-relayer boundary as kotoba-EVM R3 / PR #96). Once anchored, the
operator cannot silently rewrite or drop receipts committed before the anchor.

Remaining for full R2: per-DID signed Journal chains (requester
countersignature → non-repudiation), scheduled relayer submits, and an anchor
verification endpoint (head CID ↔ on-chain root cross-check).

---

## R2b — Author-signed CommitDag + requester evidence (2026-06-11)

Status: **Accepted** (implemented). Substrate decision: the **CommitDag, not
the KSE Journal** (deprecated, [knowledge.journal-deprecation]) — the commit
chain already had content addressing, `parents` hash-chaining, author DIDs,
IPNS heads and Base anchoring; the only missing piece was a signature.

- **`DistributedDatomCommit.author_sig`** — Ed25519 over `signed_payload()`,
  a CANONICAL encoding of all signed fields (`index_roots` as a sorted
  BTreeMap — HashMap order is instance-dependent, so re-encoding a loaded
  commit would not be byte-identical). Git-style embedded signature: the
  commit CID covers the signature. `#[serde(skip_serializing_if)]` ⇒ pre-R2b
  blocks decode unchanged with `author_sig = None`.
- **Signing**: `DistributedCommitWriter::with_author_signing_key` signs every
  sealed commit. `commit_protocol_datoms` passes the operator's AgentIdentity
  key when `author == operator_did` — so audit-graph receipt commits (and all
  node-authored protocol commits) are now operator-signed. Client-authored
  writes keep their own non-repudiation via `cacao_proof_cid`.
- **Verification**: `verify_author_sig(verifying_key)`; key resolution from
  the author DID stays above kotoba-datomic (kotoba-auth depends on it) —
  `parse_ed25519_did_key(author)` at the caller. Third-party verification
  needs only the commit block + the author DID.
- **Requester half**: receipts now carry `access/cacao-cid` — the presented
  CACAO's CBOR pinned to the block store. Receipt commit (operator-signed) +
  CACAO (requester-signed, nonce-bound) = two-party non-repudiation without a
  new countersignature protocol.

Anchored (R2a) + author-signed (R2b) ⇒ the audit chain is now tamper-evident
against the operator AND attributable: 誰も「書いてない/読んでない」と言えない.
Remaining: import-time signature enforcement on peer sync, signed IPNS heads
default-on, scheduled relayer submits, anchor verification endpoint.

### R2c — Import enforcement + chain verification (2026-06-11)

- **Merge-path gate**: `DistributedCommitWriter::with_import_check` — a
  foreign head adopted by the Merkle-CRDT merge path must pass the injected
  verifier (`kotoba_auth::commit_import_check`): `Invalid` signatures ALWAYS
  reject (tampering evidence); `Unsigned`/`Unverifiable` reject only under
  `KOTOBA_REQUIRE_SIGNED_COMMITS` (observe-first rollout). Injection keeps the
  dependency direction clean (kotoba-auth → kotoba-datomic, not vice versa).
- **`audit.verifyChain` XRPC** (operator-gated): walks the audit graph's
  CommitDag from the IPNS head, verifying every commit's `author_sig` against
  its author DID — one call answers "has anyone rewritten the receipt log?";
  pair with `audit.anchorPayload` for the on-chain half.

Remaining: signed IPNS heads default-on; scheduled relayer submits; live
merge-path adoption (`commit_datoms_merging` is still env-gated opt-in).

---

## R3 — t-of-N custodians: design + R3a share plane (2026-06-11)

Status: design **Accepted**; R3a **implemented**

### The trust-model upgrade

R0–R2c make the operator ACCOUNTABLE (sealed storage, receipts, anchors,
signatures) but still TRUSTED: one node holds KOTOBA_BLOCK_KEY, so one
operator can read everything silently. R3 removes that: the block key is
Shamir-split across N custodians; a meaningful read requires t of them, each
independently verifying CACAO + purpose and writing a receipt BEFORE
releasing its share. 「ログを書かずに鍵を出す」 then requires t colluders,
not one operator — the X-Road security server, decentralised. (Prior art:
NuCypher/TACo threshold access control; conditions = CACAO + purpose here.)

### Phases

- **R3a (this change) — share plane**: `kotoba-custody` crate.
  `split_key(key, t, custodians) → Vec<CustodianShare>` (Shamir GF(2^8) via
  the audited `sharks` crate — not hand-rolled), each share HPKE-wrapped
  (`ephemeral_pk || nonce || AES-256-GCM`, kotoba-crypto) to a custodian's
  X25519 key, with a SHA-256 share commitment checked at `open_share`;
  `combine_key(t, shares)` reconstructs. Immediate operational value even
  pre-protocol: KOTOBA_BLOCK_KEY backup/recovery without any single key file
  (deal 3-of-5 to operator devices / council members; lose any two).
- **R3b — `/kotoba/key/1` protocol**: custodian nodes hold their share and
  answer `KeyShareRequest { graph, cacao_b64, purpose, nonce }` over
  libp2p request-response (PeerID = did:key at the Noise layer). Each
  custodian: verify CACAO chain + purpose policy (reuse kotoba-auth +
  access_receipt policy) → write receipt datom + countersign → release the
  share HPKE-wrapped to the REQUESTER. Client combines t shares locally.
- **R3c — verifiable + rotatable**: Feldman VSS (curve commitments replace
  SHA-256 — custodians can verify their share against public commitments at
  deal time, not just at open time) + MLS-epoch key rotation (custodian
  set changes ⇒ new epoch ⇒ re-deal; revocation granularity = epoch).
- **R3d — enforcement economics**: custodian bonds via MishmarBondEscrow
  (#84); a custodian releasing without a receipt (detected by receipt-chain
  cross-audit within a time window) is warranted (kotoba-dht warrant
  machinery) and slashed; retainer rewards ride the pinner mKOTO settlement
  loop (#80/#81).

### R3a non-goals (explicit)

No dealer-cheating protection yet (the dealer is the current key holder —
the operator — who already knows the key; Feldman closes the gap when
re-dealing moves to custodians in R3c). No network surface yet. Mixed-dealing
shares combine to garbage, not an error (commitments are per-dealing;
quorum tooling in R3b tags dealings with a deal-id).

### R3b — custodian protocol core (`/kotoba/key/1`), 2026-06-11

Status: **core implemented** (transport shell deferred, like kotoba-turn #102)

`kotoba-custody::protocol` carries the wire types + the load-bearing
invariant, transport-agnostic:

- `KeyShareRequest { graph_cid_mb, cacao_b64, purpose, nonce,
  requester_x25519_pk }` → `KeyShareResponse::{Granted(GrantedShare), Denied}`.
- `handle_key_share_request(req, my_share, my_sk, authorize)` — the custodian
  calls the injected `authorize` closure FIRST (CACAO chain + purpose policy +
  nonce + **receipt write** all happen there); only on `Ok` does it open its
  at-rest share and re-wrap it (HPKE) to the requester's ephemeral pubkey.
  **"no receipt, no key" is control-flow-enforced** — a denied request never
  touches share material (test-pinned), and the authorize hook fires even when
  it denies (so the receipt precedes any release).
- `combine_granted(t, grants, requester_sk)` — requester opens t re-wrapped
  shares and recombines the key locally; t−1 grants cannot.
- Authorization is injected (server layer resolves CACAO via kotoba-auth +
  writes the receipt via access_receipt), keeping kotoba-custody a leaf crate
  — same seam discipline as the R2c import check.

A share in flight is sealed to the requester's key, so an eavesdropper or a
different requester cannot read it (test-pinned). The libp2p request-response
Behaviour (PeerID = did:key at Noise) is the remaining thin shell; R3c
(Feldman VSS + MLS epochs) and R3d (bonds/warrants) follow.

### R3b (server wiring) — `key.{requestShare,depositShare,custodianInfo}` XRPC, 2026-06-11

The custodian protocol core (kotoba-custody) is now reachable over XRPC; this
node acts as one custodian:

- **`key.custodianInfo`** (GET, public) — returns this node's DID + X25519
  pubkey so an operator dealing shares can wrap this node's share to it.
- **`key.depositShare`** (POST, operator-gated) — installs a `CustodianShare`
  for a graph into the in-memory `custody_shares` registry.
- **`key.requestShare`** (POST) — the release path. Builds the `authorize`
  closure injected into `handle_key_share_request`: for a Private graph it
  verifies a CACAO `datom:read` capability (issuer/aud/replay via
  `verify_cacao_graph_operation`), applies the purpose policy, and writes an
  `operation = key:requestShare` access receipt — THEN the protocol core opens
  this node's share and re-wraps it to the requester's ephemeral X25519 key.
  A denied request returns `{ok:false}` with no share material; the receipt is
  written before any release (the "no receipt, no key" invariant, now spanning
  the network boundary). The requester collects `threshold` grants from
  distinct custodian nodes and recombines locally (`combine_granted`).

Remaining R3: a libp2p request-response transport (the XRPC surface proves the
semantics; libp2p is the production carrier), per-graph key actually SPLIT to
custodians at seal time (today the operator deals manually), R3c VSS+MLS, R3d
bonds/warrants.

### R3c — epoch rotation + dealing binding (2026-06-11); Feldman VSS deferred

Status: **rotation/revocation implemented**; verifiable-secret-sharing deferred.

Two halves of R3c; we ship the operationally-load-bearing half (rotation) and
defer the cryptographic upgrade (VSS) with an honest rationale.

**Rotation + dealing binding (implemented).** Every `CustodianShare` now carries
an `epoch: u64` and a `deal_id = sha256(epoch || threshold || sorted share
commitments)`. Because the commitments derive from the random Shamir
polynomial, the deal_id is distinct not only across epochs and custodian sets
but across *any* separate re-deal — so `combine_key` now REJECTS a mixed-deal
quorum (`CustodyError::MixedDealing`) instead of silently reconstructing
garbage (closing the R3a non-goal). `rotate_key(key, t, new_custodians,
new_epoch)` re-deals to a changed set; `split_key_epoch` is the general dealer.
Server: `key.depositShare` enforces epoch monotonicity (a stale, revoked
dealing cannot be replayed over a newer one → 409); `key.requestShare`
surfaces the `epoch`. **Revocation granularity = epoch**: rotate, and a removed
custodian's old share can no longer participate in any quorum. `#[serde(default)]`
keeps pre-R3c deposited shares decoding at epoch 0.

**Feldman VSS (deferred, R3c-VSS).** True verifiable secret sharing — each
custodian checks its share against PUBLIC polynomial commitments `C_j = g^{a_j}`
at deal time, so a cheating dealer is caught immediately — requires moving the
secret sharing from the `sharks` crate's GF(2^8) field to a prime field matching
a curve's scalar order, with curve-point commitments. That is a real
cryptographic migration, not a wrapper, and the R0 review rule ("use an audited
crate, don't hand-roll") applies most sharply here. Until it lands, the
SHA-256 share commitments give detect-at-open integrity (a substituted share is
caught — see R3a tests) but not detect-at-deal; the trusted dealer is still the
current key holder (the operator), who already knows the key, so dealer-cheating
only becomes a live threat when re-dealing moves to the custodians themselves —
exactly the point at which VSS is required. Tracked as R3c-VSS.

### R3d — custodian warrants for unreceipted releases (2026-06-11)

Status: **enforcement implemented** (on-chain slashing = relayer boundary)

Closes the loop "release a share without a receipt ⇒ get caught ⇒ get
slashed", reusing the existing warrant machinery (kotoba-dht) and the R1
receipt log.

- **Signed grants = non-repudiable evidence.** `GrantedShare` is now
  self-describing (graph, requester pubkey, ts, epoch, deal_id) and
  `key.requestShare` signs it with the operator (custodian) Ed25519 key over
  `grant_signing_payload()` — same server-layer signing seam as the R2b commit
  signature (kotoba-custody is X25519-only). The requester keeps the signed
  grant.
- **Cross-audit** (`kotoba_custody::audit_grant`, pure): a grant is
  `Receipted` iff a `key:requestShare` access receipt exists for the same graph
  within `window_secs` of the grant ts; otherwise `UnreceiptedRelease`.
- **`key.reportUnreceiptedRelease`**: anyone presents a signed grant; the node
  verifies `grant_sig` against the custodian's did:key (an unsigned grant → 400,
  an invalid signature → not warranted), then cross-audits the receipt log. No
  covering receipt ⇒ a **`CustodyUnreceiptedRelease` (rule 8)** warrant is
  emitted, with the signed grant pinned as evidence and the warrant
  validator-signed. An off-chain relayer feeds the warrant + evidence to
  MishmarBondEscrow (#84) for slashing — the same build-here / submit-elsewhere
  boundary as the R2a anchor; retainer rewards ride the pinner mKOTO settlement
  loop (#80/#81).

Remaining R3: libp2p request-response transport + warrant gossip propagation
(K/2 → eviction, the deferred network shell); R3c-VSS (Feldman); the on-chain
MishmarBondEscrow bond deposit + slash execution (Solidity, operator/Council-
gated). With R3a–R3d the design is end-to-end: 「公開複製可能なのは暗号文だけ。
復号鍵が通る道は t-of-N custodian で、身元と目的を申告して署名付きで記録され、
記録なしに鍵を出した者は証拠付きで罰せられる」。

### R3 operator tooling — kotoba key {gen-key,deal,combine} (2026-06-11)

Status: implemented

Turns the R3 custody primitives into an operable feature, all offline:

- `kotoba key gen-key` — generate an X25519 custodian/requester keypair (hex).
- `kotoba key deal --key-hex K --threshold T --custodian DID:PUBKEY_HEX … [--epoch N]`
  — split KOTOBA_BLOCK_KEY into t-of-N HPKE-wrapped shares (one JSON line per
  custodian), each ready to POST to that custodian's key.depositShare.
- `kotoba key combine --grant FILE … --requester-sk-hex SK --threshold T`
  — recombine key.requestShare grants into the block key locally; the
  requester's X25519 secret never leaves the machine.

The operator's path to running R3 (deal across council devices, rotate by
re-dealing at a higher epoch, recover by combining any t grants) with no
single key file ever existing. libp2p transport + on-chain bond/slash remain
the deferred shells.
