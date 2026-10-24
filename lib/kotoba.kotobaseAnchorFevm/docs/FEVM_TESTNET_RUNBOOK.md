# Optional profile: Filecoin Calibration

This is not the standard checkpoint path. The chainless signed transparency
backend requires no Filecoin dependency. This optional profile is asynchronous
and non-authoritative. Disabling it must not affect
graph transactions, queries, heads, B2 reads, or physical-index qualification.

## Fixed testnet boundary

- Network: Filecoin Calibration
- Chain ID: `314159`
- Default RPC: `https://api.calibration.node.glif.io/rpc/v1`
- Contract: `contracts/src/KotobaseCheckpointAnchor.sol`
- On-chain fields: opaque idempotency key and opaque checkpoint digest
- Forbidden disclosure: database ID, tenant ID, logical root, physical root,
  PieceCID, graph CID, raw datoms

The public RPC value and chain ID follow the Filecoin Calibration network
documentation. Treat a public RPC as replaceable infrastructure, not as a
trust root.

The disclosure salt prevents the on-chain values from exposing or correlating
equal private checkpoint payloads across deployments. It does **not** hide the
transaction sender: submissions from one operator EOA remain publicly
correlatable. Evidence must label this as content non-correlation, not sender
anonymity. Full sender unlinkability would require a separate relayer, batching,
or account-rotation design and is not claimed by this track.

## Credentials

Generate three Calibration-only values; never reuse graph signing, graph
encryption, maintenance, physical-index, testnet tenant, or production keys:

- `FEVM_DEPLOYER_PRIVATE_KEY`: funded with test tFIL, deploy only;
- `FEVM_PRIVATE_KEY`: funded operator used by the asynchronous submitter;
- `FEVM_DISCLOSURE_SALT`: random 32-byte hex value used to make private
  checkpoint commitments non-correlatable across deployments.

Keep them in the approved secret manager. Temporary env/secrets files must be
mode `0600` and removed after use. Only public addresses enter evidence.
On macOS, `npm run credentials:calibration` provisions all three into Keychain;
the `*:keychain` commands inject them directly into child processes without
printing them or placing them in shell history.

## Deploy contract

From a clean, reviewed revision:

```sh
npm ci
npm run test:contract
FEVM_DEPLOYER_PRIVATE_KEY=... npm run deploy:calibration
```

The deploy command refuses a chain other than `314159`, requires a funded
account, waits for confirmations, verifies runtime bytecode, and emits a
source-revision-bound JSON record. Preserve that output in protected evidence.
Set its returned address as `FEVM_CONTRACT_ADDRESS`; never commit a placeholder.

## Runtime qualification

Run the durable submitter as a separate process/service with its own journal
volume. It consumes coordinator effects only after the journal CAS has
succeeded. Then execute a bounded live proof:

```sh
FEVM_PRIVATE_KEY=... \
FEVM_DISCLOSURE_SALT=... \
FEVM_CONTRACT_ADDRESS=0x... \
FEVM_EVIDENCE_JOURNAL=/protected/path/calibration-evidence.jsonl \
npm run qualify:calibration
```

Required retained evidence:

1. exact Git revision, contract bytecode digest and deployment transaction;
2. submit transaction, inclusion block number/hash, gas used and final
   confirmation count;
3. journal put-if-absent, claim CAS, receipt observations and terminal CAS;
4. retry after an injected RPC timeout with one on-chain receipt;
5. local fork/reorg drill showing a changed or missing block hash produces
   `reorged`, never `finalized`;
6. salt-A/salt-B proof that equal private inputs produce different public
   digest and idempotency values;
7. raw evidence SHA-256 and protected storage location.

`npm run qualify:reorg` performs the local Anvil snapshot/revert drill and
emits a SHA-256-bound protected journal. It must pass before live Calibration
qualification; it complements rather than replaces live finality evidence.

Calibration finality is evidence for the testnet interpreter only. It does not
authorize a production contract or establish an economic finality policy.

## Disable and rollback

The emergency control is to stop leasing new FEVM jobs. Do not delete jobs,
receipts, the journal, disclosure salt, or operator key while a submitted job
can still finalize.

- **Before submission:** release/expire the lease; queued jobs remain pending.
- **After submission:** disable new submissions but continue receipt polling,
  or export the journal to a replacement poller.
- **RPC outage:** retain claims and apply bounded backoff; do not fabricate
  failure or resubmit until the lease/CAS rules permit it.
- **Reorg:** mark the observation `reorged`; retry the same idempotency key.
  The contract makes identical replays no-ops and conflicting replays revert.
- **Contract defect:** set the runtime disabled, preserve evidence, deploy a new
  immutable contract, and write an explicit migration record. The contract is
  intentionally not upgradeable.

Rollback never changes graph authority because FEVM receipts are
non-authoritative consumers. A runbook or implementation that places FEVM on
the foreground acknowledgement path is invalid.
