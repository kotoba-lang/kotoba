# @etzhayyim/sdk

kotoba substrate SDK for `etzhayyim/root` open religious-corp apps. Per **[ADR-2605172000](../../90-docs/adr/2605172000-etzhayyim-kotoba-substrate.md)**, apps under `etzhayyim/root` MUST NOT depend on RisingWave or any centralized off-chain database. This SDK wraps the primary substrate — **AT Protocol MST + IPFS + Base L2 anchor** — as one ergonomic API.

> **Status**: scaffold v0.0.0. All implementations are TODO stubs. Reference implementation lands when the first open-* app (`open-isco` candidate) ports to the SDK.

## What it replaces

| Old (RisingWave-backed) | New (SDK call) |
|---|---|
| `INSERT INTO vertex_<actor>_<kind>` | `e.write({ collection, record, blobs? })` |
| `SELECT ... WHERE` | `e.read({ collection, prefix?, cursor?, limit? })` |
| streaming materialized view | `e.subscribe({ collections })` AsyncGenerator over PDS firehose |
| tamper-evidence / audit log | `e.verify(uri)` returns Merkle proof + on-chain anchor tx |
| large blob in RW row | `WriteOpts.blobs` Map → SDK pins to IPFS, embeds CID in record |
| Stripe Checkout / one-shot charge | `e.pay({ to, amount, reason })` USDC on Base L2 |
| Stripe Billing / subscription | `e.payStream({ to, flowRate, reason })` Superfluid stream |
| Refund / dispute | `e.escrowOpen(...)` + `e.escrowRelease(...)` Gnosis Safe 2-of-3 |
| Revenue share (W-9 1099 distribution) | `e.splitDistribute({ splitAddress, amount })` 0xSplits |

## Quick start (target API, scaffold only)

```typescript
import { Etzhayyim } from "@etzhayyim/sdk";

const e = new Etzhayyim({
  did: "did:web:etzhayyim.com",
  pdsUrl: "https://pds.etzhayyim.com",
  ipfsGateway: "https://ipfs.etzhayyim.com",
  ipfsApiUrl: "https://ipfs-api.etzhayyim.com",
  l2RpcUrl: "https://mainnet.base.org",
  anchorContract: "0xANCHOR_ETZHAYYIM",
  signer: passkeyDidSigner,  // WebAuthn → DID-bound
});

// Write — pins blob to IPFS, then createRecord on PDS, then schedules
// MST root for next L2 anchor batch.
const receipt = await e.write({
  collection: "com.etzhayyim.apps.openIsco.occupation",
  record: {
    code: "2511",
    name: "Software Developer",
    major: "2",
    handbookRef: { $type: "blob" },  // SDK fills with IPFS CID
  },
  blobs: new Map([["handbookRef", handbookPdf]]),
});
// → { uri, cid, blobCids, pendingAnchor }

// Read — MST traversal, optional blob fetch.
const { records, cursor } = await e.read<Occupation>({
  collection: "com.etzhayyim.apps.openIsco.occupation",
  prefix: "2",   // major code prefix
  limit: 50,
});

// Verify — third-party Merkle proof against L2 anchor.
const proof = await e.verify(receipt.uri);
// → { included, anchoredAt: { txHash, blockNumber, rootCid }, merklePath }

// Subscribe — replaces streaming MV.
for await (const ev of e.subscribe<Occupation>({
  collections: ["com.etzhayyim.apps.openIsco.occupation"],
})) {
  console.log(ev.op, ev.uri, ev.value);
}
```

## Module layout

```
src/
├── index.cljc    # Etzhayyim class, public types, re-exports
├── pds.cljc      # AT Protocol PDS write/read helpers
├── ipfs.cljc     # IPFS pin/fetch helpers
├── l2.cljc       # Base L2 anchor contract helpers
└── pay.cljc      # USDC + ERC-4337 + Superfluid + Safe + 0xSplits (ADR-2605172100)
```

Apps MUST import from `@etzhayyim/sdk` only. Direct imports of `@atproto/api`, IPFS client libraries, or `viem` from app code are prohibited (the SDK is the only seam where substrate clients are imported).

## Hard rules (enforced by ADR-2605172000 + ADR-2605172100 + future CI hook)

State substrate (ADR-2605172000):
- **No `risingwave` / `kysely` / `pg` / `postgres` imports** anywhere under `etzhayyim/root/60-apps/` or `etzhayyim/root/20-actors/` (excluding this SDK itself).
- **No SQL strings** (`SELECT`, `INSERT`, `CREATE TABLE`, `mv_`, `vertex_`) outside SQL-migration test fixtures.
- **No central DB credentials** in app code or env. Identity is DID; signing is WebAuthn or operator-held private key.

Payment substrate (ADR-2605172100):
- **No `stripe` / `paypal` / `square` / `razorpay` / `braintree` / `adyen` imports** anywhere under `etzhayyim/root/`.
- **No fiat currency codes** (`USD`, `EUR`, `JPY`, `INR`, ...) as `currency` field in payment records. USDC base units only.
- **No `bank_account` / `ach_credit` / `wire_transfer` / `card_number` literals**.
- **All payments through SDK pay/payStream/escrow/split methods.** Direct `viem.writeContract` for USDC transfer from app code is prohibited — `src/pay.cljc` is the only seam.
- **All payment events recorded as AT Records** (in addition to on-chain tx) so MST traversal can reconstruct payment history without a chain indexer.

## Encrypted records (Tahoe-pattern, ADR-2605181100)

Private state on the substrate. AEAD envelope (`com.etzhayyim.encrypted.record`) + per-recipient Signal-wrapped symmetric key (`com.etzhayyim.encrypted.keyWrap`). The CID over the envelope inherits MST verify-cap + L2 anchor finality from ADR-2605172000.

```typescript
await e.encryptedWrite({
  innerType:  "com.etzhayyim.governance.proposal",
  record:     { title: "Council motion 42", body: "..." },
  recipients: ["did:web:alice.example", "did:web:bob.example"],
});

const { records } = await e.encryptedRead<ProposalBody>({
  innerType: "com.etzhayyim.governance.proposal",
});
```

Direct app imports of `@noble/ciphers` / `@signalapp/libsignal-client` are **prohibited** — same hard-rule seam as `@atproto/api` and `viem`. Use:

- `@etzhayyim/sdk/crypto` — XChaCha20-Poly1305 envelope (real impl)
- `@etzhayyim/sdk/signal` — Signal session, key-wrap/unwrap (real libsignal-backed impl)
- `@etzhayyim/sdk/did-signal` — DID ↔ Signal IdentityKey binding (real impl, Ed25519 over CBOR)

### Reference impl — council deliberation

`test/council-flow.test.cljc` is the canonical E2E example: two council members each generate Ed25519 DID keys + libsignal identities, publish DID-signed `signalIdentity` records, then exchange encrypted proposal/vote records over the substrate. Copy-paste template for new private flows (uhl-right-neural council, medical referral cohort, ethics committee, etc.).

### Metadata-leak mitigations (ADR-2605181200)

Two opt-in mitigations on `encryptedWrite{,Standalone}`:

```typescript
await encryptedWriteStandalone(deps, {
  innerType: "...",
  record: {...},
  recipients: [...],
  pad: "bucket",     // ciphertext rounds up to {1, 4, 16, 64} KiB → blob fallback
  blindRkey: true,   // rkey = base32(BLAKE2b-128(symKey || seq)) — hides write time
});
```

Both default off in v0.1.x to give the council-flow reference impl a clean rollout; v0.2.0 will flip them on. Sealed Sender + PDS-side timing/decoy mitigations are tracked in follow-up ADRs.

## Dependencies

- `@atproto/api` — PDS write/read, firehose subscribe
- `viem` — Base L2 RPC + contract interaction
- `@noble/ciphers` + `@noble/hashes` + `@noble/curves` — AEAD, hash, Ed25519 (pure TS)
- `@signalapp/libsignal-client` (optional) — Signal Protocol for key-wrap delivery
- IPFS HTTP API client TBD (`ipfs-http-client` or `helia`; chosen during reference impl)

## Versioning

Current: `0.0.0` (scaffold). API surface is **not yet stable** — every method throws "not yet implemented". The first stable cut (`0.1.0`) lands together with the first reference-impl app migration.

## See also

- [ADR-2605172000](../../90-docs/adr/2605172000-etzhayyim-kotoba-substrate.md) — substrate hard rule + per-app migration patterns
- [ADR-2605171800](../../90-docs/adr/2605171800-langgraph-mst-ipfs-l2-anchor-pipeline.md) — pipeline this SDK packages
- [ADR-2605170900](../../90-docs/adr/2605170900-etzhayyim-root-adr-canonical-home.md) — etzhayyim/root canonical home rule

## License

Apache 2.0
