# Managed native Kekkai frames — JUN-757

`kekkai.frame-region` connects the roster-bound native session to the existing
Kekkai v1 carrier. It emits or consumes `6b 01 type || Noise` with handshake
init48/response49/transport50, and authenticated inner data1/ping2/pong3/
call-me-maybe4/keepalive5. It is a pure protocol adapter. It neither opens a
socket nor authorizes an app operation, service, port, endpoint or route.
The legacy `wire-region` framing and payload limits are retained.

The protected262144-byte state owner belongs to `session-region`. A separate
caller-owned262144-byte IO allocation has u32 input-used/output-capacity at0/4,
input4096..69633 (65538B), output73728..139265 (65538B), and private temporary
plaintext147456..212991 (65536B). Actual owners must be disjoint, serialized
and protected; input and the two header words stay immutable during a call.
Unused IO space is not part of the production API. In the NIC diagnostic it
holds a separate Ethernet receive copy and public result trace.

`receive(owner,actual-bytes,io,actual-io-bytes,now)` returns-1 for unauthenticated,
shape or phase refusal,0 for authenticated invalid inner plaintext, or
`kind*65536+body-bytes`. Kinds48/49 report successful handshake progress and
its plaintext;1..5 report authenticated inner types. The configured session
role must match the outer handshake kind. Invalid inner types, an empty inner
or nonempty keepalive consume the authenticated replay counter and preserve
output. Pong and call-me-maybe are typed data, never route changes. The caller
must implement their actual semantics before giving them any effect.

`send-handshake(owner,actual-bytes,io,actual-io-bytes,now)` chooses the protected
session's actual role and returns the framed wire length or-1. `send` adds an
inner-kind sixth argument and encrypts the input body, returning framed bytes
or-1; only kinds1..5 are admitted, with an empty keepalive body. All output
capacity preflights precede cipher progress. The three-byte header is written
only after successful encryption, using `wire-region/outer-header`. That new
codec entry point writes exactly3 bytes for a valid type and actual capacity
3..131072, preserving every output byte on refusal.

A full frame remains65538 bytes: handshake payload65439 initiator/65487
responder, or transport body65510 after one inner byte and24 crypto bytes.
The raw handshake API's maximum output capacity is65536; the frame adapter
bounds its plaintext output view accordingly. The maximum test exposed and
fixed passing the larger carrier capacity directly into that raw API. Logical
frame size does not establish IP segmentation or a larger physical MTU.

Shape refusals preserve state, output and temporary plaintext. Processed calls
clear all65536 IO temporary bytes, including refusal paths. The underlying
session's private transaction preserves cipher state/output on bad tags,
replay, wrong static/prologue/turn or short output. A trusted clock may still
advance or reap a session on a well-shaped refusal. The caller supplies trusted
clock/config/keys and erases its own copies; this adapter supplies no entropy,
protected storage, concurrency or power-fail atomicity guarantee.

The isolated `frame-link-gate` runs the real native adapter over RTL8139C+
MMIO/DMA and strict IPv4/UDP parsing. A fixed public peer, synthetic seconds,
signed42→revoked43→authorized44 maps and fresh public ephemeral inputs drive
45 Ethernet receive frames and14 complete byte-matching replies. Native code
reposts every descriptor, compares64-bit typed event returns, checks actual
session/IO allocation separation, and asserts final session/transient erasure
and DMA/request canaries. Independent observation compares every response byte,
all1472 output bytes, full65536 state snapshots on eligible refusals, and the
entire196608 owner transient plus65536 IO temporary region after each packet.
No-response results are acknowledged by descriptor completion, not absence
of traffic alone. Both peer sockets are restricted to127.0.0.1.

Coverage includes wrong magic/version/type/role, truncation, wrong static and
bound version, tampered authenticated packets, counter changes, wrong direction
key, replay and counter reordering, typed pong/CMM without handlers, invalid
inner/keepalive, data bodies0/1/31/64/257/1024/1444, ping/pong, wrong endpoint,
recovery after refusal, rejected signed candidates and exact policy retry,
live-key revocation, refusal while revoked, new-version fresh-key reconnect,
and rejection of old ciphertext before valid new counter0. There are34 native
shape/alias/phase/short-output/type guards (including usable-header alias
probes) and8 direct outer-header boundary probes per NIC boot.

Policy transitions are read from the immutable diagnostic schedule, never
from received packets. Diagnostic data echo is deliberately a raw carrier
probe, not a service request, native SSH command or app acceptance. The higher
application protocol carries JSON chunk/service/port/request/reply context;
a raw inner data body cannot legitimately be assigned an invented SSH port or
reverse application permission. The full product must bind that real context
to the directed roster capability/port predicate, admitted socket and shared
fresh-consent broker before effects. This unit does not implement that layer.

Four additional native boots cover both roles' maximum handshake and transport
frames, checking whole raw ciphertext BLAKE2s hashes, all plaintext bytes, exact prefix/tail
canaries, six transactional/refusal cases per boot and final erasure. The
maximum-size font fixtures retain existing public RFC/Noise known answers.
Five targeted faults alter nonempty-keepalive rejection, body offset, outgoing
handshake type, IO temporary erasure or actual owner/IO alias rejection. Each
runs15 selected real NIC packets plus all34 guards/eight header probes through
revocation/reconnect and final erasure. These are five targeted runs, not five
full45-packet runs; compile failure, timeout or a halted guest is not detection.

The diagnostic reuses the real prepared/token/full IK known answer through a
new test-only `session-region-gate/canonical-ik` export. It does not stub/delete
legacy math, exports or ValueRuntime. Native compilation/discovery/packaging
uses pinned Amu with no hosted language in PATH. Python stages/signs public
fixtures, computes independent expected cryptographic bytes and observes the
native VM; it does not interpret EDN, compile Kotoba or provide a runtime.
The two existing256KiB request allocations, owned DMA grant, actual11 runtime
sources, two PT_LOAD segments, stack and2MiB compiler code cap are retained.
User ELF/slot are packaged unchanged and not executed by this diagnostic.

See `evidence/native-os-managed-frames-20261103/receipt.json` for source graphs,
exact native artifacts, all failed prototypes, final controls and regressions.
The earlier wire/roster/session receipts describe their respective prior units;
they are not silently relabeled as product qualification by this extension.

Still open: full app/desktop import closure, actual Mac native backend and
Mac/6600H app install/connection/revoke/reconnect, per-operation app/socket and
fresh-consent binding, native SSH, protected approved config/keys/CSPRNG/clock,
durable floors/recovery, multi-peer scheduling/retries/rekey/roaming, larger
logical-frame delivery, PQ, constant-time/independent security qualification,
and the remaining distributed OS/L1 production/operations/economics gates.
PXE/SSH/console and the owner's physical-input pause remain unchanged. No
physical deployment, trusted-user consent, performance or production claim,
and no Reddit campaign/spend are established by these public diagnostic keys.
