# Native local request context — JUN-757

`kekkai.application-pending-region` adds a protected data owner for **256 active
locally originated requests on one actual managed Noise session**. This does
not install a Mac/6600H application or authorize service/socket/HTTP effects.
It composes the full1MiB message decoder with the real session's existing
public binding. The caller cannot supply a network-created binding or schema
record as authority.

## Lifecycle and ID issuance

Initialize the real262144-byte owner before the managed session is established
(phase0/1 only), after its verified roster exists. The owner pins its actual
address and managed-session address. Copying/importing an owner is forbidden.
A live established session refuses initialization, preserving the owner; this
prevents resetting its request sequence on that live channel. To recover a lost
pending owner, the host must establish a fresh session; no silent counter reset.
`stop` wipes this owner only, without stopping unrelated management/services.

`request-id-copy` emits64 lowercase hexadecimal bytes from native BLAKE2s of
`Kekkai pending v1`, the real96-byte binding, the pinned owner's little-endian
u64 namespace and its next little-endian u64 sequence. The binding contains the
actual roster generation, peer index, pinned public key and final public Noise
handshake hash. The owner namespace separates concurrent owners on the same
session. ID preparation is repeatable and does not consume a sequence. `begin`
validates the full request and decoded issued ID, then reserves a slot and
increments the monotonic sequence. **Send only after successful begin.** Retired
or cancelled IDs cannot become the next issued ID. A response must match the
stored ID and complete actual binding before a request is removed.

This is a local originator's ID producer, not a short limit on received service
request IDs. The generic shared schema still accepts arbitrary nonempty IDs
within1MiB, including the separately qualified70,000-byte fixture. No UUID-only
wire requirement is invented: the canonical service echoes a string ID.

IDs are data, not secrets, fresh entropy or capability tokens. Public test keys
and deterministic clocks do not qualify production entropy, custody or time.
A fresh cryptographic channel and protected caller lifecycle remain mandatory;
no uniqueness across broken entropy/reused Noise channels/reboots is claimed.
The last sequence range is refused rather than wrapping. A practical fixture
cannot execute2^53 requests; that exhaustion condition is a source guard, not
an executed2^53-iteration qualification.

## API and actual memory

| Operation | Arguments after owner/length | Result |
| --- | --- | --- |
| initialize | session/sessionBytes, nowMs, timeoutMs | 1 / -1, only pre-established |
| synchronize | session/sessionBytes, nowMs | actual phase0/1/2 / -1 |
| request-id-copy | session/sessionBytes, output/capacity, nowMs | 64 / -1 |
| begin | session/sessionBytes, message/capacity, used, nowMs | positive handle / -1 |
| complete | session/sessionBytes, message/capacity, used, nowMs | matched handle / -1; busy -2 |
| cancel | session/sessionBytes, handle, nowMs | 1 removed,0 absent / -1 |
| result-copy | session/sessionBytes, output/capacity, nowMs | 512 / -1 |
| release-result | no additional arguments | 1 / -1 |
| pending-count | no additional arguments | stored count / -1; snapshot only |
| stop | no additional arguments | 1 / -1; wipes entire262144-byte owner |

Owner and session are real allocations of at least262144 bytes. Message is a
real allocation of at least1MiB with used0..1MiB. All declared allocations are
disjoint and calls serialized. Output capacity is64..65536 for IDs or512..65536
for results. Output must also be disjoint from owner/session. Refused output
and all tails stay unchanged. Shape/header/clock preflight refusal leaves the
owner untouched. A processed call erases its private16384-byte scratch region.
The entire declared owner/session/input/output ranges participate in alias
checks; no fake extent or larger request grant is used.

The caller supplies trusted epoch milliseconds,0..2^53-1; managed-session poll
receives floor(nowMs/1000). Timeout is explicit positive milliseconds (canonical
client default30000). `begin` checks deadline addition before mutation. Sync
may advance trusted clock/reap even when a later schema/ID operation refuses.
At deadline equality it erases pending slots and accepted results. Channel,
peer/key, generation or phase loss erases all old pending and accepted data.
The positive sequence stays monotonic while this owner lives. The single-session
profile does not implement the eventual multi-peer controller.

Header fields are documented in the source. There are256 slots of512 bytes at4096,
not128 slots. Each stores port, handle, creation/deadline, actual96-byte binding,
issued32-byte ID, decoded service/method/path UTF16 lengths and tagged BLAKE2s
hashes of their canonical UTF8 scalars. Strings may be large or escaped without
being copied into short field buffers. The accepted512-byte KPA1 record at135168
copies the corresponding request context and adds response status, used count
and actual immutable input base. All unused/public padding and erased slots
stay zero. Private work/schema/hash/binding scratch is245760..262143.

An accepted result must be released before another completion (-2 busy).
`result-copy` synchronizes the actual session again before exposing data.
At expiry/revoke/reconnection, a previously copied record is merely stale
caller data, never permission. The caller must keep the immutable response
allocation alive until consumed and must not use an arbitrary imported/copied
record as protected state. The subsequent
[`native-application-response.md`](native-application-response.md) controller
binds actual authenticated reassembly input lifetime to this protocol. Generic
pending users must still provide the same exclusive ownership themselves.

## Validation scope

[`evidence/native-application-pending-20261103/receipt.json`](evidence/native-application-pending-20261103/receipt.json)
binds the actual sources, explicit compiler candidate, native helpers and all
original receipts. Amu discovers/checks/compiles/packages the actual ValueRuntime
graph. Kernel/EFI regenerate byte-identically; code cap/stack/grants remain.
Python stages public vectors and compares independently computed complete byte
goldens. GDB acknowledges only fixture checkpoints; no session or consent is
injected.

The fixture verifies signed public roster admission and executes real native
Noise IK before using the API. It fills all256 active slots, refuses257th,
checks native-issued IDs, full service/port/method/path context, accepted
response copy/busy/release, cancellation and delayed/retired/unissued IDs.
It reconnects with the same peer/key/generation/time but a different actual
Noise transcript and observes old pending/accepted erasure. A full1MiB request
exercises decoded1/2/3/4-byte UTF8 fields (`é文書😀`, `/日本語/😀`) and large body.
At29999ms it accepts one response while another request is still pending;
at30000ms both the remaining request and accepted result expire. A signed
revocation reaps state; explicit stop erases the whole owner.

Thirteen refusal pairs independently compare **all262144 bytes each of pending,
managed session and caller IO, plus all1MiB+1 input bytes**. Nine state checkpoints
also compare whole pending/IO/input with public goldens, including the exact
boundary-sized body, normalized field hashes and output tails. Native assertions
remain separate from independent byte comparisons. Five faults must normally
complete the same full corpus before detection: lost channel fencing, capacity
reduced to128, unissued-ID acceptance, wrong deadline equality, missed scratch
wipe. Failed compiles/probes/traps/timeouts are never counted as passes.

The initial fixture repeatedly read a length expression separately for its
subregion and callee. The native region checker correctly refused that unknown
source relationship. A single captured count now supplies both; no compiler,
checker, resource cap or semantic fallback changed. Initial failures and the
standalone/combined diagnostic builds remain preserved separately.

## Remaining product work

The actual managed session supplies identity association. It does not grant a
private-http edge. Host integration must still check the configured service,
exact port, normalized concrete URL/origin/redirect policy and fresh trusted
shared-broker operation consent before sending or executing anything. It must
use the authenticated response controller's exclusive lifetime contract without
releasing or reusing pinned input early. General concurrent outbound allocation
and product wiring remain open. Incoming service
requests and local outgoing requests have different roles; no blanket approval.

Native Mac socket/backend, actual Mac/6600H install/launch/live peer/revoke/
reconnect, multi-peer stress/retry/rekey/roaming/PQ, protected keys/config/CSPRNG/
time/version floors, hostile CPL3 denial, native SSH/security/operations and all
mandatory daily-use/distributed-OS/L1 production acceptance remain open. PXE and
existing management connections remain. Physical input tests are owner-paused;
no physical deployment, service effect, fresh consent or ad spend occurs here.
