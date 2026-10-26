# ADR-0087 — Guest TLS 1.3 CertificateVerify (ECDSA P-256); hashed-only is leftover

Date: 2026-08-23

## Status

Accepted for a **discriminating slice** of root
`adr-2608221625-aiueos-chromeos-cloud-desktop` P2 leftover
`:cert-verify-hashed-only`. **This gate is green only when QEMU serial
contains `AIUEOS_CERTVERIFY_PROBE result=ok scheme=ecdsa_secp256r1_sha256`.**
This file records the attempt. The receipt from
`kbb -M:bare-metal cert-verify` is the measurement.

`kbb -M:bare-metal cloud` stays green on HTTP+CID **without** requiring
this line. Host OpenSSL probe does not count.

**Measured 2026-08-23** on this Mac (`kbb -M:bare-metal cert-verify`
EXIT=0 leftover `[]`, and `kbb -M:bare-metal cloud` EXIT=0 leftover
`[]` on the same firmware):

```
AIUEOS_ECDSA_P256_OK rfc6979-sample s+1-refused
AIUEOS_CERTVERIFY_PROBE result=ok scheme=ecdsa_secp256r1_sha256
AIUEOS_HTTP_PROBE result=ok cid=bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku
AIUEOS_BARE_METAL_CERTVERIFY green
```

The object uses Jacobian coordinates and NIST P-256 Solinas reduction
for the field. Affine verify exhausted the imm32 fuel ceiling (vector
6). Word reduction greened CertVerify but left HTTP absent (peer idle
during the second scalar mul). Solinas brought both gates green in one
serial (~74s QEMU).

- **Chain to a trust anchor is still leftover.** This slice verifies
  CertificateVerify against the leaf P-256 SPKI. It does not walk the
  chain or pin a root. Hosted `tls.cert/verify-chain` is pin-only too.
- **RSA-PSS is not implemented.** Live `kotobase.net` serves ECDSA P-256
  (`0x0403`). A peer that offers another scheme fails closed.
- **P5 a real machine is UNVERIFIED.** This Mac is the QEMU host. QEMU ≠ P5.
- **CACAO write, guest-side IME, and a guest-side WM remain.** The Chrome OS-shaped
  desktop goal is **not complete**.

## Context

ADR-0082 greened guest TLS 1.3 Finished + HTTPS GET of the empty raw CID.
Certificate and CertificateVerify were hashed into the transcript, not
verified. AES-GCM stays C (mechanism). Signature admission is Kotoba
(ADR-0015). RSA-2048 PKCS#1 is the wrong scheme for TLS 1.3 CertVerify.
No P-256 ECDSA kernel object existed on main.

## Decision

1. **Kotoba object** `os/aiueos/kotoba/ecdsa-p256.kotoba` exports
   `aiueos-ecdsa-p256-sha256-verify` arity 5. RFC 6979 A.2.5 SHA-256
   `"sample"` must admit; `s+1` must refuse. Workspace 2048 bytes.
2. **kotoba-native** `e570d78` lists the export and replenishes the
   imm32 fuel ceiling. x86 kernel images already use the 16-page data
   offset on native main. The committed `.o` was compiled with Amu
   `9cf3a0a` plus that layout/fuel on the pin that still emits this
   object's bytes. Do not wholesale-advance Amu.
3. **C parse** (`tls13.c`): leaf SPKI P-256 uncompressed point; CertVerify
   scheme must be `0x0403`; transcript-hash **before** adding CertificateVerify
   (RFC 8446 4.4.3); content = 64×`0x20` + `"TLS 1.3, server CertificateVerify"`
   + `0x00` + transcript-hash. Finished requires `certverify_ok`.
4. **Gate:** `kbb -M:bare-metal cert-verify`. HTTP+CID without the
   CertVerify serial line is leftover `:cert-verify-hashed-only`.

## P5 — still UNVERIFIED

No physical aiueos boot was performed or claimed. This operator Mac is
the QEMU host. Attached USB is not an aiueos machine. See ADR-0084.

## Consequences

README P2 can say CertificateVerify is proven on this Mac when
`cert-verify` is green, and must still say chain-to-anchor leftover, P5
UNVERIFIED, and the Chrome OS-shaped desktop **goal is not complete**.
ADR-0082 remains the HTTP+CID discriminator. This ADR is the CertVerify
discriminator.
