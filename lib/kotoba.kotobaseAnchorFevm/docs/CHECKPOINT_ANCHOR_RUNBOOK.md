# Chain-neutral checkpoint anchor runbook

## Default: signed transparency receipts

The standard backend is `runtime/transparency-anchor.mjs`. It appends
mode-`0600`, fsync-backed JSONL receipts containing:

- monotonically increasing sequence;
- previous receipt SHA-256;
- salted opaque idempotency and checkpoint digests;
- canonical timestamp and Ed25519 public identity;
- Ed25519 signature and receipt SHA-256.

It requires durable filesystem storage, a dedicated Ed25519 signing key and a
dedicated 32-byte disclosure salt. Neither credential may reuse graph signing,
encryption, maintenance, tenant, EVM, or physical-index keys.

```sh
npm ci
npm run test:runtime
npm run qualify:transparency
```

Qualification refuses a dirty worktree, reopens the log to verify every
signature/hash link, verifies duplicate suppression, and emits a protected raw
log digest. For production, replace the ephemeral qualification identity with
an approved secret-backed identity and replicate the receipt log to B2 plus at
least one independently operated witness.

## Optional EVM adapters

EVM is a provider choice, not the checkpoint protocol. Each profile supplies:

- profile ID and chain ID;
- RPC URL;
- confirmation and gas policy;
- environment-variable prefix.

The generic contract and interpreter contain no Filecoin-specific operation.
Filecoin Calibration is retained only as `profiles/filecoin-calibration.mjs`.
Other EVM networks or a private/local EVM use the same adapter with a different
reviewed profile.

## Disable and recovery

Stop leasing new anchor jobs. Preserve the signing key, disclosure salt,
receipt log and submitted external receipts. Graph transactions and reads
continue because anchoring is asynchronous and non-authoritative.

- damaged transparency tail: stop appends, preserve bytes, restore the last
  verified receipt and reconcile replicas; never silently truncate;
- lost signing key: close that signer epoch, retain its public key and start a
  separately recorded identity transition;
- EVM RPC outage: retain queue/CAS state and poll later;
- EVM reorg: reject the orphaned block identity and replay the same opaque
  idempotency key;
- all anchor providers unavailable: report degraded audit notarization only,
  never graph-database unavailability.
