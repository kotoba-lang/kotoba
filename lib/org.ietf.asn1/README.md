# kotoba-lang/org-ietf-asn1

**[X.690](https://www.itu.int/rec/T-REC-X.690) DER, portable `.cljc`.** The
encoding layer under every signed structure in this workspace — CMS SignedData,
X.509 certificates, RFC 3161 timestamp tokens, RFC 4998 evidence records.

```clojure
(require '[asn1.core :as asn1] '[asn1.oid :as oid])

(asn1/decode (asn1/unhex "300d06092a864886f70d01010b0500"))
;=> {:asn1/type :sequence :asn1/elements [{:asn1/type :oid …} {:asn1/type :null …}] …}

(oid/describe (asn1/oid-value (asn1/path that 0)))
;=> "sha256-with-rsa (1.2.840.113549.1.1.11)"

(asn1/der-round-trips? some-der)   ;=> true, or it threw on the way in
```

## DER, not BER — and that is a security property

Everything this serves is **signed**, and a signature is over bytes. A parser
that accepts a value it cannot re-encode identically will report a valid
signature over something the sender did not sign. So the BER forms DER forbids
are refused:

| refused | why |
|---|---|
| indefinite length | the element's end is not in the bytes |
| non-minimal long-form length | `81 05` and `05` are the same length, different hash |
| non-minimal `INTEGER` | two spellings of one number |
| constructed `OCTET STRING` / `BIT STRING` | the same octets, many encodings |
| trailing bytes | what was parsed is not what arrived |
| `BOOLEAN` other than `00`/`FF` | ditto |

`decode` either returns something whose `encode` reproduces the input exactly,
or throws. Every fixture in the suite is held to `der-round-trips?`.

## Every element keeps its own bytes

`:asn1/der` is that element's complete TLV, `:asn1/content` its content octets.
Not a convenience — CMS hashes the DER of `signedAttrs` **re-tagged from
`[0] IMPLICIT` to `SET`** (`asn1/retag`), and PAdES needs byte offsets inside a
document it must not otherwise touch. Recomputing those means re-encoding, and
re-encoding is what must stay out of the trust path.

## OIDs are named, because a typo is silent

`1.2.840.113549.1.1.11` and `…1.1.5` are `sha256WithRSA` and `sha1WithRSA`.
Compare against the wrong one and you either refuse every valid signature or
honour a digest you meant to retire. `asn1.oid/dotted` throws on an unknown
name, so a mistyped keyword is an error rather than a `nil` that matches
nothing.

## Bytes

Accepts a `byte[]`, a `Uint8Array`, or a seq of 0–255 ints. Internally a vector
of unsigned ints, so both platforms behave identically. `encode` returns
platform bytes; `encode-ints` returns the vector.

## What is not here

No keys, no clock, no network. Signature verification lives in
`kotoba-lang/org-ietf-cms` and takes an injected verify function — the same
discipline `org-w3-vc-data-integrity` uses for `:resolve-key`. Time values parse
to ISO **strings**, never to instants: `UTCTime`'s two-digit year needs RFC
5280's 2049 window, and a library with no clock should not hand back something
that looks computed.

## Test

```bash
kbb -M:test
kbb -M:lint
```

Apache-2.0.
