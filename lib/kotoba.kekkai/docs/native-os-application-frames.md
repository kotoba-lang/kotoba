# Native application/1 chunks — JUN-757

`kekkai.application-frame-region` implements the existing application JSON
chunk wrapper inside authenticated Kekkai data: version, messageId, partIndex,
partCount and Base64 payload. Native `kotoba.json.region` handles syntax and
uses the unchanged shared EDN Unicode codec. This unit supplies a real wire
codec and an encrypted NIC composition, not a complete application service.

Both `decode` and `encode` take six arguments: private work, actual work bytes,
input, actual input bytes, output, actual output capacity. Work requires8192
bytes. Input/output actual capacities are0..65536 and all three active regions
must be disjoint, immutable while read and serialized by the caller. Shape
refusals preserve work/output. Every processed completion/refusal clears all
8192 private bytes. Refused output stays unchanged. Decode requires at least
2048 output bytes and returns1/-1, committing exactly2048 bytes only after full
admission. Encode consumes exactly2048 record bytes, validates them and returns
the canonical JSON byte count/-1, committing only that prefix after capacity
validation. The record is caller-owned data, never a peer or approval token.

Record layout: magic0x3146504b at0; UTF8 message-ID byte count4; UTF16 unit
count8; part index12; part count16; decoded payload byte count20. ID occupies
64..703 (640B), payload704..1403 (700B); other bytes are zero on decode. Input
record padding is not interpreted by encode. ID admits1..160 UTF16 units,
including escaped controls and astral scalars counted as two units. Version is1,
part count1..2048, index0..<count, and decoded part0..700 bytes. All byte payloads
are preserved. Caller supplies the message ID; no UUID/CSPRNG is fabricated.

Required names can be reordered/JSON-escaped; duplicate decoded required names
refuse. Unknown fields are fully syntax-checked and ignored, including nested
objects/arrays and JSON fraction/exponent numbers. The JSON cursor has64 nested
containers and no AST-node cap. Input may use the complete65536-byte allocation,
although a single managed transport body has its separate65510-byte limit.
The canonical encoder emits the same five fields in the existing order,
JSON-escapes ID controls/quote/backslash, retains other valid UTF8 and produces
standard padded RFC4648 Base64 with zero pad bits.

This native profile intentionally rejects inputs that the old JavaScript
consumer coerced or tolerated: duplicate required names, non-plain-decimal
selected numbers, noncanonical Base64, lone surrogates and excess depth. It
preserves the existing canonical encoder format and all canonical part/index/
ID/payload limits. It is not full parity with JavaScript's permissive input
language; the profile and differences are explicit rather than silent fallback.
No legacy CLJK/JVM/Node implementation is executed.

The pure native corpus has113 cases plus12 direct cursor-boundary guards: decode/encode pairs, exact700-byte parts,
part2047/2048,160-unit ASCII/BMP/astral/control IDs, raw/escaped strings and slash,
65536-byte whitespace input and a more-than32000-sibling JSON array, nesting
boundary, malformed JSON/UTF8/Base64/pad bits, selected numeric refusals,
malformed records, real short views/outputs and all allocation-alias pairs.
Each case checks64-bit actual/expected returns, complete successful-output
BLAKE2s hashes, all unused output bytes, immutable-input hashes, private work
and boundary canaries. Eight faults independently bypass alias/version/pad-bit/
UTF16/duplicate refusal, private clearing, early output or cursor-length checks.
Each must normally finish the complete113-case corpus,12 direct cursor guards
and retained shared known answers before detection. A compile error/trap/timeout is not detection.

The actual RTL8139C+ integration consumes25 Ethernet/UDP/Noise frames and
emits12 independently checked full replies. Ten admitted chunks are decoded,
checked as complete2048-byte records, canonically re-encoded and sent through
the managed native session. Six malformed authenticated chunks are refused;
their replay counters remain consumed. The same source-bound run includes
signed42→revoked43→fresh44, old-ciphertext refusal, invalid-policy refusal,
exact-policy retry and replay before/after reconnection.34 managed-frame guards,
eight direct header probes, descriptor repost, actual owner separation,
per-packet full state/output/transient and final erasure/canaries are checked.
The diagnostic copies canonical bytes before resetting the caller's previous
plaintext output buffer; codec prefix-preservation semantics stay unchanged.

One decoded fixture contains real messageType/requestId/serviceName/method/path/
headers/port/bodyBase64 fields. It remains an opaque part: the diagnostic echoes
canonical chunks and does not execute a request or fabricate a service reply,
SSH capability, socket authorization or trusted consent. Out-of-order and last
part numbers prove part-codec handling only, not completed message reassembly.
The exercised network MTU remains1500; largest logical wrapper cases run in the
pure native region diagnostic rather than pretending to be one UDP packet.

The previous HMAC unused-public-function compile failure is retained. The
fixture now actually streams a published public key/message, compares its
independent HMAC-BLAKE2s answer and wipes the state, and actually parses/indexes
a public EDN known answer. No math body/export is deleted, no ABI stub supplied,
and no compiler cap/stack/grant enlarged. The real11 runtime sources and two
PT_LOAD segments remain. Kernel/EFI/user ELF/slot reproduce; diagnostic user
ELF is packaged, not executed. Python constructs public fixtures and expected
hashes and observes native execution; it does not evaluate protocol policy or
provide an application/language runtime. The previous managed-frame NIC corpus
is separately rerun without importing the new app modules.

Still required, without reducing the original limits: peer/key/roster-epoch
bound reassembly of1MiB messages,2048 parts,128 assemblies and4MiB total;
out-of-order/duplicate/quota/lifecycle management; complete application JSON
schema; actual service/port and pending request/reply context bound to directed
roster/socket policy and fresh per-operation consent; native Mac backend and
Mac/6600H app installation/live connection; protected keys/config/entropy/
clock/durable floors; native SSH, multi-peer/rekey/roaming/PQ/security and the
remaining distributed OS/L1 production/operations gates. Existing four256KiB
domain request arenas do not by themselves establish the full reassembly owner.
PXE/SSH/console and the owner's physical-input pause remain. No physical deploy,
production readiness, trusted user approval or Reddit spend is established.

Source-bound artifacts, all normal/fault runs, superseded profiles and failed
probes: `evidence/native-os-application-frames-20261103/receipt.json`.

## Later receive-composition unit

The separate [native managed application receiver](native-application-receive.md)
connects actual authenticated NIC ingress to the full-capacity reassembly owner.
Its source-bound evidence is recorded separately; the earlier receipt and its
component scope above remain unchanged. This establishes the responder kernel diagnostic
receive/reassembly path. Product integration, complete
request/reply schema and pending service context, directed socket/policy/fresh
consent, actual Mac/6600H app installation/live peer, native SSH and production
isolation/operations/OS/L1 acceptance remain open.
