# ADR-0114 — the K16 direct path names Murakumo, but is not trusted HTTPS yet

Accepted for the bounded native TLS profile on 2026-08-29. This decision does
not claim that a physical K16 has sent the request.

## Context

The native TLS record engine was coupled to one smoke request: SNI
`kotobase.net` and a fixed CID `GET`. The K16 RTL8125 qualification therefore
could not reuse it for `api.murakumo.cloud`, even after a raw TCP transport is
connected. Calling the existing relay path "direct" would be false: the live
Murakumo inventory still labels `gmktec-k16` as `connect=mac-relay`,
`needs-relay=true`.

## Decision

The TLS engine accepts one bounded connection profile before a handshake:

- lower-case DNS SNI, at most 63 bytes;
- an HTTP request copied into a 1 KiB engine-owned buffer;
- a caller-supplied 32-byte ClientHello random;
- a caller-supplied 32-byte X25519 scalar.

The original Kotobase profile remains the byte-compatible default. The new
probe profile is exactly `api.murakumo.cloud` plus `GET /infer/queue`; it is not
a generic URL parser or ambient network capability. Empty keys, invalid host
labels, upper-case hostnames and oversized requests fail before state changes.

The host probe compiles the same freestanding `tls13.c` and AES-GCM engine,
checks the variable-length ClientHello locally, and may then run a live socket
measurement. A live result of `HTTP/1.1 200` proves SNI, key schedule,
CertificateVerify, Finished, encryption and response decryption for that
profile. It does not prove the RTL8125 transport.

## Security boundary and next gate

This engine currently verifies the TLS `CertificateVerify` signature using the
leaf key carried by the same handshake. It does not yet verify a trust chain,
hostname/SAN, validity period or revocation. The committed host probe also uses
deterministic test entropy. Therefore its evidence label is
`trust=transport-only`; it must not carry an account result, Wi-Fi secret or
CACAO credential on a physical machine.

ADR-0115 adds the source/build side of the first item below. None of the
following may be called physically green before its own K16 receipt exists:

1. RTL8125 send/receive integration for DNS and TCP, with the Mac acting only
   as an IP router during qualification rather than an application relay
   (implemented image, physical reboot unverified);
2. secure boot-time entropy and durable device-key custody;
3. chain plus `api.murakumo.cloud` hostname admission;
4. a device-owned CACAO request and a real K16 reboot receipt;
5. only after trusted auth succeeds, the native QR renderer and Wi-Fi-driver
   application path.

The hosted QR, device-key proof, CACAO minting and encrypted Wi-Fi envelope in
ADR-0113 remain real source/authority evidence, but none substitutes for these
physical gates.
