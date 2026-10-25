# kotoba-lang/org-csa-iot-matter

**The Matter (Connectivity Standards Alliance, csa-iot.org) message
frame — message header, protocol (exchange) header — and Matter's own
Tag-Length-Value (TLV) codec, in portable `.cljc`, with no dependencies.**

## What this is not

A codec, not a stack. There is no socket, no UDP/TCP/BLE transport, no
PASE/CASE session establishment, no commissioning, no interaction-model
dispatch (attribute reports, command invocations — those are *built from*
the TLV this library provides, not implemented here), and no security
(message/payload encryption, MICs, and key derivation are not
implemented — see "Not here"). Nothing here opens a socket or spawns a
thread. It turns Clojure maps into byte sequences and back, and reports
malformed input as a named `[:error reason ...]` — never a thrown
exception, never silent success.

## Surface

```clojure
(require '[matter.message :as msg]
         '[matter.protocol :as proto]
         '[matter.tlv :as tlv])

(msg/encode {:source-node-id? true :dsiz :node-id
             :session-id 0x1234 :message-counter 1
             :source-node-id my-node-id :dest-node-id their-node-id
             :payload protocol-and-tlv-bytes})
;=> [:ok bytes]

(tlv/encode-element {:tag {:kind :anonymous} :type :structure
                      :value [{:tag {:kind :context :number 0}
                               :type :uint8 :value 42}]})
;=> [:ok bytes]
```

| namespace | scope |
|---|---|
| `matter.message` | Message header — Message Flags, Session ID, Security Flags, Message Counter, optional Source/Destination Node ID |
| `matter.protocol` | Protocol (exchange) header — Exchange Flags, Protocol Opcode, Exchange ID, optional Vendor ID, Protocol ID, optional Acknowledged Message Counter |
| `matter.tlv` | Matter's TLV — tag (6 forms), element type (24 forms: signed/unsigned ints, bools, floats, strings, byte strings, null, and Structure/Array/List containers with End-of-Container) |

All multi-byte fields are **little-endian**, and bytes are `Sequential`
collections of ints in 0..255, in and out.

## The shared 802.15.4 layer — not used, and why

Zigbee (`kotoba-lang/org-csa-iot-zigbee`) built a shared IEEE 802.15.4 MAC
frame layer, and Thread (`kotoba-lang/org-threadgroup-thread`) depends on
it for the real reason that Thread traffic is genuinely carried inside
802.15.4 MAC frames. **Matter's own specified scope — the message frame
and TLV this repository implements — never touches an 802.15.4 MAC frame
directly.** Matter is transport-independent: the same message header
above rides over BLE (commissioning), Wi-Fi/IP, or Thread, and when it
rides over Thread it is Thread's own IPHC/UDP/IP layers that eventually
sit on 802.15.4, several layers below anything this repository's scope
reaches. Wiring a dependency on `org-csa-iot-zigbee` here would be
decorative — nothing in this codec would use it — so `deps.edn` has none.

## Provenance — read this before trusting a byte offset

**The Matter specification is a CSA member document, like Zigbee's; it
is not quoted here.** The field sets for the message header, protocol
header, and TLV codec are corroborated across public descriptions of
Matter's wire format and the open-source (Apache-2.0) `connectedhomeip`
reference implementation (`lib/core/PacketHeader.h`/`.cpp`,
`messaging/ExchangeMessageDispatch.h`, `lib/core/TLVTags.h`/
`TLVCommon.h`). **The exact bit position of individual subfields within
the Message Flags and Security Flags octets, and the exact direction of
the TLV control byte's 3-bit/5-bit split, are this repository's own
reconstructions, stated explicitly rather than asserted with false
confidence** — see each namespace's 'Least confident value' section.
**Every concrete byte sequence in this library's tests is `;; constructed,
not a published spec vector`.**

**Read `kotoba-lang/org-ietf-cbor` before `matter.tlv`** — not because
Matter TLV is CBOR (it is a genuinely different, self-contained format:
its 3-bit tag-control/5-bit element-type control byte split, its six tag
forms up to a vendor-id+profile+number fully-qualified tag, and its
value-embedded-in-the-type-code Boolean encoding have no CBOR
equivalent), but because the *shape* of a self-describing tagged codec —
control byte names a type, type determines what follows — is the same
idea, and `org-ietf-cbor` is a smaller, already-working example of it in
this workspace.

## A real bug the ClojureScript run caught (not hypothetical)

`matter.tlv`'s first draft of `rd-int-n-le` (decoding a signed integer)
reconstructed the *unsigned* magnitude first and subtracted `2^(8n)` if
it was in the upper half — mathematically correct, and it passed on the
JVM. Under ClojureScript, decoding `:int64 -1` came back as `0`. The
cause: a negative int64's unsigned magnitude sits near `2^64`, which the
JVM's arbitrary-precision `+'`/`*'` accumulate exactly but
ClojureScript's plain `+`/`*` (IEEE 754 doubles, 53 bits of exact
mantissa) round along the way — for `-1` specifically, the unsigned
magnitude `2^64 - 1` rounds *up* to exactly `2^64`, and `2^64 - 2^64 =
0`. That is not a precision boundary at the edges; it silently broke
*every* negative `:int64` value. The fix (now in `rd-int-n-le`'s
docstring in full) sign-extends from the most-significant byte first and
accumulates the rest onto that seed, so the intermediate values stay
proportional to the real (typically small) magnitude of the decoded
number rather than passing through a value near `2^64` at all —
`int64-negative-values-are-exact-on-both-runtimes` proves this holds even
at `-2^63`, `int64`'s own most negative legal value. `uint64` (genuinely
unsigned, no sign-extension available) keeps a real, honestly-documented
precision gap above `2^53` — see
`uint64-precision-boundary-is-documented-not-silent`.

## Errors

Returned, never thrown. Reasons are namespaced keywords —
`:matter.message/reserved-dsiz`, `:matter.message/missing-source-node-id`,
`:matter.message/header-too-short`, `:matter.protocol/missing-ack-
counter`, `:matter.tlv/reserved-element-type`, `:matter.tlv/reserved-tag-
control`, `:matter.tlv/end-of-container-must-be-anonymous`,
`:matter.tlv/missing-end-of-container`, `:matter.tlv/value-out-of-range`,
`:matter.tlv/element-too-short`, and so on. Every rejection test asserts
the specific reason keyword.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

Round-trip sweeps: every signed/unsigned integer width at its boundary
values (`matter.tlv-test/signed-int-sweep`/`unsigned-int-sweep`); the
Source-Node-ID-present × Destination-ID-size grid
(`matter.message-test/presence-sweep`); the Vendor-ID-present ×
Acknowledgment-present grid (`matter.protocol-test/presence-sweep`);
nested Structure/Array containers to several levels
(`matter.tlv-test/deeply-nested-structures`); a non-ASCII UTF-8 string,
not just byte-count arithmetic (`matter.tlv-test/utf8-multibyte-round-
trip`).

## Not here

**Message/payload security.** Matter's actual on-the-wire messages are
AEAD-encrypted (AES-CCM, keyed by the session established via PASE/CASE);
this library encodes/decodes the *header* fields plaintext, as they would
appear to a party that already holds the session key and has decrypted
the payload. No key derivation, no encryption/decryption, no MIC
computation.

**Message Extensions** (`matter.message`'s `MX` bit) and **Secured
Extensions** (`matter.protocol`'s `SX` bit). Both are acknowledged in the
flag bits (round-trippable) but their contents are not decoded — a
caller that sets either flag is responsible for whatever follows.

**Interaction Model.** Attribute reports, command invocations, event
subscriptions, and the cluster-specific TLV structures they carry are all
*built from* `matter.tlv`'s primitives, not implemented by this
repository — this is a general-purpose TLV codec plus the two framing
headers underneath it, not an Interaction Model client/server.

**PASE, CASE, commissioning, fabric management.** All out of scope for a
message-framing/TLV codec.
