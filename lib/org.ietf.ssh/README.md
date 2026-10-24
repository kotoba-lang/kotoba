# org-ietf-ssh

**The reusable, portable core of the SSH-2 transport layer (RFC 4253) with the
`curve25519-sha256` key exchange (RFC 8731 / RFC 5656) — the wire rules and, above
all, the ordered transcript whose SHA-256 is the exchange hash `H`.**

The name follows the origin-plane rule (AGENTS.md, ADR-2608040100): SSH is
specified by the IETF, so the reverse-DNS of the authority (`ietf.org` →
`org-ietf`) plus the subject gives `org-ietf-ssh`.

## Why this exists

Two SSH implementations only interoperate if, given the *same* wire bytes, they
compute the *same* exchange hash `H` — the client verifies the server's signature
over `H`, and both sides derive session keys from it. `H` is a SHA-256 over a
strictly ordered concatenation of length-prefixed fields (RFC 5656 §4):

```
H = SHA256( string(V_C) || string(V_S) || string(I_C) || string(I_S)
            || string(K_S) || string(Q_C) || string(Q_S) || mpint(K) )
```

A one-byte disagreement anywhere in that transcript — a missing leading zero in
`mpint(K)`, the wrong name-list order in a KEXINIT payload, CR-LF left on an
identification string — silently breaks the handshake. So the transcript, the
`string`/`mpint` encodings, the binary-packet framing, and the KEXINIT algorithm
profile belong in **one** place that every consumer reads. That place is
`ssh.transport`.

This namespace is **pure and portable** (`.cljc`): it does no I/O and no
randomness. The caller supplies SHA-256 and the X25519 scalar multiplication, so
the same definitions drive:

- a **host-side reference** (Clojure or nbb) used as a test oracle, and
- the **aiueos bare-metal kernel**, which west-imports this repo and mirrors
  `h-transcript` byte-for-byte in a compiled Kotoba object, reusing the kernel's
  existing X25519 and SHA-256 primitives.

Bytes are plain vectors of `0..255` integers, so the code runs identically under
Clojure and ClojureScript/SCI without a platform byte-array type.

> ⚠ **Portability footgun captured here:** `(mapv int "SSH-2.0-…")` works on the
> JVM but silently returns **zeroes** under ClojureScript (a string seqs into
> single-character strings, and `(int "S")` is `0`). Use `ssh.transport/str->bytes`
> for any string→bytes conversion. This bug zeroed `V_C`/`V_S` and the name-lists
> and was caught only because the exchange-hash test compares against an
> independent Node reference.

## What's here

`src/ssh/transport.cljk`:

| | |
|---|---|
| `msg-*` | message numbers: KEXINIT 20, NEWKEYS 21, KEX_ECDH_INIT 30, KEX_ECDH_REPLY 31 |
| `profile` | the algorithm name-lists aiueos speaks: kex `curve25519-sha256`, host-key `ecdsa-sha2-nistp256`, cipher `aes128-gcm@openssh.com` |
| `u32` / `string-bytes` / `name-list` / `mpint` | RFC 4251 §5 primitive encodings |
| `packet` / `packet-payload` / `pad-length` | RFC 4253 §6 binary-packet framing (build + validate) |
| `kexinit-payload` | RFC 4253 §7.1 SSH_MSG_KEXINIT payload |
| `h-transcript` / `exchange-hash` | **the exchange-hash transcript and `H = sha256(transcript)`** |

`src/ssh/kex.cljk` — the server side of the reply:

| | |
|---|---|
| `ec-point` / `host-key-blob` | the `ecdsa-sha2-nistp256` host key blob `K_S` (algo, curve, SEC1 point) |
| `signature-blob` | `string algo || string (mpint r \|\| mpint s)` |
| `kex-ecdh-reply-payload` / `newkeys-payload` | the `SSH_MSG_KEX_ECDH_REPLY` and `SSH_MSG_NEWKEYS` payloads |
| `ecdsa-digest` | the ECDSA message digest for `ecdsa-sha2-nistp256`: `SHA256(H)` |

`test/ssh/kex_test.cljk` runs a full round-trip with **real crypto on both sides**
(Node X25519 + ECDSA P-256): the server builds the reply, an independent client
parses it, pulls the host public key out of `K_S`, re-derives the shared secret
and `H` from the wire, and verifies the signature over `H`. If a different
implementation accepts the reply, a real `ssh(1)` will.

`src/ssh/keys.cljk` — the post-NEWKEYS key derivation (RFC 4253 §7.2):
`session-keys` returns the four `aes128-gcm@openssh.com` parameters (per-direction
key + IV) from `K`, `H`, and the session id.

`src/ssh/record.cljk` — the `aes128-gcm@openssh.com` binary packet layer (RFC
5647 + OpenSSH): `seal` / `open` with the length field as GCM AAD, the 12-byte
nonce whose 8-byte counter increments byte-wise per packet, and the block/padding
rule. The GCM cipher is caller-supplied.

`src/ssh/userauth.cljk` — the `publickey` authentication exchange (RFC 4252 §7):
the service request/accept, the USERAUTH_REQUEST, and `signed-data` — the exact
bytes the client signs and the server reconstructs to verify.

`test/ssh/session_test.cljk` runs the **whole post-NEWKEYS login end to end with
real crypto** (Node AES-128-GCM + ECDSA): derive keys, encrypted service
request/accept, and publickey userauth where the server reconstructs `signed-data`
and verifies the client's signature against the authorized key — and refuses a
signature from a non-authorized key. 13/13.

`src/ssh/connection.cljk` — the connection protocol (RFC 4254): opening a
`session` channel and running a command. `channel-open` / `-confirmation`,
`channel-request-exec`, `channel-success`, `channel-data`, `exit-status`,
`channel-eof` / `-close`, and parsers the server admits the client's messages
with. `test/ssh/session_channel_test.cljk` runs a full session over the encrypted
record layer — the client opens a channel, runs `exec`, and receives the server's
`CHANNEL_DATA` output. 9/9.

## Test

`test/ssh/transport_test.cljk` drives the core with fixed inputs and checks the
encodings against hand-computed bytes and, crucially, `H` against an *independent*
Node reference that concatenates the same RFC 5656 fields through a separate code
path. Every input is fixed — a parity failure that only reproduces sometimes is
not reportable.

```bash
kbb --backend sci --classpath src:test test/ssh/transport_test.cljk
# SSH_TRANSPORT_SUMMARY ran=13 expected=13 failed=0
```

## Scope

This is the transport **core**: negotiation profile, framing, and the exchange
hash. It deliberately does **not** contain sockets, randomness, ciphers, or the
signature step — those are the host's (aiueos kernel C for the wire and the
ephemeral key; the kernel's existing ECDSA-P256 / SHA-256 / X25519 Kotoba objects
for the crypto). Keeping the pure wire rules separate is what lets one definition
be verified on the host and executed in the kernel.

## License

Apache-2.0.
