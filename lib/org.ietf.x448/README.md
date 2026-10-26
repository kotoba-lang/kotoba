# kotoba-lang/org-ietf-x448

**X448 — [RFC 7748](https://www.rfc-editor.org/rfc/rfc7748) — in portable
`.cljc`.** No dependencies.

```clojure
(require '[x448.core :as x])

(x/public-key private-56-bytes)     ; => 56 bytes
(x/x448 private peer-public)        ; => {:status :ok :bytes …}
(x/contributory? shared)            ; => false when the result is all zeroes
```

The same shape as `kotoba-lang/org-ietf-x25519`, deliberately, so a caller
holding a Diffie-Hellman as a value can hold either. This exists for
`org-ietf-hpke`: RFC 9180 names DHKEM(X448, HKDF-SHA512) as one of its five
KEMs.

## The modulus is computed, not written down

`p = 2^448 - 2^224 - 1` is 135 decimal digits. The first draft of this
library wrote it out as a literal, split across four string chunks — and it
was a different number, 166 digits long. Every RFC vector and all 510
Wycheproof cases failed at once.

That is the *good* outcome. A mistyped 135-digit modulus mostly fails
loudly; the one that would not is a modulus that is still prime and still
about the right size, and then the library computes in a different field and
agrees with nothing while looking healthy.

So it is not written down. `p` is `(bsub (bsub (pow2 448) (pow2 224)) one)`,
and it is checked from the other side: `2^448 ≡ 2^224 + 1 (mod p)` computed
with `mod-pow`, which does not go near the subtraction that defines it, plus
Fermat on five bases.

`kotoba-lang/org-nist-ecc` cannot do this — `b`, `gx`, `gy` and `n` have no
closed form — and pays for it with structural assertions instead. Here there
is a closed form, and the cheapest way to not mistype a number is to not type
it.

## Clamping, and the bit that is not there

RFC 7748 §5 clears the two low bits of the scalar and sets the top one.
Clearing the low bits puts the scalar in the prime-order subgroup, so a
small-order public key cannot leak the low bits of the private one; setting
the top bit fixes the ladder's length. `x448` clamps what it is given, so a
caller cannot skip it by accident.

X25519 *also* masks bit 255, because its field is 255 bits inside 32 bytes
and the spare bit must go. X448's field fills its 56 bytes exactly, so there
is no spare bit — masking one would clear a bit that means something.

## The all-zero result

A shared secret of all zeroes means the public key had small order and the
result carries nothing of the private key. RFC 7748 §6.1 leaves the check to
the caller; RFC 9180 §7.1.4 requires it. So it is `contributory?`, a separate
predicate, rather than an error inside `x448` — the same split
`org-ietf-x25519` makes, and for the same reason: a caller who wants the raw
value should be able to have it.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

**1,107 assertions on both runtimes.**

RFC 7748's own vectors: both §5.2 scalar multiplications, the 1- and
1,000-iteration chains, and §6.2's full Diffie-Hellman from both sides. The
million-iteration vector is not run — it is the same code path a thousand
times more, and it would dominate the suite for no new information.

### The corpus is Wycheproof, whole

`test/x448/wycheproof.cljk` is **generated** by
`scripts/extract_wycheproof_x448.cljk` from `x448_test.json`, pinned by
sha256 (`0f8f7199…0fe5`). All **510** cases, no sampling.

| | |
|---|---|
| `Twist` | **234** u-coordinates not on the curve — X448 is x-only, so the ladder computes in the twist group and returns a value |
| `EdgeCaseMultiplication` | 406 ladder edge cases |
| `LowOrderPublic` | 14 |
| `ZeroSharedSecret` | 11 |
| `NonCanonicalPublic` | 5 — legal, because RFC 7748 reduces a u-coordinate mod p on decode |
| `PublicKeyTooLong` | 12, the only ones this refuses |

245 of them are marked `acceptable`, which does **not** mean "may be wrong".
It means an implementation may legitimately refuse the input. This one
computes and exposes the refusal separately as `contributory?`, so the
corpus's `shared` value is asserted for all 498 well-formed cases and the
policy is a caller's to set.

### What the suite discriminates

| break | failures | which tests go red |
|---|---|---|
| decode big-endian instead of little | **519** | everything |
| clear the scalar's top bit instead of setting it | **498** | the RFC vectors, the corpus, and the clamp test |
| `a24` off by one (39082) | **495** | the RFC vectors and the corpus |
| clear one low bit instead of two | **6** | the RFC vectors and the corpus |
| skip clamping entirely | **11** | the RFC vectors and the corpus |
| `contributory?` always true | **11** | the all-zero test **only** |
| *(restored)* | **0** | none |

One attempted break is worth recording because it produced **zero**
failures: masking bit 7 off before setting it,
`(bit-or (bit-and x 0x7F) 0x80)`. That is the identity function, so the
"break" was green — and a green break reads exactly like a missing test. It
was a missing break. The clamp test now sweeps five top-byte values, and
clearing the bit for real turns 498 red.

## Not constant-time

`cswap` is a conditional swap in name only: the ladder's *shape* is constant,
but `java.math.BigInteger` and `BigInt` branch and allocate on the magnitude
of their inputs. No implementation over host big integers can claim
otherwise, and this one does not. Appropriate for protocol work on data the
process already holds; not for a setting where an attacker can measure this
process.

## Not here

**Ed448.** A different construction — signatures, a different encoding, a
different hash. `x448.fp` would be reusable for it; nothing in this workspace
needs it yet.

**A shared big-integer library.** `x448.fp` and `ecc.bignum` in
`org-nist-ecc` are the same idea at about the same size. The coupling would
be wrong-way-round — an RFC 7748 curve does not belong downstream of the NIST
prime curves — and this one is narrower: one fixed modulus, one fixed width.
Two copies is a fact; three is a pattern. **Extract on the third consumer.**
