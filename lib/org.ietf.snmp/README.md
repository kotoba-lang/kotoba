# kotoba-lang/org-ietf-snmp

**SNMP v1/v2c message codec, portable `.cljc`.** [RFC 1157](https://www.rfc-editor.org/rfc/rfc1157) (SNMPv1) and [RFC 3416](https://www.rfc-editor.org/rfc/rfc3416) (SNMPv2 protocol operations, community-based per [RFC 1901](https://www.rfc-editor.org/rfc/rfc1901)): the `Message` envelope, all seven PDU shapes (GetRequest / GetNextRequest / GetResponse / SetRequest / GetBulkRequest / Trap / SNMPv2-Trap, plus InformRequest and Report), `VarBind`/`VarBindList`, the SMI application types (`IpAddress`, `Counter32`, `Gauge32`, `TimeTicks`, `Opaque`, `Counter64` — [RFC 2578](https://www.rfc-editor.org/rfc/rfc2578) §7.1.6), the RFC 3416 §3 exception markers (`noSuchObject`/`noSuchInstance`/`endOfMibView`), and OBJECT IDENTIFIER encode/decode (reused from `org-ietf-asn1`, not reimplemented).

```clojure
(require '[snmp.message :as msg])

(msg/encode-message
 {:snmp/version :v1
  :snmp/community "public"
  :snmp/pdu {:snmp/pdu-type :get-request
             :snmp/request-id 1
             :snmp/varbinds [{:snmp/oid "1.3.6.1.2.1.1.1.0"
                               :snmp/value {:snmp/type :null}}]}})
;=> #(byte array), 40 bytes — see test/snmp/message_test.cljk for the hex

(msg/decode-message some-bytes)
;=> [:ok {:snmp/version :v1 :snmp/community "public" :snmp/pdu {...}}]
;   or [:error :snmp/truncated-message] / [:error :snmp/unknown-pdu-type] / ...
```

## SNMP is BER on the wire — and this library does not implement BER

Every tag, length, and OID subidentifier in an SNMP message is X.690 BER
([RFC 1157 §4](https://www.rfc-editor.org/rfc/rfc1157), [RFC 3416
§2](https://www.rfc-editor.org/rfc/rfc3416)). `org-ietf-asn1` already
implements that codec (tag classes including APPLICATION and CONTEXT,
base-128 OID subidentifiers, definite-length forms) as a workspace-local git
dependency (see `deps.edn`), so this repo does not write a second one. What
lives here is SNMP-specific: the five/six SMI application types (which are
ordinary `asn1.core` primitives re-tagged via `asn1/retag`), the three
CONTEXT-tagged exception markers (a re-tagged NULL), the PDU CHOICE (a
re-tagged SEQUENCE per PDU type), and the `Message` envelope.

**`org-ietf-asn1` enforces DER, which is stricter than the BER SNMP nominally
allows** — no indefinite length, no non-minimal length or INTEGER forms.
This is not a problem in practice: every SNMP encoder in real use already
emits definite-length, minimal encodings (RFC 1157 §4's syntax and every
deployed agent/manager both behave this way; the indefinite-length and
non-minimal forms DER forbids exist for BER's *streaming* use case, which no
SNMP PDU needs — it is built in memory, whole, before being sent in one UDP
datagram). Nothing in this library had to work around asn1.core's
strictness; every construction here already produces the minimal form.

## What this is not

A wire **codec**: `encode-message`/`decode-message`, `encode-pdu`/
`decode-pdu`, and the varbind/value layer between them. It is **not**:

- an SNMP agent, manager, or MIB browser
- a UDP transport, socket, or retry/timeout state machine
- an SNMPv3 implementation (no USM authentication/privacy, no `msgVersion`
  header, no engine discovery — out of scope, v1/v2c only)
- a MIB parser or a registry of well-known OID names

No IO, no sockets, no threads, no clock.

## Errors

`encode-*` builds a value the caller controls and throws (via
`asn1/fail!`/`ex-info`) on a domain error — an out-of-range counter, an
unrecognized `:snmp/pdu-type`.

`decode-*` reads bytes from the network and **never throws**. Every failure
path returns `[:error kw]` with a specific keyword — `:snmp/truncated-message`,
`:snmp/truncated-varbind`, `:snmp/unknown-pdu-type`, `:snmp/unknown-version`,
`:snmp/negative-counter`, `:snmp/bad-ip-address`, `:snmp/bad-oid`,
`:snmp/malformed-value` — never a generic exception, and never a silent
best-effort partial parse.

## MD5 / password hiding

Not here — SNMPv1/v2c community strings are sent in the clear (that is the
well-documented security weakness that motivated SNMPv3's USM). See
`org-ietf-radius` for the sibling library that does need MD5, because RADIUS
does encrypt one field this way.
