# Native application association — JUN-757

`session-region/copy-application-binding(owner, actual-length, output,
actual-capacity, now)` reads the actual established managed session into a
96-byte data record. It refuses before completion of the Noise handshake or
after stop/revoke/expiry. Actual owner length must be at least262144; actual
output capacity is96..65536, disjoint from the owner. Success returns96 and
preserves the output tail. Refusal returns-1 and preserves output. As with
other session operations, trusted clock polling may advance/reap the session.
Only protected, serialized, API-created state is in scope.

The first64 bytes are the existing application reassembly binding:

| Bytes | Value |
|---|---|
|0..3|`0x3142504b` (KPB1, little endian)|
|4..7|version1|
|8..15|actual current roster generation, u64; positive and <=2^53-1|
|16..19|actual managed-session peer index, u32|
|20..23|zero|
|24..55|the actual pinned peer X25519 public key|
|56..63|zero|
|64..95|the final public Noise handshake hash|

The generation is the roster generation, not the signed netmap version or a
caller-selected message field. The peer index/key come from the protected
session header and are rechecked by the existing active-session policy before
copy. The final hash already exists at datagram+17056 after `from-handshake`;
no second hash store, new grant or changed session layout is introduced. TX/RX
keys and private/static/ephemeral secret bytes are not copied. The handshake,
transport, replay and expiry algorithms remain unchanged.

This public transcript distinguishes two real Noise channels even if they
have the same peer, key, roster generation and creation timestamp. A consumer
must discard pending data when that association changes, or when the session
stops/expires/revokes. It must not use the timestamp as channel identity. This
still requires fresh cryptographic entropy; the getter cannot prove the
product RNG, protection of state, trusted time or durable rollback floors.

The result is an association selector, not app/service/port/socket permission,
external identity enrollment, trusted approval or an authorization token.
Application execution still requires full message schema and pending-request
context, the same directed roster-policy edge, an admitted socket and fresh
trusted shared-broker operation consent. A browser permission or QEMU test
acknowledgement is not that consent.

The existing13-scenario native managed-session gate now compares every result
byte to independent public fixtures for both roles, reconnects, decoded Unicode
tailnets and version boundaries. It retains387 prior return pairs,26 complete
wire hashes,30 existing guards and all lifecycle/erasure tests. Each scenario
adds three full96-byte association checks in actual96/97/65536-byte output
views (39 successful copies), with untouched output tail/owner, and
six refusal calls: pre-handshake, actual short owner, actual short output,
oversized output, owner/output alias and post-stop. The observer verifies all
13 association cases,39 successful copies and78 refusals as well as the original cases.

Fault controls independently corrupt transcript bytes, generation selection,
peer bytes or phase admission. Each must normally complete the same full13
scenarios, all association checks/refusals, prior returns/hashes, canaries and
final erasure before detection. Compilation failure, trap, timeout or a skipped
scenario is not detection. The source-bound receipt keeps normal/fault runs,
independent expected bytes and superseded probes.

The receive/reassembly bridge is a separate integration unit. Its constructor
smoke and old NIC regression alone do not establish reception, completed
messages, correct lifecycle binding, app installation or a live connection.
Those remain open along with service authorization/consent, native Mac backend,
native SSH, physical/security/operations and full OS/L1 production acceptance.

## Later receive-composition unit

The separate [native managed application receiver](native-application-receive.md)
connects actual authenticated NIC ingress to the full-capacity reassembly owner.
Its source-bound evidence is recorded separately; the earlier receipt and its
component scope above remain unchanged. This establishes the responder kernel diagnostic
receive/reassembly path. Product integration, complete
request/reply schema and pending service context, directed socket/policy/fresh
consent, actual Mac/6600H app installation/live peer, native SSH and production
isolation/operations/OS/L1 acceptance remain open.
