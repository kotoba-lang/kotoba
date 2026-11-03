# Native authenticated response lifetime — JUN-757

`kekkai.application-response-region` connects an authenticated, completed
reassembly message to the protected local request owner. This is a native data
path on one actual managed Noise session. It does not grant a service edge,
socket, URL, application operation or consent, and does not install either app.

## Association and ownership

The managed receive bridge pins the actual session's **96-byte** public binding
after successful authenticated reassembly. The binding contains roster
generation, peer, public key and final Noise handshake hash. Optional metadata
uses reserved reassembly header bytes1152..1247; the existing 64-byte accept API,
message layout and quotas remain compatible. Pinning the same channel is
idempotent. Replacing an existing pin with a different channel refuses. Release,
reset and applicable revoke/expiry paths erase the pin with the completion.

Owner locators return bounded relative offsets: completed message6950912 and
channel1152. The controller constructs actual1MiB and96-byte `kernel-subregion`
views. It never fabricates a region from a stored address or treats an imported
record as authority. An unpinned legacy completion has a discard-only storage
locator; it cannot enter bound completion.

One exclusive host critical section owns the actual8MiB pool,262144-byte pending
owner,262144-byte managed session, receiver IO and all response consumers.
Serialize their calls. Do not mix generic reassembly release/reset or reuse the
backing allocation while an accepted response is being consumed. These are
trusted host ownership requirements, not isolation from a privileged host that
violates its own contract. Recheck current session/result after any UI or consent
yield before an application effect. A previously copied KPA1 record is data only.

## Controller API

All three exports take `pool/poolBytes`, `pending/pendingBytes`,
`session/sessionBytes`, and trusted epoch milliseconds. Declared allocations
must be disjoint; capacities must cover8MiB/262144/262144. Negative, over-range
clocks and invalid shapes refuse before mutation. The existing owner/session
checks and actual managed-session synchronization still apply after preflight.

| Operation | Result and lifetime |
| --- | --- |
| `complete` | Positive request handle for a schema-valid response matching the issued ID and actual96-byte channel; -1 refused, -2 accepted-result busy. The completed pool input stays pinned. |
| `release` | 1 only after releasing the accepted record for this exact input and current actual channel, then releasing the canonical completion; otherwise -1. |
| `discard` | Synchronizes the pending owner, then releases an unaccepted completion. An accepted record holding that exact input returns -2 and preserves it; invalid state returns -1. |

Pending exports `complete-bound` and `release-bound` accept the actual exact1MiB
input and96-byte binding views. They synchronize the actual session and compare
all96 bytes before using the existing schema/pending logic. `holds-input` is a
data snapshot for the serialized controller, not an authority or synchronization
operation. Namespace exports are not additional kernel ABI roots.

The successful release clears the matching pending result before canonical pool
release. Under the exclusive ownership contract the earlier checked canonical
completion cannot change between those steps. Expiry/revocation/reconnection may
invalidate a result; synchronize and use discard after the hold is gone rather
than treating an old result as permission.

## Initial outbound request in the integration fixture

`application-receive-region/detach-empty` relinquishes an empty pool without
stopping its transport. It requires no active assembly, buffered payload or
completed input. The host must also have no accepted input in that allocation.
Receiver association/private state is detached, the whole backing allocation
can transfer to a local request builder, and the bridge must be initialized
again before receiving. An active assembly or unused tail is never borrowed.

The native fixture uses this explicit empty-pool handoff once: discard an invalid
small completion, prepare a native issued ID, build and admit a local request,
encode/encrypt/transmit it through the actual NIC, then reinitialize reception.
The observer independently decrypts that outbound frame and learns the ID from
the wire before generating its response. There is no QMP-written ID or session.
General concurrent outbound1MiB buffer ownership/backpressure is still product
work; this initial handoff is not that implementation.

## Executed qualification

[`evidence/native-application-response-20261103/receipt.json`](evidence/native-application-response-20261103/receipt.json)
binds original native receipts, sources, source locks, compiler, helpers,
QEMU/firmware and reopened memory snapshots. Both actual Noise roles execute
the full receive corpus:2081 protocol packets, with three extra scheduled
send-first triggers for the initiator. They preserve full1MiB messages,
2048 reverse-order parts,128 assemblies and4MiB buffered-payload limits.

The native local request's ID is independently checked against its actual
binding, owner namespace and sequence. Its full1MiB encrypted response matches
the request. The observer compares the complete512-byte accepted context,
96-byte completion pin, full message bytes and accepted-input hold. A busy
completion/discard preserves input; matching release clears it. Existing
protocol/control/replay/channel/roster/expiry cases and signed revocation stay
in the corpus. Stop synchronizes and wipes the pending owner.

Fifty-three refusal pairs per run compare every byte of all five allocations:
session, IO, log,8MiB pool and pending owner. Fifteen pairs exercise each
controller operation with short pool/pending/session views, negative clock and
pool/pending alias. Legacy reassembly and pending regressions separately retain
the full old capacity and independent byte goldens.

Five faults in both roles must normally complete the full corpus before
detection: truncated channel pin, completion retag, ignored handshake-h binding,
discard of held input, and omitted canonical release. Failed compilation,
timeouts and traps are not detection passes. The first retag mutation removed
the only typed callers of private channel helpers and was refused E7106. The
corrected mutation keeps those calls and adds the always-true completed-header
alternative; no compiler/checker/cap or production source changed. Both exact
observer versions and failed receipts are retained in the evidence bundle.

The actual45-module ValueRuntime graph remains enabled. Kernel and EFI rebuild
byte-identically; RX1931136 bytes stays below the existing cap, RW2359296 bytes,
two PT_LOAD segments, stack and grants remain. This diagnostic uses public test
keys and synthetic trusted time, not production key custody or entropy.

## Remaining product acceptance

Configured directed private-http service, exact port, normalized endpoint,
redirect/socket policy and fresh trusted shared-broker consent still need to
gate send/execution. The canonical browser broker is
`kotoba-lang/kotoba/lib/kotoba.wasmWebcomponent/src/kotoba-client-runtime.js`;
this native data controller does not replace its consent contract.

Native Mac backend, concurrent outbound allocation, actual Mac/6600H app
install/launch/live peer/revoke/reconnect, native SSH, multi-peer/rekey/stress,
protected keys/config/entropy/time/floors, hostile-user isolation and operations
remain open. Mandatory daily-use, distributed OS and L1 production acceptance
remain separate. PXE/services/WIP and the owner pause on physical input testing
are preserved. No physical deployment, app effect, consent or ad spend occurs.
