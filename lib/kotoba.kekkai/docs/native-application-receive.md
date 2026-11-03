# Native managed application reception — JUN-757

`kekkai.application-receive-region` connects the actual managed Noise frame
receiver, existing application/1 chunk codec and full-capacity reassembly
owner. It produces complete JSON bytes and typed protocol data. It does not
execute an application, admit a service/socket, authorize an external
operation, change a route or obtain consent.

This is the existing single-current-session profile: one protected,
API-created session owner262144, one associated IO owner262144 and one
separate8MiB application pool. Serialize their use and preserve the private
IO cookie between calls. Never deserialize a cookie or these owners from
network/application data. A product multi-peer controller remains separate.
The original1MiB/message,2048 parts,128 assemblies and4MiB aggregate bounds
remain those of `application-reassembly-region`; no limit is reduced to fit
the ordinary request arenas. A third ordinary256KiB domain in the diagnostic
is solely an event log, not message storage or a new product grant.

## Association and lifetime

`initialize(pool, pool-bytes, session, session-bytes, io, io-bytes, now)`
requires real disjoint allocations, an admitted positive roster generation
and a pollable managed session. It initializes the pool and fixes that
pool/session pair in the cookie. Explicit initialization is required.

`synchronize` polls the actual session. Generation rollback or a backward
bridge clock refuses. A newer generation advances the pool epoch and erases
old data. Leaving an active channel for pending/stopped/expired state clears
pending and completed data. The established association comes exclusively
from `session-region/copy-application-binding`: actual generation, peer
index, pinned public key and final public Noise transcript. JSON fields
cannot select it. A different transcript clears the old pool even when
peer/key/generation/time and observed phase2 are unchanged. A timestamp is
not channel identity. Product entropy/time/key protection remain required.

`stop` synchronizes, stops the actual session and reinitializes the current
epoch's pool, erasing pending/completed data. Shape/cookie/bridge-clock
preflight refusals preserve all three owners; processed synchronization may
advance the trusted session clock or reap an invalid/expired session.
`synchronize` returns the managed phase0/1/2 or-1; `stop` returns1 or-1.

## Receive and output

`receive` retains the frame IO header: input-used at0, output-capacity at4,
input4096..69633 and output73728..139265. Both counts are at most65538.
Header/input are immutable during the call. It invokes the real frame
receiver itself, and decodes/reassembles only authenticated kind1 bodies.
Callers cannot substitute an alleged authenticated event or plaintext.

| Return | Meaning |
|---|---|
|-2|Completed result busy; no frame authentication or RX counter consumption|
|-1|Preflight/unauthenticated carrier refusal|
|0|Authenticated malformed body or application-part refusal|
|1|Accepted pending application part|
|2|Completed JSON byte string|
|3|Typed ping/pong/CMM/keepalive data, no effect|
|4|Handshake progress/payload|

Synchronization precedes the busy check so revoke/expiry/channel changes
can invalidate a pinned result. A trusted consumer copies the completed
bytes with the existing reassembly `completed-copy` and explicitly releases
them. Backpressure and reliable delivery are still consumer responsibilities.
An authenticated malformed application part consumes the frame's RX counter;
its reassembly refusal preserves the complete pool, including the previous
partial message. Corrected data uses a fresh authenticated frame.

The bridge owns record2048 at225280, association96 at227328, codec8192 at
229376, cookie128 at237568 and scalar result32 at237696. Processed calls
erase225280..237567. Application/refused results erase the complete frame
output; typed control/handshake results retain only their actual body prefix.
The frame layer erases its own65536-byte private workspace. Raw NIC scratch
at221184 and hash scratch at214016 remain outside bridge ownership.

`event-kind`/`event-bytes` expose the last processed raw frame's type/size.
`control-copy(io,length,offset,output,capacity)` copies only typed3/4 result
data, with actual capacity0..65536 and prefix-only commit/tail preservation.
Nonempty output must be disjoint from IO, associated session and pool.
Other results refuse. Copy it before another bridge/frame call or any IO buffer reuse; retained
metadata does not certify a body after external IO writes. A trusted protocol consumer may prepare the corresponding handshake
or pong using the existing frame sender; CMM data does not change a route.

## Qualification scope

The native fixture sends independent public Noise ciphertext through an
isolated RTL8139C+ NIC. This schedule exercises the responder role.
Initiator receive composition remains separate from the earlier standalone
frame/session tests and is not qualified by this receipt. The network test completes one1MiB message;128-assembly/4MiB quotas and
maximum density retain their separate pure-owner qualification.
Its full schedule contains2081 packets, including
2048 reversed parts with550 empty parts yielding exactly1MiB of JSON.
It exercises full completed-byte readback/native copy, reordering,
replacement/duplicates, changed part count, invalid completed JSON and
recovery, whole-pool refusal preservation, busy whole-session/pool
preservation and the identical ciphertext's later acceptance, ignored JSON
peer fields, actual fresh same-epoch handshake, signed-roster revoke/fresh44,
synthetic180s expiry of a pinned completion and final erasure. Only the
deliberately unobserved fresh handshake uses the existing frame API directly;
the subsequent bridge call must detect its changed public transcript.

The fixture also tests38 actual short-view/alias/cookie/clock refusals for
initialize/receive/synchronize/stop, with complete session/IO/log/pool
before/after byte comparisons. It retains41 existing transport/shape guards
(three handshakes) and8 outer-header probes, and directly exercises typed
control-copy, output tails, event queries and actual output-alias refusals.
GDB acknowledges only observation checkpoints in a dedicated test receipt.
It never injects protocol state, an application approval or a consent choice.

Fault controls omit the final transcript comparison, shift the authenticated
codec input, retain private record bytes or consume a busy RX counter. They
must normally complete the same full schedule before detection. Compile
refusals, observer setup failures, traps and timeouts do not count. The
source-bound receipt records the observed results and superseded probes.

This does not qualify live Mac/6600H app installation/connection, complete
request/reply schema or pending service context, directed policy/socket
admission, fresh trusted shared-broker consent, native Mac backend/native
SSH, identities/config/CSPRNG/time/durable floors, multi-peer/rekey/roaming,
actual hostile CPL3 denial, physical performance/operations or OS/L1 release.
The diagnostic packages but never executes its user ELF. Protected-state
assumptions are not a product process-isolation qualification. Physical
HHKB/Trackpad acceptance remains paused and existing management paths remain.

The explicit [main-derived compiler profile](native-receive-compiler-main.md)
qualifies this same responder corpus separately and retains the original
source/artifact/runtime receipts without a silent producer replacement.

The later [both-role receive qualification](native-receive-roles.md) executes
the same native kernel in initiator and responder roles. The earlier receipt
and its bounded scope remain historical evidence; product app/backend,
schema/pending/directed socket policy/fresh consent and OS/L1 gates remain open.
