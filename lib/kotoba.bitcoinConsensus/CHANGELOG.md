# Changelog

## 0.38.0 — 2026-07-31

- Add a deterministic, seed-replayable, structure-biased fuzz harness for
  transaction, block, legacy Script, and tapscript decoding/execution.
- Require canonical raw round trips, namespaced typed failures, bounded input
  and iteration counts, and an outer process timeout so host exceptions and
  hangs fail CI with replay evidence.
- Run 15,000 target cases on every change and four 300,000-case seeds nightly.

## 0.37.0 — 2026-07-31

- Implement Bitcoin Core's policy-only Taproot forward-compatibility flags for
  unknown leaf versions, `OP_SUCCESS`, and upgradable tapscript public-key
  types without changing block-consensus acceptance.
- Pass the complete caller flag set through Taproot script-path execution and
  remove the final explicitly unsupported Core Script-vector flags.

## 0.36.0 — 2026-07-31

- Classify pruned/missing undo, missing staged bodies, SQLite ancestry and
  integrity failures, pending-body limits, closed views, and chainstate
  corruption as local host failures rather than definitive block invalidity.
- Keep local/history/storage failures unannotated by a candidate block hash so
  neither durable branch quarantine nor provider punishment can result.
- Cover a real higher-work reorganization whose active undo was pruned,
  proving the candidate remains viable for authenticated reindex recovery.

## 0.35.1 — 2026-07-31

- Match Core's `BLOCK_MUTATED` result for mismatched and ambiguous transaction
  Merkle trees, allowing another copy of the body without poisoning its header.
- Apply Merkle mutation/root checks before transaction-body consensus checks,
  matching Core's validation-result precedence for malleated block copies.
- Expose one validation-error annotation boundary for hosts that parse block
  bodies before entering the pure chainstate transition.

## 0.35.0 — 2026-07-31

- Match Core's `BLOCK_MUTATED` boundary for witness malleation failures so a
  corrupted or malleated body is retried without permanently poisoning its
  otherwise valid header.
- Separate definitive consensus failures from missing local ancestry,
  verifier capability, and internal block-index state before durable branch
  invalidation.

## 0.34.3 — 2026-07-31

- Add disabled-by-default hard-crash boundaries around compact host metadata
  and pending-block updates, proving invalid-branch cleanup is all-old or
  all-new across process termination.

## 0.34.2 — 2026-07-31

- Keep the normal no-failure header-acceptance path O(1) by avoiding needless
  ancestry traversal when the invalid-root set is empty.

## 0.34.1 — 2026-07-31

- Add constant-JVM-memory normalized header-leaf discovery for one-time compact
  host migration and bounded pending-block hash enumeration for atomic invalid
  branch cleanup.

## 0.34.0 — 2026-07-31

- Persist definitive block-consensus failures as minimal invalid roots and
  reject every known descendant through ancestry without an unbounded marker
  set.
- Recalculate the viable most-work header after activation failure so an
  invalid high-work branch cannot pin block download or fork choice.
- Preserve invalid roots and exact header leaves in chainstate format v3,
  deriving both safely when migrating legacy formats.

## 0.33.0 — 2026-07-31

- Match Core's legacy `SignatureHash` entry contract by removing only parsed
  `OP_CODESEPARATOR` opcodes while retaining identical bytes inside push data
  and preserving its parser-stop plus declared-length behavior for malformed
  trailing pushes.
- Add all 500 Core v31.1 legacy sighash outcomes to the permanent conformance
  harness with zero failures.
- Run SHA-256-pinned Script, transaction, and sighash corpora in CI: 1,936
  upstream outcomes with no skipped vectors.

## 0.32.0 — 2026-07-31

- Decode transaction versions as Bitcoin Core's unsigned 32-bit wire value,
  preserving CSV and BIP68 semantics for versions above `0x7fffffff`.
- Implement `SCRIPT_VERIFY_CONST_SCRIPTCODE` FindAndDelete and legacy
  `OP_CODESEPARATOR` rejection, including separators in unexecuted branches.
- Add a permanent harness for Core v31.1 `tx_valid.json` and `tx_invalid.json`;
  all 214 transaction vectors now pass with no skipped outcomes.

## 0.31.0 — 2026-07-31

- Match Bitcoin Core's 256-bit `GetBlockProofEquivalentTime` rounding at the
  strict two-week `assumevalid` burial boundary.
- Keep Script verification enabled for the narrow work interval that the
  previous `tipWork * 2016` approximation classified as sufficiently buried.

## 0.27.0 — 2026-07-31

- Restrict historical BIP30 overwrite permission to coinbase outputs, matching
  Core's `AddCoins` semantics.
- Continue rejecting every non-coinbase collision with an unspent outpoint,
  including while either fixed BIP30 repeat block is connected.

## 0.26.0 — 2026-07-31

- Match Bitcoin Core's retroactive P2SH, WITNESS, and TAPROOT block Script
  flags across historical validation instead of gating them at activation.
- Apply historical Script flag exceptions before adding active
  DERSIG/CLTV/CSV/NULLDUMMY flags, so the Taproot exception removes Taproot
  alone without disabling unrelated active consensus rules.

## 0.25.0 — 2026-07-31

- Apply Bitcoin Core `CheckBlock`'s context-free legacy sigop bound before a
  block body can enter either the active or side-chain block tree.
- Preserve the exact 20,000-operation boundary while retaining full
  P2SH/witness sigop-cost validation during UTXO connection.

## 0.22.0 — 2026-07-31

- Match Bitcoin Core `CScript::IsUnspendable` by excluding output scripts above
  10,000 bytes from the UTXO set as well as outputs beginning with `OP_RETURN`.
- Keep large output scripts consensus-valid when created while preventing UTXO
  hash divergence, snapshot incompatibility, and false BIP30 overwrite
  rejections.
- Migrate schema-v6 databases transactionally by pruning legacy unspendable
  coins, audit current/undo rows, and require authenticated reindex if undo
  proves an impossible spend was previously accepted.

## 0.21.0 — 2026-07-31

- Replace the round 100,000 witness-item decoder cap with the exact
  block-weight-derived maximum of 3,998,993 empty items.
- Preserve consensus-valid large witness stacks for unknown witness versions,
  retaining future soft-fork compatibility instead of enforcing policy during
  decoding.

## 0.20.0 — 2026-07-31

- Enforce Bitcoin Core's one-million-byte stripped transaction limit directly
  for standalone and block transaction decoding.
- Replace round input/output caps with exact size-derived maxima, admitting
  100,001 through 111,105 minimal outputs that the former cap rejected.
- Decode output scripts above 10,000 bytes when the transaction remains within
  its consensus size bound; Script execution retains its separate limit.

## 0.19.0 — 2026-07-31

- Reject obsolete block-header versions at the exact buried BIP34, BIP66, and
  BIP65 activation heights, matching Bitcoin Core contextual header rules.
- Apply the same fail-closed deployment boundary checks to sequential and
  atomic batch header synchronization.

## 0.18.0 — 2026-07-31

- Let authenticated snapshot hosts retain a lazy normalized node map while
  supplying active-path annotation through a bounded header producer.
- Stream normalized headers between SQLite databases in 500-row batches,
  avoiding a million-node in-memory activation map.

## 0.17.0 — 2026-07-31

- Add a bounded normalized-ancestry window cursor so sequential block
  validation can cache nearby ancestor nodes after one distant traversal.
- Fail closed when a queried normalized parent does not strictly decrease in
  height, preventing corrupt cyclic ancestry from looping indefinitely.

## 0.16.0 — 2026-07-31

- Allow storage-backed block hosts to resolve distant ancestor nodes for
  AssumeValid and BIP68 checks without reopening normalized SQLite storage for
  every intermediate header.

## 0.15.0 — 2026-07-31

- Reuse one prepared upsert statement for the complete authenticated
  AssumeUTXO coin stream instead of preparing SQL once per coin.
- Preserve constant-memory streaming and the single atomic authentication
  transaction while removing tens of millions of redundant SQLite prepares
  on mainnet snapshots.

## 0.14.0 — 2026-07-31

- Add normalized-header ancestry cursors that reuse one SQLite connection and
  prepared statement while retaining raw-hash, parent, height, and cycle
  validation.
- Allow authenticated snapshot activation to receive storage-backed ancestry
  resolvers while preserving best-chain membership and complete active-path
  checks.
- Reduce a real 544,081-header mainnet ancestor lookup from about 23 minutes
  to 51.8 seconds at roughly 293 MiB RSS; a 416,180-hash active path completes
  in 32.9 seconds at roughly 417 MiB RSS.

## 0.13.0 — 2026-07-31

- Add schema-v6 monotonic active-chain undo pruning with a persisted,
  snapshot-aware availability floor and a unique height index.
- Bound immediate reorganization history without treating pruning as Bitcoin
  finality; deeper detach attempts fail with an explicit authenticated-history
  reindex requirement.
- Audit retained undo count, height range, parent linkage, tip binding, and
  UTXO metadata alongside SQLite and normalized-header integrity.
- Allow block and multi-table fork commits to prune inside their existing
  atomic boundary, with additional pre/post-prune hard-crash coverage.

## 0.12.0 — 2026-07-30

- Add disabled-by-default, process-local fault points around linear block and
  multi-table fork-transition commit boundaries.
- Verify 13 pre/post-commit hard-crash locations in separate JVMs with
  `Runtime.halt`, then reopen and audit UTXO, undo, tip, pending block, header,
  and host-state consistency.
- Add a 256-block connect/restart/integrity/disconnect soak proving durable
  undo journals return exactly to the empty genesis state.

## 0.11.0 — 2026-07-30

- Add schema-v5 bounded raw-block staging for validated side branches.
- Atomically store or consume staged blocks with normalized headers,
  checksummed host metadata, and UTXO reorganization commits.
- Enforce per-block consensus serialization size, configurable aggregate
  count/byte limits, foreign-key binding to validated headers, and rollback
  host metadata when any staging bound fails.

## 0.10.1 — 2026-07-30

- Stream full normalized-header cryptographic audits through a temporary
  disk-backed metadata index instead of retaining the complete graph.
- Validate parent linkage, height, and exact cumulative work with one SQL
  self-join and cache header work by compact target, eliminating repeated
  256-bit division across difficulty epochs.

## 0.10.0 — 2026-07-30

- Add bounded normalized-header point lookup and row-count primitives so
  disk-backed hosts can use lazy cached indexes without decoding the complete
  mainnet header graph during every process restart.

## 0.9.0 — 2026-07-30

- Add schema-v4 normalized, fixed-length header-node storage and atomically
  commit changed header rows with compact host metadata, UTXO transitions,
  snapshot activation, and reorganization state.
- Add legacy monolithic-host migration support for node hosts and expose a
  full cryptographic header audit that recomputes raw hashes, parent links,
  heights, and exact cumulative work.
- Accelerate mainnet-scale restart decoding with byte-array loops, direct hash
  conversion, transient map construction, and allocation-free parent lookup.

## 0.8.1 — 2026-07-30

- Cache exact header work by compact target within each validated batch,
  avoiding repeated 256-bit division across long difficulty epochs.
- Upgrade to `org-bitcoin-p2p` v0.5.0 for JDK-accelerated JVM SHA-256d.

## 0.8.0 — 2026-07-30

- Add atomic chronological `accept-headers` batch validation. It evaluates
  contextual PoW, expected difficulty, linkage, median time, and future time
  once over a shared 2,017-header window, then indexes the batch without
  rebuilding that window for every member.
- Reject duplicate or already indexed members before applying a batch.

## 0.7.4 — 2026-07-30

- Consume `org-bitcoin-p2p` v0.4.1 so real peers' full-range uint64 nonces
  decode without JVM overflow and `net_addr` ports use network byte order.

## 0.7.3 — 2026-07-30

- Match Bitcoin Core genesis semantics: validate and index genesis, but never
  insert its coinbase transaction into the UTXO set.
- Make background HASH_SERIALIZED validation compatible with real
  Core-generated snapshots instead of only self-generated fixtures.
- Require the live Core regtest differential to match the independently
  validated full-chain UTXO commitment against Core's dumped snapshot.

## 0.7.2 — 2026-07-30

- Recompute Bitcoin Core HASH_SERIALIZED directly from the ordered SQLite UTXO
  cursor in constant JVM memory.
- Validate AssumeUTXO background evidence from an independently persisted
  height, tip, and UTXO commitment without materializing the coin set.

## 0.7.1 — 2026-07-30

- Persist AssumeUTXO trust/status metadata in checksummed chainstate so a
  restart cannot silently forget pending background validation.
- Commit checksummed host/fork state in the same SQLite transaction as an
  authenticated constant-memory snapshot import.

## 0.7.0 — 2026-07-30

- Add Bitcoin Core v31.1 testnet4 consensus parameters, BIP94 header
  retargeting, genesis validation, and pinned AssumeUTXO/assumevalid anchors.
- Add default signet parameters and full BIP325 block-challenge verification
  through the in-process Script VM, verified against a live Core signet block.
- Upgrade the SQLite schema with atomic checksummed host-state persistence,
  durable undo lookup, schema-v1 migration, and all-or-nothing multi-block
  most-work reorganization commits.
- Allow disk-backed chainstate hosts to resolve pruned in-memory undo from the
  authenticated SQLite journal.

## 0.6.1 — 2026-07-30

- Activate witness and Taproot Script flags only at their buried or
  versionbits-derived deployment state instead of applying post-soft-fork
  semantics to historical blocks.

## 0.6.0 — 2026-07-30

- Match all 1,222 Bitcoin Core v31.1 Script vector outcomes with no skipped
  fixtures, including generated Taproot trees and policy flag behavior.
- Add an ordered, network-bound SQLite UTXO backend with WAL/FULL durability,
  immutable validation overlays, atomic coin + undo commits, durable
  disconnect, stale-tip protection, and integrity verification.
- Build undo from only the outpoints touched by a block instead of scanning the
  complete UTXO set.
- Stream authenticated Core v2 AssumeUTXO snapshots directly into SQLite
  without materializing the coin set, rolling back all rows on commitment
  failure.
- Add a resumable Core historical-range differential harness with pruned-data,
  checkpoint-height, block hash/size/weight, and final-tip guards.

## 0.5.2 — 2026-07-30

- Parameterize the live Core differential for long regtest histories.
- Atomically persist and reload the kernel chainstate at configurable intervals
  during differential validation to prove restart-safe continuation.
- Wait for the temporary Core daemon to exit before cleanup.

## 0.5.1 — 2026-07-30

- Activate an authenticated AssumeUTXO state only when its base is on the
  best-work header chain and strictly exceeds the current active chainwork.
- Preserve the original chainstate boundary for independent background
  validation by keeping activation a pure, explicit transition.

## 0.5.0 — 2026-07-30

- Add headers-first validation without activating headers that lack block data.
- Match Bitcoin Core v31.1 `assumevalid` ancestry, minimum-chainwork, and
  proof-equivalent two-week burial gates while skipping Script checks only.
- Decode and authenticate Core v2 AssumeUTXO snapshots with bounded canonical
  parsing, compressed Coin/script support, exact `hash_serialized_3`, pinned
  checkpoints, and independent background-chainstate promotion.
- Persist `best-header` in chainstate format v2 while migrating v1 snapshots.
- Add a live differential against Core-generated regtest UTXO snapshots.
- Run all 1,033 currently applicable v31.1 `script_tests.json` outcomes in CI
  from a SHA-256-pinned source; explicitly account for 189 unsupported vectors.
- Fix strict signature/public-key encoding failure semantics, historical hybrid
  public keys, CHECKMULTISIG evaluation order, and witness-disabled handling
  found by the upstream vectors.

## 0.4.2 — 2026-07-30

- Validate a real SegWit wallet spend in the 103-block Core differential.
- Decode transaction versions and other unsigned 32-bit wire fields.

## 0.4.1 — 2026-07-30

- Match BIP34 OP_1 through OP_16 coinbase-height encoding on small heights.

## 0.4.0 — 2026-07-30

- Add the in-process legacy, P2SH, SegWit v0, Taproot, BIP341/342, CLTV, CSV,
  CHECKMULTISIG, and sigop-counting consensus Script engine.

## 0.3.0 — 2026-07-30

- Add parsed block serialization for P2P and differential tooling.
- Add deterministic adversarial decoder fuzz cases and exhaustively mutate
  every byte of the mainnet genesis fixture.
- Decode unsigned 64-bit wire integers without JVM `long` overflow and keep
  serialized byte values compatible with the hashing backend.
- Add a live Bitcoin Core v31 regtest differential harness.

## 0.2.0 — 2026-07-30

- Add checksummed, atomic JVM chainstate persistence.
- Reject snapshot corruption, network mismatch, bad parent linkage, inconsistent
  active flags, and UTXO/tip height mismatch during restart.
- Add bounded multi-peer block scheduling with deduplication, response matching,
  timeout/disconnect requeue, and peer misbehavior scoring.

## 0.1.0 — 2026-07-30

- Add bounded raw legacy and SegWit transaction and block parsing.
- Enforce context-free transaction, Merkle, weight, coinbase, witness
  commitment, money-range, and duplicate checks.
- Add contextual PoW, difficulty, BIP34, finality, BIP113, and SegWit
  activation validation for mainnet, testnet3, and regtest.
- Add atomic UTXO transitions and undo-driven most-work chain reorganization.
- Validate mainnet genesis/block 1 and mined competing regtest forks.
