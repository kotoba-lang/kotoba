# noise

[![CI](https://github.com/kotoba-lang/noise/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/noise/actions/workflows/ci.yml)

**The Noise Protocol Framework (rev 34) in portable `.cljc` — the mutually
authenticating, one-round-trip handshake an identity-addressed overlay data plane
needs.** `IK` (WireGuard's pattern), `XX`, `NN`, over
`25519_ChaChaPoly_{BLAKE2s,SHA256}`, plus the transport-phase semantics a
datagram overlay needs and Noise itself deliberately leaves out.

This closes the gap the fleet overlay had: [`kekkai`](https://github.com/kotoba-lang/kekkai)
publishes a netmap and says by charter that it "never pushes WireGuard config",
while [`murakumo`](https://github.com/kotoba-lang/murakumo)'s relay sealed frames
with **one shared `--auth-key` per overlay and AES-GCM** — a single symmetric
secret, no per-peer identity, no forward secrecy, no replay window. That is the
piece this library replaces. Its consumer is
[`kekkai-node`](https://github.com/kotoba-lang/kekkai-node), the node-side agent.

## What is implemented here, and what is injected

| | |
|---|---|
| **Implemented, pure `.cljc`** | the whole protocol core (CipherState / SymmetricState / HandshakeState / token interpreter / patterns), BLAKE2s (RFC 7693), HMAC + Noise's HKDF, the transport session (counter framing, replay window, rekey and expiry policy) |
| **Injected by the caller** | X25519 and ChaCha20-Poly1305 — `noise.provider.noble` (`@noble/curves` + `@noble/ciphers`, ClojureScript) or `noise.provider.jvm` (JCA, JDK 11+, zero deps) |

The split is the security argument, not a convenience: constant-time field
arithmetic and constant-time tag comparison are exactly what a hand-rolled
portable port loses, so those two come from an audited implementation, while
everything that is pure data-shuffling — where a portable implementation is
strictly better because it is the *same* code on every runtime — lives here.
BLAKE2s is the one exception, implemented because neither platform has it (the
JCA does not; only BouncyCastle) and a hash has no secret-dependent control flow
to get wrong.

Byte values everywhere are `kotoba.bytes` byte-vectors (vector of ints 0..255),
so nothing in the protocol layer needs a reader conditional.

## Use

```clojure
(require '[noise.core :as noise]
         '[noise.provider.jvm :as provider])   ; or noise.provider.noble under cljs

(def st    (noise/suite (provider/ports)))
(def alice (noise/keypair st))
(def bob   (noise/keypair st))

;; IK — Alice already knows Bob's static public key, from the netmap
(let [i (noise/initiator {:suite st :s alice :rs (:pub bob)
                          :prologue (noise/prologue "kekkai/1 netmap:42")})
      r (noise/responder {:suite st :s bob
                          :prologue (noise/prologue "kekkai/1 netmap:42")})
      [i msg1] (noise/write-message i [])         ; 1st and only round trip
      [r _]    (noise/read-message r msg1)
      [r msg2] (noise/write-message r [])
      [i _]    (noise/read-message i msg2)]
  (noise/remote-static r)          ;=> alice's public key, now *authenticated*
  (noise/handshake-hash i)         ;=> == (noise/handshake-hash r); channel binding
  (let [sa (noise/session i {:now 0 :peer-id "bob"})
        sb (noise/session r {:now 0 :peer-id "alice"})
        [sa frame] (noise/encrypt sa (b/utf8-encode "hello") {:now 0})]
    (second (noise/decrypt sb frame {:now 0}))))  ;=> "hello" bytes
```

Everything is pure — the caller owns the clock and the socket. `noise/advice`
returns the set of actions due for a session at a given time
(`#{:rekey :keepalive :expire}`), which is what makes an agent's tick loop
testable without either.

### Why `IK`

The initiator knows the responder's static key up front (for us: from the netmap
the control plane published), so in **one round trip** both sides are mutually
authenticated and the initiator's own identity is sent *encrypted* — a passive
observer cannot tell who is dialling. It also means an unauthorized dial fails at
the cryptographic layer rather than depending on the netmap being enforced
correctly at every hop: message 1 is encrypted to the responder's static key, so
a node that is not the intended peer cannot read it at all.

`XX` is there for bootstrap (responder's static not yet known, three messages),
`NN` for anonymous probe traffic where authenticating the reply is the relay's
job.

## Transport: what this adds on top of Noise

Noise hands you two CipherStates and assumes an in-order, reliable stream. A
datagram overlay has none of that, so `noise.session` adds exactly what
WireGuard adds and nothing more:

1. **An explicit counter on the wire** — each frame is
   `[counter:8 little-endian][ciphertext]`, with the header as associated data.
   Without it a single dropped UDP packet desynchronizes the nonces and every
   later packet fails to authenticate. With it, out-of-order delivery is fine and
   rewriting the counter is a forgery.
2. **A replay window** (default 2048) — an already-accepted or too-old counter is
   rejected. Note this is a *set* of counters, not a bitmap: 64-bit bitmap
   arithmetic is not portable to ClojureScript, so this trades a few tens of KB
   per peer for having one implementation instead of two.
3. **Rekey / expiry policy on both time and volume** — WireGuard's timer
   constants (rekey after 120s, reject after 180s, 5s handshake retry, 10s
   passive keepalive), with the volume limits lowered to what a portable integer
   counter expresses exactly (see `noise.cipher-state/max-nonce`: a *tightening*
   of Noise's bound, never a relaxation).

**This is not WireGuard on the wire.** The handshake framing, the cookie/DoS
messages and the 4-byte type/index header are WireGuard's; this overlay's
identities come from the kekkai netmap instead, and it carries service streams,
not L3 packets (there is no TUN device in a `.cljc` library). What is shared is
the cryptographic design and the session semantics. If kernel-WireGuard interop
is ever wanted, it is an additive framing module over this same core — say so in
an ADR first rather than quietly claiming compatibility.

## Verification

Both runtimes run the same `.cljc` namespaces:

```bash
npm install && kbb --backend sci --classpath "src:test:../bytes/src" run-tests.cljk   # first-class
kbb -M:test                                                        # JVM/JCA compat
kbb -M:lint
```

Measured 2026-07-26: **25 tests / 152 assertions / 0 failures on both** (nbb
1.4.208 with `@noble/curves` 1.8.x + `@noble/ciphers` 1.2.x; Temurin 21 with the
JCA).

What those assertions actually establish:

- **The official Noise known-answer vectors** (85 of the 152 assertions) — the
  `cacophony` vector set that `snow` and other implementations test against, kept
  verbatim in `test/noise/cacophony_vectors.edn` with its provenance. Every
  static *and* ephemeral key is fixed, so all six vectors
  (`IK`/`XX`/`NN` × `BLAKE2s`/`SHA256`, 6 messages each including the
  post-handshake transport messages) are byte-exact or they fail. A single
  mis-ordered token or a `MixHash` on plaintext where the spec says ciphertext
  changes the first ciphertext.
- **BLAKE2s** against RFC 7693 §A *and* OpenSSL (via Node) at 0/63/64/65/128/255
  bytes — the block boundary is where a wrong final-block flag or byte counter
  hides, and Noise's own inputs are too short to ever reveal it.
- **HMAC-BLAKE2s** against OpenSSL with both a short and a 32-byte key.
- **Rejection paths**, which a KAT cannot show: dialling the wrong responder,
  any flipped byte, truncation, prologue mismatch (e.g. a netmap-version
  disagreement), out-of-turn reads and writes.
- **Datagram behaviour**: reordering accepted, loss tolerated, replays rejected,
  counters outside the window rejected, forgeries rejected *without* poisoning
  the replay state, counter-rewrite detected as forgery, and the time-driven
  rekey/keepalive/expiry advice.

Honest gaps: no cross-implementation *live* interop run (the vectors are the
evidence, not a socket handshake against `snow`), no timing-side-channel analysis
of this code's own comparisons beyond using `kotoba.bytes/constant-time-eq`
where it compares secrets, and the SHA-256 suite exists to cross-check the
protocol core rather than because anything ships on it.

## Native port (AWAI-102)

`kotoba/noise/native.kotoba` (`ns noise.native`) is Noise rev 34 for
`Noise_{NN,XX,IK}_25519_ChaChaPoly_SHA256` in native `.kotoba`; XX is the libp2p
handshake. It is the `.cljk` core (`src/noise/`) ported onto this repository's native
X25519 (`org.ietf.x25519`), ChaCha20-Poly1305 (`org.ietf.chacha20Poly1305`) and SHA-256 /
HMAC (`gov.nist.sha2`), so nothing is injected from a host. The native subset has no
maps, so a handshake state is one 362-byte vector at fixed offsets (listed in the module
header). `write-message` / `read-message` / `transport-encrypt` / `transport-decrypt`
return the new state followed by the message or payload, and an empty vector when it is
not this side's turn, a MAC fails, the message is short or the handshake is in the wrong
phase. The caller supplies the ephemeral private key; there is no random source here.
BLAKE2s and the session layer (replay window, rekey, expiry) are not ported yet.

`kotoba/noise/native_gate.kotoba` is generated by `tools/gen_native_gate.py` from
`test/noise/cacophony_vectors.edn` (the three SHA-256 vectors). Each of six groups replays
one pattern from one side: it writes or encrypts that side's messages and compares the
published ciphertext byte for byte, and reads or decrypts the peer's and compares the
payload. Every group returns 31: the handshake messages, the handshake hash, the transport
messages, a changed byte in the first received encrypted message refused, and a message
out of turn refused. The first NN / XX message travels before any key exists and is not
authenticated, as Noise specifies, so the tamper check starts after it.

Built as modules and measured 2026-10-30 on Apple M1 Max with the Amu Mac root of main
`91faa123` (groups nn-i, nn-r, xx-i, xx-r, ik-i, ik-r):

| image set | change | results |
|---|---|---|
| gate | none | **31 31 31 31 31 31** |
| ctl-hkdf | second HKDF output counter 2 -> 3 | 24 24 24 24 24 24 |
| ctl-esse | the es token computes se | 31 31 24 24 24 24 |
| ctl-nonce | counter in the wrong nonce bytes | 27 27 24 24 27 27 |
| ctl-premsg | IK pre-message not hashed | 31 31 31 31 24 24 |
| ctl-macpt | DecryptAndHash hashes the plaintext | 29 31 24 24 29 24 |

Interoperability is the claim here: the native code reproduces the vectors that snow and
other implementations test against. The post-quantum extension (ML-KEM-768 mixed into the
handshake, Ed25519 + ML-DSA-65 over the handshake hash) is the next step of AWAI-102; this
port alone is classical X25519.

### XXhfs: the post-quantum handshake (ADR-0001)

Pattern 3 of `noise.native` is `Noise_XXhfs_25519+MLKEM768_ChaChaPoly_SHA256` (accepted
ADR `docs/ADR-0001-pq-xxhfs-identity.md`): Noise's hfs modifier (noise_hfs_spec
`025f0f60`) with ML-KEM-768 (`gov.nist.mlKem`).

```
-> e, e1          e1:    this side's ML-KEM ek, via EncryptAndHash (in clear in message 1)
<- e, ee, ekem1,  ekem1: encapsulation to the received e1; the ciphertext via
   s, es                 EncryptAndHash, then MixKey(shared secret); the reader
-> s, se                 DecryptAndHash, decapsulates, then MixKey
```

`set-kem st d-z m` supplies the KEM randomness: the FIPS 203 keyGen seed `d || z` for this
side's `e1`, and `m` for its encapsulation. A KEM token without its input refuses. The
name is 44 bytes, so `h` starts as its SHA-256. The state grew to 1645 bytes to hold `d
|| z`, `m` and the received `e1`; the classical patterns are unchanged and keep their
Cacophony gate.

No published vectors exist for this suite. `kotoba/noise/xxhfs_gate.kotoba` is generated by
`tools/gen_xxhfs_gate.py` from `tools/xxhfs_reference.py`, an independent Python Noise that
calls OpenSSL 4 for ML-KEM-768. That covers keyGen from `d || z`, deterministic
encapsulation with `hexikme`, and decapsulation. X25519 and ChaCha20-Poly1305 come from the
sibling libraries' Python references. Before its XXhfs output is used, the reference's
classical path must reproduce the Cacophony XX vector byte for byte. The XXhfs run reuses
that vector's X25519 keys, prologue and payloads, with fixed public-test KEM seeds.

Both groups (initiator, responder) return 63: the handshake messages and the handshake
hash byte for byte, two transport messages, a tampered encrypted message refused, a
message out of turn refused, and a KEM token without its input refused. Measured
2026-10-30 on Apple M1 Max with the Amu Mac root of main `91faa123` (built as modules):

| image set | change | i / r |
|---|---|---|
| gate | none | **63 / 63** |
| ctl-w-mixkey | the writer skips MixKey after ekem1 | 63 / 56 |
| ctl-r-mixkey | the reader skips MixKey after ekem1 | 56 / 63 |
| ctl-e1-hash | e1 sent without EncryptAndHash | 56 / 63 |
| ctl-kem-half | decapsulation given the wrong half of the key pair | 56 / 63 |
| ctl-m-seed | encapsulation uses d instead of m | 63 / 56 |

Each mutant fails exactly the side that runs the mutated step.

### Signed identity (ADR-0001)

`kotoba/noise/identity.kotoba` (`ns noise.identity`) is the identity payload of messages 2
and 3:

- **The identity:** the Ed25519 public key (`org.ietf.ed25519` `ed25519.selfhost`)
  followed by the ML-DSA-65 public key (`gov.nist.mlDsa`), 1984 bytes.
- **The proof:** both signatures over `"kotoba-noise-pq-identity/v1\n" ++ h`, where `h`
  is the handshake hash after the message's tokens. ML-DSA signs deterministically, with
  an empty context.

`verify-payload` is true only when the identity equals the one the host expects for that
peer and both signatures verify. To make `h` available, `noise.native` splits each
handshake message into a tokens step and a payload step (`write-tokens` /
`write-payload`, `read-tokens` / `read-payload`, with `handshake-hash-now` in between).
`write-message` and `read-message` are those two steps composed. A phase byte refuses a
payload step without its tokens step; the state is now 1646 bytes.

`kotoba/noise/identity_gate.kotoba` is generated by `tools/gen_identity_gate.py`. It runs
the same XXhfs handshake with identity payloads. In the oracle, Ed25519 comes from
OpenSSL (checked against RFC 8032 test 1 first) and ML-DSA-65 from the ACVP-validated
`gov.nist.mlDsa` Python reference. Both groups return 127:

1. messages byte for byte, signatures included;
2. the handshake hash;
3. transport;
4. the peer's identity verifies;
5. it is refused against another expected identity;
6. a changed ML-DSA byte is refused;
7. a changed Ed25519 byte is refused.

| image set | change | i / r |
|---|---|---|
| gate | none | **127 / 127** |
| ctl-no-want | the expected-identity comparison skipped | 111 / 111 |
| ctl-no-dsa | the ML-DSA-65 signature not checked | 95 / 95 |
| ctl-no-ed | the Ed25519 signature not checked | 63 / 63 |
| ctl-no-label | the signed message left without its label | 124 / 112 |
| ctl-dsa-off | the ML-DSA public key read one byte early | 119 / 119 |

The identity seeds in the gate are public test values, never operational keys.

### Framing and native TCP (ADR-0001)

`kotoba/noise/frame.kotoba` (`noise.frame`) frames a message with a 2-byte big-endian
length, at most 65535 bytes, the way libp2p frames Noise. `frame-end` and `unframe` read
the first complete frame and report an incomplete one as -1 / `[-1]`.
`kotoba/noise/frame_gate.kotoba` returns 63:

1. round trips at 0, 1, 255, 256 and 65535 bytes;
2. big-endian order;
3. refusal of 65536 bytes and of non-bytes;
4. incomplete buffers;
5. back-to-back frames;
6. the largest frame size.

Mutants: byte order 44, the limit off by one 59, and an incomplete-buffer check dropped,
which reads out of bounds and traps.

`kotoba/noise/tcp.kotoba` (`noise.tcp`) carries frames over the static runtime's native TCP
wires 43-47 (amu JUN-292): `listen`, `dial`, `accept`, `send-frame` (hex chunks of at most
16384 bytes, the wire's budget), `recv-frame` (reads only what the frame still needs) and
`close`. Only Linux static images answer these wires. The host grants the exact
addresses, and every refusal is the runtime's.

`kotoba/noise/tcp_demo.kotoba` is one Linux image that listens, dials and accepts on
127.0.0.1:47011 and runs the XXhfs handshake with identities and two transport messages
across the socket. It is written by `tools/gen_identity_gate.py` with the identity gate's
inputs, so every frame on the wire must equal the oracle's message. It returns 63:

1. the five frames equal the oracle;
2. both handshake hashes;
3. both identities verify;
4. every payload arrives;
5. a 65536-byte message is refused;
6. end of stream after close.

Measured 2026-10-30 in the podman machine (Linux arm64), built with Amu main's committed
`aarch64-linux-static-root.elf` (payload compiled to `aarch64-macos`, packed into the
runner, as the CI arm64 lane does):

| run | grants | result |
|---|---|---|
| demo | wires 43-47, 127.0.0.1:47011 for listen and dial | **63** |
| control | dial wire 45 not granted | `KEXE_CAP {:wire 45 :refused :not-granted}`, exit 120 |
| control | dial address not granted | `KEXE_TRAP … :net/address-not-granted`, exit 126 |

`tools/run_tcp_demo.py` reproduces it, and `scripts/check-pq-native.py` runs it with both
controls on the CI arm64 lane. Both sides share one process here. Separate hosts, the
broker's request/response binding, retries, timeouts, backpressure and host budgets are
the remaining parts of AWAI-102.

## Design record

`com-junkawasaki/root` ADR-2607266500 (`90-docs/adr/`) — the overlay data-plane
gap this closes, and the split between what is implemented and what is injected.
