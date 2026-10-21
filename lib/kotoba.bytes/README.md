# kotoba-bytes

[![CI](https://github.com/kotoba-lang/bytes/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/bytes/actions/workflows/ci.yml)

Portable byte-vector primitives and pure SHA-1/HMAC-SHA1 for kotoba-lang
protocol libraries — no platform crypto API, identical code on JVM and
ClojureScript.

## Contract

- **`kotoba.bytes`** — portable byte-vector primitives (u16/u32 big-endian
  codecs, XOR, right-padding, base64 encode/decode, base64url encode
  (padded or not, as `java.util.Base64/getUrlEncoder`), UTF-8 encode,
  constant-time equality). Every "bytes" value in this library is a plain
  `vector<int 0..255>`, never a platform byte-array, so almost all of this
  code runs on the JVM and in ClojureScript unmodified — the sole exception
  is `utf8-encode`'s internal UTF-16-code-unit accessor, which needs one
  small reader conditional (`.charAt` vs `.charCodeAt`) to actually produce
  byte-identical output on both platforms, not just claim to (see the
  `kotoba.bytes/code-unit-at` docstring for the bug this fixed).
- **`->bytes` is where that contract is enforced rather than asserted.** A
  library can say its values are `vector<int 0..255>`, but values arrive from
  hosts that disagree — a JVM `byte[]` is signed, a `Uint8Array` and a Node
  `Buffer` are neither `vector?` nor `sequential?`, and a string is not bytes
  at all until something picks an encoding. `->bytes` is the one function that
  turns any of those into the shape everything else here promises, so a
  consumer has one place to convert instead of a private copy per consumer.
  `nil` stays `nil`: absent and empty are different answers and only the
  caller can tell them apart.
- **Host bytes, the JDK's exact answers** — the one place this library
  answers the HOST's byte container (`byte[]` on the JVM, `Int8Array` under
  ClojureScript/kbb, what kbb's `(.getBytes s "UTF-8")` returns) instead of a
  vector: `base64-decode-bytes` / `base64url-decode-bytes` /
  `base64mime-decode-bytes` (= `(.decode (Base64/getDecoder|getUrlDecoder|getMimeDecoder) x)`,
  a String or bytes in; where the JDK throws IllegalArgumentException these
  throw ex-info `{:kotoba.bytes/error :illegal-base64}`), `utf8-bytes`
  (= `(.getBytes s UTF_8)`, a lone surrogate is `?`), `utf8-string`
  (= `(String. b UTF_8)`, U+FFFD at the JDK's granularity) and `->host-bytes`.
  They exist for code migrating off those JDK calls; the vector functions
  (`base64-decode`, `utf8-decode`: nil on malformed input) are unchanged.
  Measured against JDK 21 as the oracle: `test/kotoba/bytes/host_bytes_oracle.edn`
  (17,338 seeded random + adversarial cases, from
  `scripts/gen-host-bytes-oracle.cljk`) replays with 0 mismatches on kbb and
  on the JVM.
- **`kotoba.bytes.sha1`** — pure SHA-1 (FIPS 180-4) + HMAC-SHA1 (RFC 2104), no
  platform crypto API. Depends only on `kotoba.bytes`.

```clojure
(require '[kotoba.bytes :as b])

(b/u16->bytes 0x2112)          ;=> [0x21 0x12]
(b/bytes->u32 [0 0 0 42])      ;=> 42
(b/xor-bytes [1 2 3] [1 1 1])  ;=> [0 3 2]
(b/utf8-encode "kotoba")       ;=> [107 111 116 111 98 97]
(b/base64-encode (b/utf8-encode "hi"))  ;=> "aGk="
(b/base64url-encode [0xfb 0xff] {:pad? false})  ;=> "-_8"
(b/constant-time-eq "abc" "abc")        ;=> true

(b/->bytes (byte-array [1 -1 0]))       ;=> [1 255 0]   (JVM byte[] is signed)
(b/->bytes (js/Uint8Array.from #js [1 255 0]))  ;=> [1 255 0]
(b/->bytes "日本語")                     ;=> [230 151 165 ...]  (UTF-8, 9 bytes)
(b/->bytes nil)                         ;=> nil         (absent, not empty)
(b/->bytes 42)                          ;=> throws — no byte reading
```

```clojure
(require '[kotoba.bytes.sha1 :as sha1]
         '[kotoba.bytes :as b])

(sha1/sha1-bytes (b/utf8-encode "abc"))
;; => [0xa9 0x99 0x3e 0x36 ...]  (20-byte vector, FIPS 180-1 vector)

(sha1/hmac-sha1 (b/utf8-encode "key") (b/utf8-encode "The quick brown fox"))
;; => 20-byte vector (RFC 2104 HMAC-SHA1)
```

## Background

This repo was extracted from
[`kotoba-lang/turn`](https://github.com/kotoba-lang/turn) (Phase 1 of a
shared-lib consolidation across kotoba-lang protocol libraries): `turn`
originally owned `kotoba.turn.bytes` and `kotoba.turn.sha1` as internal
implementation details of its RFC 8656 TURN/STUN codec, but neither namespace
is actually TURN/STUN-specific — they are generic low-level primitives that
any protocol-message codec or credential/HMAC path needs. Pulling them out
into their own repo lets other kotoba-lang libraries depend on the same
byte-vector/hash primitives instead of re-implementing them.

Intended/likely consumers: `kotoba-lang/turn` (STUN/TURN message codec,
ephemeral-credential mint/verify) and `kotoba-lang/dtn` (which currently has
ad-hoc, non-portable length-prefix framing code that this library is meant to
replace).

## Test

```
kbb -M:test
kbb -M:lint
```

## License

Apache License 2.0. See `LICENSE`.

## `kotoba.bytes.sha256` — pure SHA-256 / HMAC-SHA256

`sha256-bytes`, `sha256-hex`, `hmac-sha256`, `hmac-sha256-hex`, plus `hex` /
`unhex` on `kotoba.bytes`.

These exist because `MessageDigest` and `crypto.subtle` disagree on more than
spelling: one returns a value, the other returns a Promise. Any portable `.cljc`
that wanted a digest had to fork its own code path or make the whole call chain
async — so instead of solving that once, this workspace solved it 112 times,
each repo hand-rolling its own `sha256` and its own `hmac` (audited 2026-07-25:
112 repos with a private sha256 helper, 33 with a private bytes→hex, 36 with a
private hex→bytes, 30 with a private HMAC-SHA256).

A pure implementation is **synchronous on both runtimes**, which removes the
reason those forks existed.

The trade is speed: this is Clojure arithmetic, not a native digest. Use it for
signatures, identifiers, checksums and canonical hashes — kilobytes at a time.
For hashing large payloads, keep the platform primitive behind whatever seam you
already have (`sigv4.protocols/ICrypto`, for instance).

Pinned to the published vectors, not to our own output: FIPS 180-4's worked
examples (including the 55/56/64-byte padding boundaries where a padding bug
hides) and RFC 4231's HMAC cases (including the >64-byte key that a naive
implementation forgets to hash first). `kbb --backend sci --classpath src
scripts/verify-cljs.cljk` requires ClojureScript to produce the same bytes; both
run in CI.

`hex` pads bytes below `0x10` — the leading zero a `toString(16)`-based encoder
drops, which silently shortens a digest — and `unhex` returns `nil` on an odd
length or a non-hex character rather than decoding a corrupted digest to
something plausible.
