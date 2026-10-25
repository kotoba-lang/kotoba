# pqh

`@etzhayyim/pqh` — the crypto-agility seam: AEAD envelope encryption,
password-based KDF, a post-quantum hybrid layer, DID&harr;Signal identity
binding, and a deprecated toy Signal-session stand-in.

| Namespace | What it does |
|---|---|
| `crypto.cljc` | XChaCha20-Poly1305 AEAD envelope (24-byte nonce, 16-byte tag) over dag-cbor, with an ISO/IEC-7816-4 padding-bucket scheme; raw AEAD behind the `IAead` seam |
| `kdf.cljc` | Argon2id (RFC 9106) password-based key derivation, suite `argon2id-v1`; raw Argon2id behind the `IKdf` seam |
| `pq.cljc` | Post-quantum hybrid layer, suite `pqh-v1`: X25519+ML-KEM-768 (FIPS 203) KEM combiner, Ed25519+ML-DSA-65 (FIPS 204) dual signatures; raw primitives behind the `IPq` seam |
| `pq_bc.clj` | Production JVM `IPq` provider backed by BouncyCastle 1.79 |
| `did_signal.cljc` | DID&harr;Signal `IdentityKey` binding verification (did:web / did:plc / did:key), with optional ML-DSA-65 hybrid signature |
| `signal.cljc` | **Deprecated** in-memory session/key-wrap stand-in, retained only because a real test exercises the PQ-hybrid-into-session-wrap path against it |

Zero business-logic coupling — every collection/DID/purpose value is a plain
parameter, not a hardcoded etzhayyim NSID. Per ADR-2607012200 the pure core
imports no vendor crypto SDK: the raw primitives (XChaCha20-Poly1305, Argon2id,
X25519/ML-KEM/ML-DSA, HKDF) are injected capabilities (`IAead`/`IKdf`/`IPq`)
bound via dynamic vars. The JVM BouncyCastle PQ provider is shipped from
`src/kotoba/lang/pqh/pq_bc.cljk`; the AEAD and KDF providers remain test
fixtures until a production consumer requires them.

## Provenance

Relocated 2026-07-01 from `etzhayyim/root:20-actors/etzhayyim-sdk/src/
{crypto,kdf,pq,did-signal,signal}.ts` to `kotoba-lang/pqh` per the
org-taxonomy library-placement rule (any library/substrate code belongs in
`kotoba-lang`, ADR-2606302300). Design authority remains ADR-2605181100
(AEAD envelope + Signal keywrap) and ADR-2606111300 (PQ hybrid layer),
both in `etzhayyim/root`.

Named `pqh` (the suite identifier the code already uses, "pqh-v1"), not
`crypto` — `kotoba-lang/crypto` already exists as an unrelated, independently
authored CLJC "foundational stdlib" repo (hash/HMAC/HKDF + a host-injected
AEAD *interface*, no cipher implementation). Different abstraction layer,
same domain name; a future CLJC port of this package could plausibly build
on that repo's primitives rather than duplicate them.

Former TS consumers (`etzhayyim-sdk`'s re-export shims, the karute app via
`@etzhayyim/sdk/signal`) consumed this package's now-deleted npm `dist/`. With
the TypeScript deleted per ADR-2607012200, those paths need reconciliation to
the Clojure implementation. The only in-tree source dependency was
`kotoba-lang/checkpointer`'s `src/checkpointer.ts`, which is itself ported to
Clojure in a follow-up step (ADR-2607012200 §Step-6); other references are
doc/ADR only.

The initial relocation was a **physical move only** (TypeScript unchanged).
A Clojure port then landed and is now the only implementation: the TypeScript
(`src/*.ts` + committed `dist/`) was deleted per ADR-2607012200 (the
`kotoba-lang` org's pure-Clojure admission rule), with the crypto primitives
moved behind injected-capability seams (`IAead`/`IKdf`/`IPq`).

## Clojure port

`src/kotoba/lang/pqh/{crypto,kdf,pq,did_signal,signal,util}.cljc` is a port
of the five former TS modules (plus a shared `util.cljc` byte/UTF-8/time
helper namespace), one namespace per file
(`kotoba.lang.pqh.{crypto,kdf,pq,did-signal,signal,util}`), following the
`kotoba.lang.*` namespace convention established by `kotoba-lang/crypto` and
`kotoba-lang/ipfs`. Per ADR-2607012200 the pure core imports no vendor crypto
SDK: the raw primitives are injected capabilities (`crypto/IAead`,
`kdf/IKdf`, `pq/IPq`) bound via dynamic vars, with JVM BouncyCastle host
impls in `test/kotoba/lang/pqh/{aead,kdf,pq}_bc.clj`. The "crypto library
choices" below name the BouncyCastle primitives those host impls wrap (and
that the test-suite parity vectors were verified against); the JDK
`java.security` (MessageDigest/SecureRandom) used by `util.cljc` /
`did_signal.cljc` is platform, not vendor.

**`.cljc` status (updated, closes the earlier JVM-only gap).** `kdf.cljc`
and `pq.cljc` are genuinely dual `:clj`/`:cljs` today: both are pure
orchestration over their injected seam (`IKdf`/`IPq`), so nothing in
either file needs the raw Argon2id/X25519/ML-KEM/ML-DSA math itself.
`crypto.cljc`'s seam bookkeeping, `generate-key`/`generate-nonce`,
`key-id-of`, `pick-bucket`, and ISO/IEC-7816-4 `pad-iso7816`/
`unpad-iso7816` are real `:cljs` too (pure arithmetic over `util.cljc`'s
portable byte-array helpers). `signal.cljc` is fully dual at the
orchestration level (it has no direct `java.*`/`js.*` calls of its own).

What's still `:clj`-only, with a throwing `:cljs` stub (not silently
scoped out — see each namespace's docstring): **(1)** `crypto.cljc`'s
HChaCha20 subkey derivation + the XChaCha20-Poly1305 pipeline
(`xchacha20poly1305-encrypt`/`-decrypt`) and its dag-cbor-dependent
`encrypt`/`decrypt` — HChaCha20's fixed-width 32-bit-wraparound math
(`unchecked-add-int`, `Integer/rotateLeft`) would need a from-scratch
ToInt32-coerced cljs rewrite this repo has no build/test tooling to verify
byte-for-byte, and `encrypt`/`decrypt` call `cbor.core`
(`kotoba-lang/dag-cbor`), itself a JVM-only `.clj` peer lib with no cljs
port yet; **(2)** `did-signal.cljc`'s signing/verification functions
(everything except `signal-identity-fingerprint`), which delegate to the
peer libs `ed25519.core` (`kotoba-lang/ed25519`) and `cbor.core`
(`kotoba-lang/dag-cbor`) — both JVM-only `.clj`, so this namespace cannot
be genuinely dual until those peer libs are ported too, independent of any
work done here; **(3)** `util.cljc`'s `sha256` — JVM's
`MessageDigest.digest()` is synchronous but the only browser primitive
(`SubtleCrypto.digest`) is Promise-based, so a same-signature cljs port
needs a hand-rolled pure-JS SHA-256 (e.g. `@noble/hashes`) this repo has
no tooling to verify.

The underlying reason these three are hard is unchanged from the original
scope decision below: **every one of this package's five modules needs at
least one primitive with zero Web Crypto browser coverage**
(XChaCha20-Poly1305 AEAD, Argon2id, and ML-KEM-768/ML-DSA-65 all have no
native `SubtleCrypto` primitive), so a *host* cljs implementation of
`IAead`/`IKdf`/`IPq` (via `@noble/ciphers`/`@noble/hashes`/
`@noble/curves`+`@noble/post-quantum`) is still a separate, unattempted
undertaking — this update makes the *core* genuinely portable per
ADR-2607012200 ("no unguarded `java.*`/`js.*` in core"; a `.cljc` file that
`require`s cleanly under both readers), it does not yet ship a working
browser host. `did-signal.cljc`'s Ed25519-only baseline path remains the
best future cljs candidate (Ed25519 sign/verify is in the current Web
Crypto spec) once `ed25519.core`/`cbor.core` are ported — a well-scoped
follow-up, not attempted unverified here.

**Crypto library choices (JVM):**

- **AEAD (`crypto.cljc`, BC host impl in `aead_bc.clj`)** — XChaCha20-Poly1305 is composed from two pieces:
  HChaCha20 subkey derivation (hand-rolled, ~30 lines, matching
  `@noble/ciphers`' exported `hchacha()` function instruction-for-instruction)
  plus Bouncy Castle's standard RFC 8439 `ChaCha20Poly1305` AEAD
  (`bcprov-jdk18on`, `org.bouncycastle.crypto.modes.ChaCha20Poly1305`) for the
  inner 12-byte-nonce step. Bouncy Castle 1.79 does not expose XChaCha20
  directly, so composing it from HChaCha20 + standard ChaCha20-Poly1305 (the
  documented, standard construction) was the right call over vendoring a
  second AEAD library.
- **KDF (`kdf.cljc`, BC host impl in `kdf_bc.clj`)** — Bouncy Castle's `Argon2BytesGenerator` +
  `Argon2Parameters.Builder(ARGON2_id)`, version `ARGON2_VERSION_13`.
- **Ed25519 (`did_signal.cljc`)** — delegates to the peer library
  `kotoba-lang/ed25519` (`ed25519.core`, a git dependency) rather than
  reimplementing Ed25519 or reaching for Bouncy Castle: JDK's own
  `java.security.KeyPairGenerator.getInstance("Ed25519")`, driven through a
  seeded `SecureRandom`, does **not** reproduce the RFC 8032 public key for
  that seed (verified independently this session on a parallel port); Bouncy
  Castle's `Ed25519PrivateKeyParameters`/`Ed25519Signer` do work, but
  `kotoba-lang/ed25519` already solves this correctly with a *different*
  technique (PKCS8-wrapping the raw seed directly and driving JDK's own
  `KeyFactory`/`Signature` — no BouncyCastle, babashka-friendly) and is
  reused here rather than duplicated. This port independently re-verified
  `ed25519.core`'s `pubkey-from-seed`/`sign`/`verify` against
  `@noble/curves/ed25519` byte-for-byte (not just against its own JCA
  self-check).
- **X25519 / ML-KEM-768 / ML-DSA-65 (`pq.cljc`, BC host impl in `pq_bc.clj`)** — Bouncy Castle
  (`org.bouncycastle.crypto.params.X25519*`,
  `org.bouncycastle.pqc.crypto.mlkem.*`,
  `org.bouncycastle.pqc.crypto.mldsa.*`). HKDF-SHA256 (the KEM combiner) is
  BC's `HKDFBytesGenerator`.
- **Canonical CBOR** (`crypto.cljc`'s plaintext envelope, `did_signal.cljc`'s
  signing bytes) — delegates to the peer library `kotoba-lang/dag-cbor`
  (`cbor.core`, a git dependency), not reimplemented.

**What was cross-verified byte-for-byte** against this repo's own npm deps
(never against a hand-typed hex literal — every vector is programmatically
generated with `node:crypto`'s `randomBytes`, per this session's own
"don't hand-transcribe hex" lesson): XChaCha20-Poly1305 ciphertext+tag
(`@noble/ciphers`), Argon2id output (`@noble/hashes`), Ed25519 public key +
signature (`@noble/curves`), canonical dag-cbor encoding (`@ipld/dag-cbor`),
X25519 shared secret (`@noble/curves`), HKDF-SHA256 output (`@noble/hashes`),
ML-KEM-768 decapsulated shared secret + key encodings (`@noble/post-quantum`),
and ML-DSA-65 keygen-from-seed (public key AND full encoded secret key) plus
cross-verification of a `@noble/post-quantum`-signed message under a
Bouncy-Castle-loaded public key. The vectors live in
`test/kotoba/lang/pqh/vectors.edn`; regenerate with
`node scripts/gen-cross-lang-vectors.mjs > test/kotoba/lang/pqh/vectors.edn`.

**One documented, deliberate API divergence.** `pq.ts`'s
`generateMlDsaKeyPair` returns a `secretKey` in `@noble/post-quantum`'s FIPS
204 *expanded* encoding (4032 bytes for ML-DSA-65). This port's
`generate-ml-dsa-key-pair` instead returns `:secret-key` as the 32-byte FIPS
204 *seed*. This was a *found*, not assumed, constraint: Bouncy Castle
1.79's `MLDSAPrivateKeyParameters(params, seed)` constructor (32-byte input)
was verified to reproduce noble's public key **and** its full expanded
secret-key encoding byte-for-byte for the same seed — but the *same class'*
single-byte-array constructor, given a full 4032-byte expanded key instead
of a seed, does **not** reconstruct a signing-capable key, even when
round-tripping Bouncy Castle's *own* freshly-generated key through its own
`getEncoded()`. (That isolation test — BC-own-keygen → `getEncoded()` →
re-`MLDSAPrivateKeyParameters` → sign → verify-with-original-pubkey — is
what confirmed this is a real constructor-scope limitation, not a
noble-compatibility gap.) The seed representation is also FIPS 204's own
NIST-recommended canonical storage form, and `pq.ts` itself always derives
from a seed internally (`randomBytes(32)` when the caller doesn't supply
one) — this port just retains that seed instead of discarding it. Secret
keys never cross the wire in this package's actual protocol (only
`publicKey`, ciphertexts, and signatures do, and all three of those ARE
byte/verification-compatible with noble), so this divergence is contained;
it is called out explicitly in `kotoba.lang.pqh.pq`'s namespace docstring.

**Nothing was scoped out silently.** Every primitive this package uses
(XChaCha20-Poly1305, Argon2id, Ed25519, ML-KEM-768, ML-DSA-65, X25519,
HKDF-SHA256, canonical dag-cbor) was independently verified against this
repo's own npm dependencies before being relied on; none was shipped on the
strength of a memorized spec or an assumption about a library's behavior.

## Development

```bash
kbb -M:lint      # clj-kondo (errors fail)
kbb -M:test      # cognitect test-runner (binds the BouncyCastle host impls)
```

Cross-language known-answer vectors (`test/kotoba/lang/pqh/vectors.edn`) can
be regenerated from the @noble reference libs with
`node scripts/gen-cross-lang-vectors.mjs` (install `@noble/ciphers`,
`@noble/hashes`, `@noble/post-quantum`, `@noble/curves`, `@ipld/dag-cbor`
ad hoc — the committed vectors are the source of truth; the script is
provenance for how they were generated).

## License

Apache 2.0 + Charter Compliance Rider v3.6 (`/CHARTER-RIDER.md`).
