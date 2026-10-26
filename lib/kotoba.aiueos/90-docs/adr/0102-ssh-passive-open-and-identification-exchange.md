# 0102 — SSH passive open, and the identification exchange

Accepted 2026-08-25. Tranche four of root ADR
`adr-2608251418-aiueos-usb-install-and-headless-bootstrap`; it follows the SSH
contract + provisioning of ADR-0101. It removes the two architectural blockers
under the SSH crypto — the kernel had no LISTEN/accept and no post-evidence
service step — and proves it with a real external client. No crypto is added.

## What the kernel could not do, and now can

Before this, every TCP flow in the kernel was a compile-time-scripted client
probe: it opened connections, it never accepted one, and the boot was a
straight line that emitted evidence and exited. An SSH server is the opposite
shape — it waits for a peer to open a connection — so the first thing to prove
was that the kernel can accept one at all.

`kernel/pci.c` now has `net_ssh_listen` (compiled only under
`-DAIUEOS_SSH_LISTEN`): it waits for an inbound SYN to port 22 from SLIRP's
gateway, completes the three-way handshake with its own ISN, sends the SSH-2.0
identification string `SSH-2.0-aiueos_0.1\r\n`, and reads the client's. It
mirrors `net_tcp_probe` with the roles reversed, reuses the already-linked
`tcp-segment-valid.kotoba` for inbound admission and the self-checked
`net_tcp_send` for the answers, and is bounded throughout: a peer that never
connects, or a step that never completes, returns and the boot continues. The
listener can only ADD an evidence marker, never withhold one the network chain
already earned.

## Measured

`smoke-qemu-ssh.cljs` boots the SSH kernel through the same `smoke-qemu-uefi.sh`
harness the other network gates use — the one that reaches the network
evidence on this machine — with `AIUEOS_SSH_HOSTFWD` adding a host→guest:22
forward. A real external node client connects IN, and the gate is green only
when BOTH hold: the serial shows `AIUEOS_SSH_LISTEN_OK port=22 accepted
client-id=valid`, and the client read exactly `SSH-2.0-aiueos_0.1` from the
kernel. The marker alone could be a self-report; the client read alone could be
anyone; together they are an accepted inbound connection and a completed
identification exchange.

Two measured hazards shaped the gate:

- The guest's RX ring holds one buffer and is polled, so the listener waits for
  the inbound SYN across enough re-post/re-await windows to catch a SLIRP
  retransmit rather than giving up on the first empty poll.
- The client's timing cuts both ways: a socket that closes before the guest
  accepts loses the banner, and a single long-held socket can go stale before
  the listener (tens of seconds into the TCG boot) posts. The client keeps a
  pool of overlapping connections so a live host socket is always available for
  the guest to complete.

Every other build is byte-for-byte unchanged: the listener and its marker are
behind `#ifdef AIUEOS_SSH_LISTEN`, 158 added lines and zero removed, and the
default kernel that ships never compiles them.

## What is still red — this is not a login

This proves passive open and the SSH identification exchange. It is NOT an SSH
session: there is no key exchange, no host-key signature, no encryption, no
userauth. Those need SHA-512 and Ed25519 (verify for the client key, sign for
the host key) on the metal, and the survey in ssh-v1.edn is precise about why
that is a separate tranche: the KIR interpreter cannot provide the memory a
SHA-family object needs, so each new crypto primitive can only be functionally
measured by native compilation with the pinned amu or a QEMU kernel boot, not
by the vector-test harness that pure objects use. I4 stays RED until an
external client completes a publickey handshake with the provisioned key.

The listener also does not persist: it accepts one connection during the boot's
network phase and returns. A resident sshd that serves after boot is the same
service-loop seam, widened — also a later tranche.
