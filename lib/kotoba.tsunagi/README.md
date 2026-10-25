# tsunagi

**A Reticulum-style overlay network in pure kotoba**: self-certifying
addresses, signed announces, a routing node as a pure state machine,
forward-secret links and store-and-forward messages. Bearer-agnostic — the
same node runs over LoRa, Wi-Fi mesh, a community LTE cell or the Internet.

Part of the decentralised phone stack: `tsunagi` → `nafuda` → `monban` →
`yobidashi` → `denwa` (see [denwa](../denwa/README.md) for the whole picture).

| namespace | what |
|---|---|
| `tsunagi.identity` | X25519 + Ed25519 identity from one seed; 16-byte identity and destination hashes; single-packet encryption |
| `tsunagi.packet` | the ≤ 500-byte packet; duplicate-suppression hash |
| `tsunagi.announce` | signed announces; replay ordering by emission |
| `tsunagi.transport` | routing node: path table from announces, transport-header forwarding, on-path link relaying, path requests — effects as data |
| `tsunagi.link` | one-RTT ephemeral X25519 link, HKDF-SHA256 keys, ChaCha20-Poly1305, 64-wide replay window, in-channel caller identification |
| `tsunagi.message` | signed + encrypted messages and a propagation store with authorised fetch and an `:admit?` hook for stamps |
| `tsunagi.resource` | split / reassemble payloads larger than one packet |

All cryptography is first-party: `org-ietf-x25519`, `org-ietf-ed25519`,
`org-ietf-chacha20-poly1305`, `org-nist-sha2`, `org-ietf-hpke` (HKDF). The
X25519 and Ed25519 implementations are **not constant-time** — see
`tsunagi.crypto`.

This is not wire-compatible with Reticulum; it borrows the ideas, not the
format.

```sh
npm test    # kbb --backend sci … run-tests.cljk
```
