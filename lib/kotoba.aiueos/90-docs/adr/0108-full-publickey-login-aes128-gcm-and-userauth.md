# 0108 — The full publickey login: aes128-gcm record layer and userauth

Accepted 2026-08-26. Follows ADR-0107, which landed the real `curve25519-sha256`
handshake and left, for a login, the encrypted record layer that turns on after
NEWKEYS and the publickey userauth on top of it. This lands both: after the
handshake the kernel derives the session keys, speaks `aes128-gcm@openssh.com`,
and authenticates a client by publickey — an independent real-crypto client
completes the **entire** exchange and receives an encrypted `USERAUTH_SUCCESS`.
The authentication half of an SSH login is done on the metal.

## What runs on the metal

`net_ssh_userauth` in `kernel/pci.c`, continuing from the NEWKEYS `net_ssh_kex`
already sent:

1. **Key derivation** (RFC 4253 §7.2): the four `aes128-gcm@openssh.com`
   parameters (per-direction key + IV) as `SHA256(mpint(K) || H || letter || H)`,
   with `session_id = H`.
2. Receive the client's NEWKEYS (the last unencrypted packet), then everything is
   `aes128-gcm@openssh.com`: `ssh_seal` / `ssh_open` frame a packet as
   `uint32 packet_length` (in clear, the GCM AAD) `|| ciphertext || tag[16]`, with
   the 12-byte nonce whose 8-byte counter increments per packet.
3. Decrypt the client's `SERVICE_REQUEST`, answer `SERVICE_ACCEPT`.
4. Decrypt the `USERAUTH_REQUEST`, reconstruct the exact `signed-data`
   (`string(H)` followed by the request up to but not including the signature),
   pull the offered public point out of the key blob, check it is the authorized
   key, and verify the `ecdsa-sha2-nistp256` signature over `SHA256(signed-data)`
   with the kernel's existing ECDSA **verify** object.
5. Answer `USERAUTH_SUCCESS`.

Every byte layout mirrors `ssh.keys` / `ssh.record` / `ssh.userauth` in
kotoba-lang/org-ietf-ssh (west-imported), whose `session_test.cljs` ran the whole
post-NEWKEYS login — key derivation, the GCM record round-trip (tag rejects
tampering, wrong counter rejects), and publickey userauth (server verifies the
client signature, refuses a non-authorized key) — through an independent
real-crypto implementation before the kernel port. The crypto is the kernel's:
AES-128-GCM (`tls_aes_gcm.h`) and the ECDSA verify object, already linked.

The authorized key is a fixed `ecdsa-sha2-nistp256` public point, baked; the
client holds the matching private half. Per-device authorized keys are the
provisioning's job (ssh-v1.edn).

## Measured

- `ssh.{keys,record,userauth}` `session_test.cljs`: the whole login end-to-end
  with Node AES-128-GCM + ECDSA — 13/13, including the GCM tag rejecting a
  tampered byte and the server refusing a signature from a non-authorized key.
- Boot under QEMU with a real inbound client (`smoke-qemu-ssh-auth.cljs`): the
  client completes kex, sends NEWKEYS, then the encrypted service request and a
  publickey `USERAUTH_REQUEST` signed by the authorized key, and decrypts an
  `AIUEOS_SSH_AUTH_OK` `USERAUTH_SUCCESS`:
  `AIUEOS_SSH_AUTH_SMOKE_OK an independent client completed a full publickey login
  (kex + aes128-gcm + userauth) against the kernel`. Kernel 524,864 bytes, well
  under the 1 MiB ceiling.

## I4 status

The authentication is complete and independently verified: `curve25519-sha256`
key exchange, `ecdsa-sha2-nistp256` host authentication, the
`aes128-gcm@openssh.com` record layer, and `publickey` userauth ending in
`USERAUTH_SUCCESS`, all over a real socket. What a stock `ssh(1)` would do next is
open a session channel (`CHANNEL_OPEN` / `CHANNEL_REQUEST "shell"` or `"exec"`)
and exchange data — that is a channel multiplexer, not authentication, and it is
the next tranche. The client still cooperates on TCP segmentation (the guest RX
holds one buffer); making the pump robust to a pipelining `ssh(1)` is part of the
same remaining work. No SHA-512, no Ed25519.
