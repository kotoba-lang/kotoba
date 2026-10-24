# kotoba-lang/org-ietf-netconf

**NETCONF message-layer and transport-framing codec — RFC 6241 (NETCONF
Protocol) and RFC 6242 (NETCONF over SSH) — in portable, dependency-light
`.cljc`.**

Framing: this implements **RFC 6242 §4.2's chunked framing**, the
**current** wire framing (negotiated when both peers' `<hello>` advertise
`urn:ietf:params:netconf:base:1.1`), *not* the older `]]>]]>`
end-of-message marker framing from §4.3 (originally RFC 4742, kept in
6242 only for a peer that advertises `:base:1.0` alone). §4.3 exists for
backwards compatibility with an assumption RFC 6242 itself says was
wrong: *"The previous version of this document defined the character
sequence `]]>]]>` as a message separator, under the assumption that it
could not be found in well-formed XML documents. However, this
assumption is not correct. It can legally appear in XML attributes,
comments, and processing instructions."* Chunked framing doesn't have
that hole — it delimits by byte *count*, not by scanning content for a
marker — so it's the framing worth implementing carefully. §4.3's
`]]>]]>` marker is mentioned here only for context; it is not
implemented (correctly reproducing a scheme the RFC itself deprecates as
unsafe isn't the point of this repo).

## What's here

```clojure
(require '[netconf.framing :as framing]
         '[netconf.bytes :as b]
         '[netconf.message :as msg]
         '[netconf.operations :as op])

;; RFC 6241 §7.7 <get> wrapped in an <rpc>, RFC 6242 §4.2 chunk-framed:
(def wire (framing/encode-chunks (b/utf8-encode (op/get-op "101"))))
;=> a byte-seq: \n#28\n<rpc message-id="101" ...><get/></rpc>\n##\n

(framing/decode-chunks wire)
;=> [:ok <those same payload bytes>]
```

| namespace | RFC | |
|---|---|---|
| `netconf.framing` | 6242 §4.2 | `encode-chunks`, and an incremental `decoder`/`feed` state machine plus a one-shot `decode-chunks` |
| `netconf.message` | 6241 §4, §8.1 | `<hello>`, `<rpc>`, `<rpc-reply>`, `<rpc-error>` — the fixed message-layer envelope |
| `netconf.operations` | 6241 §7 | all nine standard operations: `get-config`, `edit-config`, `copy-config`, `delete-config`, `lock`, `unlock`, `get-op`, `close-session`, `kill-session` |
| `netconf.bytes` | — | a small hand-rolled UTF-8 codec bridging XML strings and the byte-seqs `netconf.framing` operates on |

XML itself — hiccup `[:tag {"attr" "val"} child...]` ⇄ XML text — is
`kotoba-lang/xml`, taken as a real `deps.edn` git dependency, not
reimplemented here (see "Reuse", below).

## RFC 6242 §4.2: chunked framing

```
Chunked-Message = 1*chunk
                   end-of-chunks

chunk           = LF HASH chunk-size LF
                   chunk-data
chunk-size      = 1*DIGIT1 0*DIGIT
chunk-data      = 1*OCTET

end-of-chunks   = LF HASH HASH LF

DIGIT1          = %x31-39
DIGIT           = %x30-39
HASH            = %x23
LF              = %x0A
OCTET           = %x00-FF
```

*"The chunk-size field is a string of decimal digits indicating the
number of octets in chunk-data. Leading zeros are prohibited, and the
maximum allowed chunk-size value is 4294967295."* — §4.2 verbatim; the
"no leading zero" rule falls straight out of the ABNF (`chunk-size`
starts with `DIGIT1`, `1`-`9`, never `0`), and `max-chunk-size` in
`netconf.framing` is that literal number, not derived or guessed.

**Chunking is pure byte-stream segmentation and knows nothing about
XML.** §4.2's own worked example splits `message-id="102"` across a
chunk boundary and the namespace declaration across another — neither
split lines up with any XML token. `netconf.framing/feed` is written to
match: `decode-chunks`/`feed` count declared chunk-data length and
never scan chunk-data content for `\n`/`#` (a test constructs chunk-data
that *contains* bytes shaped like a chunk header, to prove this), and
the decoder is a byte-at-a-time state machine so a message split across
**any** boundary — including mid-digit of a chunk-size, mid-chunk-data,
or mid-`##` end marker — still reassembles correctly. `framing_test.cljc`
exhaustively feeds the RFC's own 119-byte worked example at every one of
its 118 internal split points (not a sample), plus one byte at a time,
and checks it decodes to the same payload every time.

## Reuse: `kotoba-lang/xml`

NETCONF's message layer is XML. A real, already-published,
dependency-free hiccup⇄XML codec exists in this workspace at
`kotoba-lang/xml` — writing a second one for the small, fixed-shape XML
this library builds (`<rpc>`, `<hello>`, `<rpc-reply>`, `<rpc-error>`,
the nine operation wrappers) would be exactly the kind of redundant
protocol-shaped-but-not-real work this repo exists to avoid. `deps.edn`
takes it as a real git dependency (same pattern `org-ietf-snmp` uses for
`org-ietf-asn1`), pinned to a commit SHA.

`netconf.message` uses `xml.core/compact` (no inserted whitespace)
rather than `xml.core/xml` (indented) throughout, for the same reason
`xml.core`'s own README gives for its EPP `clTRID` example: every
element this library builds either wraps other elements or wraps a
single *value* that gets compared, not displayed — a capability URI, a
message-id, a session-id, an error-tag. RFC 6241 §8.1's own `<hello>`
example happens to line-break `<capability>` content onto its own
indented line; `xml.core/compact` avoids reproducing that as literal
whitespace inside the value.

## What this is not

- **A codec, not a NETCONF agent/server/client.** No sockets, no SSH
  transport, no session state machine, no capability negotiation logic
  beyond modeling `<hello>`'s shape. You bring the transport; this turns
  data into wire bytes and back.
- **No datastore.** Nothing here stores or applies configuration.
  `edit-config`/`copy-config`/`get-config` build and parse the *request
  and reply shapes* RFC 6241 §7 specifies; what a real device does with
  the `<config>`/`<filter>` content is out of scope by construction.
- **No YANG (RFC 7950).** NETCONF's operation-specific payloads
  (`<filter>`, `<config>`, `<data>`) are schema-defined per device via
  YANG modules — a distinct, much larger spec. This codec treats that
  content as **opaque, caller-supplied hiccup**: you build it, this
  library carries it inside the right wrapper element and never
  interprets it. No YANG module parsing, no `container`/`leaf`/`list`
  typing, no datastore validation against a schema is implemented, not
  even partially — that was explicit in this repo's scope from the
  start, not a corner cut under time pressure. The one YANG-adjacent
  thing this codec *does* handle is capability URIs like
  `urn:ietf:params:netconf:capability:yang-library:1.1` — but only as
  opaque strings in the `<hello>` capability list, the same as every
  other capability URI; it doesn't parse or validate them.
- **No capability-gated behavior tracking.** RFC 6241 gates some
  parameters on the peer having advertised a capability (`test-option`
  needs `:validate:1.1`, `<url>` elements need `:url`, etc.). This codec
  can *represent* those shapes but doesn't track session capability
  state to enforce the gating — it's a stateless codec, not a session.

## What's scoped narrower than it could be

- **`<rpc-error>`'s `error-info` mandatory content (RFC 6241 Appendix A)
  is caller-built, not generated.** Several error-tags mandate specific
  `error-info` children (`lock-denied` → `<session-id>`,
  `missing-attribute` → `<bad-attribute>`/`<bad-element>`, etc.).
  `netconf.message` models the full Appendix A error-tag enumeration (all
  20 tags) and validates against it, but leaves building the
  tag-specific `error-info` shape to the caller as opaque hiccup rather
  than special-casing all 20 tags' mandatory content — that would be a
  second, smaller YANG-shaped modeling problem nested inside this one.
- **`copy-config`/`delete-config`'s `<url>` element** is representable
  (pass an already-built `[:url "..."]` hiccup vector as `source`) but
  this codec doesn't validate it's a well-formed URL — same "opaque,
  caller-supplied" treatment as `<filter>`/`<config>` content.

## Verify

```sh
kbb -M:test
```

## License

Apache-2.0, verbatim from `kotoba-lang/org-modbus`.
