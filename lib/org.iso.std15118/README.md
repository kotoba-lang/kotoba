# kotoba-lang/org-iso-15118

**ISO 15118 (EV–EVSE communication interface) — the V2GTP (V2G Transfer
Protocol) transport header, in portable `.cljc`, with no dependencies. This
library targets ISO 15118-2's V2GTP+EXI stack specifically (not
DIN 70121 or ISO 15118-20's 2nd-generation network layer).**

## Scoping decision: EXI is NOT implemented here — read this first

ISO 15118's application-layer message bodies (SupportedAppProtocolReq,
SessionSetupReq, ChargeParameterDiscoveryReq, and so on) are encoded with
**EXI (Efficient XML Interchange, a W3C recommendation)**. A correct,
general EXI codec — the bit-packed grammar-driven encoding, not just a
binary format — is a substantial independent piece of work on its own, on
the scale of a full protocol library by itself.

This library made the honest choice named in its own scoping brief:

> (a) Implement V2GTP framing completely and correctly, treat the EXI
> payload as an opaque byte string, and name EXI as the bounded gap.

**Payload is always an opaque byte vector here.** `v2gtp.frame/encode` takes
whatever bytes you give it as `:payload` and writes them verbatim after the
header; `v2gtp.frame/decode` hands back exactly `PayloadLength` bytes,
unparsed. Nothing in this library reads, validates, or generates EXI. A
caller that needs to actually construct or interpret a SessionSetupReq (or
any other ISO 15118 application message) needs a real EXI codec on top of
this, which does not exist in this workspace as of this library's creation
(checked via `kbb --backend sci scripts/repo-search.cljk exi xml w3c` against the
workspace-wide concept index before starting — the closest existing
libraries are `kotoba-lang/xml`, a Hiccup<->XML text codec with no EXI
compression, and several `com-*`/`org-w3-*` facade repos that are
API-shaped stubs, not codecs).

**What this means concretely**: this library can correctly frame, route,
and pipeline the bytes of an ISO 15118-2 exchange over TCP (it can tell you
"here are the next 214 bytes and they claim to be an EXI-encoded V2G
Message" and hand you exactly those 214 bytes), but it cannot tell you what
those 214 bytes *mean*. That is a real, useful, and honestly bounded piece
of the protocol — not the whole protocol.

## What this is not

- Not an EXI codec (see above — the deliberate, stated gap).
- Not a TLS or TCP client. No sockets, no IO.
- Not SDP's UDP multicast discovery logic, TLS certificate handling, or
  Plug & Charge / ISO 15118-2's identity/contract-certificate machinery.
  Those all ride on top of V2GTP framing (SDP's own request/response
  bodies are themselves V2GTP payloads, per `PayloadType` 0x9000/0x9001) —
  this library frames them, it doesn't implement them.
- Not a charging session state machine (no SessionSetup->
  ServiceDiscovery->...->SessionStop sequencing).
- Not ISO 15118-20 (2nd generation) — this targets the 15118-2 V2GTP header
  and its documented ProtocolVersion 1 pairing specifically.

## Surface

```clojure
(require '[v2gtp.frame :as frame] '[v2gtp.payload-type :as pt])

(def enc (frame/encode {:protocol-version 0x01
                         :payload-type 0x8001 ; EXI encoded V2G Message
                         :payload exi-bytes})) ; opaque — this library doesn't touch it
;; enc => [0x01 0xFE 0x80 0x01 <4-byte length> ...exi-bytes]

(frame/decode enc)
;; => [:ok {:protocol-version 0x01 :payload-type 0x8001 :payload-length N
;;          :payload [...] :leftover []}]

(pt/name-of 0x8001) ; => :exi-encoded-v2g-message
```

| namespace | |
|---|---|
| `v2gtp.bits` | big-endian u16/u32 <-> byte-vector primitives — see "The trap" below |
| `v2gtp.payload-type` | known `PayloadType` values + name lookup |
| `v2gtp.frame` | the 8-byte V2GTP header: `encode`/`decode` |

Bytes are `Sequential` collections of ints in 0..255, in and out.

## The header

8 bytes, **big-endian**:

| offset | size | field |
|---|---|---|
| 0 | 1 | ProtocolVersion |
| 1 | 1 | InverseProtocolVersion (bitwise complement of ProtocolVersion) |
| 2 | 2 | PayloadType |
| 4 | 4 | PayloadLength |
| 8 | PayloadLength | Payload |

Corroborated against the Eclipse-hosted **RISE-V2G** reference
implementation (`SwitchEV/RISE-V2G`, `RISE-V2G-Shared/.../misc/V2GTPMessage.java`
— MIT-licensed, "the only fully-featured reference implementation of ...
ISO 15118" per its own README), whose constructor computes
`InverseProtocolVersion` as `protocolVersion ^ 0xFF` and whose `getMessage()`
docstring cites the standard directly: *"the order of a newly created byte
buffer is always big endian (see [V2G2-085] on page 27)"*. `PayloadType`
values (`0x8001` EXI-encoded V2G Message, `0x9000` SDP request, `0x9001`
SDP response, `0xA000..0xFFFF` manufacturer-specific, everything else
reserved) are cited to that same javadoc plus the value table as
independently reproduced by other public implementers/analyses of the
protocol (see `v2gtp.payload-type`'s docstring for the honest caveat: this
workspace does not have paid access to the ISO 15118-2:2014 PDF itself, so
these are corroborated against a widely-deployed open-source
implementation and public secondary sources, not against a section number
in the purchased standard text).

## The trap this library's arithmetic is built to avoid

PayloadLength is a 4-byte **unsigned** integer — its wire range goes up to
4294967295, which crosses the sign bit of a 32-bit **signed** integer at
0x80000000. `v2gtp.bits`' docstring and the test suite's
`sign-bit-trap-demonstration` spell this out in full, but the short version:
reconstructing that field as `(bit-or (bit-shift-left b0 24) ...)` is
correct on the JVM (64-bit long bitwise ops) and **silently returns a
negative number under ClojureScript** (32-bit signed `ToInt32` coercion)
for any PayloadLength >= 0x80000000 — exactly the "`bit-or` ToInt32
coercion producing negatives" bug class this workspace has hit repeatedly
elsewhere. `v2gtp.bits/bytes->u32`/`u32->bytes` sidestep it entirely by
using ordinary multiplication/division instead of a 24-bit shift, which is
exact on both runtimes for the whole unsigned 32-bit range.

## Errors

Returned, never thrown. `:reason` is a keyword: `:v2gtp/header-too-short`
(fewer than 8 bytes total), `:v2gtp/payload-too-short` (the header parses,
but fewer than the declared `PayloadLength` bytes remain), and
`:v2gtp/inverse-version-mismatch` (byte 1 isn't the bitwise complement of
byte 0). **Those keywords are contract.**

## `:leftover`

`decode` takes exactly one frame's worth of bytes and returns whatever
follows as `:leftover` — V2GTP frames are meant to be read back-to-back off
a TCP stream (SDP, the TLS handshake, and every EXI-encoded V2G message all
share this same framing), so a decoder that refuses or discards trailing
bytes makes stream pipelining impossible. `:leftover` is `[]` when the
input was exactly one frame.

## Relationship to `kotoba-lang/org-ocpp-charging`

Both are EV-charging-adjacent, but at different layers of the stack and
speaking to different parties. **OCPP** (Open Charge Point Protocol) is the
**back-office <-> charge point** management protocol — a charge station
talking to its Charge Point Management System over WebSocket/JSON (remote
start/stop, firmware updates, tariffs, availability). **ISO 15118** is the
**vehicle <-> charge point** protocol on the other side of the same charge
station — the EV and the EVSE negotiating over the charging cable itself
(Plug & Charge, power delivery parameters, session identity). A single
charge point implementation typically speaks both, to two different
counterparties, and this library doesn't touch OCPP at all.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

Both run the same 17 deftests / 346 assertions in `test/v2gtp/core_test.cljk`.

**Header field values are cited** (RISE-V2G + public secondary sources, see
above) — this library's own frame-level test vectors (the specific EXI/SDP
payload byte sequences used in `encode-known-exi-frame`/
`decode-known-sdp-request-frame`) are constructed, not captured real V2G
traffic; the payload bytes are opaque as far as this library is concerned,
so what those vectors actually exercise is the header arithmetic around
them, which is checked against the cited big-endian layout and computed
`InverseProtocolVersion`/`PayloadLength` values.

**Discrimination was verified by breaking the real implementation, not just
a test fixture.** `v2gtp.bits/inverse-byte` was temporarily changed to
always return `0` (a "forgot to implement the complement" bug) and the JVM
suite re-run: every test decoding a previously-valid frame
(`decode-known-exi-frame`, `decode-known-sdp-request-frame`,
`inverse-byte-known-values`, `encode-known-exi-frame`) failed immediately,
because every real frame's `InverseProtocolVersion` byte (0xFE for
ProtocolVersion 1) no longer matched the broken function's constant-0
output — exactly the `:v2gtp/inverse-version-mismatch` path firing on
input it should never fire on. The change was then reverted and both JVM
and ClojureScript suites re-run clean (0 failures, 346 assertions each).
