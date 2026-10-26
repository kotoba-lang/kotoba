# ADR-0022 — TCP: one connection that completes

- Status: accepted
- Date: 2026-08-05
- Extends: ADR-0021 (IPv4 + ICMP)

## Context

ADR-0021 got a datagram out and back. ICMP echo proves the IPv4 envelope and
both checksums, and nothing about *connections* — no ports, no sequence space,
no peer that has to agree with us about either.

Reaching murakumo.cloud is link → IPv4 → **TCP** → TLS → HTTPS. This is the
third layer, and the first one where the peer keeps state too.

## Decision

**Complete exactly one connection against a real peer, end to end**: three-way
handshake, send a payload, admit the peer's echo of it, close.

1. **The peer is `guestfwd`.** QEMU accepts a connection to 10.0.2.100:9000 and
   pipes the stream through `cat`:

   ```
   -netdev user,id=aiueosnet,guestfwd=tcp:10.0.2.100:9000-cmd:/bin/cat
   ```

   This is what makes the gate mean something. Sequence numbers, ACKs and both
   checksums all have to be right or nothing comes back — the OS cannot satisfy
   it by echoing itself, and no external network is involved.

2. **Two Kotoba objects**, keeping ADR-0015's split:
   - `tcp-checksum-ok.kotoba` → `kotoba_aiueos_tcp_checksum_ok`, the TCP
     checksum over the IPv4 pseudo-header plus header and payload.
   - `tcp-segment-valid.kotoba` → `kotoba_aiueos_tcp_segment_valid`, which
     independently re-checks the IPv4 envelope and header checksum, the TCP
     checksum, the source, the ACK field, and the flags byte — assuming nothing
     a caller might have checked.

   **Flags are compared for exact equality, not masked.** A SYN-ACK and a
   SYN-ACK-PSH are different events, and the caller has to say which one it is
   expecting rather than accepting a family of segments.

3. **Outgoing checksums reuse `kotoba_aiueos_ipv4_checksum`** over a scratch
   buffer holding `[pseudo-header ++ segment]`. C lays the bytes out
   (mechanism); the already-reviewed object does the arithmetic. The
   pseudo-header cannot simply be overlaid on the frame — to sit contiguous with
   the TCP header it would start at offset 22, putting its address fields four
   bytes off from where the IPv4 header carries them.

## Consequences

- **`AIUEOS_TCP_OK handshake echo close kotoba-admitted`**, alongside
  `AIUEOS_IPV4_OK`, `AIUEOS_VIRTIO_NET_OK` and `AIUEOS_UEFI_SMOKE_OK`. Four
  admissions — SYN-ACK, echo, FIN-ACK, and every checksum inside them — all
  decided by compiler-emitted Kotoba.

- Failure prints one of six distinct `AIUEOS_TCP_FAIL <reason>` markers rather
  than one. That is deliberate: there are four admissions in a row, and a re-run
  costs many minutes on a loaded host, so a failure that names its stage is
  worth more than a failure that does not.

- **This is a probe, not a stack.** No retransmission timers, no congestion
  control, no window management beyond a fixed advertised window, no
  out-of-order reassembly, no multiple connections, no options (data offset 5).
  The receive ring holds exactly one buffer, so two segments arriving back to
  back means the second is dropped and recovery depends entirely on the peer
  resending. HTTPS will need more than this.

- **The echoed bytes are never compared with what was sent.** The verified
  checksum proves the segment is intact, not that it carries our payload; the
  admission's five parameters are spent. Likewise the destination address and
  both port numbers go unchecked — harmless under SLIRP's fixed topology, not
  harmless on a real wire.

- **One bounds check lives in C** (`net_tcp_peer_next`): the peer's data offset
  is constrained before it is used to derive an acknowledgement number, because
  an out-of-domain value would produce that number from an underflow rather than
  from the wire. It guards a *derivation*, not an admission, and it is the
  closest anything here comes to deciding in C. A sixth parameter or a third
  object would move it.

- **A correction to this ADR's own framing.** The work was specified as
  "the peer is off-link, so frames go to the gateway MAC". That is wrong:
  10.0.2.100 is inside 10.0.2.0/24 and therefore on-link by netmask, and a
  conforming stack would ARP for it. The approach works anyway because SLIRP
  does not filter inbound IPv4 on the Ethernet destination MAC, so a frame
  addressed to the cached gateway MAC still reaches its `ip_input`. Implemented
  as specified, with the discrepancy recorded rather than quietly ARPed around —
  a real network would not be so forgiving.

- Still no TLS and no HTTPS, so a node still cannot reach murakumo.cloud.
  Proved under QEMU SLIRP only; no physical NIC has carried any of this.
