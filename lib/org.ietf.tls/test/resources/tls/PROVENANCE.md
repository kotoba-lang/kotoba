# Where these fixtures came from, and when

Captured or generated **2026-08-22** for `tls.cert`. Two of them have expiry
dates, and one of those has already passed — see "Certificates that expire"
below before you conclude the suite is broken.

Hand-built bytes make a parser agree with the person who built them. Every
positive assertion here is against octets some other implementation produced:
OpenSSL 3.6.3, Google Trust Services, or the RFC 8448 authors.

## RFC 8448 §3, "Simple 1-RTT Handshake"

`rfc8448-simple-1rtt-{client-hello,server-hello,encrypted-extensions,certificate,certificate-verify}.hex`

Extracted 2026-08-22 from <https://www.rfc-editor.org/rfc/rfc8448.txt>
(RFC 8448, *Example Handshake Traces for TLS 1.3*, January 2019) — the octet
dumps at the lines labelled `ClientHello (196 octets)`, `ServerHello (90
octets)`, `EncryptedExtensions (40 octets)`, `Certificate (445 octets)` and
`CertificateVerify (136 octets)`. Each file is the complete handshake message
including its 4-octet header, as lowercase hex with no separators, and the
octet count matches the label.

These are what makes `certificate-verify-content` a claim about TLS rather than
about this repository. `SHA-256(ClientHello ‖ ServerHello ‖ EncryptedExtensions
‖ Certificate)` is `764d6632b3c35c3f3205e3499ac3edbaabb88295fba751461d3678e2e5ea0687`;
the CertificateVerify carries `rsa_pss_rsae_sha256` (`0x0804`) and a 128-octet
signature; and that signature verifies against the content this library builds.
An implementation nobody here wrote made those bytes in 2019.

Reproduced outside Clojure before the test existed:

```
openssl pkeyutl -verify -pubin -inkey <leaf pubkey> -sigfile <sig> \
  -in <sha256 of the content> \
  -pkeyopt rsa_padding_mode:pss -pkeyopt rsa_pss_saltlen:32 -pkeyopt digest:sha256
# => Signature Verified Successfully
```

## kotobase.net, live

`kotobase-net-{leaf,intermediate,root}.pem`, `kotobase-net-{leaf,intermediate}.der`

```
openssl s_client -connect kotobase.net:443 -servername kotobase.net -showcerts </dev/null
```

run 2026-08-22 10:36 JST. Leaf `CN=kotobase.net`, issued by
`C=US, O=Google Trust Services, CN=WE1`, serial `0324FEB527DF14D00EC703D21B229FD0`,
P-256, SAN `kotobase.net, ipni.kotobase.net, *.ipni.kotobase.net`.

Its SubjectPublicKeyInfo digest is
`50602ad366823fcf5274a7c917baa4fd24b9de4fd15635ff501177c83d05473e` —

```
openssl x509 -in kotobase-net-leaf.pem -noout -pubkey \
  | openssl pkey -pubin -outform DER | openssl dgst -sha256
```

— which is the value the live gate has been pinning this host at, and the
reason this fixture is here: it is the cross-check that `tls.cert`'s pin format
is the same format as `aiueos.provider.cloud/spki-sha256-hex`'s.

## Generated, keys discarded

`ed25519-leaf`, `rsa2048-leaf`, `p256-expired-leaf`, `no-san-leaf`, `p384-leaf`,
`critical-ext-leaf` (`.pem` and `.der`), by `openssl req -x509` on 2026-08-22,
subjects under `.test.invalid` (RFC 6761 — a name that can never resolve).

**Validity windows are stated explicitly, not taken from the generation clock.**
The first cut used `-days 7300`, so `notBefore` was the minute they were made —
and `authenticate-peer` tests that pass `:tls/now 2026-08-22T00:00:00Z` refused
them as `:certificate-not-yet-valid`, correctly, because midnight that morning
was before they existed. A fixture whose validity depends on when someone ran
`openssl` is a fixture that tests a different thing every time.

```
BC="basicConstraints=critical,CA:FALSE"
openssl req -x509 -nodes -not_before 20260101000000Z -not_after 20460101000000Z \
  -newkey ed25519 -subj "/CN=ed25519.test.invalid" -addext "$BC" \
  -addext "subjectAltName=DNS:ed25519.test.invalid"      -out ed25519-leaf.pem
  … -newkey rsa:2048                                     /CN=rsa.test.invalid
  … -newkey ec -pkeyopt ec_paramgen_curve:prime256v1     /CN=no-san.test.invalid
        (no subjectAltName addext: the absent SAN is the point)
  … -newkey ec -pkeyopt ec_paramgen_curve:secp384r1      /CN=p384.test.invalid
  … -newkey ec -pkeyopt ec_paramgen_curve:prime256v1     /CN=critical.test.invalid
        -addext "1.3.6.1.4.1.99999.1=critical,ASN1:UTF8String:unrecognised"
  … -not_before 20200101000000Z -not_after 20200401000000Z
    -newkey ec -pkeyopt ec_paramgen_curve:prime256v1     /CN=expired.test.invalid
```

`basicConstraints=critical,CA:FALSE` is not decoration either: OpenSSL 3's
`req -x509` writes **CA:TRUE** by default, so every one of these was a CA
certificate until it was said otherwise — and `authenticate-peer` refuses a CA
as an end entity (`:leaf-is-ca`), which is what caught it.

`critical-ext-leaf` carries a critical extension under a private-enterprise arc
nobody implements. `x509.core/usable?` refuses it, and `authenticate-peer`
reports that as `:leaf-unusable` — the one refusal here that is not this
library's own judgement.

**The private keys were not kept.** Nothing in the suite needs to sign, and a
checked-in private key is a finding in someone's scanner. The one signature
that had to be made was made once, at generation time, and checked in:

`ed25519-certificate-verify.sig.hex` — 64 octets, `openssl pkeyutl -sign -rawin`
over the CertificateVerify content for the transcript hash in
`certificate-verify-transcript-sha256.hex`
(`SHA-256("org-ietf-tls cert_test transcript, 2026-08-22")`), built by shell and
OpenSSL rather than by this library:

```
{ printf '\x20%.0s' $(seq 64); printf 'TLS 1.3, server CertificateVerify';
  printf '\x00'; cat transcript.bin; } > content.bin      # 130 octets
openssl pkeyutl -sign -inkey <ed25519 key> -rawin -in content.bin -out sig
```

If `certificate-verify-content` ever emits a different byte, this signature
stops verifying. That is the entire job of this fixture. Regenerating it means
generating a new key and a new leaf, per the commands above.

## Certificates that expire

| fixture | notAfter | what happens |
|---|---|---|
| `kotobase-net-leaf` | **2026-11-18** | the live host will have rotated; `authenticate-peer` tests pin `:tls/now` to `2026-08-22T00:00:00Z`, so they keep passing — but the SPKI digest will stop matching the live gate's, and re-capturing is the fix |
| `kotobase-net-intermediate` | 2029-02-20 | — |
| RFC 8448 leaf | **2016-07-30 → 2026-07-30, already expired** | deliberate: nothing asserts it is currently valid. It is a signature fixture, not a validity one |
| `p256-expired-leaf` | 2020-04-01, already expired | deliberate: it is the `:certificate-expired` fixture |
| generated leaves | 2046-01-01 | — |

Nothing in the suite reads a clock. Every validity assertion passes `:tls/now`
explicitly, which is why an expiring fixture makes a test *stale* rather than
*red* — and why this table is here, because stale is the harder one to notice.

## `othername-only-leaf`

`othername-only-leaf` (`.pem` and `.der`), by `openssl req -x509` on
2026-08-22, OpenSSL 3.6.3:

```
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -sha256 \
  -days 3650 -nodes -keyout othername.key -out othername-only-leaf.pem \
  -subj "/CN=othername-only.test.invalid" \
  -addext "subjectAltName=email:nobody@othername-only.test.invalid,URI:https://othername-only.test.invalid/" \
  -addext "basicConstraints=critical,CA:FALSE"
```

It exists for one reason: it is the only fixture whose `subjectAltName` is
**present and contains no `dNSName`**, so `x509.core/dns-names` answers `[]`
rather than nil. Before it, the suite fed the reader only nil (`no-san-leaf`)
and non-empty (`kotobase-net-leaf`) — so a reader that collapsed `nil` into
`[]`, or `[]` into nil, would have passed. Those are different facts about a
certificate and they get different refusals (`:no-subject-alt-name` versus
`:server-name-mismatch` with an empty `:presented`); `cert_test` asserts both.

The private key is not kept. Nothing signs with this certificate — it is
parsed, and its SubjectPublicKeyInfo is pinned in one test.
