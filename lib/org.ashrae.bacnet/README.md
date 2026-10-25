# kotoba-lang/org-bacnet

**BACnet/IP (ASHRAE 135, the 2020 edition's numbering) wire codec — BVLC,
NPDU, APDU, primitive application tags, and four services — in portable
`.cljc`, with no dependencies.**

## What this is not

A **codec**, not a device stack. There is no socket here, no UDP transport,
no device object database, no COV subscription manager, no segmentation
reassembler, and no BBMD/foreign-device registration state machine. Given
bytes this decodes them into data; given data this encodes bytes. What a
caller does with a socket and those bytes is a separate concern this
library does not take on, the same split `org-modbus` (its `README`'s
explicit model for this one) draws between framing and transport.

## Surface

```clojure
(require '[bacnet.tags :as tags] '[bacnet.npdu :as npdu] '[bacnet.bvlc :as bvlc]
         '[bacnet.apdu :as apdu] '[bacnet.services :as services])

;; A ReadProperty-Request for AI:5's Present-Value, wrapped down to wire bytes.
(def svc (:bytes (services/encode-read-property-request
                   {:object-type 0 :instance-number 5 :property :present-value})))
(def apdu-bytes (:bytes (apdu/encode-confirmed-request
                          {:invoke-id 1 :service :read-property
                           :max-segments-accepted 1 :max-apdu-length-accepted 1476}
                          svc)))
(def npdu-bytes (:bytes (npdu/encode {} apdu-bytes)))
(:bytes (bvlc/encode :original-unicast-npdu npdu-bytes))
```

| namespace | |
|---|---|
| `bacnet.tags` | Clause 20.2.1 primitive application tag encoding — tag header (incl. extended tag number and extended length), Null/Boolean/Unsigned/Signed/Enumerated/BACnetObjectIdentifier, opening/closing tags |
| `bacnet.npdu` | Clause 6 — version, control octet, DNET/DADR/SNET/SADR, hop count |
| `bacnet.bvlc` | Annex J — the BACnet/IP header (Result, Original-Unicast-NPDU, Original-Broadcast-NPDU) |
| `bacnet.apdu` | Clause 20.1 — Confirmed-Request/Unconfirmed-Request/SimpleACK/ComplexACK/Error/Reject/Abort |
| `bacnet.services` | Clause 15/16 parameters for ReadProperty, WriteProperty, Who-Is, I-Am |

Bytes are `Sequential` collections of ints in 0..255, in and out — same
convention as `org-modbus`.

## Four details that are usually got wrong

**BACnet is big-endian; OPC UA (`org-opcfoundation-ua`, this workspace's
other new protocol library) is little-endian.** A codec ported between the
two by habit gets every multi-byte field backwards. See `bacnet.npdu`'s
docstring.

**The BVLC length counts its own 4-octet header**, not just the NPDU that
follows — the same "off by the header size" trap `modbus.tcp`'s MBAP length
documents, except UDP has no stream to resynchronise on the next read, so
this one does not recover.

**Boolean's encoded shape depends on the tag class, not just its value.**
Application-tagged, the value lives in the LVT nibble and there are zero
data octets. Context-tagged, it is an ordinary length-1 primitive whose one
data byte is 0 or 1. Reading one form as the other silently reads the wrong
byte, or a byte that is not there. See `bacnet.tags`'s docstring.

**I-Am's four fields are application-tagged; ReadProperty/WriteProperty's
are context-tagged.** A decoder that assumes "services use context tags"
because that is the common case misreads I-Am, because the two differ only
in one bit and both parse as *something*. See `bacnet.services`'s docstring.

## Errors

Returned, never thrown. `:reason` (or the second element of an `[:error
reason]` pair) is a keyword naming the rule — `:bacnet/truncated-tag`,
`:bacnet/opening-tag-must-be-context`, `:bacnet/object-type-out-of-range`,
`:bacnet/instance-number-out-of-range`, `:bacnet/source-address-required`,
`:bacnet/length-mismatch` (BVLC), `:bacnet/tag-number-mismatch`,
`:bacnet/unknown-service`, `:bacnet/frame-too-short`, and more — each
namespace's decoder functions name the specific ones they raise. **Those
keywords are contract.**

## Object identifier packing — the classic cross-platform trap

`BACnetObjectIdentifier` packs a 10-bit object-type into the top of a
32-bit word. For object-type values >= 512 that sets bit 31 — the sign bit
of a JavaScript bitwise operand. ClojureScript's `bit-shift-left`/`bit-or`
compile straight to JS `<<`/`|`, both **signed** 32-bit, so the packed
value can print negative in the browser and positive on the JVM — same
bits, different sign story, and neither side is wrong. `bacnet.tags`'
`unpack-object-identifier` only ever extracts through `bit-and`/
`unsigned-bit-shift-right`, which read the 32-bit pattern as unsigned on
both platforms; comparing the packed integer directly (rather than the
type/instance pair it unpacks to) would be the mistake this avoids.
`bacnet.tags/decode-unsigned-value` hits the same trap from the other
direction — reconstructing a 4-byte Unsigned >= 0x80000000 needs one final
`unsigned-bit-shift-right … 0` (the `x >>> 0` idiom) to come back positive
in ClojureScript; without it, `4000000000` decodes to `-294967296` on the
ClojureScript path and to the correct value on the JVM, so a JVM-only test
suite would never catch it. Both docstrings walk through this in full.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

51 tests, 430 assertions, on both runtimes. Coverage: object-identifier
pack/unpack across boundary values (0, max object-type, max instance,
mid-range); every implemented primitive type round-tripped through the
application tag form including 4-byte unsigned values that exercise the
sign trap above; extended tag numbers (>= 15); extended length across all
three widths (1-octet, 2-octet at the 254 boundary, 4-octet at the 65536
boundary); NPDU with/without destination and source, including the hop
count's position after both address blocks; all three implemented BVLC
functions; all seven implemented APDU PDU types including segmented-header
round-trips; all nine Reject reasons and all six named Abort reasons;
ReadProperty/WriteProperty/Who-Is/I-Am each round-tripped standalone and
then again as a single BVLC(NPDU(APDU(service))) frame decoded back down
through all four layers.

Every test vector in this suite is **constructed, not a published spec
vector** — ASHRAE 135, unlike the Modbus specification `org-modbus` tests
against, is not something this library has verbatim worked examples for to
cite. Each constructed vector says so at its assertion and states the
encoding rule it was hand-derived from, rather than presenting itself as
spec text.

## Not here

**Segmentation.** `bacnet.apdu` accepts and round-trips the SEG/MOR header
bits and the sequence-number/proposed-window-size octets, because refusing
to decode a real segmented header would be worse than partial support — but
this library does not reassemble a multi-segment message, and
`SegmentACK-PDU` (the transport-only PDU type segmentation uses) is
recognized by name and refused (`:bacnet/segment-ack-not-implemented`)
rather than guessed at.

**Real/Double/OctetString/CharacterString/BitString/Date/Time** — six of
Table 20-1's twelve application tag types. `bacnet.tags` implements
Null/Boolean/Unsigned/Signed/Enumerated/BACnetObjectIdentifier, the ones
ReadProperty/WriteProperty/Who-Is/I-Am need. Real in particular needs an
IEEE-754 single-precision encoder this library does not carry; adding six
untested type codecs "for completeness" is how a protocol library acquires
bugs nobody finds, the same call `org-modbus` makes about function codes
0x18 and up.

**Services beyond ReadProperty/WriteProperty/Who-Is/I-Am.** `bacnet.apdu`
names the full Confirmed/Unconfirmed service-choice enumeration for
recognition, but only these four have parameter codecs in
`bacnet.services`.

**BBMD/foreign-device management** — `bacnet.bvlc` recognizes only Result,
Original-Unicast-NPDU, and Original-Broadcast-NPDU. Write/Read-Broadcast-
Distribution-Table, Register-Foreign-Device, Read-Foreign-Device-Table,
Delete-Foreign-Device-Table-Entry, Forwarded-NPDU, and Distribute-
Broadcast-To-Network are BBMD administrative machinery this library does
not implement.

**Sockets.** UDP port 47808 (0xBAC0), the network-layer message subtype
this library reports but does not decode (`:network-layer-message?`), and
everything a real BACnet/IP stack needs beyond turning bytes into data and
back are the caller's job.
