# 0101 — Headless SSH: the contract, and the provisioning half

Accepted 2026-08-25. Tranche three of root ADR
`adr-2608251418-aiueos-usb-install-and-headless-bootstrap` (I0/I1/I2 =
ADR-0097, I3/I5 under QEMU = ADR-0099). It designs I4 in full and lands the
first measured half of it — provisioning — while being explicit that the
served handshake is still red and why.

## The design (ssh-v1.edn)

`os/aiueos/contracts/ssh-v1.edn` records the SSH-2 profile AIUEOS's own
bare-metal server will speak, chosen so every algorithm has a path to the
metal:

- kex `curve25519-sha256` — X25519 and SHA-256 already exist in the kernel.
- host key `ssh-ed25519`, cipher `aes128-gcm@openssh.com` — AES-128-GCM
  exists; the GCM tag is the MAC.
- userauth `publickey` / `ssh-ed25519`, verified against the provisioned
  authorized key; password auth refused.

The reachability floor is declared as reachability, never as a file's
presence: an external `ssh(1)` from another host must complete the publickey
handshake with the intent's key, a wrong key must be refused with a reason,
and both must survive a reboot. `:not-green-on` names the three tempting
false positives (key file in the image, sshd binary present, port 22 open
without a completed auth).

## The four measured blockers (kernel survey, all file:line verified)

1. **No passive open.** TCP is client-only — compile-time-scripted probes, no
   TCB, no port table, no LISTEN/accept. `tcp-seq-acceptable.kotoba` (RFC 9293
   windowing) is written but has no `.o` and is not linked.
2. **RX depth 1, polled, ring handles are stack locals** of `virtio_net()`.
3. **No random-bytes API and no signing primitive.** virtio-rng asks for 32
   bytes once and discards them; ECDSA P-256 is verify-only; Ed25519 is
   absent. A standards server MUST sign the exchange hash H per handshake, so
   a provisioned-and-only-verified host key does not suffice — host-key SIGN
   is unavoidable, which is why the host key is ssh-ed25519 and the long pole
   is Ed25519 + SHA-512.
4. **No steady state.** `main.c` is a straight line ending in `ud2` →
   `qemu_exit(0x30)`; a server loop must be inserted before that, under the
   1 MiB kernel-ELF ceiling.

Reusable today: X25519, SHA-256, HMAC-SHA256, HKDF, AES-128-GCM, digest-equal;
the TLS 1.3 client (`tls13.c`) is a TCP-passive byte codec whose shape `ssh.c`
mirrors. Reference implementations for the crypto bricks:
`kotoba-lang/org-ietf-ed25519` and `kotoba-lang/org-ietf-sftp` (both `.cljc`).

## Landed and measured this tranche: provisioning

`os/aiueos/scripts/make-provision-record.cljk` — the per-device SSH identity,
generated **on the target at install time** (never at USB-build time): a
one-time ed25519 host-key seed and the authorized key copied from the intent.
The host key derived from RFC 8032 test-vector-1's seed equals that vector's
public key, byte-for-byte — the generator makes the *right* key, not merely an
ed25519-shaped one.

`os/aiueos/scripts/install-to-disk.cljk` writes the record into a reserved
16 KiB zone just below the target receipt (in the target's last MiB, outside
the release extent), reads it back, and binds its digest into the target
receipt — so a target that carries a receipt always has a matching SSH
identity beside it. The seed is written only there, on the target; it never
touches the install USB (secret floor 1: the tool generates it, no credential
is ever typed).

Measured:
- `test-provision-record.cljs` — 6/6: RFC 8032 host key, authorized = intent's
  key with a matching fingerprint, seed present-and-digested, injected-seed
  refused outside `NODE_ENV=test`, non-ed25519 authorized key refused,
  tampered-intent fingerprint refused.
- `test-install-chain.cljs` — 22/22 (was 18): the fake-device install now
  places a provision record; the record is present, its host key is a valid
  ed25519 key, the authorized key is the owner's, and the receipt binds its
  digest.
- `smoke-qemu-install.cljs` — the live installer, under QEMU, provisions the
  target: after boot1 the gate reads the provision zone off the NVMe and
  asserts a valid record. (See the gate evidence for this commit.)

## Still red — and this is I4, so it stays red

- **sshd**: TCP passive-open + the SSH transport + userauth + a post-evidence
  service loop are all unimplemented (blockers above).
- **Crypto bricks**: SHA-512 and Ed25519 (verify for userauth, sign for the
  host key) do not exist on the metal. `ssh-v1.edn :crypto-bricks` names each
  with its vectors and what it reuses.
- Provisioning is the *static* half decision 4 already calls necessary-but-
  not-sufficient: a placed authorized key is not a completed handshake. I4 is
  green only when an external client logs in with the intent's key, a wrong
  key is refused, and both survive a reboot. None of that has happened.
