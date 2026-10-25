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

## Design record

`com-junkawasaki/root` ADR-2607266500 (`90-docs/adr/`) — the overlay data-plane
gap this closes, and the split between what is implemented and what is injected.
