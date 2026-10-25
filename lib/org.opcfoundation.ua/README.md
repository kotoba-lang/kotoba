# kotoba-lang/org-opcfoundation-ua

**OPC UA binary encoding (IEC 62541-6 / OPC 10000-6, "UA Part 6: Mappings")
— built-in types, NodeId/ExpandedNodeId, Variant, and the TCP transport
(UACP) framing — in portable `.cljc`, with no dependencies.**

## What this is not

A **codec**, not a device stack, a session, or a subscription client. There
is no socket here, no TCP connection, no SecureChannel handshake logic, no
session/subscription/monitored-item state machine, and — see below — **no
OPC UA security**. Given bytes this decodes them into data; given data this
encodes bytes. `org-bacnet` (this workspace's other new protocol library,
published alongside this one) draws the identical line for BACnet/IP, for
the identical reason: what a caller does with a socket and these bytes is a
separate concern this library does not take on.

### OPC UA security is explicitly NOT implemented here

This library carries the **shape** of the security-relevant fields —
`opcua.transport`'s `AsymmetricAlgorithmSecurityHeader` (SecurityPolicyUri,
SenderCertificate, ReceiverCertificateThumbprint) and
`SymmetricAlgorithmSecurityHeader` (SecureChannelId, TokenId) both
round-trip through this codec — but this library does **not** validate a
certificate chain, does not perform the OpenSecureChannel key derivation,
does not sign or verify a MessageChunk, and does not encrypt or decrypt a
symmetrically-secured chunk's body. Those need X.509 parsing (`org-ietf-
x509`), AES (`org-nist-aes`), and SHA-2 (`org-nist-sha2`) — all present
elsewhere in this workspace — wired together into an actual security
policy implementation (`Basic256Sha256`, `Aes256_Sha256_RsaPss`, etc.),
which is a substantial project of its own and out of scope for "wire
codec." Treating SecurityMode `None` bytes as though they were the whole
security story, or half-implementing signing without verifying, would be
worse than not implementing it and saying so.

## Surface

```clojure
(require '[opcua.builtin :as b] '[opcua.nodeid :as nid]
         '[opcua.variant :as v] '[opcua.transport :as t])

;; A Variant carrying a UInt32, the shape a ReadResponse's DataValue.Value holds.
(:bytes (v/encode {:type :uint32 :value 3000000000}))

;; A NodeId for ns=2;i=1001, smallest legal encoding for that pair.
(:bytes (nid/encode {:encoding :numeric :namespace-index 2 :identifier 1001}))

;; A Hello message ready to send as the first bytes on a fresh TCP connection.
(:bytes (t/encode-message :hel :final
          (t/encode-hello {:protocol-version 0 :receive-buffer-size 65536
                            :send-buffer-size 65536 :max-message-size 4194304
                            :max-chunk-count 4000 :endpoint-url "opc.tcp://host:4840"})))
```

| namespace | |
|---|---|
| `opcua.builtin` | Part 6 §5.2 — Boolean, SByte, Byte, Int16/UInt16, Int32/UInt32, Int64/UInt64 (word pairs), Float, Double, String, ByteString/XmlElement, DateTime (as raw ticks), Guid, StatusCode, QualifiedName, LocalizedText |
| `opcua.nodeid` | NodeId's four identifier encodings (two-byte/four-byte/numeric/string/guid/opaque) and ExpandedNodeId's namespace-uri/server-index flag bits |
| `opcua.variant` | Variant (scalar/array/array-with-dimensions), ExtensionObject, DataValue |
| `opcua.transport` | UACP message header (type/chunk/size), Hello/Acknowledge/Error bodies, SequenceHeader, Asymmetric/Symmetric security headers |

Bytes are `Sequential` collections of ints in 0..255, in and out — same
convention as `org-modbus`/`org-bacnet`.

## Four details that are usually got wrong

**OPC UA is little-endian throughout; BACnet (`org-bacnet`) is big-endian
throughout.** A codec ported between the two by habit gets every
multi-byte field backwards.

**The -1 null convention.** String/ByteString both start with an Int32
length prefix; -1 means absent, 0 means present-but-empty, and they are
different wire values a decoder must not collapse into one. See
`opcua.builtin`'s docstring.

**A `UInt32`/`Int32` reconstructed by accumulating bytes with
`bit-shift-left`/`bit-or` prints differently signed on the JVM (64-bit
`long`, never overflows) than on ClojureScript (JavaScript's 32-bit
*signed* bitwise ops)** — the exact same trap `bacnet.tags` documents for
`BACnetObjectIdentifier`, hit here from the opposite (little-endian)
direction, plus a second variant for `Int32` where "the bitwise op already
signs it correctly" is true on exactly one platform. `opcua.builtin`'s
`decode-uint32` and `decode-int32` docstrings walk through both failures
in full — this is not a footnote, it is why this library has two
different-looking fixes for what looks like the same bug.

**NodeId has four wire shapes, ExpandedNodeId reuses the same body but
repurposes the first byte's top 2 bits as flags instead of extending the
identifier-type code.** A decoder that reads the raw first byte as the
identifier-type code (instead of masking off the flag bits first) silently
misreads every ExpandedNodeId that actually sets a flag — this library's
own test suite catches exactly that mistake when deliberately introduced
(see Verify).

## Errors

Returned, never thrown. `:opcua/truncated`, `:opcua/negative-length`,
`:opcua/unknown-encoding` (NodeId), `:opcua/identifier-out-of-range`,
`:opcua/unknown-type` (Variant), `:opcua/dimensions-without-array`,
`:opcua/body-not-allowed` (ExtensionObject), `:opcua/unknown-message-type`,
`:opcua/unknown-chunk-type` — each namespace's decoders name the specific
ones they raise. **Those keywords are contract.**

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

51 tests, 400 assertions, on both runtimes. Coverage: every implemented
built-in type round-tripped across boundary values (including a UInt32 at
and above 0x80000000, the sign trap above); the -1 null convention
asserted as byte-distinct from empty for both String and ByteString; all
six NodeId identifier encodings round-tripped, plus ExpandedNodeId across
all four combinations of namespace-uri/server-index presence; Variant
scalar round-tripped for every implemented type, plus array, null array,
and array-with-dimensions; ExtensionObject across all three encoding
formats; DataValue across several field-presence combinations; the UACP
message header round-tripped across all six message types and three chunk
types; a full Hello/Acknowledge/Error/OpenSecureChannel handshake frame
encoded and decoded back through the common header into its typed body.

Every test vector is **constructed, not a published spec vector** — this
library was not written against ASHRAE-135-style worked examples the way
`org-modbus`'s Modbus tests are (OPC UA Part 6 does not carry the same
kind of verbatim byte-sequence worked examples in the sections this
library implements). Each constructed vector says so at its assertion and
states the encoding rule it was hand-derived from, rather than presenting
itself as spec text.

Negative-test discrimination was verified by deliberately breaking two
things and confirming the *specific* named test failed (not just some
test): (1) the -1 null check in `decode-string`/`decode-byte-string`,
changed to return a sentinel string instead of `nil` — every string/
byte-string/qualified-name/asymmetric-security-header test touching a nil
field failed with the substituted value visible in the diff; (2) the
ExpandedNodeId flag-mask, changed to use the raw first byte as the
identifier-type code instead of masking off the top 2 bits first — every
`expanded-node-id-round-trip` case with a flag set failed
(`:status nil` instead of `:ok`, since the corrupted "identifier-type
code" no longer matched any known encoding). Both were restored and the
suite re-verified green before publishing.

## Not here

**DiagnosticInfo** (BuiltInType 25) — a recursively-nested structure (an
optional inner DiagnosticInfo referencing further string-table indices)
whose encoding mask has seven independent optional fields. Getting this
wrong from memory without a spec worked example to check against was a
worse bet than naming it and stopping, the same call `org-bacnet` makes
about SegmentACK.

**OPC UA security** — see above; the biggest scoped-out piece.

**Session/Subscription services.** No CreateSession, Activate Session,
Browse, Read/Write service request/response bodies beyond what
`DataValue`/`Variant` already give a caller to build them from, no
MonitoredItem, no PublishRequest/Response. This library gives the
building blocks (built-in types, NodeId, Variant); assembling a specific
service's request/response shape from those blocks is generated-from-
schema territory (the OPC Foundation ships an XML schema and a code
generator for exactly this), not something a small hand-written codec
should freehand service-by-service.

**Calendar conversion for DateTime.** `opcua.builtin/decode-date-time`
returns the raw 100-nanosecond tick count since 1601-01-01T00:00:00Z as a
`{:low :high}` word pair — see that namespace's docstring for why (the
tick count for a present-day timestamp exceeds `2^53`, the largest exact
integer a JavaScript double represents, so converting to/from a calendar
`Date` needs 64-bit-safe arithmetic this library does not attempt).
Combining the tick pair with the well-known FILETIME/Unix epoch offset
(116444736000000000 ticks between 1601 and 1970) to get a calendar date is
left to a caller who has decided how they want to handle that precision
boundary on the ClojureScript side.

**Sockets, TCP connection lifecycle, and MessageChunk reassembly** across
`C` (intermediate) chunks — `opcua.transport` decodes one chunk's header
and hands back its declared body; stitching several `C` chunks plus a
final `F` chunk into one logical message is a stateful transport-layer
concern, the same split `bacnet.apdu` draws around BACnet's own
segmentation.
