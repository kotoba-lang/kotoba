# 0109 — The session channel: running a command over the login

Accepted 2026-08-26. Follows ADR-0108, which closed the authentication half of an
SSH login (`USERAUTH_SUCCESS` on the metal). This adds the connection protocol
(RFC 4254) on top of it: the kernel opens a `session` channel, accepts an `exec`
request, and streams the command's output back as `CHANNEL_DATA`. An independent
client runs a command and receives the result — the login is now *usable*, not
just authenticated.

## What runs on the metal

`net_ssh_userauth` in `kernel/pci.c` continues past `USERAUTH_SUCCESS` (all over
the same `aes128-gcm@openssh.com` record layer, the packet counters continuing):

1. `CHANNEL_OPEN` (`session`) → parse the client's channel id →
   `CHANNEL_OPEN_CONFIRMATION`.
2. `CHANNEL_REQUEST` (`exec`) → parse the command → `CHANNEL_SUCCESS`.
3. `CHANNEL_DATA` — `"aiueos: <command>\n"`. Echoing the received command proves
   the whole round-trip: the channel opened, the exec request parsed, and data
   returned on the right channel.
4. `exit-status` (0), `CHANNEL_EOF`, `CHANNEL_CLOSE`.

Everything is best-effort after `USERAUTH_SUCCESS` (each step returns 1, not 0,
so the login marker still fires if the client does not go on to open a channel).
The byte layouts mirror `ssh.connection` in kotoba-lang/org-ietf-ssh
(west-imported), whose `session_channel_test.cljs` ran a full `exec` session
through an independent real-crypto implementation before the kernel port.

This is a *command* session, not an interactive shell: the kernel answers `exec`
with a fixed transform of the command. A real shell would need a command
interpreter over `kuro`/`kobo`; that is a separate, much larger piece. What is
real here is the SSH connection layer — channels, requests, data, and clean
teardown — over the authenticated, encrypted transport.

## Measured

- `ssh.connection` `session_channel_test.cljs`: a full session over real
  AES-128-GCM — open, `exec`, `CHANNEL_SUCCESS`, `CHANNEL_DATA`, exit-status,
  EOF, close — 9/9, the client receiving the command output.
- Boot under QEMU with a real inbound client (`smoke-qemu-ssh-session.cljs`): the
  client completes the login, opens a channel, runs `uname -a`, and decrypts the
  kernel's `CHANNEL_DATA` `"aiueos: uname -a\n"`:
  `AIUEOS_SSH_SESSION_OK` and
  `AIUEOS_SSH_SESSION_SMOKE_OK an independent client ran a command (exec) over a
  session channel and got its output back from the kernel`. Kernel 528,960 bytes.

## Status

The SSH surface is now complete for a headless command login: `curve25519-sha256`
kex, `ecdsa-sha2-nistp256` host auth, the `aes128-gcm@openssh.com` record layer,
`publickey` userauth, and a `session`/`exec` channel — all real over a socket,
verified end-to-end by an independent client. What remains is breadth, not a
missing layer: an interactive shell with a real interpreter, `pty-req` and
window-change, multiple/concurrent channels, rekeying, and hardening the pump for
a pipelining `ssh(1)` (the client still cooperates on TCP segmentation because
the guest RX holds one buffer). No SHA-512, no Ed25519.
