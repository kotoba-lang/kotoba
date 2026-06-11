# Kotoba accountability architecture — the X-Road translation

> *"Access is possible, but who accessed what and why is retained, and someone
> is accountable."* — the Estonia e-government (X-Road) stance, translated to
> content-addressed storage.

Plain IPFS gives availability but no accountability: anyone who learns a CID
fetches the block, and nothing records that they did. Kotoba keeps the
availability and adds the accountability **at the mediation layer**, not the
storage layer — the same architectural choice X-Road makes (the storage is
ordinary; the Security Server is where authentication, purpose, and signed
logging live).

The one-sentence invariant the stack enforces:

> **What replicates publicly is ciphertext only. The decryption key travels one
> path — a t-of-N custodian quorum that releases a share only after the
> requester declares identity and purpose and the release is signed and
> receipted; the receipt log is anchored and tamper-evident; and a custodian
> who releases without a receipt is provably guilty and slashable.**

Every layer below is implemented, tested, and (R1–R3d) verified running over
HTTP against a live server. Full design + rationale:
[`docs/ADR-sealed-cold-tier.md`](./ADR-sealed-cold-tier.md).

## The layers

| Layer | Property | Mechanism | Where |
|-------|----------|-----------|-------|
| **R0** | Only ciphertext leaves the node | `SealedBlockStore` — AES-256-GCM `KSB1` envelope per block, stored under `sealed_cid = H(envelope)` so Kubo's CID-recompute still works; deterministic content-derived nonce; `KOTOBA_BLOCK_KEY` to enable | `kotoba-store` |
| **R1** | Who / what / why / when is recorded | Access receipts — every authorized non-public read (and key release) emits a datom (`access/{graph,accessor-did,operation,purpose,ts-unix}`) into `kotoba/audit/access-receipts/v1`; `x-kotoba-purpose` header; batched background writer | `kotoba-server` `access_receipt` |
| **R2a** | The operator can't silently rewrite history | `audit.anchorPayload` — `AnchorBridge.commitRoot` calldata committing the audit-graph head to Base (relayer submits; KSI analog) | `kotoba-server` + `kotoba-evm` |
| **R2b** | Neither party can deny it | Author-signed CommitDag — `DistributedDatomCommit.author_sig` (Ed25519 over a canonical payload); receipts carry `access/cacao-cid` (requester-signed evidence). *The Journal is deprecated; the CommitDag is the canonical chain.* | `kotoba-datomic` |
| **R2c** | Tampered history can't be imported, and is checkable in one call | `commit_import_check` gates the merge path (`Invalid` always rejects; `Unsigned`/`Unverifiable` under `KOTOBA_REQUIRE_SIGNED_COMMITS`); `audit.verifyChain` walks the audit chain reporting per-commit verdicts | `kotoba-auth` + `kotoba-server` |
| **R3a** | The key is not a single point | t-of-N Shamir split (`sharks` GF(2^8)), each share HPKE-wrapped to a custodian's X25519 key, SHA-256 share commitments | `kotoba-custody` `shares` |
| **R3b** | No receipt, no key — across the network | `key.requestShare` — custodian verifies CACAO `datom:read` + purpose + nonce and **writes a receipt before** opening and re-wrapping its share to the requester; client recombines t grants locally | `kotoba-custody` `protocol` + `kotoba-server` `key_share` |
| **R3c** | Custodians and keys rotate; revocation is real | `epoch` + `deal_id` (binds the polynomial) on every share; `combine_key` rejects mixed-deal quorums; `key.depositShare` enforces epoch monotonicity (stale dealing → 409) | `kotoba-custody` |
| **R3d** | An unreceipted release is punishable | Grants are custodian-Ed25519-signed (non-repudiable); `key.reportUnreceiptedRelease` cross-audits a signed grant against the receipt log and emits a `CustodyUnreceiptedRelease` warrant + pinned evidence (relayer → MishmarBondEscrow slash) | `kotoba-custody` `audit` + `kotoba-dht` + `kotoba-server` |
| **ops** | Operable, no single key file | `kotoba key {gen-key,deal,combine}` — deal a key across council devices, rotate by re-dealing at a higher epoch, recover by combining any t grants | `kotoba-cli` |

## Live-verified flow

Running against a server (`KOTOBA_IPFS=off KOTOBA_NO_SWARM=1 kotoba serve`):

1. `key.custodianInfo` → node DID + X25519 pubkey.
2. `kotoba key deal --threshold 2 --custodian …` → 3 shares bound by one `deal_id`.
3. `key.depositShare` → installed (operator-gated; non-operator → **401**).
4. `key.requestShare` → custodian writes a receipt, releases a **64-byte
   Ed25519-signed** grant with a 93-byte HPKE share.
5. `audit.listReceipts` → the `key:requestShare` receipt is present.
6. `audit.verifyChain` → `depth 1, valid 1, invalid 0, ok:true`.
7. `key.reportUnreceiptedRelease`: genuine grant → `receipted`; unsigned grant
   → **400**; a validly self-signed grant with no receipt → **`warranted:true`**,
   accused DID identified, evidence pinned.
8. Re-deal at `epoch 1` → deposit replaces; stale `epoch 0` re-deposit → **409**;
   grant reports the rotated epoch.

## What is intentionally deferred

- **R3c-VSS** (Feldman verifiable secret sharing — detect a cheating dealer at
  deal time) needs migrating off `sharks` GF(2^8) to a prime field with
  curve-point commitments; the audited-crate rule applies, so it is a tracked
  follow-up, not a hand-rolled patch.
- **libp2p transport** for `/kotoba/key/1` + warrant gossip propagation: the
  XRPC surface proves the semantics; libp2p is the production carrier.
- **On-chain** MishmarBondEscrow bond deposit + slash execution (Solidity,
  Council-gated): kotoba builds the warrant + anchor payloads; an off-chain
  relayer submits — the same build-here / submit-elsewhere boundary throughout.

These are operational shells. The cryptographic and accountability design
(R0–R3d) is complete.
