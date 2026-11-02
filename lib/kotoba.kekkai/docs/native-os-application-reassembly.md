# Native application/1 reassembly — JUN-757

`kekkai.application-reassembly-region` adds the existing application message
reassembly limits to the native chunk codec: 1,048,576 bytes per message,
2,048 parts, 128 pending assemblies and 4,194,304 pending payload bytes.
It accepts out-of-order chunks and replaces duplicate parts, including
zero-length parts. It validates a complete JSON document before committing
completion. It returns pinned JSON bytes, not a hosted object or an executed
application request. The existing codec and its encrypted NIC proof remain
separate; this unit does not yet join reassembly to the live network/service.

The owner is an actual, exclusively held 8MiB allocation. The explicit
Amu `x86_64-aiueos-kernel-v4` / EFI boot-v7 application pool supplies it;
old kernel targets, four 256KiB domain arenas, runtime/stacks and PCI grants
are not enlarged or borrowed. This is one kernel-host owner for bounded
multiplexing, not a per-app isolation or consent mechanism. Callers serialize
all access, initialize it, protect its state, and never import an untrusted
serialized owner. Corrupt private state is outside this API's input contract.

## Interface and binding

`initialize(owner, actual-length, epoch)` clears the first 8MiB and establishes
a positive epoch at most 2^53-1. A larger actual owner is allowed; its tail is
untouched. All shape refusals precede the first state access/mutation.

`accept(owner, actual-length, binding, actual64, record, actual2048, now)`
returns -1 on refusal, 0 for a committed pending part, or 1 for completion.
All three allocations must be disjoint. The binding and record stay immutable.
The record is validated by the codec's shared `valid-record` operation; no
second, divergent ID/part validation rule is introduced. A refusal preserves
every owner byte, including when completing bytes fail JSON validation.

The caller supplies a protected association from the already-authenticated
managed session/current roster. Binding64 contains magic `0x3142504b`,
version1, epoch64 at8, peer index32 at16 (1..64), zero reserved32 at20,
nonzero X25519 public-key bytes24..55 and zero reserved64 at56. The owner
requires its exact current epoch. An assembly key is the tuple of peer index,
key, epoch and exact decoded UTF8 message ID. The index must identify the
current roster node; the caller must not take it from application JSON. The
binding is data, not evidence of authentication, app/port permission or consent.
Different keys or peers cannot supply one another's missing parts.

An existing assembly's part count cannot change. Replacement subtracts the
old part before checking both quotas. The aggregate quota is checked before
removing a completed message, preserving the legacy order. There is no
fixed-block fragmentation that reduces the promised pending capacity.

`completed-size(owner, actual-length)` reports the pinned byte count.
`completed-copy(owner, actual-length, offset, output, actual-capacity)` copies
up to 65536 bytes, returns the copied prefix length, leaves the output tail
untouched, and refuses invalid offset/capacity/overlap without output changes.
Offset equal to the completed length returns zero. While completion is pinned,
`accept` refuses; the consumer must finish using the bytes and call `release`.
`release` wipes the entire 1MiB staging region and completed metadata.

`advance-epoch` requires a strictly newer epoch and wipes/reinitializes all
8MiB. `revoke` erases every pending/completed item for the exact binding;
it does not implement a separate permanent allow/deny roster. `expire` takes
an explicit positive idle interval, erases at `now-last >= idle`, and advances
the in-boot clock floor. Normal acceptance has no implicit TTL. Successful
acceptance and explicit expiry require a nondecreasing clock <=2^53-1;
refusals do not advance it. This is not a trusted clock, durable version floor,
authorization enrollment, entropy or a retransmission protocol.

## Memory and JSON

The 8MiB layout is global4096; 128 headers of1024 from4096; 262144 entries
of10 bytes from135168; packed payload4MiB from2756608; completed1MiB from
6950912; unused tail389120 from7999488. The entry holds payload offset32,
present/length16 and next32 at6. Presence is independent of zero length.
A linked arrival list supports one-pass compaction, survivor-offset updates
and erasure of the old tail when replacing or removing data. Header/key/ID
and entry bytes are cleared when an assembly is removed.

`kotoba.json.document-region/valid-document(input, actual-capacity, used)`
requires a real capacity >=1MiB and used0..1MiB. The existing 64KiB JSON cursor
keeps its original contract. The new scanner has at most64 nested containers
and no sibling/node cap. It shares the existing strict character codec through
actual <=12-byte windows, including Unicode/escape boundaries across64KiB.
It accepts JSON scalar roots, numbers, duplicate object keys, whitespace and
containers; it supplies no AST, duplicate-field schema or service semantics.
It refuses invalid UTF8, lone surrogates, comments, non-JSON numbers and trailing
data. The native profile is deliberately stricter than the old JS decoder's
replacement/coercion behavior; canonical valid JSON and original byte/part
limits remain. It is not the whole legacy object API or JSON facade migration.

## Verification and remaining integration

`scripts/check-kekkai-application-reassembly-os.py` uses Amu's native module
discovery, source lock, actual selfhosted Mac compiler and boot packager.
It retains the real 11-source ValueRuntime, two PT_LOAD segments, the prior
diagnostic user payload, 113 codec cases, 12 cursor guards and shared EDN/HMAC
known answers. The staged adapter only invokes the new tests before that
unchanged corpus; it does not remove a body/export or substitute a runtime.
The guest executes under QEMU; its diagnostic user ELF is packaged, not run.

Native tests exercise full1MiB completion/copy, all4MiB pending payload,
128 simultaneous assemblies, 128*2047 simultaneous incomplete parts and the
2048th part, zero-length duplicate presence, size-changing duplicate replacement,
out-of-order parts, complete-invalid rollback, long ASCII/BMP/astral/control IDs,
peer/key/epoch separation, clock/expiry/revocation, short actual views and every
input/owner alias. Independent whole8MiB observations check full aggregate,
maximum-density, epoch-reset and final completion images. Every accept refusal
is compared against its complete prior owner and immutable input bytes.

Python creates public inputs/expected bytes and observes the native results;
it does not parse policy or execute Kotoba/application logic. Loopback GDB writes
only a checkpoint acknowledgement in a dedicated test receipt while QMP pauses
the owned guest, letting whole-state observations complete before continuation.
This harness acknowledgement is never app approval or production control.

The source-bound evidence records normal runs, full-corpus guard-removal faults
and retained failed build/observer probes. A compile error, trap or timeout is
not a detected fault. Production readiness still requires the actual managed
NIC/reassembly bridge, complete request/reply schema and pending context,
directed service/port/socket policy and fresh trusted per-operation consent,
native Mac backend, app install/launch on Mac and6600H, live authenticated
revoke/reconnect, protected identities/config/entropy/clock/durable floors,
native SSH, isolation/security/operations and distributed-OS/L1 acceptance.
PXE/SSH and the owner's physical-input pause remain. No physical deployment,
production release, trusted approval or Reddit spend is implied.

## Later receive-composition unit

The separate [native managed application receiver](native-application-receive.md)
connects actual authenticated NIC ingress to the full-capacity reassembly owner.
Its source-bound evidence is recorded separately; the earlier receipt and its
component scope above remain unchanged. This establishes the responder kernel diagnostic
receive/reassembly path. Product integration, complete
request/reply schema and pending service context, directed socket/policy/fresh
consent, actual Mac/6600H app installation/live peer, native SSH and production
isolation/operations/OS/L1 acceptance remain open.
