# bitcoin-node

Backend-neutral, watch-only Bitcoin node integration for Clojure.

`bitcoin-node` defines a small `NodeBackend` protocol and ships a hardened
Bitcoin Core JSON-RPC adapter for:

- chain and initial-sync status;
- canonical public output descriptor inspection;
- Taproot and SegWit multisig policy validation;
- public receive-address derivation;
- explicit UTXO-set scans.
- network/genesis identity binding and Core capability discovery;
- serialized scan execution, progress reporting, and cancellation;
- optional compact-block-filter history candidate scans.
- a CAIP-2 `bip122` snapshot implementing the shared
  [`chain-observer`](https://github.com/kotoba-lang/chain-observer) contract.

It also exposes an opt-in embedded host around
[`bitcoin-consensus`](https://github.com/kotoba-lang/bitcoin-consensus).
`bitcoin.node.consensus/open` uses its in-process Script VM, validates raw
blocks before atomically publishing state, and can persist checksummed
chainstate. It supports headers-first indexing and authenticated Bitcoin Core
v2 AssumeUTXO activation while retaining a separate fully validated background
chainstate. A verifier override remains available for differential tests; the
security boundary documented by `bitcoin-consensus` still applies.
The pinned kernel release additionally fails CI on host exceptions, untyped
decoder failures, non-canonical raw round trips, or process timeout under a
replayable transaction/block/legacy-Script/tapscript fuzz corpus.
The node-owned wire boundary applies the same discipline to complete P2P
frames, command bytes, version messages, headers messages, and compact filters.
Its state-machine corpus then mines competing regtest branches into the real
SQLite host, verifies integrity and active ancestry after every transition,
reopens after every block, exercises a longer-chain reorganization, and proves
that a mutated block fails with typed evidence. Every-change and nightly runs
print the seed and exact target count so failures can be replayed locally.
Transaction decoding uses weight-derived input, output, and witness limits,
including unknown witness versions reserved for future soft forks. Transaction
versions retain Core's unsigned 32-bit wire value, so values above
`0x7fffffff` keep CSV and BIP68 enabled instead of being reinterpreted as
negative. Legacy signature hashing removes only opcode-level
`OP_CODESEPARATOR` values with Core's exact parser and serialization behavior;
the pinned kernel CI covers all 500 official legacy sighash outcomes.
Block validation rejects all witness serialization before the network's
SegWit activation height, even when a coinbase commitment is present, and
enforces BIP141 commitments only after activation.
Taproot forward-compatible leaf versions, `OP_SUCCESS`, and unknown tapscript
public-key types retain consensus anyone-can-spend behavior; callers can opt
into Bitcoin Core's corresponding policy-only discouragement flags without
changing block validation.
Prevout Script validation independently follows Core's retroactive
P2SH/WITNESS/TAPROOT flags and exact historical exception composition.
BIP30 collision checks use Core's parent-view scan, pinned BIP34-chain
optimization, and height 1,983,702 recheck boundary. Replacement applies only
to coinbase outputs; non-coinbase outpoint collisions remain forbidden.
BIP9 deployment state uses Core's exact start/timeout and
threshold/timeout transition precedence at period boundaries.
Compact proof-of-work targets use Core's exact `SetCompact` boundaries,
including valid exponent-33/34 encodings whose mantissa still fits 256 bits
and rejection of their adjacent negative or overflow encodings.
The `assumevalid` fast path uses Core's 256-bit
`GetBlockProofEquivalentTime` rounding and keeps Script checks enabled through
the exact strict two-week burial boundary.
The disk UTXO layer matches Core's `IsUnspendable` rule for `OP_RETURN` and
scripts above 10,000 bytes; schema-v7 migration repairs legacy current coins
but requires authenticated reindex when undo proves an impossible spend.
Input values, transaction input totals, and accumulated block fees use Core's
exact `MoneyRange` boundary.

`bitcoin.node.compact-filter` implements BIP158 basic-filter construction,
strict decoding, membership matching, and BIP157 filter-hash/header chaining.
Its output matches all 10 SHA-256-pinned Bitcoin Core v31.1
`blockfilters.json` cases. `bitcoin.node.peer` requests `cfheaders` and
`cfilter` only from peers advertising `NODE_COMPACT_FILTERS`; it correlates
the stop block, requires the exact requested header count, extends an explicit
local anchor, strictly decodes the GCS payload, and authenticates each filter
against its expected header before returning it. Compact filters are
non-consensus hints. `get-basic-filter-headers-from-peers!` therefore requires
2..32 unique peers and returns only after a configurable quorum has supplied a
byte-identical chain for the same retained anchor, exact height range, and stop
block. Successful but conflicting replies never count toward quorum.
`get-basic-filter-from-peers!` then fails over across filter peers while
authenticating the payload into the agreed expected header, so callers can
safely use a negative match without silently trusting one peer.

`bitcoin.node.disk-consensus` is the mainnet-scale embedded host. It validates
headers and blocks, selects the most-work chain, and atomically commits the
resulting UTXO delta, active-chain undo journals, and checksummed fork-choice
metadata to one SQLite database. Header-only progress, side-chain blocks,
multi-block reorganizations, and process restarts retain one consistent
security boundary. Pruned undo, missing local block data, SQLite ancestry or
integrity failures, unavailable verification, and local resource limits are
reported as recovery-required host failures; they never invalidate a candidate
branch or punish its block provider. Both sequential and batch header ingestion enforce buried
BIP34, BIP66, and BIP65 block-version floors plus testnet4's BIP94 600-second
adjustment-boundary timewarp rule. Block bodies never enter the checksummed
tree when their context-free legacy sigop count exceeds Core's 20,000-operation
limit, and raw block bodies never enter the checksummed EDN host metadata.
Validated side-branch bodies are retained as bounded raw SQLite values and
rehydrated only along a candidate activation path. Attached staging rows are
deleted in the same UTXO reorganization transaction; a detached branch must
be fetched again before a later reactivation. Defaults retain at most 288
blocks and 512 MiB, configurable with `:pending-block-limit` and
`:pending-byte-limit`. Active-chain undo is independently retained for at
least 288 blocks by default. The monotonic prune floor does not create Bitcoin
finality: a deeper valid fork produces an explicit authenticated-history
reindex plan. A definitive activation failure persists its minimal invalid
root, rejects descendants through ancestry, returns best-header selection to
the highest-work viable branch, and removes staged invalid bodies in the same
SQLite transaction.
Normalized headers are exposed through an immutable lazy map with a bounded
LRU and write overlay, so normal restart reads only compact host metadata plus
the active and best tips. A bounded block locator is persisted with that
metadata and advanced incrementally instead of walking every ancestor before
each peer request. Databases using normalized host format v1 perform one
transactional full-index migration. Format v2 discovers exact header leaves
once with disk-backed temporary storage; subsequent v3 opens remain bounded.

`bitcoin.node.disk-utxo` remains available as a lower-level linear-chain host.
It parses raw blocks, derives consensus Script flags, atomically commits
touched outpoints plus undo, supports durable tip disconnect and integrity
checks, and streams authenticated AssumeUTXO snapshots without materializing
all coins. Its caller owns header validation and fork selection.

`bitcoin.node.peer` adds a bounded, read-only JVM P2P transport for
mainnet, testnet3, testnet4, signet, and regtest. It performs version/verack,
answers ping, verifies network magic and checksums before decoding bounded
payloads, enforces an overall monotonic deadline even during control traffic
or partial frames, and retrieves headers in protocol-sized batches. The disk
host builds a sparse Bitcoin-style block locator, validates every returned
header, and commits each batch atomically, so synchronization resumes after
restart and can find a common ancestor after a reorganization. A bounded peer
set fails over from the latest durable locator, records typed failure evidence,
and can compare independently reported tips; only local validation and exact
most-work fork choice select state. It deliberately has no transaction relay,
mempool, wallet, signing, or mining commands. Best-chain blocks are scheduled
across up to eight diverse peers, with at most 16 in-flight requests per peer
and 128 raw blocks resident per window. Every response is correlated from its
80-byte header, unfinished work is requeued after a timeout or disconnect, and
downloaded blocks are released in chronological order to the full consensus
validator. Complete parsing, Merkle-result classification, invalid-branch
quarantine, and UTXO validation remain owned by the serial SQLite consensus
boundary. One overall batch deadline actively closes stalled sockets rather
than allowing 16 individual request timeouts to accumulate. SQLite publication
remains one fully validated block at a time, so parallel network completion
cannot expose a child before its parent. A rejected provider body preserves
that committed prefix and immediately recomputes pending work: mutation retries
the same header from another eligible peer, while definitive invalidation moves
to the best viable branch. This retry path is bounded and never attributes
missing local verification state to a peer.

Initial public-network header synchronization now uses a Bitcoin Core-style
two-phase anti-DoS boundary until the network's pinned minimum chainwork is
reached. The first download performs full PoW, difficulty, linkage, MTP, and
future-time validation but does not enter SQLite. It retains salted one-bit
commitments at the Core v31 network-specific periods. A redownload must match
those commitments, and headers remain behind the network-specific lookahead
buffer before durable indexing. The maximum commitment count is derived from
the anchor MTP and the consensus maximum block-production rate, so a peer
cannot grow temporary state with an impossibly long chain. Short low-work
chains, commitment overruns, and equivocation fail over with typed evidence.
`consensus-status` exposes the best-header and minimum chainwork,
`:headers-presync-required?`, `:invalid-blocks`, and up to 16 recent
`:invalid-block-roots` for operator visibility.

```bash
kbb -M:test
kbb -M:lint
kbb -M:coverage
kbb -M:fuzz 21000000 5000
./scripts/core_blockfilter_vectors.sh
```

`bitcoin.node.peer-pool` bootstraps bounded public IPv4 candidates from the
Bitcoin Core DNS seed set, then rotates peers using local success, failure,
latency, exponential-cooldown history, distinct IPv4 /16 network groups, and a
persisted salted rotation counter. DNS is discovery only: every peer must still
complete the network-bound handshake and all downloaded data crosses
the same local consensus boundary. Pool snapshots are bounded, checksummed,
and atomically replaced so health and unpredictable selection history survive
process restarts without becoming consensus input. Only globally routed IPv4
unicast answers are accepted; local, CGNAT, documentation, benchmark,
multicast, and reserved ranges are excluded. Explicit operator anchors can be
prioritized as reconnect candidates and peer service bits can be required, but
neither bypasses local proof-of-work, fork-choice, header, block, or Script
validation.

The adapter is loopback-only by default, prefers Bitcoin Core's short-lived
cookie authentication, rejects URL userinfo/query/fragment components, limits
response size, correlates JSON-RPC IDs, and allows only:

- `getblockchaininfo`
- `getblockhash`
- `getindexinfo`
- `getnetworkinfo`
- `getdescriptorinfo`
- `deriveaddresses`
- `scantxoutset`
- `scanblocks`

Private descriptors and unsolvable or unsupported policies fail closed.
Cloud applications should keep user/organization persistence and Passkey
approval outside this library.

`node/ready?` is intentionally stricter than connectivity: initial block
download must be false, block and header heights must both be non-negative
integers, and the heights must match. Address derivation and scan inputs are
bounded before an RPC call is made.

## Non-goals

This project is not yet a production Bitcoin Core replacement, signer, key
store, wallet database, or broadcast API. Bitcoin Core remains the default
production validating security boundary. Other backends must provide
equivalent validation semantics and contract tests.

## Usage

```clojure
(require '[bitcoin.node.core :as core]
         '[bitcoin.node.protocol :as node]
         '[chain.observer.protocol :as observer])

(def backend
  (core/backend
   {:url "http://127.0.0.1:8332"
    :expected-chain "main"
    :expected-genesis-hash
    "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
    :cookie-file "~/Library/Application Support/Bitcoin/.cookie"}))

(node/node-identity backend)
(node/capabilities backend)
(node/node-status backend)
(node/descriptor-info backend "tr(xpub.../0/*)#checksum")
(node/derive-addresses backend "tr(xpub.../0/*)#checksum" [0 4])
(node/scan-status backend)
(node/abort-scan! backend)
(observer/snapshot backend)
```

Embedded validation:

```clojure
(require '[bitcoin.node.consensus :as consensus])

(def embedded
  (consensus/open
   {:network :mainnet
    :genesis-bytes raw-genesis-block
    :verify-script verify-bitcoin-script
    :snapshot-path "data/mainnet-chainstate.edn"}))

(consensus/accept-block! embedded raw-block unix-time)
(consensus/accept-header! embedded raw-80-byte-header unix-time)
(consensus/load-assumeutxo! embedded core-snapshot-input-stream)
(consensus/accept-background-block! embedded historical-raw-block unix-time)
(consensus/consensus-status embedded)
```

Atomic disk-backed validation:

```clojure
(require '[bitcoin.node.disk-consensus :as disk-consensus])

(def durable
  (disk-consensus/open
   {:network :mainnet
    :genesis-bytes raw-genesis-block
    :path "data/mainnet-consensus.sqlite"
    :pending-block-limit 288
    :pending-byte-limit (* 512 1024 1024)
    :undo-retention-blocks 288}))

(disk-consensus/accept-header! durable raw-80-byte-header unix-time)
(disk-consensus/accept-block! durable raw-block unix-time)
(disk-consensus/consensus-status durable)
(disk-consensus/integrity-check! durable)
(disk-consensus/recovery-plan durable fork-height)
```

When `recovery-plan` reports `:reindex-required`, rebuild beside the live
database and cut over only after verification:

```clojure
(def reindex
  (disk-consensus/begin-reindex!
   durable fork-height
   {:mode :fully-validated-genesis-replay
    :target-options
    {:path "data/mainnet-consensus.reindex.sqlite"
     :network :mainnet
     :genesis-bytes raw-genesis-block}}))

(doseq [raw-block authenticated-competing-history]
  (disk-consensus/accept-reindex-block! reindex raw-block unix-time))

(disk-consensus/verify-reindex! reindex)
(disk-consensus/reindex-handoff reindex)
(disk-consensus/publish-reindex-handoff!
 reindex "data/mainnet-consensus.pointer")
(disk-consensus/load-reindex-pointer
 "data/mainnet-consensus.pointer" :mainnet)
```

The target can be reopened and passed back to `begin-reindex!` after an
interruption. Snapshot mode uses
`:authenticated-assumeutxo-with-background-validation` and advances its
independent history with `accept-reindex-background-block!`. Verification
requires the source tip to remain unchanged, a fully validated target, the
declared common ancestor, strictly greater target chainwork, and a complete
integrity audit. The handoff is a descriptor for an application-owned atomic
storage-pointer switch. `publish-reindex-handoff!` durably and atomically
replaces a checksummed pointer file only after those proofs still match;
filesystems without atomic replacement fail closed. Loading rejects corrupt,
network-mismatched, relative-target, and missing-target pointers. Canonical
paths and filesystem identity prevent the source and target from aliasing.
Publication seals the in-process source, target, and their background
chainstates against further header, block, background, and undo mutations;
cutover or rollback explicitly reopens the selected unchanged database.
Neither function renames, overwrites, or deletes a chainstate database.

Direct header synchronization:

```clojure
(require '[bitcoin.node.peer :as peer])

(with-open [connection
            (peer/connect! {:host "127.0.0.1" :network :mainnet
                            :timeout-ms 30000})]
  (disk-consensus/sync-headers!
    durable connection unix-time {:max-batches 500})
  (disk-consensus/sync-blocks!
   durable connection unix-time {:max-blocks 128}))
```

Managed discovery, failover, and durable peer health:

```clojure
(require '[bitcoin.node.peer :as peer]
         '[bitcoin.node.peer-pool :as peer-pool])

(def peers
  (atom
   (-> (peer-pool/create
        (peer-pool/discover-dns!
         :mainnet {:timeout-ms 5000 :maximum-results 64}))
       (peer-pool/add-peers
        [{:host "operator-node.example"
          :network :mainnet
          :anchor? true
          :source :operator
          :required-services peer/node-network-service}]))))

(disk-consensus/sync-headers-managed!
 durable peers unix-time
 {:maximum-peers 8
  :max-batches 500
  :pool-path "data/mainnet-peers.edn"})

(peer-pool/status @peers (System/currentTimeMillis))
```

Applications should retain explicit operator peers as additional candidates
and periodically rediscover when the eligible pool is depleted. A DNS answer
is never treated as identity, finality, chain state, or a reason to bypass
proof-of-work, difficulty, timestamp, or block validation.

Block synchronization walks only unvalidated members of the most-work header
chain, oldest first. Each block is fully validated and committed separately;
after interruption or restart the next call derives its cursor from durable
consensus state.

After the initial database is seeded, `genesis-bytes` may be omitted on
restart. A populated legacy UTXO database without the matching atomic
chainstate blob is rejected; it is never assigned inferred fork-choice state.

For snapshot-start, pass an authenticated Core v2 snapshot as
`:snapshot-source` and a separately PoW/difficulty-validated, headers-only
chainstate as `:header-state`. The snapshot base must be on its most-work
header chain. When that state came from another normalized disk node, pass its
`:backend` as `:snapshot-header-backend`; ancestry authentication then uses one
bounded SQLite cursor rather than repeatedly opening the database, and header
rows are copied in bounded batches without materializing the complete map.
Because
normalized header state does not retain full blocks, also pass canonical
`:background-genesis-bytes` when genesis cannot be derived from
`:header-state`. UTXOs, `:assumed` trust status, active tip, and headers are
committed together; `ready?` remains false across restart until independent
background validation reproduces the pinned UTXO commitment. The disk host
creates `<path>.background` from genesis and advances it with
`disk-consensus/accept-background-block!`. At the exact snapshot base it checks
SQLite integrity, streams Core HASH_SERIALIZED without loading the UTXO set,
and atomically changes the foreground trust state to `:validated`.

If promotion verification is interrupted after the background block commit,
`disk-consensus/verify-background!` safely retries without advancing either
chain. Status reports `:background-height`, `:background-tip`, and the pinned
snapshot base. A custom foreground DataSource must also provide an independent
`:background-datasource` or `:background-path`.

An AssumeUTXO state reports `:snapshot-status :assumed` until background
validation reaches the exact base and recomputes the pinned UTXO commitment.
The assumed and background chainstates are persisted separately; startup fails
closed if an assumed state has lost its background state.

`core/scan-blocks` requires a discovered, fully synchronized basic block
filter index and otherwise fails with `:bitcoin.node/capability-unavailable`.
It returns candidate block hashes, not transaction history; consumers must
fetch and validate the relevant blocks separately.

## Verify

```bash
kbb -M:test
kbb -M:lint
kbb -M:coverage
```

Snapshot-start historical differential against a synchronized/pruned Core:

```bash
CONSENSUS_CORE_DATADIR=/path/to/bitcoin \
CONSENSUS_SNAPSHOT_PATH=/path/to/utxo.dat \
CONSENSUS_SNAPSHOT_HEIGHT=840000 \
CONSENSUS_HEADER_CHAINSTATE=/path/to/headers.edn \
CONSENSUS_DISK_CHAINSTATE=/path/to/consensus.sqlite \
CONSENSUS_HISTORY_END=850000 \
./scripts/core_snapshot_history_differential.sh
```

For an archival Core, the disk-backed genesis-to-target verifier resumes after
every committed block, rejects a stale/reorganized resume tip, freezes Core's
`hash_serialized_3` before a long run, reopens at bounded intervals, performs a
full SQLite integrity audit, and atomically writes machine-readable evidence:

```bash
CONSENSUS_CORE_DATADIR="/absolute/core" \
CONSENSUS_DISK_CHAINSTATE="/absolute/kernel-mainnet.sqlite" \
CONSENSUS_HISTORY_END=960326 \
CONSENSUS_EVIDENCE_PATH="/absolute/full-history-evidence.json" \
./scripts/core_full_history_differential.sh
```

CI runs the same boundary against checksum-pinned Bitcoin Core v31.1 on a
fresh regtest chain. It validates the first import, a zero-work durable resume,
and rejection of a replaced Core tip without writing false success evidence:

```bash
./scripts/core_full_history_regtest.sh
```

If the target is not Core's current tip, provide its previously captured
`CONSENSUS_EXPECTED_UTXO_HASH`. A pruned Core is accepted only when the durable
kernel resume height is at or above its retained block range.

The harness independently validates every header through the requested end,
authenticates the snapshot against the pinned Core v31.1 AssumeUTXO anchor,
compares each retained raw block's hash/size/weight with Core, applies it to
the disk consensus host, and reopens the database at a configurable interval.
If a pruned node no longer has the requested post-snapshot range it fails
before importing state. `CONSENSUS_GENESIS_HEX` is needed only when Core has
also pruned the genesis block and no header checkpoint exists.

Applications can bind a retained evidence target to the currently served
local chain with `disk-consensus/active-block-hash-at-height`. The lookup is
bounded to one validated height and uses normalized SQLite ancestry; it does
not consult Core, an explorer, or a peer.

On an archival Core, set `CONSENSUS_BACKGROUND_VALIDATE=true` to replay blocks
1 through the snapshot base into the independent disk chainstate, reopen it at
the configured interval, recompute the base commitment, and require the final
foreground state to report `snapshot=validated` and `ready=true`.

For a pruned Core and an existing normalized header database, a bounded
snapshot-to-retained-tip soak avoids creating a million-header EDN file:

```bash
CONSENSUS_CORE_DATADIR=/path/to/bitcoin \
CONSENSUS_NORMALIZED_HEADER_DATABASE=/path/to/headers.sqlite \
CONSENSUS_SNAPSHOT_PATH=/path/to/utxo.dat \
CONSENSUS_SNAPSHOT_HEIGHT=410600 \
CONSENSUS_SNAPSHOT_BASE_HASH=<dumptxoutset.base_hash> \
CONSENSUS_SNAPSHOT_COMMITMENT=<dumptxoutset.txoutset_hash> \
CONSENSUS_SNAPSHOT_CHAIN_TXS=<dumptxoutset.nchaintx> \
CONSENSUS_GENESIS_HEX=<canonical-genesis-block-hex> \
CONSENSUS_DISK_CHAINSTATE=/path/to/soak.sqlite \
CONSENSUS_HISTORY_END=410647 \
./scripts/core_normalized_snapshot_soak.sh
```

The snapshot must come from Core's `dumptxoutset`; the harness authenticates
its base against the already consensus-validated normalized header ancestry,
prefetches the complete retained raw-block range before the long import so
Core cannot prune it mid-run, compares every block's hash/size/weight, reopens
on a bounded interval, and finishes with SQLite, undo-linkage, and full
normalized-header integrity checks. A restart skips only heights whose
active-chain hashes still match the prefetched manifest.

The v0.20 streaming regression run imported the real mainnet height-416179
snapshot (39,062,903 UTXOs) against 960,261 normalized headers, reopened it
with the release code, and completed the full integrity audit in 3,695.16
seconds. Maximum RSS was 2,421,440,512 bytes (about 2.26 GiB), versus roughly
5.3 GiB for the previous million-header materialization path. The resulting
chainstate was 3.3 GiB with a fully checkpointed zero-byte WAL.
