# Roster-bound native Noise session — JUN-757

`kekkai.session-region` composes the verified roster, canonical allocation-free
Noise IK and datagram owners. It binds one managed peer/session to the current
roster and erases it on replacement/revoke/expiry. It performs no IO and grants
no app/socket/consent authority. It is not an installed Mac or Itonami app.

The state is the existing262144-byte roster owner. Current roster0..32767 stays
in `roster-region`; reserved session32768..65535 contains a512-byte header,
IK8192B at33280 and datagram17408B at41472. Header fields are magic0x31534b4b
at+0, generation u64+8, peer index u32+16, role0/1 u32+20, phase u32+24,
creation/last-success u64+32/+40 and pinned peer public32B+64. Unused session
bytes are zero. Caller-owned state must be protected, API-created and
serialized, never restored from untrusted or unauthenticated snapshots.

`start(owner,actual-bytes,peer,32,secrets,64,now,role)` returns1 or0. The two
32-byte private inputs are static and ephemeral. Their inputs must be nonzero
and distinct; the static private key's actual X25519 public key must equal the
signed/configured self public key. This is a consistency check, not proof of
fresh entropy or protected key custody. Inputs are immutable and the caller
must erase its own secret buffers. Peer must be an eligible unique roster key
and no active attempt/transport may be replaced through start. A new attempt
needs fresh ephemeral input after stop/expiry; freshness is a host duty.

The bound IK prologue is the existing wire string `kekkai-node/1 tailnet:` +
decoded tailnet UTF8 + ` netmap:` + decimal version. Escaped Unicode is decoded
and re-encoded as UTF8; nonnegative i64 versions include0 and9223372036854775807.
Both roles require the roster's expected remote static. The caller selects
initiator1/responder0; deterministic dial scheduling is not implemented here.

`poll(owner,actual-bytes,now)` returns phase0/1/2, or-1 for shape/clock refusal.
It advances the roster's monotonic clock and checks current generation, peer
index/key, self/peer eligibility, bound datagram peer and phase. Pending
handshakes expire at90 seconds; transport uses the canonical180-second expiry
and volume limits. `advice` reports0 usable/1 rekey/2 unavailable, retaining the
120-second rekey advice. Advice does not launch a replacement handshake.
`next-send-counter(owner, ownerBytes, nowSeconds)` polls that same actual
session before returning its next transmit counter, or -1 if unavailable.
The fragmented sender uses this data query to retire a cached frame beyond
the 2048-counter replay-window guarantee. It exposes neither keys nor egress
authority; it retains poll's existing expiry/revocation/clock semantics.
`stop(owner,actual-bytes)` clears all32768 session bytes and retains the roster.
Every successful new-version roster update also clears the full session;
same-version exact refresh keeps it unless the peer expires. A revoked or
expired self/peer cannot start or continue. The new `roster-region/peer-eligible`
index query delegates to the same policy; indices alone are not identities or
authority, so the session adapter separately compares its pinned key.

`handshake-message(owner,actual-bytes,input,actual-input-bytes,output,
actual-output-capacity,now,writing0/1)` handles full Noise messages. Successful
handshake completion checks the peer again when constructing datagram state,
then clears all8192 IK bytes, including static/ephemeral private copies.
`transport-message` has the same8-argument shape with opening0/sealing1. It
handles raw datagram bytes, not app operations. It preserves the existing2048
replay window, authenticated counters, limits and rekey/expiry advice.

Each message uses a private transaction: trial IK65536..73727, staging output
81920..147455, trial datagram147456..164863. Only after the complete operation
and any handshake-to-datagram conversion succeed does it commit cipher state
and the returned output prefix. All196608 transient bytes clear on processed
completion/refusal. A malformed authenticated message, bad tag/replay, wrong
peer/prologue, short output or bad turn cannot alter session/cipher state or
output. A trusted clock may still advance or reap an expired session during a
well-shaped refusal. Shape refusals preserve state. Input/output must be
physically outside owner and mutually disjoint; capacities are0..65536. Max
handshake/datagram wire remains65535, including65439/65487 handshake payloads
and65511 transport plaintext. There is no concurrent/power-fail atomicity claim.
These raw Noise/datagram lengths exclude the existing three-byte Kekkai outer
header; `wire-region` retains its separate65538-byte envelope bound.

Raw authenticated data does not grant a capability, port, reverse edge or a
fresh operation approval. A protected host must bind the actual operation and
inner packet to `roster-region/permitted`, the admitted socket and the shared
fresh-consent broker. This adapter performs no network send and cannot supply
that binding. Authority/config revocation still requires host clear/re-admit;
changing config arguments alone does not revoke previous admitted state.

The source-bound diagnostic runs13 policy/lifecycle scenarios, including both
roles, Unicode, version bounds, rejected signed candidates, same/new-version
refresh, real live-key revoke/expiry, stop and fresh-key reconnection. Old
ciphertext is refused before the new session accepts its valid counter0.
Four separate maximum-size suites cover each role's maximum handshake and
datagram. Each boot runs30 real-view/alias/seed/phase guards, full retained
legacy RFC8032/SHA256 known answers and a prepared/token/full IK known answer.
Independent public X25519/ChaChaPoly/hash expectations check full wires or
full-wire BLAKE2s hashes, plaintext, transcript and directional keys. Native
snapshots compare the full65536-byte current roster/session range except the
allowed last-clock field; every transient/session wipe is asserted in full.
Readback retains64-bit actual/expected return pairs, all native wire hashes,
case assertion counters, final session/transient bytes and final caller output.

The diagnostic allocates two existing domain request regions: one state owner
and one separate caller IO/snapshot/trace region. It checks their actual
addresses do not overlap. No compiler memory grant, stack limit,2MiB code cap,
actual ValueRuntime exports or two-PT_LOAD contract is changed. It packages but
does not execute the unchanged user ELF. Two early E7106 probes from unrooted
legacy prepared APIs are retained. Real prepared/token/wipe known answers keep
those APIs exercised; no math body/export is deleted or replaced with a stub.
This diagnostic closure does not prove the full desktop/app import closure.

Fourteen targeted native faults independently bypass self/peer/version/Unicode,
timeout/lifetime, erasure, active-start, transaction, output/alias and roster-wipe
checks. Each selected case plus all guards/legacy checks must finish normally
and detect the fault; they are not fourteen full-corpus runs. See
`docs/evidence/native-os-managed-session-20261103/receipt.json` for exact source,
corpus, native artifacts, failed probes and bounded qualification.

Still required: actual NIC/socket wiring and per-packet/service/operation
binding; full app/desktop closure and native Mac backend/install; protected
approved config/keys, fresh CSPRNG/clock and durable floor/recovery; multi-peer
orchestration, the existing three-attempt/late-response retry queue, concurrent
rekey and roaming/path policy; fresh consent and real6600H-Mac app traffic;
native SSH, PQ and full distributed OS/L1 production/security/operations gates.
These are public deterministic inputs and synthetic seconds, not fresh entropy,
wall-clock lifetime, actual NIC traffic, performance or production acceptance.
Machine-code constant-time behavior is not qualified by this unit.
PXE/SSH/console and physical-input pause remain unchanged; no Reddit spend.
