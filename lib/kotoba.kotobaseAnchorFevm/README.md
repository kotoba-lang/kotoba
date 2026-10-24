# kotobase-checkpoint-anchor-runtime

Asynchronous, chain-neutral checkpoint receipts for Kotobase.

The default capability is a signed append-only transparency log. It requires
no Filecoin account, blockchain, gas token, RPC service, IPFS, or physical
storage format. Receipts contain only salted opaque commitment values, a hash
chain and an Ed25519 signature. Database IDs, epochs, logical/physical roots,
graph CIDs and datoms do not cross the disclosure boundary.

`kotobase.anchor.checkpoint` owns the portable submission plan.
`runtime/checkpoint-material.mjs` owns private commitment derivation.
`runtime/transparency-anchor.mjs` is the standard chainless implementation.
`runtime/journal-store.mjs` supplies the fsync-backed durable CAS/receipt log.

Public-chain notarization is optional. `runtime/evm-interpreter.mjs` implements
standard EVM JSON-RPC, gas bounds, confirmations and block-hash reorg handling.
`profiles/filecoin-calibration.mjs` is one replaceable network profile; it is
not imported by the chainless path. The Solidity contract uses no Filecoin
precompile or PieceCID and can deploy on any compatible EVM.

The historical `kotobase.anchor.fevm` namespace and
`runtime/rpc-interpreter.mjs` remain compatibility facades. Neither default nor
optional runtime dependencies resolve `cloud-filecoin`.

No anchor is an `IEngine`, graph head, transaction acknowledgement, block
provider, or query dependency. Losing every anchor backend must not make the
graph database unavailable.

```sh
kbb -M:test
kbb -M:lint
npm ci
npm run test:cljs
npm run test:runtime
npm run test:contract
npm run qualify:transparency
```

## Where this fits / quick use

Stack position: kotoba (language, authority) -> itonami (jobs) -> murakumo
(compute) -> kotobase (state/results) -> **optional anchor (this repo)**. The
private-network layer, AWAI DNA (DNA CID = network id, signed per-agent source
chains), is a proposed spec only (network-awai/network-awai-apex PR #14, branch
`dna-private-network-spec`, `awai-dna/`). Interactive figure:
<https://kotoba-lang.org/anatomy/kotoba-murakumo/>.

Default path, no blockchain: a signed, append-only transparency log
(`runtime/transparency-anchor.mjs`). Each receipt is a line in a local
fsync-backed JSONL file carrying a sequence number, the previous receipt's
SHA-256, salted opaque digests and an Ed25519 signature, so anyone with the
public key can verify the whole log and spot a truncated or edited tail. It
needs only Node, a dedicated signing key and a dedicated disclosure salt.

Optional path: notarize on an EVM network through `runtime/evm-interpreter.mjs`
(standard JSON-RPC, gas bounds, confirmations, reorg handling). The network is a
replaceable profile (chain ID, RPC URL, confirmation and gas policy);
`profiles/filecoin-calibration.mjs` is one example and the chainless path never
imports it. This path needs `npm ci` (`ethers`), an RPC endpoint and a funded
key, and is not needed for the default.

To exercise the default path locally (no network, no keys; the qualification
script generates an ephemeral identity and requires a clean git worktree):

```sh
node --test runtime/test/transparency-anchor.test.mjs
npm run qualify:transparency   # appends 2 receipts, reopens, verifies the chain
```

Rule: no anchor is on the query or availability path. A kotobase graph never
waits on, reads from or is acknowledged by an anchor, and losing every anchor
backend degrades audit notarization only.

See [`docs/CHECKPOINT_ANCHOR_RUNBOOK.md`](docs/CHECKPOINT_ANCHOR_RUNBOOK.md).
Filecoin Calibration remains an optional profile documented in
[`docs/FEVM_TESTNET_RUNBOOK.md`](docs/FEVM_TESTNET_RUNBOOK.md).
