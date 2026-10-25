# kotoba-lang/ch-iec-61850

**GOOSE (IEC 61850-8-1) wire encoding/decoding in portable `.cljc`: the
Ethernet/APPDU envelope, the BER `goosePdu`, its `Data` value CHOICE, and the
`stNum`/`sqNum` retransmission state machine as pure predicates.** Sampled
Values (IEC 61850-9-2) and MMS (ISO 9506) are **not implemented** — see
"What this is not" below.

## Why this exists

GOOSE is what a protection relay uses to tell every other relay on the
station bus "the breaker just tripped" in under 4ms, with no acknowledgment
and no retry — it is UDP-less multicast Ethernet, one frame, and the only
recovery mechanism is the publisher repeating itself. Nothing in this
workspace could previously encode or decode one.

## Surface

```clojure
(require '[iec61850.appdu :as appdu]
         '[iec61850.goose :as goose]
         '[iec61850.data :as data]
         '[iec61850.utctime :as utctime])

(def apdu
  (goose/encode {:gocbRef "IED1LD0/LLN0$GO$gcb01"
                 :timeAllowedToLive 2000
                 :datSet "IED1LD0/LLN0$DataSet1"
                 :goID "IED1LD0/LLN0$GO$gcb01"
                 :t {:seconds 1735689600 :fraction 0.25 :time-accuracy 20}
                 :stNum 5 :sqNum 0 :simulation false :confRev 1 :ndsCom false
                 :allData [[:boolean true] [:integer -12] [:floating-point 50.5]]}))

(def frame
  (appdu/encode {:dst-mac [0x01 0x0C 0xCD 0x01 0x00 0x01]
                 :src-mac [0x00 0x30 0xA7 0x12 0x34 0x56]
                 :ethertype appdu/ethertype-goose :appid 1 :apdu apdu}))

(let [[:ok f] (appdu/decode frame)]
  (goose/decode (:apdu f)))
;=> [:ok {:gocbRef "IED1LD0/LLN0$GO$gcb01" :stNum 5 :sqNum 0 ...}]

(goose/classify-transition {:stNum 5 :sqNum 0} {:stNum 6 :sqNum 0})
;=> :data-change
```

| namespace | |
|---|---|
| `iec61850.appdu` | the Ethernet/802.1Q/EtherType/APPID/Length/Reserved envelope shared by GOOSE and SV — `encode` `decode`, EtherType constants |
| `iec61850.goose` | the `goosePdu` BER SEQUENCE — `encode` `decode`; `data-change?` `retransmission?` `restart?` `classify-transition` `next-stnum` `next-sqnum` |
| `iec61850.data` | the MMS-style `Data` value CHOICE — `encode-data` `decode-data`, 9 variants (see below) |
| `iec61850.utctime` | IEC 61850-7-2's 8-octet binary `UtcTime`, distinct from ASN.1's textual `UTCTime` — `encode` `decode` |

Bytes are `Sequential` collections of ints in 0..255, in and out — same
convention as `org-modbus` and `org-ietf-asn1`.

## Reuse, not reinvention: wired to `org-ietf-asn1`

GOOSE and MMS are BER on the wire — a `[APPLICATION 1]` SEQUENCE full of
context-tagged fields. `org-ietf-asn1` (`kotoba-lang/org-ietf-asn1`) is a real
BER/DER codec that already existed in this workspace, so this library is a
workspace-local git dependency on it (`deps.edn`), not a second BER codec.

Specifically: `asn1/implicit` retags an already-built universal element
(INTEGER, BOOLEAN, OCTET STRING) under a context tag without touching its
content — which is exactly what IEC 61850's `[n] IMPLICIT` fields are — so
`iec61850.data` and `iec61850.goose` build every INTEGER/BOOLEAN/OCTET
STRING/BIT STRING field by calling `asn1/integer`, `asn1/boolean*`,
`asn1/octet-string`, `asn1/bit-string`, then `asn1/implicit`, and read them
back with `asn1/integer-value`, `asn1/boolean-value`, `asn1/bit-string-value`,
`asn1/string-value`. The DER-minimal-integer encoding, the BOOLEAN
`0x00`/`0xff` rule, BIT STRING unused-bit handling, and all BER tag/length
framing are `org-ietf-asn1`'s, unmodified.

Two things `asn1.core` does not export that this library needed, and how
they were handled **without** forking or vendoring `asn1.core`:

- **VisibleString under a context tag.** `asn1.core` has no bare
  `visible-string` constructor. GOOSE's string fields (`gocbRef`, `datSet`,
  `goID`) are `[n] IMPLICIT VisibleString`; since IMPLICIT tagging discards
  the universal tag on the wire anyway, `iec61850.goose` calls
  `asn1/ia5-string` (which builds identical ASCII content octets) and
  `asn1/implicit`-retags it — reusing `asn1.core`'s own content-encoding
  function rather than duplicating the one-line `(map int s)` it contains.
- **The binary `UtcTime` type and the `Data` CHOICE's context tags.**
  `asn1.core`'s typed constructors (`integer`, `boolean*`, ...) only build
  *universal*-class elements; IEC 61850 needs bare context-class elements
  too (e.g. `[2] IMPLICIT SEQUENCE OF Data` for a `structure`, or the raw
  8-octet `UtcTime` content under `[4]`). `asn1.core`'s own element shape —
  a map of `:asn1/class`/`:asn1/tag`/`:asn1/constructed?`/`:asn1/content`
  (or `:asn1/elements`) — is exactly what `encode-ints`/`decode-at` consume
  regardless of class, so `iec61850.data`/`iec61850.goose` build those maps
  directly and pass them straight into `asn1/encode-ints` / read them back
  from `asn1/decode-at`'s output. This is using `asn1.core`'s public element
  representation, not reimplementing its tag/length machinery — no BER
  framing logic of any kind lives in this repo.

## The `Data` CHOICE

```clojure
(data/encode-data [:boolean true])
(data/encode-data [:structure [[:visible-string "phase-A"] [:unsigned 400]]])
```

| choice | ASN.1 shape |
|---|---|
| `:structure` | `[2] IMPLICIT SEQUENCE OF Data` (recursive) |
| `:boolean` | `[3] IMPLICIT BOOLEAN` |
| `:bit-string` | `[4] IMPLICIT BIT STRING` — value `{:unused-bits n :ints [...]}` |
| `:integer` | `[5] IMPLICIT INTEGER` |
| `:unsigned` | `[6] IMPLICIT INTEGER`, refuses a negative value |
| `:floating-point` | `[7] IMPLICIT OCTET STRING` (MMS `FloatingPoint`: 1-octet exponent-width=8 + IEEE 754 binary32, 32-bit profile only) |
| `:octet-string` | `[9] IMPLICIT OCTET STRING` |
| `:visible-string` | `[10] IMPLICIT VisibleString` |
| `:utc-time` | `[17] IMPLICIT UtcTime` (the 61850 binary form, `iec61850.utctime`) |
| array, real, binary-time, bcd, booleanArray, objId, mMSString | — | **not implemented** |

## On the honesty of the tag numbers — read this before trusting a byte

IEC 61850-8-1 and ISO 9506-2 are paywalled. Nothing in this repository was
written by reading their text. The BER structure — field order, context tag
numbers, the `[APPLICATION 1]` outer tag — is reconstructed from public,
widely-deployed open-source implementations that ship their own copy of this
ASN.1: libiec61850's headers and Wireshark's BSD-licensed
`epan/dissectors/asn1/goose`/`mms` modules. Tags 0-11 of `goosePdu` and 1-16
of `Data` are consistent across every such source seen; tag 17 for the
IEC 61850-7-2 `utc-time` extension to `Data` is the value seen most often but
could not be cross-checked against standard text. `EtherType 0x88B8`/`0x88BA`
and the Ethernet/APPDU envelope shape are likewise reconstructed from public
sources, not the standard.

What this library can actually prove, and does, with real bit operations —
not string comparison, not `=` on opaque blobs — and property tests:
`decode(encode(x)) = x` for `goosePdu` and every implemented `Data` variant,
the UtcTime fraction is a `2^-24`-resolution binary fixed point (not a
disguised microsecond count — the classic mistake, tested explicitly),
`TimeQuality`'s bit layout, and the APPDU `Length` field's exact byte range.
Every fixture that is not independently checkable against published spec
text is labelled `;; constructed, not a published spec vector` in the test
source, rather than presented as a verified spec worked example. The
Ethernet/802.1Q header, `EtherType` constants, and BER tag/length rules
(inherited from `org-ietf-asn1`, whose own suite verifies them) are the parts
with the highest confidence; the exact `Data` CHOICE tag assignment (in
particular tag 17) has the least.

## The two classic bugs this deliberately guards against

**`FractionOfSecond` is `raw / 2^24`, not `raw / 10^6`.** Both a correct
binary-fixed-point reading and a wrong microsecond reading produce a
plausible-looking sub-second value for small inputs and only disagree once
you check a specific boundary — `iec61850.utctime`'s test suite asserts
`0.5s -> 0x800000` explicitly rather than relying on round-trip alone, which
a self-consistent wrong divisor would also pass.

**`stNum`/`sqNum` are not a version counter to compare with `>`.** `stNum`
increments on a genuine data change and resets `sqNum` to 0; `sqNum`
increments on every retransmission of *unchanged* state. `iec61850.goose`
models this as four separate pure predicates
(`data-change?`/`retransmission?`/`restart?`) plus `classify-transition`
rather than a single "is this newer" comparison, because "newer" is not
well-defined across a `stNum` reset (a publisher restart) the way it is for
a monotonic sequence number.

## What this is not

- **Not an IED stack.** No configuration model, no subscription management,
  no GOOSE Control Block, no publisher/subscriber runtime.
- **No Ethernet I/O.** No raw sockets, no NIC binding, no multicast
  join/leave, no threads, no timers. This library only turns bytes into
  values and back.
- **No SCL parsing.** IEC 61850-6 System Configuration Language (the XML
  substation description format) is out of scope entirely — nothing here
  reads or writes `.scd`/`.icd`/`.cid` files.
- **No conformance certification.** This is not a UCA International Users
  Group-certified implementation and makes no claim of interoperability
  testing against real IEDs.
- **Sampled Values (IEC 61850-9-2) and MMS (ISO 9506) are not implemented.**
  `EtherType 0x88BA` is recognized by `iec61850.appdu/decode` (so a mixed
  GOOSE/SV capture does not misclassify SV frames as bad-ethertype), but
  there is no `savPdu`/ASDU codec. MMS's `Initiate`/`Read`/`Write`/
  `GetNameList`/`InformationReport` PDUs are not implemented at all — only
  the `Data` type mapping they would share with GOOSE's `allData` is here,
  under `iec61850.data`. Scoped out deliberately: GOOSE done correctly and
  honestly, over three layers done shallowly.
- **No signing/encryption.** GOOSE's optional `security [12]` field
  (R-GOOSE / IEC 62351-6) is not implemented.
- **`:floating-point` is 32-bit only.** MMS's `FloatingPoint` type permits
  other exponent widths in principle; only the IEC 61850-7-2 32-bit profile
  (the only one real GOOSE traffic uses) is implemented, and a different
  width is refused with `:iec61850.data/floating-point-unsupported-width`
  rather than silently misread.

## Verify

```sh
kbb -M:test
```

Errors are returned, never thrown, as `[:error kw data]` with a namespaced
keyword naming the specific reason (`:iec61850.appdu/bad-ethertype`,
`:iec61850.utctime/wrong-length`, `:iec61850.goose/malformed-ber`,
`:iec61850.goose/numdatasetentries-mismatch`, `:iec61850.data/unknown-choice-tag`,
...) — decoding a hostile or malformed frame from the wire is an expected
outcome, not a programmer error, and "it failed somehow" is not
distinguishable from a different bug. `encode` functions given
self-evidently invalid input (a negative `:unsigned` Data value, a MAC that
is not 6 octets) throw `ex-info` with a `:type` keyword instead, matching
`org-ietf-asn1`'s own convention for construction-time misuse.
