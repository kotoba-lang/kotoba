# multiformats-clj

[![CI](https://github.com/kotoba-lang/io-multiformats/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/io-multiformats/actions/workflows/ci.yml)

**base58 · base32 · varint · sha2-256 multihash · CIDv1 · multiaddr — real `.cljc`,
verified on both the JVM and ClojureScript, babashka-friendly. Compute a
file's CID without shelling out to `ipfs`.**

In a kotoba/IPFS codebase the same encodings get reimplemented in every actor:
base58btc for `did:key`, base32 for the multibase `b` CID, the sha2-256
multihash, and `CIDv1`. And computing a blob's content address usually means
shelling out to `ipfs add --only-hash` — a runtime dependency on the ipfs CLI
just to hash some bytes. This is that logic once, and it's **byte-identical to
`ipfs add --cid-version=1 --raw-leaves`** for single-block (≤256 KiB) inputs —
on both platforms.

## Portability

This used to be JVM-only (`java.security.MessageDigest`) despite living in a
`.cljc`-named file — a documented, known gap every downstream repo in this
ecosystem carried. `sha256` / `sha384` now use `kotoba-lang/org-nist-sha2` on
both hosts (pure `.cljc`, no npm). `cid-of-file` stays `:clj`-only — that's file
I/O, not a gap.

Two correctness pitfalls found while verifying this under the real
`shadow-cljs` compiler (not just an `nbb` smoke test — see below):

- **`multihash-sha256` used to return a plain ClojureScript vector on
  `:cljs`.** Every other "bytes" this library hands back is array-like
  (byte-array on `:clj`, `Uint8Array` on `:cljs`), so callers reasonably use
  `aget`/`alength` on them — but `aget` on a plain vector silently returns
  `nil` (coerced to `0` by `bit-and`) instead of throwing, which is exactly
  the kind of gap that stays invisible until it corrupts a real multihash.
  Fixed to return a real `Uint8Array`.
- **`count` has no `ICounted` implementation for a raw `Uint8Array`/
  `Int8Array` on `:cljs`** (it works for `:clj` byte-arrays, and for cljs's
  own native `Array`, just not `TypedArray`). Use `alength`, not `count`,
  for byte-array/`Uint8Array` length in any portable code calling into this
  library.

## Install

deps.edn (git dep):

```clojure
io.github.kotoba-lang/io-multiformats {:git/sha "<sha>"}
```

## Use

```clojure
(require '[multiformats.core :as mf])

;; content addresses (== go-ipfs / kubo)
(mf/cidv1-raw (.getBytes "hello\n"))   ;=> "bafkreicysg23kiwv34eg2d7qweipxwosdo2py4ldv42nbauguluen5v6am"
(mf/cid-of-file "build/app.wasm")       ;=> "bafkrei…"   (no ipfs CLI; single block)
(mf/kotoba-cid "ibuki")                 ;=> "bafyrei…"   dag-cbor CID of the name (KotobaCid)

;; multibase / multihash primitives
(mf/base58btc some-bytes)  (mf/base58btc-decode "z6Mk…body")
(mf/base32 some-bytes)     (mf/base32-decode "kreih…")
(mf/multihash-sha256 bytes)            ;=> 0x12 0x20 ‖ sha256
(mf/varint 300)                        ;=> bytes 0xac 0x02
(mf/cid->bytes "bafkrei…")             ;=> 0x01 0x55 0x12 0x20 …
```

`cid-of-file` replaces `ipfs add -Q --cid-version=1 --raw-leaves <path>` in build
and publish scripts, dropping the ipfs binary from the toolchain. It is
**single-block only** (≤256 KiB, the ipfs default chunk) and throws on larger
input — a multi-block dag-pb tree is intentionally out of scope.

## Correctness

```bash
kbb -M:test                    # JVM (no network, no ipfs at test time)
npm install && npm run test:cljs   # real ClojureScript, via shadow-cljs node-test
```

- **CIDv1-raw vectors minted by real go-ipfs/kubo** (`ipfs add --raw-leaves`) for
  empty / `"hello\n"` / a fixed string — reproduced exactly.
- multihash framing (`0x12 0x20` + the canonical `e3b0c442…` sha256 of empty),
  varint boundaries, base58/base32 round-trips (incl. leading-zero `1`s), and CID
  decode round-trips.

```
Ran 7 tests containing 28 assertions.
0 failures, 0 errors.
```

on both platforms. Verification note: an initial check via `nbb` (a fast
SCI-based cljs interpreter) passed cleanly, but that was verifying the
*wrong* thing — it doesn't catch either bug above (its own array/typed-array
semantics happen to paper over both). Compiling with real `shadow-cljs` (the
same toolchain `net-kotobase`/`app-aozora` deploy with) is what actually
caught them. A fast interpreter is a good first pass, not a substitute for
the real target toolchain before trusting a "portable" claim.

## License

Apache-2.0.

## multiaddr

`multiformats.multiaddr` — self-describing network addresses
(`/ip4/127.0.0.1/tcp/4001/p2p/QmPeer`). Added because libp2p speaks them and
this org had none.

```clojure
(ma/parse "/ip4/127.0.0.1/tcp/04001")   ;=> "/ip4/127.0.0.1/tcp/4001"
(ma/peer-id "/ip4/1.2.3.4/tcp/80/p2p/QmY…")  ;=> "QmY…"
(ma/transport "/ip4/1.2.3.4/udp/4001/quic-v1") ;=> :quic
```

**The binary form is the identity.** `/ip4/127.0.0.1/tcp/4001` is one specific
octet sequence, and two addresses are the same address when their octets match.
`equal?` compares octets and `parse` normalizes through them — comparing the
strings instead makes `/tcp/04001` a different address from `/tcp/4001` and
lets one peer occupy two routing-table entries.

**A `/p2p/` peer ID round-trips through its multihash**, not its text, for the
same reason.

**`/unix` consumes the rest of the address**, because a filesystem path
contains slashes. Parsed one segment at a time, `/unix/tmp/sock` looks like an
unknown protocol `sock`.

**A flag protocol yields `nil`, not `""`** — an empty string is a value and
`/quic` has none.

**Varint bytes are masked.** `multiformats.core/varint` returns a host byte
array whose bytes are signed on the JVM, so 0x91 comes back as -111; without
the mask the same address encodes differently per platform. There is a test
against the octet sequence the multiaddr spec documents.

## Pure Kotoba: `multiformats.cid`

[`src/multiformats/cid.kotoba`](src/multiformats/cid.kotoba) assembles a CIDv1
in pure Kotoba (root ADR-2610082200 §16): unsigned LEB128 varints, RFC 4648
lower-case base32 without padding, and `"b" + base32(varint 1 ++ varint codec ++
0x12 0x20 ++ digest)`. It has no effects. The digest comes from the
`hash/sha256` capability in
[`src/multiformats/cid_hash.kotoba`](src/multiformats/cid_hash.kotoba)
(`cidv1-raw-text`, `kotoba-cid`); a guest using it declares `[:cap/call 3]`.
`multiformats.core` stays as the oracle (`migration/cid-v1.edn`).

```bash
kbb --backend sci --classpath "src:$(kbb -Spath)" scripts/cid-oracle-cases.cljk
```

asks `multiformats.core` every question the Kotoba tests assert (18 cases,
2026-10-09). `cid.kotoba`'s four `test-*` pass on wasm32-browser
(`--fuel 5000000`).
