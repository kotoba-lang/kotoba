# kotoba-lang/org-ietf-radius

**RADIUS wire codec, portable `.cljc`.** [RFC 2865](https://www.rfc-editor.org/rfc/rfc2865) (Remote Authentication Dial In User Service) and [RFC 2866](https://www.rfc-editor.org/rfc/rfc2866) (RADIUS Accounting): the packet header (Code, Identifier, Length, 16-octet Authenticator), attribute TLVs including Vendor-Specific (type 26), the Response Authenticator and Accounting-Request Authenticator computations, and User-Password hiding/unhiding — all of which need MD5, which is implemented here too (`radius.md5`, RFC 1321).

```clojure
(require '[radius.packet :as packet] '[radius.auth :as auth])

(def request
  {:radius/code :access-request
   :radius/identifier 1
   :radius/authenticator (vec (repeat 16 0)) ; NAS-generated random bytes, in real use
   :radius/attributes [{:radius/type 1 :radius/value (mapv int "bob")}]})

(packet/encode-packet request)  ;=> a vector of ints, the wire bytes

(packet/decode-packet some-bytes)
;=> [:ok {:radius/code :access-request ...}]
;   or [:error :radius/truncated-header] / [:error :radius/bad-length] / ...

(auth/hide-password "secret123" (:radius/authenticator request) "shared-secret")
;=> the User-Password attribute's Value octets
```

## Why there is no dependency on `org-ietf-asn1`

RADIUS is not ASN.1. It is a flat Type-Length-Value format with a fixed
20-octet header — no tags, no BER/DER length forms, no OID subidentifiers.
Its sibling library in this workspace, `org-ietf-snmp`, DOES depend on
`org-ietf-asn1` because SNMP is BER; this one legitimately has nothing to
reuse from it. What this repo's `radius.bytes` namespace has instead is the
much smaller amount of real bit-level work RADIUS actually needs: the
2-octet Length field and the 4-octet Vendor-Id, both `bit-and`/
`unsigned-bit-shift-right`/`bit-shift-left`/`bit-or` like every other
multi-byte wire integer in this workspace's codecs.

## MD5

No shared MD5 library existed in this workspace when this was written
(checked with `kbb --backend sci scripts/repo-search.cljk md5 hash digest`;
`org-nist-sha2` is SHA-2, not MD5). `radius.md5` implements RFC 1321
directly — padding, the four auxiliary functions, the T-table (computed
from RFC 1321 §3.4's own `floor(2^32 × |sin(i)|)` definition rather than
transcribed by hand), and the 64-step compression loop — verified against
RFC 1321 Appendix A.5's full seven-vector test suite in
`test/radius/md5_test.cljk`. **It may be worth extracting into a standalone
`org-ietf-md5` (or similar) repo** if a second consumer shows up; RADIUS is
the only known one today, so it stays here per this repo's own scope.

MD5 is used here **only** because RFC 2865/2866 mandate it for wire
compatibility with 25+ years of deployed RADIUS infrastructure — not as an
endorsement. RADIUS's MD5-based Authenticator/password-hiding scheme is a
well-documented weak point (RFC 2865 §3 says so itself: a passive
eavesdropper with one captured Access-Request and known plaintext can
dictionary-attack the shared secret from the Response Authenticator alone).
Nothing about that weakness is this codec's to fix — it is the wire format.

## What this is not

A wire **codec**: `encode-packet`/`decode-packet`, `encode-attribute`/
`decode-attribute-at`, and the Authenticator/password functions in
`radius.auth`. It is **not**:

- a RADIUS server (NAS) or authentication backend
- a UDP transport, socket, retry/timeout, or duplicate-detection state
  machine — RADIUS runs over UDP and needs all of those in a real
  deployment; none of them live here
- a dictionary of vendor attribute definitions — `radius.attribute`
  understands the Vendor-Specific TLV shape (type 26 → Vendor-Id + nested
  sub-TLVs), not what any particular vendor's attribute numbers mean
- an EAP implementation (RADIUS commonly tunnels EAP for 802.1X, but EAP
  itself is a different, unimplemented, protocol)

No IO, no sockets, no threads, no clock, and — despite implementing the
algorithm — no claim that MD5 is suitable for anything new.

## Errors

`encode-*` builds a value the caller controls and throws (via `ex-info`) on
a domain error — an unrecognized `:radius/code`, a >255-octet attribute, a
>128-octet password, a wrong-length Authenticator.

`decode-*` reads bytes from the network and **never throws**. Every failure
path returns `[:error kw]`: `:radius/truncated-header`, `:radius/bad-length`,
`:radius/truncated-packet`, `:radius/bad-attribute-length`,
`:radius/truncated-attribute`, `:radius/truncated-vendor-attribute`,
`:radius/not-vendor-specific`, `:radius/bad-password-length`. Per RFC 2865
§3, bytes beyond the packet's own `Length` field are padding and are
**not** an error — decoding is deliberately more lenient there than
`org-ietf-asn1`'s DER strictness, because that leniency is what the RFC
actually specifies for this format.
