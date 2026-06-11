# Mishmar Storage Covenant — kotoba observation-side sketch

Companion to **ADR-2606082100** (`etzhayyim-root/90-docs/adr/`).

**Boundary invariant (do not break):** kotoba is **read + verify only** for all
chains. The Mishmar staking/slashing/SBT and the on-chain social-capital
settlement live on the **anchor chain** (geth-private PoA → Base L2 via
`AnchorBridge`). kotoba **observes and verifies** them; it never signs a tx,
custodies a bond, or settles on-chain. This mirrors the existing `eth/*` +
`bind_evm` posture (EVM read+verify surface, 2026-05-30) and the Bitcoin
read+verify surface (2026-06-03).

```
            ANCHOR CHAIN (operating-entity side — kotoba does NOT write)
            ┌───────────────────────────────────────────────────────────┐
            │ AnchorBridge.commitRoot(rootHash, ipfsCid, batchSize)       │
            │ MishmarBondEscrow: Pinned / Challenged / Proven / Slashed   │
            │ TitheRouter: Routed(purpose="storage-slash" | "retainer")   │
            │ ReputationSBT: mint / burn                                  │
            └───────────────────────────────────────────────────────────┘
                         │  eth_getLogs / eth_call / EIP-1271 (READ ONLY)
                         ▼
            ┌───────────────────────────────────────────────────────────┐
            │ kotoba  (observe → verify → project to Datoms)              │
            │   kotoba-auth/eth/*      decode + verify                    │
            │   kotoba-runtime bind_evm  RPC read (CALL_FOREIGN, 1000 gas)│
            │   kotoba-graph QuadStore   project observations → :mishmar/*│
            └───────────────────────────────────────────────────────────┘
```

## What kotoba observes (and where it plugs in)

| Anchor-chain fact | kotoba read path (existing) | Projected Datom |
|---|---|---|
| `Pinned(pinId, rootCid, pinner, bond, dur)` | `bind_evm` `eth_getLogs` (raw JSON, caller-decode) | `:mishmar/pin/<pinId>` {rootCid, pinner_did, bond_mkoto, duration} |
| `Challenged` / `Proven` | `eth_getLogs` | `:mishmar/pin/<pinId>/proof/<epoch>` |
| `Slashed(pinId, bond, purpose)` | `eth_getLogs` + `TitheRouter.Routed` cross-check | `:mishmar/pin/<pinId>/slashed` |
| witness quorum sig | EIP-1271 (`eth/eip1271.rs`) for contract signers; Ed25519/CACAO for DID signers | `:mishmar/proof/<pinId>/witness/<n>` |
| ReputationSBT balance | `erc20-balance-of`-style view call (`eth/token.rs`, SBT is non-transferable ERC) | `:social/reputation/<DID>` |
| rootCid liveness | kotoba's own block store `has(cid)` + Kubo `block/stat` | `:mishmar/avail/<rootCid>` (self-measured, the thing the proof asserts) |

## Verification kotoba performs (read-only, no signing)

1. **Anchor cross-check** — for a `Pinned.rootCid`, confirm the *same* root was
   committed via `AnchorBridge.commitRoot` (`committerOf[rootHash] != 0`) and
   that kotoba's CommitDag head for that graph hashes to it. Three-way match:
   geth-private ↔ Base L2 anchor ↔ local CommitDag root.
2. **Witness quorum** — recompute `hash(rootCid) % N` to derive the expected
   5-cell set; verify ≥3 distinct attestation signatures over the challenge
   nonce (DID sigs via CACAO/Ed25519; contract sigs via EIP-1271 magic
   `0x1626ba7e`). This is the *same* quorum kotoba already uses for
   kotoba-datomic membrane validation — reused, not reinvented.
3. **Slash integrity** — a `Slashed` event must be matched by a
   `TitheRouter.Routed(purpose="storage-slash", recipient=publicFund)` with the
   90/10 split intact. A slash that does not land in the Public Fund is invalid
   (flag for Council).
4. **Self-availability truth** — kotoba independently checks `block_store.has`
   / Kubo `block/stat` for the challenged block, so its projection reflects
   *observed* availability, not just the on-chain *claim*.

## Social-capital read (the economic denominator)

Social capital is an **internal Quad ledger** (`social/capital/<DID>/<epoch>`),
minted from validated **information-disclosure** (`attest/*` + CitationLedger
hit) and **wellbecoming intervention** (KaizenObserver wellbecoming-Δ, ADR-0075).
kotoba already owns these inputs:

- disclosure: `attest/stake_mkoto` + `citation/royalty_mkoto` (kotoba-server
  attestation.rs + CitationLedger) — already Datoms.
- wellbecoming-Δ: ingested from KaizenObserver as a signed observation, gated by
  Council Lv6+ ≥3 attestation before minting.

kotoba **computes** social capital (mint + exponential decay per epoch) as a
materialized view over these Datoms, and **exposes** it read-only so Part C
(donation routing) and witness-selection weighting can consume it. Decay means
it is a *flow* that must be re-earned — never a transferable store (§2(b) /
Yobel safe).

```
social_capital(DID, epoch)
  = Σ_disclosure  w_d · validated_disclosure(DID, ≤epoch) · decay(epoch − t)
  + Σ_wellbecoming w_w · max(0, wellbecoming_Δ(DID, ≤epoch)) · decay(epoch − t)
  − Σ_burn        falsified_or_harm(DID, ≤epoch)
```

## Proposed surfaces (follow-up, not yet implemented)

- `kotoba-auth`: `mishmar.rs` — decode `MishmarBondEscrow` / `TitheRouter` logs
  via `eth/abi.rs`; verify quorum via existing CACAO + `eip1271.rs`. I/O-free
  codec, same shape as `eth/token.rs`.
- `kotoba-runtime` `bind_evm`: no new host fn needed — `eth_getLogs` + `eth_call`
  already cover it; caller-side decode in guest/server.
- `kotoba-server`: XRPC `com.etzhayyim.apps.kotoba.mishmar.status?rootCid=…`
  returning the three-way cross-check + current pin/proof/slash state +
  originating-agent social capital.
- `kotoba-graph`: `:mishmar/*` + `:social/*` projection namespace; a MV over the
  disclosure/wellbecoming Datoms for the social-capital score.

## Explicitly NOT in kotoba (operating-entity boundary)

- posting/answering/settling bonds, minting/burning SBTs, routing tithe,
  signing anchor txs — all etzhayyim-exclusive, on the anchor chain.
- kotoba's role ends at: **observe → verify → project → expose read-only**.
