# eth-crypto-clj

[![CI](https://github.com/kotoba-lang/eth-crypto/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/eth-crypto/actions/workflows/ci.yml)

Standalone, **dependency-free** Ethereum crypto primitives in `.cljc` — Keccak-256,
EIP-55, EIP-712 typed data, secp256k1 sign/recover, RLP, and EIP-155 legacy +
**EIP-1559 (type-2)** transaction signing.

**The whole public API runs on both platforms**: the JVM/babashka (`clojure.*` +
`java.math.BigInteger`) and **ClojureScript** (`js/BigInt`). No third-party
dependencies on either. That means the same code signs a transaction in a Node
script and in a browser wallet where the key never leaves the user's device.

Sibling of [`kotoba-lang/ed25519`](https://github.com/kotoba-lang/ed25519):
where that covers the did:key / Ed25519 side, this covers the **Ethereum
secp256k1 / Keccak-256 / EIP-712** side.

## Why pure Clojure/ClojureScript (no BouncyCastle, no @noble)

babashka is a GraalVM *native image*: it can only use Java classes baked into the bb
binary. Arbitrary jars on the classpath are **not** loadable at runtime
(`java.security` exposes SHA3-256 but **not** Keccak-256, and any `org.bouncycastle.*`
import throws `ClassNotFoundException`). So Keccak-256 is the Keccak-f[1600] permutation
implemented here, and secp256k1 uses `java.math.BigInteger` (which IS available in bb).

## The ClojureScript half, and the trap it had to avoid

This library was `:clj`-only for its entire crypto half, with throwing `:cljs`
stubs. The reasons were real, and worth stating because they generalise:

- **Keccak-f[1600] cannot be naively ported.** It permutes 25 **64-bit** lanes, and
  cljs's `bit-xor`/`bit-and`/`bit-shift-left` compile to native JS bitwise
  operators, which ECMAScript defines on **32-bit** integers. A naive port does not
  fail to compile — it silently truncates every lane and returns a **wrong hash**:
  a wrong address, a wrong function selector, a wrong signing digest, with no error
  anywhere. `eth-crypto.keccak` carries lanes as `js/BigInt` instead (JS bitwise
  operators are defined on BigInt too).
- **`js/BigInt` has no `modInverse` and no `modPow`**, which secp256k1's field
  arithmetic needs. `eth-crypto.secp256k1` implements both (extended Euclid,
  square-and-multiply).
- **RFC 6979 needs HMAC-SHA256, and `SubtleCrypto` is async** — using it would make
  signing return a Promise and infect every caller. `eth-crypto.sha256` is a pure
  cljs implementation; SHA-256 is defined on 32-bit words, so unlike Keccak it is a
  natural fit.
- **RLP needs a type-level distinction between a byte string and a list.** On the
  JVM a `byte-array` is not `sequential?` and a vector is, so `rlp-encode` can tell
  them apart. In cljs both would be vectors — and `[1 2 3]` as a byte string encodes
  to `83 01 02 03` while the same value as a list encodes to `c3 01 02 03`. So on
  the cljs side a **JS array** is a byte string and a cljs vector is a list.

Also true on both platforms and stated rather than left implicit: **this is not
constant-time.** `BigInteger`/`BigInt` arithmetic is variable-time and point
multiplication is a plain double-and-add. Fine for signing with a key its owner
controls; **not** suitable for a shared process signing on behalf of others.

## API (`eth-crypto.core`)

| fn | in → out |
|---|---|
| `keccak256` | bytes → 32 bytes (Keccak-256, **not** SHA3-256) |
| `eip55-checksum` | 20-byte addr / hex → EIP-55 mixed-case `0x…` string |
| `encode-type` / `type-hash` | EIP-712 type encoding + `keccak256` thereof |
| `encode-data` / `hash-struct` | EIP-712 struct encoding + hash |
| `domain-separator` | EIP-712 domain separator |
| `eip712-digest` | `(domain types primary message) →` the `keccak256(0x1901‖domainSep‖structHash)` digest |
| `ecrecover` | `(digest sig)` → 20-byte signer address (secp256k1 public-key recovery) |
| `ecrecover-checksum` | as above → EIP-55 checksummed `0x…` |
| `private->public` | 32-byte privkey → 64-byte uncompressed pubkey (`X‖Y`, no `0x04`) |
| `address-of-privkey` | 32-byte privkey → EIP-55 `0x…` address |
| `secp256k1-sign` | `(privkey digest)` → `{:r :s :recovery-id}` — deterministic ECDSA (**RFC 6979** HMAC-SHA256 nonce) with EIP-2 low-s |
| `secp256k1-verify` | `(digest {:r :s} SEC-pubkey)` → boolean — ECDSA verification for compressed and uncompressed public keys |
| `secp256k1-low-s?` | `s` scalar → boolean; protocol-specific DER/low-S policy stays separate from curve verification |
| `rlp-encode` | byte-string / nested list → canonical Ethereum **RLP** bytes |
| `sign-tx-legacy` | `(tx privkey)` → `0x…` raw signed **EIP-155** legacy tx (replaces python `eth_account`) |
| `eip1559-digest` | `(tx)` → 32-byte `keccak256(0x02 ‖ rlp(payload))` — the digest to hand an out-of-process signer |
| `eip1559-raw` | `(tx {:r :s :recovery-id})` → `0x…` raw type-2 tx assembled from a **detached** signature |
| `sign-tx-eip1559` | `(tx privkey)` → `0x…` raw signed **EIP-1559 (type-2)** tx |
| `raw-tx-hash` | raw signed tx (hex/bytes) → `0x…` tx hash, computable **before** broadcast (legacy or typed) |
| `hex->bytes` / `bytes->hex` / `strip0x` / `utf8` | byte/hex helpers |

`sign-tx-eip1559` takes `{:chain-id :nonce :max-priority-fee-per-gas
:max-fee-per-gas :gas :to :value :data :access-list}` — the chain id is a
first-class payload field and the signature parity is a plain `yParity` 0/1, so
the EIP-155 `v = recovery-id + chainId*2 + 35` arithmetic does **not** apply.
`:access-list` is a seq of `{:address … :storage-keys […]}` and may be omitted.

## Verification

Verified against the canonical **EIP-712 "Ether Mail" spec vector**
(eips.ethereum.org/EIPS/eip-712):

```clojure
;; digest of the spec Mail message
(= (bytes->hex (eip712-digest domain types "Mail" message))
   "be609aee343fb3c4b28e1df9e632fca64fcfaede20f02e86244efddf30957bd2")  ;=> true
;; recover the spec signature → the spec signer
(= (ecrecover-checksum digest spec-signature)
   "0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826")                        ;=> true
```

plus Keccak-256 and EIP-55 known-answer vectors.

The **signing** side is gated against the canonical **EIP-155 worked example**
(privkey `0x4646…46`, the EIP-155 spec tx) — the signing hash, `v=37`/`r`/`s`, and
the full raw signed tx all match byte-for-byte, plus a sign→`ecrecover` roundtrip and
an `address-of-privkey` vector — see `test/eth_crypto/test_signing.cljk`.

**EIP-1559 (type-2)** has no worked example in the EIP text itself, so its vectors
are generated by an *independent* implementation — **viem 2.x** (`serializeTransaction`
/ `keccak256` / `privateKeyToAccount.signTransaction`, secp256k1 via `@noble`) — and
asserted byte-for-byte here: the signing digest, the full raw signed tx, and the
pre-broadcast tx hash, for both an empty access list (`yParity` 0) and a
two-slot access list with calldata (`yParity` 1). That makes it a genuine
cross-implementation check rather than a snapshot of this library's own output.

**Both platforms are gated on the SAME vectors.** That is what makes the cljs port
trustworthy rather than merely present: a wrong Keccak lane, a wrong modular
inverse or a wrong deterministic nonce cannot accidentally reproduce a published
signature.

```bash
kbb -M:test                             # JVM  — 20 tests, 28 assertions
kbb --backend sci --classpath src:test bin/run_tests.cljk  # cljs — 29 tests, 48 assertions
kbb -M:lint
```

The cljs run includes the shared `.cljc` suite plus `test_cljs_primitives.cljs`,
which checks the two primitives written from scratch at their own level: SHA-256
and HMAC-SHA256 against canonical digests (their 64 round constants are
transcribed — the error-prone part), Keccak on a **multi-block** input (200 bytes >
the 136-byte rate, which the short shared vectors never exercise), and
`mod-inverse`/`mod-pow` against Fermat's little theorem on the real secp256k1
field.

## Usage

```clojure
;; deps.edn / bb.edn
io.github.kotoba-lang/eth-crypto {:git/sha "<sha>"}

;; code
(require '[eth-crypto.core :as eth])
(eth/eip712-digest domain types "CreditorConsent" message)
(eth/ecrecover-checksum digest signature)   ;=> "0x…"
```

## Test

```bash
kbb -M:test
# Ran 5 tests containing 7 assertions. 0 failures, 0 errors.
```

## License

Apache-2.0. First-party org library; the etzhayyim Charter Compliance Rider applies to
first-party consumers per their own NOTICE.
