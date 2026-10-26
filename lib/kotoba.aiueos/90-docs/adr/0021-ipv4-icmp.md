# ADR-0021 — IPv4: an ARP cache, and a datagram that comes back

- Status: accepted
- Date: 2026-08-05
- Extends: ADR-0020 (the link layer)

## Context

ADR-0020 got aiueos onto the wire: it sends an ARP request and admits the reply.
That proved a peer answers, and nothing more — the reply was validated and then
thrown away, so the OS still had no idea who to address a datagram to, and no
datagram to address.

Reaching murakumo.cloud is link → **IPv4** → TCP → TLS → HTTPS. This is the
second layer.

## Decision

1. **Keep the peer's MAC.** The ARP reply already contains it; it is now stored
   in a small static cache once the reply has been *admitted*, never before.
   Storing six bytes is mechanism, so C owns it and no Kotoba object is
   involved — the decision that made those bytes trustworthy already happened.

2. **Send an ICMP echo request to 10.0.2.2 and admit the reply.** ICMP echo is
   the smallest thing that exercises a full IPv4 round trip: header
   construction, both checksums, and a real peer that has to route the datagram
   back. It needs no port allocation, no handshake and no state machine, so
   nothing above IPv4 is smuggled in to prove IPv4 works.

3. **Two new Kotoba objects**, keeping the mechanism/decision split (ADR-0015):
   - `ipv4-checksum.kotoba` → `kotoba_aiueos_ipv4_checksum`, the RFC 1071
     one's-complement checksum as a bounded tail recursion.
   - `ipv4-icmp-reply-valid.kotoba` → `kotoba_aiueos_ipv4_icmp_reply_valid`,
     which admits a received frame only if it is IPv4 (version 4, IHL 5), the
     protocol is ICMP, **both** checksums verify, the source is the peer that
     was asked, the ICMP type is 0 (a reply — 8 is what was sent), and the
     identifier and sequence match the request this boot made.

   The identifier/sequence check is the part that matters: a well-formed echo
   reply answering an *earlier* request, or addressed to somebody else, is a
   real datagram and still not evidence that this exchange completed.

## Consequences

- **`AIUEOS_IPV4_OK icmp-echo-reply kotoba-admitted`**, alongside
  `AIUEOS_VIRTIO_NET_OK` and `AIUEOS_UEFI_SMOKE_OK`. aiueos builds an IPv4
  datagram, a peer routes it, and the reply is admitted by compiler-emitted
  Kotoba with both checksums verified.

- **A failed exchange is not silent.** With a NIC present and the link layer
  already OK, failure prints `AIUEOS_IPV4_FAIL no-admitted-echo-reply` rather
  than nothing, because silence would be indistinguishable from a build that
  never tried — the trap `AIUEOS_VIRTIO_NET_ABSENT` exists to avoid one layer
  down. It does not fail the boot: whether a peer answers ICMP is a property of
  the network, not of this OS.

- **The checksum is implemented twice**, once per object. A kernel object is
  compiled with host imports disabled and exports exactly one symbol, so one
  object cannot call another. The duplication is the price of that isolation,
  and is paid rather than moving the arithmetic into C where it would stop
  being reviewable as a decision.

- **A kernel memory base must NAME a region, not compute one.** The first
  version passed `(+ frame 14)` to a bounded load and was rejected outright
  (`kernel memory base must name a region`). Summing a sub-range therefore
  carries a base *offset* alongside the frame, which is what keeps a bounded
  load bounded: a computed base could put the 2048-byte trap bound anywhere.

- **What "IPv4" does NOT mean here.** No fragmentation or reassembly — headers
  with IHL ≠ 5 are rejected rather than parsed, and a fragmented datagram is
  simply not admitted. No routing table, no ARP *expiry* (one peer, cached
  once), no IP address configuration: 10.0.2.15 and 10.0.2.2 are SLIRP's fixed
  topology, written into the driver. DHCP would be the way to stop hardcoding
  them, and does not exist.

- Still no TCP, no TLS, no HTTPS, so a node still cannot reach murakumo.cloud.
  Proved under QEMU SLIRP only; no physical NIC has carried any of this.
