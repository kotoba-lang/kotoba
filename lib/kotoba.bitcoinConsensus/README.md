# bitcoin-consensus

Portable, deterministic Bitcoin full-block consensus kernel for kotoba-lang.

This repository is separate from the permanently read-only
[`org-bitcoin-p2p`](https://github.com/kotoba-lang/org-bitcoin-p2p) observer.

## Implemented

- bounded, canonical CompactSize and raw legacy/SegWit transaction decoding,
  including Core's stripped-size and weight-derived input/output/witness limits
- unsigned 64-bit amount decoding without host integer overflow
- txid/wtxid, exact transaction and block weight, money-range and prevout checks
- transaction Merkle trees with CVE-2012-2459-style mutation detection
- activation-aware BIP141 witness malleation and commitment validation,
  including pre-SegWit `unexpected-witness` rejection
- block coinbase, duplicate transaction, and 4,000,000 weight checks
- contextual header difficulty, PoW, linkage, MTP, future-time, testnet4
  BIP94 adjustment-boundary timewarp protection, buried BIP34/BIP66/BIP65
  version floors, Core-exact compact-target overflow boundaries, and chainwork
- mainnet, testnet3, testnet4/BIP94, default signet/BIP325, and regtest
  consensus parameters and genesis trust anchors
- legacy, P2SH, SegWit v0, and Taproot key/script-path Script verification
- legacy, BIP143, and BIP341/342 sighash plus ECDSA/BIP340 Schnorr verification
- Core-retroactive P2SH/WITNESS/TAPROOT flags plus historical
  lax-DER/BIP66, CLTV, CSV/BIP68, BIP147, Taproot, and BIP30 exceptions
- Core-identical BIP30 collision gating: coinbase replacement at the two
  historical repeats and below height 1,983,702 on pinned BIP34 chains;
  non-coinbase UTXO overwrites remain forbidden in every block
- Core-ordered BIP9 versionbits transitions, including start/timeout and
  threshold/timeout precedence, plus network-specific buried deployments
- early `CheckBlock`-equivalent legacy sigop rejection plus full
  legacy/P2SH/witness accounting with the 80,000 block-cost limit
- transaction finality plus BIP34/BIP113 and relative lock-time validation
- atomic UTXO application, input/accumulated-fee MoneyRange, coinbase
  maturity, per-network subsidy, fees, and undo
- network-bound SQLite UTXO storage with WAL/FULL durability, ordered outpoints,
  atomic block delta + undo commits, stale-tip rejection, restart-safe
  disconnect, multi-block reorganization + host-state commits, integrity
  checks, schema migration, normalized fixed-length header nodes, compact host
  metadata, disabled-by-default subprocess crash-test fault points, and
  O(touched outpoints) transition memory
- monotonic active-chain undo retention with a snapshot-aware prune floor,
  bounded immediate reorganization depth, typed deep-reorg recovery, and
  retained-journal linkage audits
- single-connection normalized ancestry cursors for mainnet-scale snapshot and
  recovery proofs without connection-per-header amplification
- Core-identical `OP_RETURN`/oversized-script UTXO pruning and unsigned
  32-bit transaction-version handling for CSV/BIP68
- most-cumulative-work fork choice, tested multi-block reorganization, and
  durable invalid-branch quarantine with viable-header recovery
- headers-first synchronization that never activates missing block data
- Bitcoin Core-exact `assumevalid` gates: assumed/best chain ancestry,
  minimum chainwork, and 256-bit `GetBlockProofEquivalentTime` rounding at
  the strict two-week proof-equivalent burial boundary
- authenticated Core v2 AssumeUTXO streaming decode for mainnet, testnet3,
  testnet4, and signet, including exact `hash_serialized_3` commitments and
  constant-memory authenticated import into SQLite
- separate assumed and background-validated snapshot states
- checksummed atomic chainstate v2 persistence, v1 migration, and restart
  invariant validation, plus explicit raw-header/hash/link/height/chainwork
  integrity audit
- bounded multi-peer block scheduling, response matching, timeout requeue, and
  misbehavior scoring
- official BIP143/BIP340/BIP341 vectors, mainnet genesis/block 1 fixtures,
  all 1,222 Bitcoin Core v31.1 Script outcomes, all 214 Core transaction
  outcomes, all 500 Core legacy sighash outcomes, mined multi-block
  validation, and Core-generated AssumeUTXO regtest differential conformance

## Security boundary

The JVM chainstate now uses the in-process Script verifier by default; an
explicit callback remains available for differential testing. AssumeUTXO
snapshots are activated only after their network, independently validated base
header, coin count, and Core commitment match a pinned checkpoint; promotion
to `:validated` additionally requires a full background chainstate match.

This is still not a drop-in Bitcoin Core replacement. All 1,222 upstream
Script, all 214 transaction, and all 500 legacy sighash vectors run in CI with
exact parity, including Core-generated Taproot fixtures and policy flags for
unknown leaf versions, `OP_SUCCESS`, and upgradable tapscript public-key types.
These policy flags remain opt-in and do not narrow block-consensus acceptance. The
mainnet-sized disk UTXO/undo backend is integrated by `bitcoin-node` with atomic
fork-choice metadata and snapshot-start support. Completing a full
genesis-to-tip mainnet historical differential run remains required.
Script, AssumeUTXO, and persistence adapters are currently JVM-only;
wire codecs, consensus values, BIP9, headers-first state, and scheduling remain
portable Clojure/ClojureScript values.

```bash
kbb -M:test
kbb -M:lint
kbb -M:coverage
kbb -M:fuzz 21000000 5000     # replayable 15,000-target CI corpus
./scripts/core_regtest_differential.sh # requires bitcoind + bitcoin-cli
./scripts/core_script_vectors.sh       # all pinned Core v31.1 corpora
kbb -M:core-tx-vectors \
  /path/to/bitcoin/src/test/data/tx_valid.json \
  /path/to/bitcoin/src/test/data/tx_invalid.json
kbb -M:core-sighash-vectors \
  /path/to/bitcoin/src/test/data/sighash.json

# Resume a real Core-backed historical range from a durable kernel checkpoint:
CONSENSUS_CORE_DATADIR=/path/to/bitcoin \
CONSENSUS_HISTORY_NETWORK=mainnet \
CONSENSUS_HISTORY_START=0 \
CONSENSUS_HISTORY_END=9999 \
CONSENSUS_HISTORY_CHAINSTATE=/path/to/kernel-chainstate.edn \
./scripts/core_history_differential.sh

# Long differential with restart/reload every 250 blocks:
CONSENSUS_DIFFERENTIAL_BLOCKS=1003 \
CONSENSUS_RESTART_INTERVAL=250 \
./scripts/core_regtest_differential.sh
```

The fuzz runner bounds inputs to 4,096 bytes and iterations to 1,000,000,
prints the exact seed, rejects host exceptions or untyped failures, and checks
canonical transaction/block/Script raw round trips. CI replays one seed with a
90-second process deadline; the scheduled workflow runs four larger seeds with
independent five-minute deadlines.
