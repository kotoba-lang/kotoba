# Native signed-roster admission — JUN-757

`kekkai.roster-region` consumes the unchanged signed-netmap envelope through
`kekkai.envelope-region`, then parses authenticated UTF8/EDN through the shared
`kotoba.edn.region` owner and validates the roster schema. Only after all
checks succeed does it replace the current compact roster. It is a prerequisite
for app/Noise integration, not a replacement for a successful app connection.

The caller supplies one262144-byte owner and a separate4096-byte independently
protected and approved configuration. Inputs are immutable and calls must be
serialized. Configuration contains magic0x4746434b, authority32B at32,
expected self X25519 public32B at64, nonnegative version floor u64 at96,
self-ID/tailnet byte lengths u32 at104/108, clock floor u64 at112, plain UTF8
self-ID at128 and tailnet at1152 (each1..1024 bytes). A magic number cannot
establish provenance or app-operation consent. Envelope data never enrolls its
own authority. Input envelopes must be outside the owner and at most98304B.

Owner layout:

| Byte range | Purpose |
| --- | --- |
| 0..32767 | Current compact roster |
| 32768..65535 | Reserved managed-session state |
| 65536..163839 | Envelope/EDN/hash work |
| 163840..196607 | Candidate compact roster |
| 196608..262143 | Authenticated raw payload |

`initialize(owner,actual-bytes)` clears the owner. `update(owner,actual-bytes,
envelope,actual-input-bytes,config,actual-config-bytes,now)` returns0 refusal,
1 new generation or2 identical same-version payload. All update refusals
preserve current roster and session bytes. Processed attempts clear the full
transient196608B before returning; shape/config/clock refusals preserve work.
The successful commit is a serialized memory copy, not a concurrent or
power-fail atomic transaction. No durable floor, clock, key or configuration
store is supplied here.
Revoking or replacing protected configuration requires the host to clear and
re-admit its state. A rejected update deliberately retains the previous
authority/policy; changing the supplied configuration alone does not revoke
an already admitted roster or session.

The required root fields are version, tailnet, self, peers, edges and relays;
funnels is optional. Unknown/duplicate fields and malformed node/edge/metadata
records refuse. The expected self ID/public key and tailnet must match the
configuration. Node IDs and decoded nonzero32-byte keys must be unique,
including self; decoded Unicode escapes cannot alias a second ID. This does
not validate all X25519 point/contributory properties; the actual handshake
must still check them. Nodes retain overlay, status, expiry and optional
endpoint metadata. Relays/funnels are typed and retained, never activated or
treated as implicit grants.

Current header: magic0x31524e4b, version/last-clock/generation u64 at8/16/24,
valid/node-count/edge-count/arena-used u32 at32/36/40/44. Tailnet, relays and
funnels have raw source references at48/56/64; exact raw-payload SHA512 is
at96 and admitted authority32B at160. Node records are96B from512 (self0);
edge records32B from8192; raw escaped strings/metadata use16384..32767.
The explicit profile limits are64 peers,128 edges,16KiB arena, plus the shared
reader's65536-byte input/4096-node/depth64 limits. Larger rosters need a
separately implemented profile; these are not universal protocol limits.

Versions cannot decrease. A repeated version requires the exact raw-payload
SHA512 and authority pin to match; semantically equivalent edited text still
refuses at the same version. Every new generation erases all32768 reserved
session bytes because the Noise prologue includes the roster version. At the
same version, advancing time reaps an ineligible session. The session header
contract reserves generation u64 at+8, peer index u32 at+16 and phase u32
at+24; this unit tests populated bytes, not an actual completed Noise session.

Only status `authorized` with absent/nil expiry or expiry strictly greater
than now is eligible. Self may omit status; explicitly revoked/expired self
cannot connect. An `:overlay` edge in either direction is also required for
session eligibility. `permitted` additionally requires the requested direction,
capability and port on the same directed edge; ports may contain `:any`.
It never unions a capability from one edge with a port from another.

`sessionable` and `permitted` advance the in-boot monotonic clock and may erase
an expired session even when returning0. They are policy predicates, not
socket admission or user approval. The32-byte request has direction0/1 at0,
port at4, now u64 at8 and expected generation u64 at16. A trusted host must
bind it to the actual operation/packet and fresh consent. Supplying these
bytes does not prove that binding. `advance-clock` must be called with a
trusted current clock even when no new roster arrives.

Native qualification uses public RFC seeds and synthetic time1750000000.
It covers69 signed update/policy cases,55 direct EDN cases, five additional
capacity cases, eight actual short-view/alias guards, and the existing public
signed fixture. It checks configured authority/self/tailnet/floors, pending/
revoked/expiry, direction/same-edge ports/stale epochs, same-version conflicts,
state preservation, new-version/reap erasure and transient clearing. Full
request/state dumps permit independent return/identity/node/edge/clear checks.
Fourteen separately booted targeted faults must normally complete their
selected case, all guards and retained legacy known answers and be detected.
They are targeted controls, not fourteen full-corpus runs. Evidence names the
exact corpus and graph for each boot.

The native build retains actual ValueRuntime11 sources, two PT_LOAD segments,
compiler2MiB code cap and existing request/stack grants. Kernel, EFI, user ELF
and slot reproduce. The legacy signature-byte verifier and wire/NIC regression
remain distinct evidence. Failed syntax/type/provenance/name/stack probes are
retained; a compiler refusal or halted VM is not a successful negative test.
The legacy `AGENTS.md` line20 saying no Kekkai module has a native gate already
predates the previous region/wire proofs; this unit adds only the bounded
roster qualification and does not claim whole legacy control-plane coverage.

Still required: protected authority/config/output ownership and durable
version floor, fresh entropy/key custody/trusted clocks, roster-bound actual
Noise handshake and session teardown/reconnect, admitted socket/real packet
binding, full desktop/app compiler closure, native Mac and OS app install,
fresh operation consent, real authenticated6600H peer exchange, native SSH,
PQ and production release/operations/L1 acceptance. No physical deployment,
PXE/SSH/console change, physical-input request or Reddit spend occurs here.
