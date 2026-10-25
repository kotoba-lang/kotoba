# Security policy

Do not open public issues containing wallet descriptors, RPC cookies,
credentials, transaction drafts, or incident details.

Report vulnerabilities through GitHub's private vulnerability reporting for
this repository. Include the affected commit, a minimal reproduction, and the
expected security boundary.

This library is watch-only. Applications must never pass private descriptors,
seed phrases, WIF keys, or signing shares to it. Keep Bitcoin Core RPC on
loopback unless a separately authenticated and encrypted transport has been
reviewed. A connected node is not considered ready until initial block download
has finished and validated block height equals header height.

Production configuration should bind both `:expected-chain` and
`:expected-genesis-hash`. POSIX cookie files are rejected when group or other
permissions are present. A UTXO scan result is an observation at its returned
height and best-block hash; use `bitcoin.node.protocol/same-observation?` before
treating a cached result as current after the tip changes.

The disk consensus host always derives header pre-sync anchors from its own
durable state. Until the configured network minimum chainwork is reached,
peer-supplied headers must pass the two-download salted-commitment protocol
before entering SQLite. Direct users of the lower-level `bitcoin.node.peer`
API must supply `:presync` themselves; omitting it is appropriate only when a
separate trusted host already enforces an equivalent anti-DoS boundary.

Managed block synchronization keeps the network pipeline and chainstate
publication as separate boundaries. Up to eight peers may download
concurrently, but each is capped at 16 requests, the resident raw-block window
is capped at 128, and one overall batch deadline actively closes stalled
sockets. Header hashes must match their scheduler assignments; complete body
parsing and chronological validation happen only at the SQLite consensus
boundary. Failed peers cannot
make unfinished assignments disappear: they are requeued and the typed failure
enters the durable cooldown history. Invalid and mutated provider bodies retry
inside the same bounded cycle after preserving its committed prefix; local
verifier, pruned history, missing body, SQLite, and resource-limit failures
stop without peer attribution or branch invalidation. Operators must recover
the local capability or data before resuming synchronization.

All live inbound frame, version, and headers decoding must pass through
`bitcoin.node.wire`. It enforces protocol payload and user-agent bounds,
canonical CompactSize values, printable/NUL-padded command bytes, checksum and
network binding, and exact input consumption. Its public decoder surface must
return only values or typed `bitcoin.node/*` failures for hostile bytes.
Deterministic fuzzing continuously exercises that boundary, compact filters,
and SQLite fork/reopen transitions. Fuzzing is defense in depth; it does not
replace Bitcoin Core differential vectors, independent review, or a complete
genesis-to-tip validation run.
