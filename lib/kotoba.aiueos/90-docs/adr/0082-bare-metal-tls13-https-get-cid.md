# ADR-0082 — Guest TLS 1.3 handshake and HTTPS GET of a raw CID; P2 is green only on that serial line

Date: 2026-08-22

## Status

Accepted for a **discriminating slice** of root
`adr-2608221625-aiueos-chromeos-cloud-desktop` **P2**. **P2 is green only when
QEMU serial contains `AIUEOS_HTTP_PROBE result=ok` with `cid=`.** This file
records the attempt; the receipt from `kbb -M:bare-metal cloud` is the
measurement.

**Measured 2026-08-22** (`kbb -M:bare-metal cloud`, EXIT=0, leftover `[]`):

```
AIUEOS_DHCP_CONSUMED src=10.0.2.15 dns=10.0.2.3
AIUEOS_DNS_PROBE result=ok name=kotobase.net a=104.21.37.83
AIUEOS_TCP_CLOUD_PROBE result=ok dst=104.21.37.83 port=443
AIUEOS_TLS_PROBE result=ok
AIUEOS_HTTP_PROBE result=ok cid=bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku
AIUEOS_BARE_METAL_P2 green leftover=[]
```

The A is Cloudflare anycast; a later boot may print a different address. Hosted
`cloud-live` / session smoke / a host curl still do not green this gate.

## Context

ADR-0081 got the UEFI guest as far as DHCP consumed, DNS A for `kotobase.net`,
TCP :443, and a TLS record (type 22) after a compiled ClientHello with a dummy
x25519 share. Leftover was `:tls-handshake-incomplete` and `:http-absent`.
`kbb -M:bare-metal cloud` exited 1. AES-GCM is not a kotoba-native
kernel-object, so a decision-free C record layer is the only way to finish the
handshake on this target (ADR-0015: C is mechanism). X25519, SHA-256, and
digest_equal were already linked.

Host probe (not guest success): kotobase accepts `TLS_AES_128_GCM_SHA256` and
serves `GET /ipfs/bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku`
as HTTP/1.1 200 with an empty body whose SHA-256 is the empty digest.

## Decision

1. **Record layer in C** (`tls_aes_gcm.c`): AES-128-GCM, NIST vectors at boot.
   No libc. Limits are compile-time. Admission of a CID is not here.
2. **Key schedule in C calling Kotoba** (`tls13.c`): HMAC-SHA256 / HKDF via
   `kotoba_aiueos_sha256`, ECDHE via `kotoba_aiueos_x25519`. RFC 4231 and
   RFC 5869 extract vectors at boot. Cipher 0x1301 only. CertificateVerify
   is ADR-0087 (ECDSA P-256 against the leaf SPKI). The chain to a trust
   anchor is still not walked (hosted profile is pin-only too).
3. **TCP window 1792** on the cloud socket (`1792+54 < NET_FRAME_MAX 2048`) so
   kotobase's HTTPS record (~1298 bytes) fits one virtqueue slot. The HTTP
   pump admits ACK equal to post-GET `our_next` **or** the ClientHello-only
   sequence, because NewSessionTicket can still ACK only ClientHello. A
   handshake-key retransmit must not abort the HTTP wait.
4. **HTTP GET** of the empty raw CID as TLS 1.3 application data. Body SHA-256
   is admitted with `kotoba_aiueos_digest_equal` against the empty digest.
   Serial prints the compiled CID string only after that compare succeeds.
5. **Leftover names**: handshake without HTTP is `:http-absent` only. A TLS
   record without Finished stays `:tls-handshake-incomplete`. Host fetch is
   still `:host-fetch-does-not-count`. No D1.

Not executable, and stated here rather than at the end:

- **`kbb -M:cloud-live check` does not green P2.**
- **`kbb -M:session smoke` does not green P2.**
- **A host curl is `:host-fetch-does-not-count`.**
- **P4 itonami, P5 a real machine, and WM/IME/virtio-gpu 2D remain.** The
  Chrome OS-shaped desktop goal is not complete.

## Consequences

The UEFI guest completed TLS 1.3 (cipher 0x1301) and HTTPS GET of the empty
raw CID, then verified the body SHA-256 with `kotoba_aiueos_digest_equal`.
That is P2 green for the QEMU profile. Rows 4–5 of ADR-0041 for bare metal
move with that serial. CertificateVerify is ADR-0087; chain-to-anchor is
still leftover. P4 itonami, P5 a real machine, and WM/IME/virtio-gpu 2D
remain. The Chrome OS-shaped desktop goal is not complete.
