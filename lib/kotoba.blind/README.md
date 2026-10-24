# blind

`kotoba-lang/blind` is the **L1 crypto layer** of the kotobase stack: a keyed
deterministic MAC (`blind-fn`) and a deterministic AEAD (`encrypt-fn` /
`decrypt-fn`), as portable `.cljc` running on the JVM and ClojureScript with
**zero third-party dependencies** — `javax.crypto` on one side, Web Crypto on
the other, and nothing else.

## Why this repository exists

`arrangement.core`, `kotobase-peer.core` and `kotobase-server` all take
`blind-fn` / `encrypt-fn` / `decrypt-fn` as **injected** functions, with (in the
server's words) *no silent default*. That is good design — the storage layer
should not own the keys. But it had a consequence nobody had written down:

> Searching the fleet for a real cryptographic primitive — `crypto.subtle`,
> `Mac/getInstance`, `AES-GCM` — found them **only in test files**
> (`arrangement/test/arrangement/core_test.cljc` and
> `kotobase_peer/test/kotobase_peer/core_test.cljc`).

So the security property the architecture rests on — leaf keys are blinded, leaf
values are AEAD ciphertext, therefore a server holding the blocks cannot filter
or range-scan on plaintext values — **was exercised only by test doubles.** It
was declared everywhere and implemented nowhere.

This library is the promotion of those two (identical, working, already
correct) test helpers into one reviewable place. It is **not new
cryptography**: it composes HMAC-SHA-256 and AES-256-GCM exactly as those
helpers already did, with the same wire format, so a value sealed by the old
test helper and a value sealed by this library are byte-identical.

Wiring the three consumers to it is a **separate, follow-up change**. This
repository does not touch them.

## Use

```clojure
(require '[blind.core :as blind])

;; Key material is passed in. That is the entire key-management story here.
(def blind-key  key-bytes-32+)   ; HMAC key for index-key blinding
(def dek        key-bytes-32)    ; AES-256 data-encryption key
(def nonce-key  key-bytes-32+)   ; HMAC key for nonce derivation — distinct!

(def blind-fn   (blind/blind-fn blind-key))
(def encrypt-fn (blind/encrypt-fn {:dek dek :nonce-key nonce-key}))
(def decrypt-fn (blind/decrypt-fn {:dek dek}))

;; ...then hand those three to arrangement / kotobase-peer as they already expect.
(blind-fn "alice")     ;=> "cCwHWeBCCGH/epJcq744gT2VWGK6D+dKMBIo0B4hGn4="  (JVM)
                       ;=> js/Promise of that string                        (cljs)
```

Wire format of a sealed value is one blob: `nonce (12) ++ ciphertext ++ tag (16)`.
`decrypt-fn` splits the nonce back off, so it needs only the DEK.

Low-level `hmac-sha256`, `aes-gcm-seal`, `aes-gcm-open`, `derive-nonce` and
`random-nonce` are also public — `aes-gcm-seal`/`open` take an explicit nonce,
which is what lets NIST's vectors be replayed against them verbatim.

## The deterministic nonce, and what it costs

`encrypt-fn`'s default mode derives its GCM nonce from the plaintext:

```
nonce = HMAC-SHA-256(nonce-key, plaintext)[0..12)
```

This is **required, not stylistic**. `kotobase-peer.core/fold!` documents that
folding identical state from *any* writer — a server cron, a browser at idle —
produces the identical snapshot CID, which is what makes concurrent redundant
folds safe, convergent and effectively free (re-`put!`ing already-stored bytes
is a no-op at the block store). A random-nonce `encrypt-fn` makes byte-identical
state encrypt to different bytes on every call, so every fold yields a different
CID and that property is silently gone. `kotobase-peer`'s own docstring warns
about this and names `nonce = HMAC(nonce-key, plaintext)` as the fix.

**The cost, stated plainly: deterministic encryption leaks equality of
plaintexts.** Two identical values under the same keys produce identical
ciphertext, so an observer holding the blocks learns *which encrypted values
equal each other* — and, if they also hold the keys, can confirm a guessed
plaintext by encrypting it. It does **not** leak the plaintexts themselves.
This is a real, named cost, accepted deliberately in exchange for the
fold-convergence design. If your threat model cannot accept it, do not use the
default mode.

GCM's actual requirement still holds. GCM breaks catastrophically when one
nonce is reused with the same key for *different* plaintexts; here different
plaintexts get different HMAC outputs and hence different nonces with
overwhelming probability. Only *identical* plaintexts reuse a nonce, and that
produces identical ciphertext rather than a keystream collision across two
different messages.

### The opt-in random mode, and why you probably don't want it

```clojure
(blind/encrypt-fn {:dek dek :nonce :random})   ; fresh random nonce per call
```

**Choosing this breaks fold determinism.** Identical state folds to a different
snapshot CID on every writer and every retry, so redundant concurrent folds stop
converging and stop being free. Do not choose it merely because "random nonces"
is the usual advice — choose it only if you have decided that plaintext-equality
leakage is unacceptable *and* that you can pay for non-convergent folds. One
`decrypt-fn` reads both modes (the nonce is on the wire), so the choice is the
writer's alone.

## Platform contract: JVM is synchronous, ClojureScript returns Promises

Every function that touches a primitive returns its result **directly on the
JVM** and returns a **`js/Promise` of that result on ClojureScript**. Web
Crypto has no synchronous AEAD or HMAC, and a browser/Worker runtime has no
other primitive to fall back to.

This split is not introduced here — it is already baked into the callers:
`arrangement.core/commit!` and `kotobase-peer.core/fold!` are documented as
synchronous on the JVM and `js/Promise`-returning on cljs for exactly this
reason. Papering over it would either be impossible (you cannot block on a
Promise in a Worker) or dishonest.

| | JVM | ClojureScript |
|---|---|---|
| primitive | `javax.crypto` | `crypto.subtle` (Web Crypto) |
| `blind-fn` | `String` | `js/Promise<string>` |
| `encrypt-fn` / `decrypt-fn` | `byte[]` | `js/Promise<js/Uint8Array>` |
| `random-nonce` | `byte[]` | `js/Uint8Array` (sync — the RNG is the one sync part of Web Crypto) |

Both sides produce **byte-identical output** for the same key material and the
same input. That is asserted, not assumed; see below.

## What this library does NOT provide

It takes key material as an explicit argument, and that is all.

- **No key management.** It does not read environment variables, files,
  keychains, 1Password, KMS, or any other ambient source. There is no
  configuration.
- **No key generation.** It never creates a key. (`random-nonce` generates a
  *nonce*, which is not secret.)
- **No key storage, wrapping, escrow or derivation.** No KDF, no password
  handling.
- **No key rotation.** Nothing here knows a key has versions. Note that
  rotating any of the three keys changes every token and every ciphertext, so
  rotation is a re-index, and designing that belongs to whoever owns the data.
- **No logging.** Nothing here prints. Key material and plaintext never appear
  in an exception message or in `ex-data` — errors carry a `:blind/error`
  keyword, a role, and lengths, and a test asserts exactly that.
- **No AAD / associated data.** The callers' wire format has no place for it
  yet; adding it later is a format change, not a parameter.
- **Not a general-purpose crypto library.** AES-256 only, SHA-256 only, no
  algorithm negotiation. If you need something else, this is the wrong layer.

## Verification

A crypto library whose only tests are round-trip (`decrypt(encrypt(x)) = x`) is
**not verified** — ROT13 passes that test. So the suite is built on published
known-answer vectors from third parties, plus cross-runtime agreement:

1. **RFC 4231 §4** — all 7 published HMAC-SHA-256 vectors, replayed against
   `hmac-sha256` (including the short-key, oversized-key and truncated-output
   cases).
2. **NIST CAVP `gcmEncryptExtIV256.rsp`** (CAVS 14.0) — the
   `[Keylen=256][IVlen=96][AADlen=0][Taglen=128]` groups, `Count = 0` at three
   plaintext lengths (0, 128 and 408 bits), i.e. exactly this library's
   parameters. Both seal *and* open directions.
3. **Cross-runtime golden vectors** for this library's own *composition* (the
   derived nonce, the `nonce ++ ct ++ tag` framing, `pr-str` serialisation,
   base64 encoding). RFC 4231 and NIST pin the primitives; these pin the way
   they are put together. The JVM suite and the ClojureScript suite assert
   against the **same literal bytes** in `test/blind/vectors.cljk`, so passing
   both means the two runtimes agree with each other, not merely each with
   itself.
   Those goldens were generated by `dev/gen_golden.cljk`, which uses Node's
   `node:crypto` — a **third** implementation, independent of both
   `javax.crypto` and Web Crypto. Regenerate with `npm run golden` and compare
   by eye; a diff is a finding.
4. **RFC 4648 §10** vectors for the portable base64 in `blind.bytes`. Base64 is
   implemented in portable Clojure rather than via `java.util.Base64` / `btoa`
   precisely because a per-platform codec is one more place for two writers to
   silently disagree — but then it has to be shown to still be *standard*
   base64, which is what these vectors do.
5. Behavioural tests for tamper detection, truncated blobs, wrong-key
   rejection, key-length validation, the absence of any ambient key source, and
   the determinism property itself (including an explicit test that the
   random-nonce mode *does* lose it).

```bash
kbb -M:test        # JVM (javax.crypto)
kbb -M:lint        # clj-kondo
npm install && npm run test:cljs   # real ClojureScript via shadow-cljs on Node's Web Crypto
```

Both runtimes: **16 tests, 80 assertions, 0 failures.**

## License

MIT.
