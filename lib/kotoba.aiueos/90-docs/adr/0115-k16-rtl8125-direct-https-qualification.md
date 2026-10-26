# ADR-0115 — K16 direct HTTPS starts as a secret-free transport gate

Accepted for the diskless physical qualification image on 2026-08-29. Source,
build and QEMU negative-path evidence are green; physical K16 execution is not
claimed until a new reboot receipt is observed.

## Context

ADR-0114 made the native TLS engine able to name `api.murakumo.cloud`, but the
physical RTL8125 path still stopped at ARP or handed application traffic to a
Mac relay. Moving the existing account or CACAO flow onto that path would be
unsafe because the engine verifies CertificateVerify with the leaf key from
the same handshake but does not yet admit a trusted chain or hostname/SAN.

## Decision

Add one read-only qualification profile that reuses the admitted RTL8125
handoff and static K16 qualification link:

- K16 is `10.77.0.10`; a passwordless Mac user service on `10.77.0.1`
  answers the bounded DNS query on UDP `1053` and forwards opaque TLS bytes
  from TCP `8443` to `api.murakumo.cloud:443`;
- the K16 builds and admits DNS, TCP, TLS 1.3 and HTTP frames itself;
- SNI is `api.murakumo.cloud` and the only request is public
  `GET /infer/queue`;
- the EFI and Mac forwarder contain no account token, Wi-Fi passphrase or
  device CACAO, and the Mac does not terminate the K16 TLS session;
- all DMA waits and receive attempts are bounded, and the NVRAM result keeps a
  distinct error stage;
- the image remains read-only for the USB and internal SSD.

Ports `1053` and `8443` are deliberate: binding `53` or `443`, installing a
packet-filter redirect, or enabling host NAT requires administrator authority
on macOS and would reintroduce an unlock prompt after rule loss or reboot. The
high-port path starts as the logged-in user and keeps TLS end-to-end between
AIUEOS and Murakumo. It is therefore a user-space L4 forwarding dependency,
not evidence of a standalone routed Internet connection.

The build label is `trust=transport-only`. An HTTP 200 proves that the native
K16 network/TLS implementation reached and decrypted a Murakumo response. It
does not yet authorize the endpoint or authenticate the device.

## Qualification and promotion rule

The committed QEMU smoke proves a machine without RTL8125 returns the bounded
8201 result; it cannot prove physical traffic. The first promotion therefore
requires a K16 reboot with the new EFI and an observed 8150 receipt. That may
change only `physical-state` from unverified to transport-proved.

Secrets may be enabled only after separate physical evidence for:

1. secure entropy and durable device-key custody;
2. X.509 trust-chain, validity and `api.murakumo.cloud` hostname/SAN admission;
3. device-owned Ed25519 signing and a short-lived CACAO;
4. native QR rendering and the encrypted onboarding poll;
5. native Wi-Fi driver association and reboot recovery.

Until all five gates are green, hosted QR/CACAO and encrypted Wi-Fi envelope
evidence remains separate from the physical K16 direct transport.
