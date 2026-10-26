# ADR-0081 — The guest consumes its DHCP lease and probes DNS / TCP:443 / a TLS record; that is not P2 green

Date: 2026-08-22

## Status

Accepted for a **discriminating slice** of root
`adr-2608221625-aiueos-chromeos-cloud-desktop` **P2**. **P2 is not green.**

`kbb -M:bare-metal cloud` boots the existing UEFI + `KERNEL.ELF` QEMU path
(`AIUEOS_TEST_NET=1 ./os/aiueos/scripts/smoke-qemu-uefi.sh`, no new `.sh`). The
guest:

1. obtains a DHCPv4 lease (ADR-0076) and **sends from that address**
   (`AIUEOS_DHCP_CONSUMED src=10.0.2.15`);
2. issues one compiled QNAME query for `kotobase.net`;
3. if an A arrives, opens TCP to that address port 443;
4. piggybacks a TLS 1.3 ClientHello on the handshake ACK and looks for a
   handshake (0x16) or alert (0x15) record.

It does **not** complete TLS, does **not** HTTP GET `https://kotobase.net`, and
does **not** verify a CID. Exit 0 is reserved for that guest HTTP+CID line.
Measured on this Mac's QEMU slirp: DNS A, TCP :443, TLS record type 22
(`AIUEOS_TLS_PROBE result=record type=22`). This landing exits 1 with leftover
`:tls-handshake-incomplete` and `:http-absent`.

Not executable, and stated here rather than at the end:

- **`kbb -M:cloud-live check` does not green P2.** That is the hosted JVM
  profile (ADR-0073 / ADR-0077).
- **`kbb -M:session smoke` does not green P2.** That is the session process
  on the Mac host (ADR-0078).
- **A host curl / `java.net.http` GET is `:host-fetch-does-not-count`.** Tests
  name that red; this namespace does not open a socket to kotobase.
- **DHCP that never applies a lease is still red.** ARP/ICMP/guestfwd-TCP keep
  using compiled-in `10.0.2.15` so the four-boot DHCP tamper gate stays a
  demonstration. DNS and cloud-TCP send from `aiueos_dhcp_address()`.
- **This is not a DNS stub resolver, not `org-ietf-tls` in ring-0, not HTTP.**
  kotoba-native has no DNS/TLS/HTTP/AES-GCM kernel-object entry. QNAME, A
  admission, and ClientHello bytes sit at constant offsets the way TCP headers
  already did. `kotoba-lang/http` and `org-ietf-tls` remain the hosted
  libraries; linking them into the kernel is a kotoba-native change this pin
  does not have.
- **No D1 as premise.** The target is kotobase content-addressed GET.
- **P4 itonami, P5 a real machine, and full WM/IME/virtio-gpu 2D remain.** The
  Chrome OS-shaped desktop goal is not complete.

## Context

ADR-0041 row 1 closed for bare metal (ADR-0076) with the lease recorded and
nothing consuming it. Rows 2–5 for that profile were untouched: no resolver, no
TCP stream off the SLIRP guestfwd peer, no TLS, no HTTP. Hosted TLS/HTTP
(ADR-0077) proved those libraries on JDK sockets, which this profile does not
have.

`kotoba-lang/org-ietf-dns` is an authoritative server, not a stub client.
`org-ietf-tls` and `kotoba-lang/http` are `.cljc` on a byte transport this
kernel does not provide. New Kotoba objects need a kotoba-native export before
they can be linked. This slice therefore reuses the existing TCP admission
(`tcp-segment-valid`, `tcp-checksum-ok`, `ipv4-checksum`) and DHCP option 6,
and keeps new judgement out of C (ADR-0015).

## Decision

1. After a lease, the virtio-net probe sends one DNS query from
   `dhcp_address` to option 6 (else SLIRP `10.0.2.3`). Successful TX is
   consumption even if no A arrives. A constant-offset A for compiled
   `kotobase.net` is admitted; anything that needs an options-style walk is
   unwritten.
2. On an A, SYN to `:443`, then a compiled TLS 1.3 ClientHello with SNI
   `kotobase.net` on the handshake ACK (so an empty ACK and the ServerHello
   cannot race on the one-buffer virtqueue). A payload type 0x16 or 0x15 is a
   TLS *record*, not a completed handshake and not HTTP.
3. Serial marker **names** are stable for the offline floor
   (`AIUEOS_DNS_PROBE`, `AIUEOS_TCP_CLOUD_PROBE`, `AIUEOS_TLS_PROBE`,
   `AIUEOS_HTTP_PROBE`, `AIUEOS_BARE_METAL_P2`). The result lives in the rest
   of the line so public-network failure does not make extras non-deterministic.
4. Gate: `kbb -M:bare-metal cloud`. P1 / P1b / compositor / session guest
   smokes stay green. UEFI smoke with `AIUEOS_TEST_NET=1` requires
   `AIUEOS_DHCP_CONSUMED src=10.0.2.15`; it does not require public DNS/TCP.

## Consequences

The machine can use the address it was given, resolve `kotobase.net`, open
TCP :443, and (on this QEMU path) see a TLS handshake record. It still cannot
finish TLS or HTTP GET. P2 stays red until serial contains
`AIUEOS_HTTP_PROBE result=ok` with `cid=`. AES-GCM is not a kotoba-native
kernel-object entry, so the leftover is named `:tls-handshake-incomplete`
rather than silently skipped. The Chrome OS-shaped desktop goal is not
complete.
