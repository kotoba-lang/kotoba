# kotoba-lang/org-ietf-diameter

**The Diameter base protocol wire format — RFC 6733 — as a portable `.cljc`
codec, with no dependencies.**

Diameter is the AAA (authentication, authorization, accounting) protocol
that succeeded RADIUS. This library encodes and decodes its bytes: the
20-octet message header, the AVP header with its 24-bit length and its
flag bits, the padding rule that gets AVPs onto 4-octet boundaries, the
base data formats, and grouped (nested) AVPs.

## Surface

```clojure
(require '[diameter.message :as msg]
         '[diameter.avp :as avp]
         '[diameter.types :as t]
         '[diameter.avps :as avps])

(msg/encode-message
 {:diameter.message/command-code 257           ; CER, RFC 6733 §5.3.1
  :diameter.message/application-id 0
  :diameter.message/request? true
  :diameter.message/hop-by-hop 1
  :diameter.message/end-to-end 1
  :diameter.message/avps
  [{:diameter.avp/code 264 :diameter.avp/m? true   ; Origin-Host, §6.3
    :diameter.avp/data (t/encode-utf8 "client.example.com")}]})

(msg/decode-message wire-bytes)
;=> [:ok {:diameter.message/command-code 257 ...} 40]
;         the third element is where this message ended in the stream
```

| namespace | |
|---|---|
| `diameter.bytes` | big-endian 16/24/32-bit integers, the `{:hi :lo}` 64-bit pair, hex |
| `diameter.avp` | §4.1 AVP header, §4.1.1 Vendor-ID, the §4 padding rule — `encode-avp` `decode-avp-at` `encode-avps` `decode-avps` |
| `diameter.types` | §4.2 basic and §4.3.1 derived data formats |
| `diameter.message` | §3 message header — `encode-message` `decode-message` |
| `diameter.avps` | base-protocol AVP codes, and CER/CEA (§5.3.1/§5.3.2) as full commands |

Bytes are `Sequential` collections of ints in 0..255, in and out — the
same `->ints` convention `org-ietf-radius` and `org-ietf-asn1` use in this
workspace.

## What this is not

A codec. Not a Diameter node.

There is no peer state machine (RFC 6733 §5.6), no transport — no SCTP, no
TCP, no TLS/DTLS — no routing table, no realm-based request routing, no
session state, no duplicate detection, no watchdog, no failover, no relay
or proxy or redirect agent behaviour. Nothing here opens a socket, spawns a
thread, or reads a clock. `encode-message` will happily build a message
whose AVPs violate a command's CCF; enforcing that a CER really does carry
exactly one Origin-Host is a job for the layer that knows which application
it is speaking, and this library does not.

The one thing it does do, it tries to do exactly.

## Three details that are usually got wrong

**AVP Length is three octets, and it excludes the padding.** §4.1 defines
it as covering "the AVP Code field, AVP Length field, AVP Flags field,
Vendor-ID field (if present), and the AVP Data field" — and §4 says of the
padding that "the length of the padding is not reflected in the AVP Length
field". So Length is 8 (or 12 with a Vendor-ID) plus the data, and the
padding sits *outside* it. Folding the padding into Length is the single
most common Diameter implementation bug, in both directions: an encoder
that does it overstates every AVP whose data isn't already 4-aligned, and a
decoder that reads `Length` bytes and then carries on — instead of
advancing to the next 4-octet boundary — desynchronizes on the *next* AVP
rather than the one it mishandled, which is why it survives casual testing.

**Padding exists for the AVP that comes after.** A single AVP round-trips
correctly whether or not you implement padding at all; only a second AVP
placed behind a first one with, say, 11 octets of data reveals it. That
case has its own test here (`two-avps-back-to-back-decode-independently`),
because a round-trip suite alone will not catch it.

**Reserved bits are ignored, not rejected.** §3 says the header's reserved
Command Flags "MUST be set to zero and ignored by the receiver", and §4.1
says a receiver "SHOULD ignore all 'R' (reserved) bits" of the AVP flags.
So a message with them set decodes successfully. This library still hands
the value back (`:diameter.message/reserved-flags`,
`:diameter.avp/reserved`) rather than dropping it, so a caller that wants
to look can. The 'P' bit is likewise decoded rather than discarded: §4.1
reserves it for end-to-end security that does not yet exist, but it is
still a real bit on the wire.

## How this relates to RADIUS (`kotoba-lang/org-ietf-radius`)

Diameter is RADIUS's successor, and its AVP is a generalization of the
RADIUS attribute. The differences are the reason both libraries exist
rather than one:

| | RADIUS (RFC 2865) | Diameter (RFC 6733) |
|---|---|---|
| attribute length | 1 octet — an attribute can never exceed 255 total | **3 octets** (24-bit) |
| attribute code | 1 octet | **4 octets** |
| vendor extension | one wrapper attribute, type 26, with the vendor's own sub-TLVs inside a length-255 ceiling (§5.26) | a **V flag** on any AVP plus a 4-octet Vendor-ID in that AVP's own header (§4.1.1) — the vendor space is the full AVP space |
| alignment | none — attributes are packed byte-tight | every AVP padded to a **4-octet boundary**, padding excluded from Length (§4) |
| nesting | only the type-26 wrapper, one level, by convention | **Grouped** is a first-class data format and nests arbitrarily (§4.4) |
| transport | UDP, one packet per datagram | **SCTP or TCP** — a byte stream (§2.1), so `decode-message` returns where the message ended |
| header | 20 octets: Code, Identifier, Length, 16-octet Authenticator | 20 octets: Version, Message Length, Command Flags, Command Code, Application-ID, Hop-by-Hop, End-to-End (§3) |
| security | shared secret + MD5 in the protocol itself | delegated entirely to TLS/DTLS (§13); nothing cryptographic in the message format |

AVP codes 1–255 are deliberately "reserved for reuse of RADIUS attributes,
without setting the Vendor-Id field" (§4.1), so the numbering is
intentionally continuous with its predecessor — but nothing else is, and
no code is shared between the two repos.

## Why there is no dependency on `org-ietf-asn1`

Diameter is a flat header plus TLVs, like RADIUS. There is no ASN.1 in it —
no BER length forms, no tag classes, no OID subidentifier encoding — so
there is nothing in this workspace's `org-ietf-asn1` for it to reuse. The
sibling SNMP library depends on `org-ietf-asn1` because SNMP genuinely *is*
BER all the way down; this one would be importing a parser it never calls.

## Why there is no MD5 (or any crypto) here

`org-ietf-radius` carries its own `radius.md5` because RADIUS's Response
Authenticator and User-Password obfuscation are defined in terms of MD5 —
the cryptography is part of that wire format. Diameter's is not: RFC 6733
§13 delegates all of it to TLS/DTLS below the message layer. There is no
Authenticator-equivalent field for this library to compute, so it computes
nothing, and `deps.edn` stays empty.

## Data formats

Implemented (§4.2 basic, §4.3.1 derived): OctetString, Integer32,
Integer64, Unsigned32, Unsigned64, Float32, UTF8String, DiameterIdentity,
Enumerated, Grouped.

**Scoped out, deliberately** — this repo would rather be narrow and right
than broad and guessed:

- **Address** (§4.3.1) — a discriminated union keyed on a two-octet
  AddressType drawn from the IANA Address Family Numbers registry, which
  this repo does not vendor. `Host-IP-Address` (§5.3.5) is the one
  base-protocol AVP that needs it, and it is carried here as a raw
  OctetString: encodable and decodable as bytes, not interpreted.
- **Time** (§4.3.1) — NTP-epoch seconds plus the 2036 rollover procedure.
- **DiameterURI** (§4.3.1) — its own URI grammar with default-port and
  transport rules.
- **IPFilterRule** (§4.3.1) — its own grammar, unrelated to AVP framing.
- **Float64** (§4.2) — Float32 already depends on the platform's IEEE-754
  (`Float/floatToIntBits` on the JVM, `DataView` in JS) to get the bit
  pattern exactly right. Doubling the width doubles the chance of a quiet
  bit-order mistake, and RFC 6733 publishes no test vector for either, so
  shipping it unverified would be worse than not shipping it.

Nothing this library builds needs any of them.

## AVP and command codes

Every code in `diameter.avps` is cited to its RFC 6733 section in a comment
beside it, read out of the RFC text rather than recalled: Session-Id 263
(§8.8), Origin-Host 264 (§6.3), Destination-Realm 283 (§6.6),
Destination-Host 293 (§6.5), Origin-Realm 296 (§6.4), Result-Code 268
(§7.1), Auth-Application-Id 258 (§6.8), Acct-Application-Id 259 (§6.9),
Inband-Security-Id 299 (§6.10), Vendor-Id 266 (§5.3.3), Firmware-Revision
267 (§5.3.4), Host-IP-Address 257 (§5.3.5), Supported-Vendor-Id 265
(§5.3.6), Product-Name 269 (§5.3.7), Origin-State-Id 278 (§8.16),
Disconnect-Cause 273 (§5.4.3). Command Code 257 is CER/CEA (§5.3.1,
§5.3.2); `DIAMETER_SUCCESS` is 2001 (§7.1).

## Errors

Returned by decode, never thrown. Thrown by encode, never returned. The
split is deliberate and matches the sibling libraries: the caller built the
input to `encode-*`, so a bad value there is a bug worth a stack trace; the
network built the input to `decode-*`, so a bad value there is Tuesday.

Decode reasons are contract:
`:diameter/avp-length-too-short`, `:diameter/avp-truncated-header`,
`:diameter/avp-truncated-data`, `:diameter/avp-padding-truncated`,
`:diameter/avp-padding-invalid`, `:diameter/truncated-header`,
`:diameter/unsupported-version`, `:diameter/message-length-too-short`,
`:diameter/message-length-not-aligned`, `:diameter/truncated-message`.

An AVP-level failure inside a message surfaces as the AVP's own reason, not
a generic message-level one — `decode-bubbles-up-avp-error` asserts exactly
that, because collapsing them loses which of the two layers was wrong.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

Both are worth running. This library assembles every field with
`bit-and`/`bit-or`/`bit-shift-left`/`unsigned-bit-shift-right`, and
JavaScript's bitwise operators are 32-bit and **signed** where the JVM's
are 64-bit. That is not a hypothetical here: `diameter.bytes/bytes->uint32`
carries an explicit unsigned fold because without it, ten assertions across
four namespaces failed under nbb while the JVM suite was green — any
Application-ID or Hop-by-Hop Identifier above `0x7fffffff` came back
negative. It was found by running the suite, not by reasoning about it.

### Which test vectors come from the RFC

**RFC-cited.** The AVP-length arithmetic in `diameter.avp-test` is RFC 6733
§4.4.1's own worked Example-AVP walkthrough — the only place in the
document where real AVP bytes are written out with code, length and content
together. The literal strings (`"example.com"`, both
`"grump.example.com:…"` Session-Ids) and the Length values asserted against
them (19, 49, 50) are the RFC's own, not recomputed. The Grouped length
rule (`8 + total length of all included AVPs, including their headers and
padding`) is §4.4 verbatim. Disconnect-Cause's three values are §5.4.3's.

**Constructed.** Anything built by hand is marked `;; constructed, not a
published spec vector` at the site. That covers the grouped AVP composed
from the RFC's Origin-Host and Session-Id sub-AVPs (§4.4.1's real
Example-AVP also carries two large opaque AVPs not reproduced here, so its
stated total of 496 does not apply to the narrower composition, and only
the sub-lengths are the RFC's numbers); the CER/CEA fixtures; and the
Host-IP-Address bytes, which follow §4.3.1's AddressType-then-address
layout for wire realism over an address from RFC 5737's TEST-NET-1 range.
The IEEE-754 constants in `diameter.types-test` (`0x3f800000` for 1.0) are
standard single-precision patterns, not from RFC 6733, and are used only to
cross-check this repo's encode against a number verifiable by hand.

RFC 6733 publishes no complete worked byte-level example of a full CER or
CEA message, so this repo does not claim one.

## Licence

Apache-2.0.
