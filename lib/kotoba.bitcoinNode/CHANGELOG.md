# Changelog

## 0.49.0 — 2026-07-31

- Add a fail-closed node-owned P2P wire boundary for canonical command bytes,
  exact authenticated frames, bounded version user agents, canonical
  CompactSize values, and exactly consumed headers payloads.
- Route the live peer handshake and header-sync decoder through typed node
  failures instead of allowing dependency assertions or host indexing errors
  to escape.
- Add seed-replayable fuzzing for P2P frames, version and headers payloads,
  compact filters, and an actual SQLite main/side-chain reorganization with an
  integrity check and reopen after every block.
- Run 20,000 wire cases plus the durable fork scenario on every change and
  400,000 wire cases per seed in a four-seed nightly matrix.

## 0.48.0 — 2026-07-31

- Upgrade to `bitcoin-consensus` v0.38.0, whose transaction, block, legacy
  Script, and tapscript boundaries now run replayable bounded fuzzing on every
  change plus a multi-seed nightly corpus.

## 0.47.0 — 2026-07-31

- Expose bounded active-chain hash lookup from the durable SQLite ancestry so
  applications can bind historical differential evidence to the exact local
  chain they currently serve without trusting an external explorer.

## 0.46.0 — 2026-07-31

- Exercise the real Core RPC to raw-block to disk-consensus to
  `hash_serialized_3` full-history boundary in CI with a checksum-pinned
  Bitcoin Core v31.1 binary.
- Prove both zero-work durable resume and fail-closed rejection after Core
  replaces the persisted tip, without emitting false success evidence.

## 0.45.0 — 2026-07-31

- Upgrade to `bitcoin-consensus` v0.37.0 for explicit Bitcoin Core-compatible
  policy rejection of unknown Taproot leaf versions, `OP_SUCCESS`, and
  upgradable tapscript public-key types while preserving consensus acceptance.

## 0.44.0 — 2026-07-31

- Upgrade to `bitcoin-consensus` v0.36.0 and explicitly separate local
  chain-history, storage, verifier, and resource failures from candidate block
  invalidity.
- Stop managed synchronization immediately for pruned undo, missing block
  bodies, SQLite ancestry failures, and pending limits without retrying or
  cooling down the innocent provider.

## 0.43.0 — 2026-07-31

- Retry invalid or mutated provider bodies from another eligible peer inside
  the same managed synchronization cycle instead of waiting for the next
  supervisor interval.
- Preserve already committed chronological prefixes across retries, recompute
  pending work after invalid-branch recovery, and retain bounded validation
  failure evidence in the cycle result.
- Bound validation rejection retries to 1..32 while stopping immediately for
  unattributed local verifier, ancestry, or host failures.

## 0.42.0 — 2026-07-31

- Restrict the parallel P2P stage to bounded raw transport plus requested
  header-hash correlation; the SQLite consensus host now exclusively owns
  complete body parsing and validation-result classification.
- Quarantine indexed headers for definitive context-free body failures before
  a UTXO view opens, while retrying Core-style Merkle mutations from another
  severely cooled-down provider without poisoning the header.
- Persist and expose the same source-peer evidence for early parse failures as
  for contextual activation failures.
- Treat truncated or undecodable 80-byte response headers as severe typed
  response mismatches while retaining their bounded codec failure evidence.

## 0.41.1 — 2026-07-31

- Preserve bounded source-peer and applied-feedback evidence on validation
  errors so supervisors can explain which provider entered severe cooldown.

## 0.41.0 — 2026-07-31

- Retain an exact source peer alongside every chronologically ordered block
  body through parallel download and deterministic failover.
- Feed definitive invalid and retryable mutated-body validation failures back
  into the durable peer pool with maximum cooldown, while leaving local host
  capability and ancestry failures unattributed.
- Upgrade to `bitcoin-consensus` v0.35.0 so witness malleation cannot
  permanently poison an otherwise valid header.

## 0.40.0 — 2026-07-31

- Upgrade to `bitcoin-consensus` v0.34.3 and permanently quarantine definitive
  invalid block roots plus their descendants.
- Recover best-header selection to the highest-work viable branch after a
  staged ancestor fails activation, preventing a high-work invalid branch from
  pinning synchronization.
- Atomically persist invalid roots, the recovered block locator, and deletion
  of every staged invalid descendant; hard-process crash points prove the
  transition is all-old or all-new.
- Migrate normalized host metadata to v3 with one-time constant-JVM-memory leaf
  discovery and expose bounded invalid-root evidence in consensus status.

## 0.39.0 — 2026-07-31

- Connect the existing pure block scheduler to the real P2P, peer-pool, and
  SQLite consensus path instead of downloading every block from one peer.
- Fetch from up to eight diverse peers concurrently with Bitcoin Core's
  16-block per-peer and 128-block resident-window bounds, while committing
  fully validated blocks strictly in chain order.
- Correlate every parsed block with its scheduler request, retain valid
  prefixes, requeue unfinished work after disconnect or timeout, and fail
  closed with typed evidence when all peers are exhausted.
- Enforce one overall deadline per parallel batch and actively close timed-out
  sockets, preventing per-block timeouts from accumulating across 16 requests.
- Persist selection, latency, service-bit, failure, and cooldown evidence for
  block downloads through the same durable peer pool used by header sync.

## 0.38.0 — 2026-07-31

- Add Bitcoin Core-style two-phase header pre-sync below each public network's
  minimum-chainwork threshold, keeping the first download outside durable
  storage.
- Retain salted periodic one-bit commitments and require a protected
  redownload before releasing headers through a network-specific lookahead
  buffer; use Bitcoin Core v31's generated commitment/buffer parameters.
- Fully validate PoW, exact difficulty, linkage, MTP, and future time during
  both phases, and fail closed on low-work short chains, commitment
  equivocation, overruns, or MTP-impossible chain length.
- Recompute the pre-sync anchor after peer failover and expose best-header
  chainwork, required minimum chainwork, and pre-sync state in node status.

## 0.37.0 — 2026-07-31

- Require byte-identical BIP157 filter-header agreement from a bounded set of
  2..32 unique peers sharing the same retained anchor, exact height range, and
  stop block.
- Count only matching responses toward the configurable quorum; preserve
  bounded peer/failure evidence and reject successful but conflicting chains.
- Add authenticated compact-filter fetch failover after quorum, accepting a
  payload only when strict GCS decoding and its expected filter header match.
- Automatically require `NODE_COMPACT_FILTERS` without weakening any
  operator-supplied service-bit requirements.

## 0.36.0 — 2026-07-31

- Implement BIP158 basic compact-filter construction, strict decoding,
  membership matching, filter hashes, and BIP157 header chaining.
- Match all 10 SHA-256-pinned Bitcoin Core v31.1 `blockfilters.json` cases in
  CI, including empty scripts, OP_RETURN exclusion, duplicate elements,
  witness scripts, and malformed output scripts.
- Add bounded `getcfheaders` and `getcfilters` P2P requests gated by
  `NODE_COMPACT_FILTERS`, with exact range correlation, explicit anchor
  extension, strict GCS validation, and authenticated expected headers.
- Keep compact filters outside the consensus boundary and require consumers to
  retain anchors and compare independent peers before trusting negative scans.

## 0.35.0 — 2026-07-31

- Upgrade to `bitcoin-consensus` v0.33.0 for Core-identical legacy
  `SignatureHash` `OP_CODESEPARATOR` serialization.
- Pin all 1,936 Core Script, transaction, and legacy sighash outcomes in the
  upstream kernel CI with no skipped vectors.

## 0.34.0 — 2026-07-31

- Upgrade to `bitcoin-consensus` v0.32.0 so transaction versions retain Core's
  unsigned 32-bit CSV and BIP68 behavior above `0x7fffffff`.
- Adopt `SCRIPT_VERIFY_CONST_SCRIPTCODE` compatibility and the permanent
  214-vector Core transaction conformance harness.

## 0.33.0 — 2026-07-31

- Upgrade to `bitcoin-consensus` v0.31.0 so `assumevalid` Script skipping uses
  Core's exact 256-bit proof-equivalent-time rounding.
- Keep Script verification fail-closed throughout the former two-week
  approximation gap.

## 0.32.0 — 2026-07-31

- Upgrade to `bitcoin-consensus` v0.30.0 for Bitcoin Core-identical compact
  target decoding at the exponent-33/34 and 256-bit overflow boundaries.
- Preserve fail-closed initial-context header validation for negative, zero,
  and overflowing compact targets.

## 0.29.0 — 2026-07-31

- Upgrade to `bitcoin-consensus` v0.27.0 so historical BIP30 replacement is
  restricted to coinbase outputs.
- Keep non-coinbase unspent-outpoint collisions fail-closed in embedded and
  disk-backed block connection.

## 0.28.0 — 2026-07-31

- Upgrade to `bitcoin-consensus` v0.26.0 for Core-identical retroactive
  P2SH/WITNESS/TAPROOT validation across historical block replay.
- Preserve active DERSIG/CLTV/CSV/NULLDUMMY checks at the historical Taproot
  exception block while disabling Taproot alone.

## 0.27.0 — 2026-07-31

- Upgrade to `bitcoin-consensus` v0.25.0 so excessive legacy sigops are
  rejected before active or side-chain block bodies enter node storage.
- Preserve full prevout-aware P2SH and witness sigop validation during atomic
  UTXO connection.

## 0.24.0 — 2026-07-31

- Upgrade to `bitcoin-consensus` v0.22.0 so output scripts above Core's
  10,000-byte execution limit are valid when created but never enter the UTXO
  set.
- Adopt transactional schema-v7 repair for legacy unspendable coins and
  fail-closed authenticated reindex evidence for impossible historical spends.

## 0.23.0 — 2026-07-31

- Upgrade to `bitcoin-consensus` v0.21.0 so unknown witness versions retain
  consensus-valid, block-weight-bounded witness stacks above 100,000 items.
- Preserve future soft-fork compatibility by keeping policy limits out of
  transaction decoding.

## 0.22.0 — 2026-07-31

- Upgrade to `bitcoin-consensus` v0.20.0 for Core-aligned stripped transaction,
  item-count, and large output-script decoding boundaries.
- Add a disk-backed, resumable genesis-to-target Bitcoin Core differential
  verifier with canonical resume-tip checks and pruned-range preflight.
- Freeze and compare Core/kernel `hash_serialized_3`, run full SQLite integrity,
  detect target reorganization, and atomically publish JSON evidence.

## 0.21.0 — 2026-07-31

- Upgrade to `bitcoin-consensus` v0.19.0 so sequential and atomic batch header
  synchronization reject obsolete block versions at the exact buried BIP34,
  BIP66, and BIP65 activation heights.

## 0.20.0 — 2026-07-31

- Activate AssumeUTXO over a source-backed lazy header map, capture only its
  authenticated active-path set, and stream normalized rows into the target in
  bounded batches.
- Rebind the returned chainstate to the target database after the atomic
  commit, eliminating the million-node activation map and its multi-gigabyte
  transient heap.
- Validate a real height-416179 mainnet snapshot containing 39,062,903 UTXOs
  against 960,261 normalized headers in 3,695.16 seconds with full integrity
  success and 2,421,440,512-byte maximum RSS, down from the pre-streaming
  activation's approximately 5.3 GiB.
- Add a resumable, source-non-destructive reindex session for genesis replay
  or authenticated snapshots, with explicit block/background ingestion.
- Require an unchanged source tip, fully validated target, declared common
  ancestor with different immediate children, strictly better chainwork, and
  full integrity before issuing a storage-pointer handoff; neither database is
  renamed or deleted.
- Atomically publish and checksum a path-backed reindex pointer for
  process-supervised cutover while retaining the source as rollback state;
  reject canonical path aliases, missing targets, network mismatches, corrupt
  pointers, and filesystems without atomic replacement.
- Seal the live source, target, and their background chainstates against every
  mutation at pointer publication, while leaving both databases untouched and
  explicitly reopenable for cutover or rollback.

## 0.19.0 — 2026-07-31

- Retain a configurable active-chain undo window with a Bitcoin Core-sized
  minimum/default of 288 blocks and prune it inside the atomic fork commit.
- Expose retained journals, persisted prune floor, and immediate reorg depth
  in node status; distinguish in-place forks from authenticated-history
  reindex recovery.
- Upgrade to `bitcoin-consensus` v0.17.0 for schema-v6 undo linkage audits,
  snapshot-aware monotonic pruning, single-connection ancestry proofs, and a
  single prepared upsert across the complete authenticated snapshot stream.
- Route normal AssumeValid and BIP68 block checks through the normalized
  storage ancestry cursor instead of opening SQLite once per intermediate
  header.
- Retain a bounded 288-height ancestry window for each recent proof tip, so
  sequential historical blocks pay for one distant traversal rather than one
  traversal per block.
- Add a resumable Core differential soak that reuses the bounded normalized
  mainnet header database instead of materializing a million-header EDN state.
- Validate a real height-416179 mainnet snapshot through ten independently
  fetched retained blocks, restart at height 416189, and audit 960,261 headers,
  39,059,286 UTXOs, and 79,591 undo rows with no integrity error.

## 0.18.0 — 2026-07-30

- Upgrade to `bitcoin-consensus` v0.12.0, whose SQLite transition boundary is
  verified across 13 hard-process crash points and a 256-block reversible
  restart soak.

## 0.17.0 — 2026-07-30

- Select eligible peers across distinct public IPv4 /16 groups before reusing
  a group, and expose eligible group and operator-anchor counts.
- Replace predictable host ordering with a cryptographically salted,
  counter-rotated rank that survives checksummed atomic pool snapshots.
- Migrate v1 peer pools to the v2 selection format without trusting persisted
  reputation as consensus input.
- Support explicit operator anchors while retaining cooldown and local
  validation, and require configured P2P service bits after version handshake.
- Persist observed peer service masks and quarantine peers that fail required
  service negotiation.

## 0.16.0 — 2026-07-30

- Move validated side-branch block bodies out of checksummed EDN host metadata
  into schema-v5 bounded raw SQLite staging.
- Rehydrate only the candidate ancestry needed for activation after restart,
  then consume attached staged blocks in the same atomic UTXO reorganization.
- Expose pending block count/bytes and configured limits in consensus status.
- Enforce configurable count and byte ceilings; a limit failure rolls back
  the candidate header, staged body, and host metadata together.
- Upgrade to `bitcoin-consensus` v0.11.0 for foreign-key-bound pending storage.

## 0.15.0 — 2026-07-30

- Replace eager normalized-header materialization with a map-compatible lazy
  SQLite index, immutable write overlay, and shared bounded LRU cache.
- Persist a bounded restart-ready block locator and incrementally age its
  ancestry, eliminating full-chain walks from normal peer synchronization.
- Preserve hot ancestor context across atomic batch commits and reduce
  transition-path derivation from full-chain traversal to reorganization
  depth.
- Upgrade normalized v1 host metadata transactionally on first open; all
  subsequent v2 restarts use bounded point lookups.
- Upgrade to `bitcoin-consensus` v0.10.1 for normalized-header point lookup,
  row counts, and bounded temporary-index full-graph audits.

## 0.14.0 — 2026-07-30

- Add bounded concurrent discovery from the Bitcoin Core DNS seed set while
  rejecting private, loopback, link-local, multicast, and non-IPv4 answers.
- Add health-aware peer rotation with latency history, typed failure evidence,
  exponential cooldown, and extended quarantine for protocol violations.
- Persist bounded peer health in checksummed, atomically replaced snapshots,
  including selection history when synchronization exits unexpectedly.
- Integrate managed failover with the durable disk consensus host without
  making discovery or peer reputation part of consensus.

## 0.13.0 — 2026-07-30

- Replace the growing monolithic header-state blob with compact checksummed
  host metadata plus fixed-length normalized header nodes, including atomic
  legacy migration and durable restart from every accepted batch.
- Add bounded multi-peer header failover, retry evidence, optional independent
  tip comparison, and local most-work resolution of competing valid branches.
- Enforce monotonic overall handshake/header/block deadlines, including while
  a peer sends control traffic or trickles a partial frame.
- Extend disk integrity checks through every raw header hash, parent link,
  height, and exact cumulative-work value.

## 0.12.0 — 2026-07-30

- Add bounded best-chain block synchronization from P2P retrieval through
  full transaction, Script, UTXO, and fork-choice validation.
- Derive the next download set from durable `block-valid?` state so each
  atomic commit is restart-safe without a separate cursor.

## 0.11.0 — 2026-07-30

- Add bounded witness-capable P2P full-block retrieval with exact requested
  hash verification, explicit `notfound`, malformed-block, and timeout errors.
- Validate the implementation against a live mainnet peer and a retained Core
  block at height 385,310: 627,730 serialized bytes and 489 transactions
  matched Core exactly.

## 0.10.0 — 2026-07-30

- Add a bounded JVM Bitcoin P2P client for all supported networks with
  version/verack, ping/pong, checksum and magic validation, payload limits,
  minimum-version enforcement, and batched `getheaders`.
- Feed P2P header batches through full header consensus and persist each batch
  atomically in the disk host.
- Generate sparse Core-style block locators from durable best-header ancestry
  for restart and deep-reorganization recovery.
- Cover real TCP framing, full-range peer nonces, obsolete versions, wrong
  network magic, corrupt checksums, oversized payloads, and atomic batches.
- Upgrade to `bitcoin-consensus` v0.8.1 for shared-window atomic batch
  validation and its corrected P2P wire dependency.

## 0.9.0 — 2026-07-30

- Maintain a separate genesis-started SQLite consensus database for every
  assumed snapshot.
- Resume full background block validation across process restarts and expose
  its durable height/tip.
- At the exact snapshot base, stream the background UTXO commitment in constant
  memory, require matching height/tip/commitment, and atomically promote the
  foreground snapshot to `:validated`.
- Retain fail-closed behavior when background storage is absent or mismatched.
- Match Core genesis semantics in both integrated and lower-level disk hosts:
  genesis is validated/indexed but its coinbase never enters the UTXO set.

## 0.8.2 — 2026-07-30

- Add a resumable Core-backed snapshot historical harness covering full header
  validation, retained post-snapshot blocks, and interval process restarts.

## 0.8.1 — 2026-07-30

- Add atomic AssumeUTXO initialization to the disk consensus host using an
  independently validated headers-only state.
- Keep snapshot-start nodes explicitly unready while background validation is
  pending, including after validating later blocks and across process restart.
- Upgrade to `bitcoin-consensus` v0.7.1 so snapshot UTXO, trust status, and
  fork-choice metadata share one SQLite transaction.

## 0.8.0 — 2026-07-30

- Upgrade to `bitcoin-consensus` v0.7.0 for testnet4, default signet,
  BIP94/BIP325 validation, and atomic host-state persistence.
- Add `bitcoin.node.disk-consensus`, integrating validated headers,
  cumulative-work fork choice, disk UTXO transitions, durable undo, and
  checksummed restart state in one SQLite commit boundary.
- Support header-only persistence and atomic multi-block reorganization.
- Prune active block bodies and undo values from the metadata blob while
  retaining side-chain block data until activation.
- Fail closed when a populated lower-level UTXO database lacks its matching
  consensus host state.

## 0.7.0 — 2026-07-30

- Upgrade to `bitcoin-consensus` v0.6.1 with complete Core Script-vector
  parity and historical soft-fork flag selection.
- Add a node-facing SQLite UTXO host for raw block parsing, network deployment
  flags, atomic connect/undo, durable disconnect, integrity checks, and
  constant-memory authenticated AssumeUTXO import.
- Require independently validated MTP context before connecting CSV-active
  history and reject blocks that do not extend the durable tip.

## 0.6.0 — 2026-07-30

- Upgrade the embedded kernel to `bitcoin-consensus` v0.5.1.
- Expose atomic headers-first indexing without premature block activation.
- Authenticate and activate Core v2 AssumeUTXO snapshots while retaining a
  separate background chainstate.
- Promote snapshots only after full historical validation reproduces the
  pinned base commitment; fail closed when background state is unavailable.
- Report best-header, snapshot, and background-validation progress explicitly.

## 0.5.2 — 2026-07-30

- Upgrade the embedded consensus kernel to v0.4.2.

## 0.5.1 — 2026-07-30

- Upgrade the embedded consensus kernel to v0.4.1.

## 0.5.0 — 2026-07-30

- Use the built-in consensus Script verifier by default.

## 0.4.1 — 2026-07-30

- Upgrade the embedded kernel to `bitcoin-consensus` v0.3.0 for overflow-safe
  unsigned wire decoding, block serialization, adversarial fuzz coverage, and
  Bitcoin Core v31 differential verification.

## 0.4.0 — 2026-07-30

- Integrate the separately versioned `bitcoin-consensus` v0.2.0 kernel.
- Add a thread-safe embedded consensus host that validates raw blocks before
  compare-and-set publication.
- Require a Script verifier and optionally persist atomic checksummed
  chainstate after every accepted block.
- Report embedded validation height, best block, chainwork, UTXO count, and
  persistence readiness without weakening the Bitcoin Core backend.

## 0.3.0 — 2026-07-30

- Implement the shared read-only `chain-observer` snapshot contract.
- Identify Bitcoin networks with the CAIP-2 `bip122` genesis-hash prefix.
- Preserve Bitcoin's probabilistic best-chain semantics instead of claiming a
  deterministic finalized head.
- Report local Bitcoin Core validation, sync, peers, warnings, and discovered
  history capability through one validated observation.

## 0.2.0 — 2026-07-30

- Bind a backend to an expected chain and genesis block.
- Discover Bitcoin Core version, network state, peers, warnings, and block
  filter index capability at runtime.
- Add best-block and chainwork evidence to sync status.
- Serialize local UTXO scans and expose progress and cancellation.
- Add fail-closed compact-block-filter history candidate scans.
- Reject POSIX RPC cookies readable or writable by group/other users.
- Validate response content type and normalize transport failures without
  credential-bearing error data.
- Add form/line coverage reporting with a 70% CI floor.

This release remains watch-only. It neither signs nor broadcasts transactions.
Compact-filter scans return candidate blocks, not verified transaction history.
