# 0107 — The real curve25519-sha256 handshake, verified by an independent client

Accepted 2026-08-26. Follows ADR-0106, which landed the exchange hash `H` as a
boot known-answer test and left the live wire exchange, the host-key signature,
and record protection as what remained. This lands the live handshake: the
kernel accepts a real TCP connection on port 22, runs the full
`curve25519-sha256` key exchange, and sends `KEX_ECDH_REPLY` (`K_S`, `Q_S`, an
`ecdsa-sha2-nistp256` signature over `H`) and `NEWKEYS` — and an **independent
real-crypto client verifies that signature**. The cryptographic core of an SSH
login (transport kex + server host authentication) is now real over a socket.

## What runs on the metal

`net_ssh_kex` in `kernel/pci.c`, continuing from the identification exchange the
passive-open listener (ADR-0102) already did:

1. send `SSH_MSG_KEXINIT` (the profile in `ssh.transport`), receive the client's
   KEXINIT, and its `KEX_ECDH_INIT` carrying `Q_C`;
2. generate a real X25519 ephemeral from the entropy source (ADR-0103), compute
   `Q_S = eph·G` and `K = eph·Q_C` with the kernel's X25519 object;
3. assemble the RFC 5656 transcript and `H = SHA256(transcript)` (the same
   `ssh.transport/h-transcript` ADR-0106 verified);
4. sign `SHA256(H)` with the ECDSA-P256 sign object (ADR-0105) under the host
   key, and send `KEX_ECDH_REPLY` + `NEWKEYS`.

Every wire byte layout — framing, `mpint`, the KEXINIT profile, `K_S`, the
signature blob, the reply — mirrors `ssh.transport` / **`ssh.kex`** in
kotoba-lang/org-ietf-ssh (west-imported), whose `kex_test.cljs` ran the same
reply through an independent real-crypto verifier before any kernel boot. The
kernel supplies the crypto from its Kotoba objects; the assembly is decision-free
byte layout.

Two choices worth recording:

- **The ECDSA nonce.** The sign object wants `k` in `[1, n-1]`. Rather than run an
  HMAC_DRBG (RFC 6979) in the kernel, `net_ssh_kex` takes 32 random bytes and
  clears the top bit: `n` for P-256 is `> 2^255`, so `k < 2^255 < n` is a valid
  nonce, and one bit of entropy is a non-issue for a single signature. It retries
  on the object's `r==0`/`s==0` refusal.
- **The host key is fixed and baked** (private `d` plus its public point `(x,y)`,
  precomputed off-target since the kernel has no P-256 base multiply). The client
  pins it. A per-device key is the provisioning's job (ssh-v1.edn); a fixed key
  makes the handshake reproducible for the gate.

## The 1 MiB ceiling, actually measured this time

ADR-0105 kept the ~50 KiB sign object out of the listener build, believing the
two would not fit under 1 MiB. Measured: listener + sign is **1,043,688 bytes** —
under the ceiling. Adding `net_ssh_kex` pushed the *file* to 1,067,112, but its
**loadable** size (the only thing the loader maps) was 516,096; the rest was a
~551 KiB symbol table the loader never uses yet shas and reads into a 1 MiB
buffer. The fix is `--strip-all` at link time (relocations are resolved for a
static freestanding kernel; nothing needs the symbol table at runtime). The
stripped kernel is **516,672 bytes** — 532 KiB of headroom for every build, and
ADR-0105's separation is lifted.

## Measured

- `ssh.kex` `kex_test.cljs`: an independent Node-crypto client verifies the reply
  end-to-end — 10/10.
- Boot under QEMU with a real inbound client on the hostfwd
  (`smoke-qemu-ssh-real.cljs`): the serial shows
  `AIUEOS_SSH_LISTEN_OK ... client-id=valid len=18`,
  `AIUEOS_SSH_KEX_REPLY_OK curve25519-sha256 ecdsa-sha2-nistp256 reply+newkeys sent`,
  and the client reports `client-verified=true`:
  `AIUEOS_SSH_REAL_SMOKE_OK an independent client verified the kernel's
  ecdsa-sha2-nistp256 signature over H (real curve25519-sha256 handshake)`.
- Teeth: the same gate with one signature byte flipped rejects with
  `reason "signature did not verify over H"` — the client's ECDSA verification is
  real, not a self-report.
- The root cause of the first empty boot is recorded so the next agent does not
  relive it: `smoke-qemu-uefi.sh` **always rebuilds** the kernel and inherits the
  gate's env, so `AIUEOS_SSH_LISTEN=1` must be in the gate's env or the rebuild
  silently drops every line of SSH code and the boot runs a non-SSH kernel.

## I4 status

The hard cryptographic half of a login is done and independently verified: the
`curve25519-sha256` key exchange and the `ecdsa-sha2-nistp256` server host
authentication, over a real socket. What remains for an interactive login is the
`aes128-gcm@openssh.com` record layer that turns on after NEWKEYS and the
publickey userauth on top of it (the kernel already has the AES-128-GCM object
and the ECDSA *verify* object; what is missing is the encrypt/decrypt record pump
and the userauth message sequence). The client here cooperates on TCP
segmentation only — the guest RX holds one buffer — which a real `ssh(1)` that
pipelines KEXINIT would not; making the pump robust to coalesced segments is part
of the same remaining work. No SHA-512, no Ed25519.
