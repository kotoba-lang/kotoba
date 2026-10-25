# ed25519-clj

[![CI](https://github.com/kotoba-lang/ed25519/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/ed25519/actions/workflows/ci.yml)

**Recover an Ed25519 public key (and its `did:key`) from a raw 32-byte seed — in
pure Clojure, no BouncyCastle, no native code, babashka-friendly.**

The JVM's JCA `Ed25519` provider can *sign* with a PKCS8 seed and *verify* with an
X.509 SPKI public key, but it offers **no way to derive the public key from a raw
seed**. On babashka / GraalVM it's worse: the `EdEC*` interface classes aren't on
the image and BouncyCastle isn't on the path. So if you're holding a raw seed — a
stored signing key, a wallet or tenant secret, a `did:key` you need to reconstruct —
you're stuck generating a throwaway keypair or pulling in a heavy dependency.

This library does the derivation directly, per **RFC 8032 §5.1.5 (edwards25519)**:

```
A = clamp(SHA-512(seed)[0..32]) · B
pubkey = compress(A)
```

using **only `java.security.MessageDigest` (SHA-512) + `BigInteger`** — it runs
anywhere Clojure and SHA-512 do, **babashka included**.

## Install

deps.edn (git dep):

```clojure
io.github.com-junkawasaki/ed25519-clj {:git/sha "<sha>"}
```

## Use

```clojure
(require '[ed25519.core :as ed])

(ed/pubkey-from-seed seed-bytes)        ;=> ^bytes (32)   raw public key
(ed/seed-hex->pubkey-hex "9d61b1…")     ;=> "4bafa390…"   hex → hex
(ed/did-key-from-seed seed-bytes)       ;=> "did:key:z6Mk…"
(ed/did-key-from-seed-hex "9d61b1…")    ;=> "did:key:z6Mk…"

;; sign / verify / parse
(ed/sign seed-bytes msg-bytes)          ;=> ^bytes (64)  Ed25519 signature
(ed/verify pub-bytes msg-bytes sig)     ;=> true
(ed/verify-did "did:key:z6Mk…" msg sig) ;=> true   (signer identified by did:key)
(ed/did-key->pubkey "did:key:z6Mk…")    ;=> ^bytes (32)  the inverse of did-key-from-pub

;; vector-free correctness check: sign with PKCS8(seed), verify under the derived pubkey
(ed/verify-derivation seed-bytes)       ;=> true
```

Also exposed: `did-key-from-pub`, `private-from-seed` / `public-from-raw` (JCA
key objects from raw bytes), `hexify` / `unhex`, `b58`, and the field constant `P`.

## Correctness

`kbb -M:test` runs two independent oracles, neither relying on a
memorized RFC table:

1. **JCA oracle** — generate keypairs with the JVM's own conformant RFC-8032
   provider, pull out the seed (PKCS8 tail) and pubkey (SPKI tail), and assert the
   derivation reproduces the provider's pubkey byte-for-byte across many keys.
2. **Fixed regression vector** — one JCA-verified `(seed → pubkey)` pair, so a
   refactor that breaks determinism fails loudly.

```
$ kbb -M:test
Ran 11 tests containing 71 assertions.
0 failures, 0 errors.
```

Two invocations this section used to name are **unavailable**, and neither is
replaced by the other:

- `kbb -M:test` — babashka was retired as this workspace's script host
  (ADR-2607173000) and the conversion left `scripts/tasks.edn` empty, so it has
  had no runnable path since 2026-07-17 (ADR-2608131600). The recovered
  babashka body is in `scripts/tasks-complex.edn`.
- `kbb -X:test` — the `:test` alias supplies `:main-opts`, not `:exec-fn`,
  so `-X` exits with "No function found on command line or in :exec-fn". Use
  `-M:test`. (Both measured 2026-08-13; the transcript above is the real
  `-M:test` output, replacing a stale 6-test/31-assertion one.)

## Why "no BouncyCastle"

Adding BouncyCastle (or `tink`, or a JNI binding) works on the JVM but defeats the
point on babashka/GraalVM native images and bloats the dependency graph for what is,
mathematically, one scalar multiplication. This is ~120 lines of stdlib Clojure.

## Selfhost (amu, no host crypto)

`kotoba/ed25519/selfhost.kotoba` is SHA-512 (FIPS 180-4) and Ed25519
(RFC 8032) in the Amu selfhost seed subset. A loaderless static image built
by the amu root compiler can use it to derive a public key from a seed, sign
and verify, with no JVM, no Node.js and no host crypto. Linear JUN-326 is the
tracking issue. The itonami node management plane uses it to sign its L1
intent and L2 observations (com-junkawasaki/root ADR-2610222140).

- The arithmetic is TweetNaCl's:
  - a field element is 16 limbs of 16 bits in a `:vector-i64`;
  - scalars are reduced on byte limbs;
  - every product fits an i64.
- `verify?` also checks S < L, which RFC 8032 requires and TweetNaCl does not.
- `sign-into` writes the signature into a 64-byte vector the caller owns.
- **Memory.** A static image frees nothing by itself, and one verify
  allocates about 8 MiB. `verify?` runs inside `(arena-scope ..)`, which
  releases all of it when the bool comes back. `sign-into` does the same
  around `sign`. A long-lived image can therefore verify and sign without
  growing. `sign` and `public-from-seed` return vectors, which cannot leave a
  scope, so use them for one-off work.
- Bytes are `:vector-i64` of 0..255; `hex-bytes` reads lowercase hex.
- `test-*` check the FIPS 180-4 SHA-512 vectors and the RFC 8032 §7.1 vectors
  (public keys and signatures). The vectors were checked with RFC 8032's own
  §6 reference code.
- The tests also refuse altered signatures, messages and keys, and the
  malleable S + L.

Gate (no JVM, Node.js, nbb or babashka):

```bash
AMU=../amu; G=$(mktemp -d)   # G must be under a path podman can mount
cp "$AMU/seed/bootstrap/aarch64-linux-static-root.elf" "$G/root.elf"
F=kotoba/ed25519/selfhost.kotoba
{ echo '(ns ed25519-gate (:export [main]))'
  tail -n +$(( $(grep -n 'test-sha512 test-public test-sign test-verify test-sign-into\]))' $F | cut -d: -f1) + 1 )) $F
  cat <<'EOF'
(defn main [] :i64
  (+ (if (test-sha512) 1 0) (+ (if (test-public) 2 0)
  (+ (if (test-sign) 4 0) (+ (if (test-verify) 8 0) (if (test-sign-into) 16 0))))))
EOF
} > "$G/gate.kotoba"
podman run --rm --platform linux/arm64 --network none -e KEXE_CAP_RESOURCES_35="$G" \
  -v "$G:$G" -w "$G" docker.io/library/python:3.12-alpine sh -c \
  "./root.elf compile $G/gate.kotoba --target aarch64-linux --output $G/gate.elf --format static \
   && chmod +x gate.elf && KEXE_STRUCTURED_REPORT=1 ./gate.elf"
#   → {:status :ok :result 31 ...}      (31 = all five test-* true)
```

The first measurement was on 2026-10-23 with the root of amu `1585cb48`
(sha256 `98d4bcb7…b774`), before `sign-into`: `:result 15`. Remeasured the
same day with the root of amu `457042ab` (sha256 `1739f52f…682e`):
`:result 31`. Two negative controls:

- Folding the field product with 37 in place of 38 gives `1`: only SHA-512
  still passes.
- Dropping the S < L check gives `23` (`7` before `sign-into`): the S + L
  case is then accepted.

**Memory gate.** Use the same body with this `main`, which does 32 verifies
and 8 signs into one vector:

```clojure
(defn main [] :i64
  (let [out (bzero 64)
        v (loop [i 0 ok 0] (if (= i 32) ok (recur (inc i) (if (verify? (pk1) (bzero 0) (sig1)) (inc ok) ok))))
        s (loop [i 0 ok 0] (if (= i 8) ok (let [z (sign-into out (seed1) (bzero 0))] (recur (inc i) (if (bytes=? out (sig1)) (inc ok) ok)))))]
    (+ v s)))
```

Run it under `busybox time -v` in `alpine:3`. It reports `:result 40` and a
maximum resident set of 8,508 KiB. The controls replace one
`(arena-scope` with `(do`, using sed on `^  (arena-scope$` and
`^    (arena-scope$`:
- with `verify?` unscoped, the peak is 273,852 KiB;
- with `sign-into` unscoped, it is 66,364 KiB.

The results are the same in both controls. Only the memory differs.

The receipts are `docs/evidence/selfhost-gate-20261023.edn` (the first
measurement) and `docs/evidence/selfhost-memory-20261023.edn`. The `.cljk`
library is unchanged and does not call this module.

## License

Apache-2.0.

## Signing and verification (RFC 8032)

```clojure
(require '[ed25519.sign :as ed])

(def sk (ed/secret-key! seed))       ; 32 random bytes in
(:public sk)                          ; 32 bytes
(def sig (ed/sign sk message))        ; 64 bytes
(ed/verify (:public sk) message sig)  ; true / false
```

`ed25519.core` — this library's older half — derives keys and encodes them
(PKCS8, SPKI, did:key, base58) and reaches the **platform's** signer through a
reader conditional. That is fine where a platform signer exists and is nothing
at all where one does not. Measured across the 193 repositories in this
workspace declaring `@noble/curves`, the consumers call `sign` 193 times and
`verify` 131; neither had a first-party implementation until now.

### What it is and is not

**PureEd25519 only.** RFC 8032 also defines Ed25519ph and Ed25519ctx; both
take a domain-separation prefix this does not build, and adding them without a
consumer would ship two untested code paths that look interchangeable with
this one and are not.

**Signatures are deterministic** — the nonce comes from the private key and
the message, which is the specification's design and why there is no
ECDSA-style catastrophe from a repeated one.

**`verify` rejects `S >= L`** (§5.1.7). Without it, `S + L` is a second valid
signature for the same message and key, which breaks anything treating a
signature as an identifier — a deduplication key, a transaction id.

**`verify` returns `false` for every rejection**, never throws and never
distinguishes *which* part of a forgery attempt was wrong.

**Not constant-time.** Timing is a property of machine code and no portable
Clojure controls it. Where a timing side channel is in scope, use the
platform's Ed25519 and treat this as the reference it is checked against.

### The constants were derived

`d = -121665/121666`, `sqrt(-1) = 2^((p-1)/4)`, the base point's `y = 4/5`
with `x` recovered from the curve equation, and `L` itself. All were computed
with arbitrary precision and checked against the published values before being
written into the source.

The field arithmetic is `kotoba-lang/org-ietf-x25519`'s — the same
GF(2^255-19) — rather than a second copy of it. Only the curve is new.

### Verify

```sh
kbb -M:test     # RFC 8032 §7.1 and the rejection suite
kbb -M:oracle   # + differential against BouncyCastle
kbb --backend sci --classpath "$(kbb -A:test -Spath)" run-tests.cljk
```

All four RFC 8032 §7.1 vectors, **independently reproduced with BouncyCastle
1.78.1 before being written here**. Every single-bit flip in a signature (512
cases) and in a public key (256) rejected. `S + L` rejected. Then a
differential sweep: 30 key derivations, 140 signatures across message lengths
that straddle SHA-512's 111-byte padding boundary, 12 cases where
**BouncyCastle verifies what this signs**, and 12 where **this verifies what
BouncyCastle signs** — the second direction being what exercises point
decoding and the square root inside it.

| break | assertions turned red |
|---|---|
| scalar reduction truncates instead of flooring | **175** |
| one limb of `d` | **18** |
| the `S < L` check removed | **1** |

The ClojureScript run takes about four minutes: 768 verifications at roughly
two scalar multiplications each, and a scalar multiplication is ~150 ms there.
The JVM suite is seconds. That is the same not-constant-time, not-fast
reference implementation the note above describes.
