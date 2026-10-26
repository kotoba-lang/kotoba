# 0106 — The SSH transport, the exchange hash H, and the org-ietf-ssh import

Accepted 2026-08-26. Follows ADR-0105, which landed the last crypto brick (the
ECDSA P-256 sign object) and named what remained for a login: the SSH
binary-packet transport and the exchange hash the host key signs over. This
lands that transport's wire rules and the exchange hash, and — at the owner's
direction ("共通化できる部分は kotoba-lang org repo に実装して, import するように
設計") — puts the reusable part in a shared kotoba-lang repo the kernel imports,
rather than writing SSH's wire rules a second time inside the kernel.

## The reusable part is the wire rules, and there is exactly one copy

Two SSH implementations interoperate only if, given the same wire bytes, they
compute the same exchange hash `H`. `H` is a SHA-256 over a strictly ordered
concatenation of length-prefixed fields (RFC 5656 §4, RFC 8731):

```
H = SHA256( string(V_C) string(V_S) string(I_C) string(I_S)
            string(K_S) string(Q_C) string(Q_S) mpint(K) )
```

A one-byte disagreement anywhere in that transcript — a missing leading zero in
`mpint(K)`, the wrong name-list order in a KEXINIT payload, a CR-LF left on an
identification string — silently breaks the handshake. So the transcript, the
`string`/`mpint` encodings, the binary-packet framing, and the KEXINIT algorithm
profile are the thing that must not be written twice.

They now live once, in **`kotoba-lang/org-ietf-ssh`** (`ssh.transport`, a pure
portable `.cljc`; west-registered, public). The name follows the origin-plane
rule — SSH is an IETF specification, `ietf.org` → `org-ietf`, plus the subject:
`org-ietf-ssh`. The namespace is pure: the caller supplies SHA-256 and X25519,
so the same definitions drive a host-side reference and the kernel.

That library carries its own scar. `(mapv int "SSH-2.0-…")` works on the JVM but
silently returns **zeroes** under ClojureScript (a string seqs into
single-character strings and `(int "S")` is 0), which zeroed `V_C`/`V_S` and the
name-lists. It was caught only because the exchange-hash test compares against an
independent Node reference — the encodings all "passed" against each other while
being wrong together. `ssh.transport/str->bytes` is the portable fix.

## What the kernel imports

The kernel does not depend on the `.cljc` at runtime — it is bare metal. It
imports the definition in two concrete, load-bearing ways:

1. **`aiueos_ssh_kex_h()` in `kernel/main.c` mirrors `ssh.transport/h-transcript`
   byte-for-byte.** The transcript assembly is decision-free mechanism (u32
   length prefix, byte copy, the mpint leading-zero rule) — the aiueos discipline
   keeps judgment in Kotoba objects and byte layout in C. The hash is the
   already-linked Kotoba SHA-256 object, so this adds **no new object** and rides
   under `AIUEOS_SSH_LISTEN` (unlike the ~50 KiB ECDSA sign object of ADR-0105,
   which needs its own flag near the 1 MiB ceiling).
2. **`smoke-qemu-ssh-kex.cljs` `(require '[ssh.transport :as t])`** — it imports
   the shared core, recomputes `H` for the same fixed inputs, and asserts the
   kernel's emitted `H` equals it. This is the import with teeth: the kernel also
   bakes that `H` as a self-check `want[]`, but the **authority is the core**. If
   org-ietf-ssh's transcript order or encoding ever drifts, the recomputed `H`
   moves, the kernel's emitted hex (still equal to the stale baked `want`) no
   longer matches, and the gate goes red — even though the kernel self-reports
   `AIUEOS_SSH_KEX_OK`. A gate that trusted only the kernel's own marker would be
   a self-report; the AGENTS.md rule "a negative test must reject for the reason
   it names" is why the core, not the kernel, holds the reference.

## Measured

- `ssh.transport` test (`test/ssh/transport_test.cljs`): 13/13, including the
  exchange hash matched against an independent Node reference. Every input fixed.
- `aiueos_ssh_kex_h()` over the fixture inputs SHA-256s a 173-byte transcript to
  `H = 520a9ba7…09833`, which is exactly `ssh.transport`'s `H` for those inputs.
- Built under `AIUEOS_SSH_LISTEN=1` and run under QEMU:
  `AIUEOS_SSH_KEX_H 520a9ba7…09833` and
  `AIUEOS_SSH_KEX_OK curve25519-sha256 exchange-hash-match org-ietf-ssh`.
  (See the gate evidence for this commit.)

## I4 status

RED, and honestly so. What is proven is the exchange hash — the value the whole
handshake pivots on — computed identically by the shared core and the kernel.
What remains for a login is the **live** wire exchange (receive `KEX_ECDH_INIT`
with `Q_C`, generate the ephemeral scalar from the ADR-0103 entropy, send
`KEX_ECDH_REPLY` with `K_S`, `Q_S`, and the ECDSA-P256 signature over `H` using
the ADR-0105 object, then `NEWKEYS`), `aes128-gcm@openssh.com` record protection,
and publickey userauth (the existing kernel ECDSA verify). Those bricks are all
present; what is not yet built is the socket pump that drives them in sequence,
and fitting the listener and the sign object into one kernel under 1 MiB. No
SHA-512, no Ed25519.
