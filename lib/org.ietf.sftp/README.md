# org-ietf-sftp

[![CI](https://github.com/kotoba-lang/org-ietf-sftp/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-ietf-sftp/actions/workflows/ci.yml)

SFTP filesystem semantics + an experimental SSH transport, part of the
kotobase.net storage-protocol extension effort
(ADR-2607172210 in `com-junkawasaki/root`; addressing contract: the
Kotoba Resource Protocol §16.4, `90-docs/protocols/kotoba-resource-protocol.edn`
— an SFTP path is a **Location** only, no Name/Record/Content mapping of
its own, mirroring how git's dumb-HTTP surface is scoped in KRP §8).

**"SFTP" here means the IETF secsh working group's `draft-ietf-secsh-filexfer`
series — this specification was NEVER RATIFIED TO AN RFC.** It reached
draft 13 and stalled; there is no "RFC 4251/4253-for-SFTP" to claim
conformance to, unlike SSH's own transport/connection/authentication layers
(which SFTP rides on top of, and which *did* become real RFCs — 4251–4254 —
that this repo's transport layer borrows wire-format SHAPE from, without
claiming full conformance to those either; see below). This repo does not
say "RFC-compliant SFTP" anywhere, and neither should anything that depends
on it — this is the same naming discipline `com-junkawasaki/root`
ADR-2607060100 already applies to `json`/`dag-cbor`/`openapi`-named repos:
don't overclaim conformance to a formal body's spec that isn't actually
ratified.

## Two independently-useful layers

| Layer | Namespace | Status |
|---|---|---|
| **Phase 1 core** — real filesystem semantics (readdir/stat/open/read/write/mkdir/rmdir/rename/remove) over `kotobase.store` | `kotobase.sftp.fs` (`.cljc`) | Solid. 8 tests / 65 assertions, pure, JVM-testable, zero SSH concepts. |
| **Phase 1 transport** — a hand-rolled SSH transport + a minimal SFTP subsystem wired to the core above | `kotobase.sftp.transport.*` (`.cljs`-only) | **EXPERIMENTAL — see the bold warning below.** Genuinely works, cross-process-tested, but has not had a security review. |

The core ships regardless of how the transport question resolves — this is
deliberate (ADR-2607172210's own framing): a real filesystem-over-`IStore`
model is useful today; a hand-rolled SSH server is comparatively much
higher-risk and is scoped, tested, and warned about accordingly.

### Phase 1 core: `kotobase.sftp.fs`

Pure `.cljc`, parallel in shape to [`kotobase-protocols`](https://github.com/kotoba-lang/kotobase-protocols)'s
`s3.cljc` (an object store projected onto `IStore`) — here it's a real
directory tree instead of a flat key space:

```clojure
(require '[kotobase.local :as local]
         '[kotobase.sftp.fs :as fs])

(def ctx {:store (local/local-store) :now "2026-07-17T00:00:00Z"})

(fs/mkdir ctx "home" "alice")
;; => {:ok? true :path "alice"}
(fs/write ctx "home" "alice/hello.txt" "hello sftp")
;; => {:ok? true :path "alice/hello.txt" :size 10}
(fs/readdir ctx "home" "alice")
;; => {:ok? true :path "alice" :entries [{:name "hello.txt" :type :file :size 10 :mtime "2026-07-17T00:00:00Z"}]}
```

**Directory-creation model**: `write` and `mkdir` both require the parent
directory to already exist — no auto-vivification, mirroring real POSIX
`open(O_CREAT)`/`mkdir` semantics (and SFTP's own `SSH_FX_NO_SUCH_FILE`)
rather than S3's flat-key convention. See the namespace docstring for the
full "deliberately out of scope" list (permission bits, symlinks, extended
attributes, partial/byte-range write, cross-share rename).

Every mutation (`write`/`mkdir`/`rmdir`/`remove-file`/`rename`) appends an
audit event onto `:kotobase.protocols/audit`, same convention as the rest of
the `kotobase-protocols` family.

### Phase 1 transport: `kotobase.sftp.transport.*`

> [!WARNING]
> **EXPERIMENTAL. PENDING SECURITY REVIEW. Do not expose this on a network
> you don't fully trust; do not use it to protect anything sensitive.**
> A hand-rolled SSH transport-protocol implementation is security-sensitive
> even when the underlying crypto primitives (`node:crypto`'s
> X25519/Ed25519/AES/HMAC) are library-provided and correct — the FRAMING,
> STATE MACHINE, and NEGOTIATION LOGIC around those primitives is exactly
> where real-world SSH implementation vulnerabilities have historically
> lived, and this implementation has not had that kind of review. This is
> the highest-risk item in ADR-2607172210, and that ADR says so explicitly.

A minimal, RFC-4253/RFC-8731-**shaped** SSH transport over plain
`node:net` (zero npm dependencies, matching the `kotoba-lang/dtn` precedent
— see below), carrying a minimal SSH connection layer, carrying a minimal
SFTP subsystem:

- **Version exchange** — `SSH-2.0-...` line, both directions.
- **`SSH_MSG_KEXINIT`** negotiation — one supported algorithm per category:
  `curve25519-sha256` (key exchange), `ssh-ed25519` (host key),
  `aes128-ctr` (cipher, both directions), `hmac-sha2-256` (MAC, both
  directions), no compression.
- **Key exchange** — real X25519 ECDH (`node:crypto`'s `diffieHellman` +
  `generateKeyPairSync('x25519')`), a real RFC-8731-shaped exchange hash
  (SHA-256 over V_C/V_S/I_C/I_S/K_S/Q_C/Q_S/K), and a real Ed25519 host-key
  signature over that hash that the client verifies (TOFU — no
  known_hosts/pinning; see below).
- **`SSH_MSG_NEWKEYS`** → real `aes-128-ctr` encryption + `hmac-sha2-256`
  integrity on every subsequent packet, both directions, independently
  derived per RFC 4253 §7.2's KDF.
- A minimal SSH connection layer: `SERVICE_REQUEST`/`ACCEPT`
  (`ssh-userauth`), **accept-any `none` userauth** (explicitly NOT a
  security boundary), one `session` channel, one `subsystem sftp` request.
- A minimal SFTP subsystem (`kotobase.sftp.transport.sftp-subsystem`):
  `SSH_FXP_INIT/VERSION`, `OPEN/CLOSE/READ/WRITE`, `OPENDIR/READDIR`,
  `STAT`, `REMOVE`, `RENAME`, `MKDIR/RMDIR` — wired straight to
  `kotobase.sftp.fs`.

**This genuinely works, and is genuinely tested, not merely "shaped":**
`test/kotobase/sftp/transport/ssh_demo.cljk` spawns a real second `nbb` OS
process running this code as a server, drives it as a client from a
different process over a real TCP socket, and proves the FULL chain —
handshake through an encrypted `mkdir → write → close → open → read → stat
→ readdir → rename → remove → rmdir` SFTP session — actually completes,
with the encrypted `READ` response containing the exact bytes an earlier
encrypted `WRITE` sent from the other process. See "What's actually
verified" below for the precise, non-rounded-up claim.

Following the same-day precedent `kotoba-lang/dtn` set
(`90-docs/adr/2607161817-...`) and `ADR-2607172210`'s own note: no host
capability for inbound TCP listen or crypto exists in this workspace's
`kotoba wasm`/`clojurewasm` runtimes today, so this transport is plain nbb
`.cljs` over Node's `node:net`/`node:crypto` core modules as an OS process
— not WASM-guest execution. True WASM-guest hosting is an explicit,
separately-ADR'd Phase 2, blocked on new `kotoba-core-contracts` host
capabilities that don't exist yet; this repo does not attempt to invent
them.

#### What's actually verified (read this before trusting anything above)

| Claim | Verified how | Confidence |
|---|---|---|
| Packet framing (plaintext + encrypted, MAC'd, arbitrary chunk boundaries) | Unit tests, `wire_test.cljs` — including a MAC-tamper-rejection test and a NEWKEYS-mid-chunk-boundary test | High |
| `mpint` encoding | Byte-exact against RFC 4251 §5's own worked examples | High |
| X25519 ECDH / Ed25519 sign-verify | Round-trip through raw-byte JWK reconstruction (the wire representation), unit-tested | High |
| Exchange hash + key derivation | Self-consistency + fixed-length-output unit tests | High (self-consistency only — not checked against an external RFC 8731 test vector, because none was found) |
| SFTP opcode encode/decode/dispatch against the fs core | `sftp_subsystem_test.cljs`, 25 assertions, no sockets | High |
| Full handshake + full SFTP session, END TO END, ACROSS TWO REAL OS PROCESSES, OVER A REAL SOCKET | `ssh_demo.cljs`, 11/11 checks — this is the strongest evidence in this repo | High, for THIS repo's client talking to THIS repo's server |
| Interop with a real OpenSSH client or server | **Not tested. Not claimed.** | None |
| Resistance to a real adversary (timing side channels, malformed-input fuzzing, protocol-downgrade attacks, resource-exhaustion beyond the one packet-length-size guard `wire.cljs` has) | **Not tested. Not claimed.** | None |
| Security review by anyone other than the implementing agent | **Has not happened.** | None |

#### Everything this transport deliberately does NOT do (v0.1)

See `kotobase.sftp.transport.ssh`'s own docstring for the authoritative,
maintained list — restated here:

- No `SSH_MSG_DEBUG`/`IGNORE`/`UNIMPLEMENTED` handling.
- No re-keying (one `KEXINIT` per connection, ever — fine for a short demo
  session, not fine for a long-lived production connection).
- No real user authentication (`none` always succeeds).
- No host-key persistence/known_hosts/TOFU-with-pinning on the client side.
- Exactly one channel, one `subsystem sftp` request — no shell, no exec, no
  port forwarding.
- No `SSH_MSG_CHANNEL_WINDOW_ADJUST` (one large fixed initial window,
  never replenished — never exercised by this repo's own small demo
  payloads, which is itself a gap worth naming).
- Multi-chunk `SSH_FXP_WRITE` is supported by accumulating pieces
  offset-sorted at `CLOSE` time, but does NOT gap-fill non-contiguous
  writes — see `sftp-subsystem`'s own docstring.
- `uint64` fields (READ/WRITE offset, ATTRS size) only read/write the low
  32 bits — correct for this repo's own file sizes, silently wrong for
  anything needing the high bits.
- Byte-exact interop with a real OpenSSH client/server: not attempted.

## Develop / test

First-class runtime is **nbb/cljs** (repo-wide runtime priority: `kotoba
wasm` > `clojurewasm` > `ClojureScript` > `nbb` > (jvm/bb)):

```bash
git clone https://github.com/kotoba-lang/kotobase .deps/kotobase

# Phase 1 core + wire/kex unit tests + sftp-subsystem unit tests (fast, no sockets)
kbb --backend sci --classpath "src:test:.deps/kotobase/src" bin/run_tests.cljk

# The real cross-process SSH/SFTP demo (slower — spawns a second OS process)
kbb --backend sci --classpath "src:test:.deps/kotobase/src" test/kotobase/sftp/transport/ssh_demo.cljk
```

The `:test` alias in `deps.edn` is the JVM **compat** suite for the pure
`.cljc` core (`kotobase.sftp.fs`) only — it never loads anything under
`src/kotobase/sftp/transport/` (`.cljs`-only, cannot run on the JVM at all).

### Try the experimental transport by hand

```bash
kbb --backend sci --classpath "src:test:.deps/kotobase/src" bin/sftp_node.cljk listen --port 6222 --share home
# separate terminal / process — no general-purpose CLI SFTP client ships
# here (see kotobase.sftp.transport.ssh's docstring: the client this repo
# provides is demo/test-only); use the REPL API in ssh.cljs directly, or
# read ssh_demo.cljs for a worked example of driving it.
```

## Scope guards (read before extending)

- **SFTP paths are a Location only** (KRP §16.4) — no Name/Record/Content
  mapping. Don't add one here; if a file reachable over SFTP needs a
  Name/Content identity, that comes from another projection (HTTP, git),
  per KRP.
- **The transport is not a security boundary today.** Treat it the same
  way you'd treat an unreviewed crypto library: fine for local
  experimentation and this repo's own demo, not fine for anything that
  needs to actually keep data confidential or a service actually
  available against an adversary.
- **The core (`kotobase.sftp.fs`) has no SSH-specific concepts** — no
  session, no channel, no wire packet shape. Keep it that way; it's the
  single swap-in point for any future transport, including a real
  Phase-2 WASM-guest one.
- **`uint64` narrowing, ATTRS narrowing, no re-keying, no auth** — see the
  tables above before assuming this transport does something it doesn't.

## License

Apache-2.0
