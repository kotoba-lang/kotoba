# kotoba-lang/org-nist-ecc

**The NIST prime curves — P-256, P-384 and P-521 — and ECDH, in portable
`.cljc`.** No dependencies.

```clojure
(require '[ecc.curve :as curve] '[ecc.ecdh :as ecdh] '[ecc.bignum :as b])

(def c (:p256 curve/curves))
(ecdh/public-key c scalar)      ; => {:status :ok :bytes (0x04 || X || Y)}
(ecdh/ecdh c scalar peer-point) ; => {:status :ok :bytes X}
```

One implementation, three parameter sets. All three are short Weierstrass
with `a = p - 3`, so the doubling formula specialised for `a = -3` is not an
optimisation chosen for these curves — it is the reason these curves were
given that `a`.

This exists for `org-ietf-hpke`: RFC 9180 names five KEMs and three of them
are DHKEM over these curves.

## Two things the corpus does not cover, and what does

**Wycheproof never multiplies the base point.** It supplies both parties'
keys, so `gx` and `gy` could both be wrong and all 1,806 of its cases would
still pass. Measured: changing one digit of P-256's `gy` leaves the entire
corpus **green** and turns only the parameter invariants and the
`java.security` oracle red. Both of those exist for that reason.

**`scalar-mult` never reaches one branch of `add-points`.** Left-to-right
double-and-add adds `P` to a multiple of `P` that is never `P` itself, so the
tangent case cannot arise there. Measured: forcing that branch to `false`
left the whole suite green.

An earlier draft of this repository justified the `ecc.bignum` wrapper by
exactly that branch. The justification was wrong — not because the wrapper is
unnecessary, but because the branch nothing reaches is not the one the
wrapper protects. The branch is now reached from a test, and the wrapper's
docstring names the branch that actually breaks.

## Why `ecc.bignum` exists

It is the **only** file here with a reader conditional. Above it the curve
arithmetic is written once.

ClojureScript's arbitrary-precision integers are `BigInt`, and not all of
`cljs.core` knows that. Measured under nbb:

| | |
|---|---|
| `(+ (js/BigInt 3) (js/BigInt 4))` | `7n` — works |
| `(mod (js/BigInt -1) (js/BigInt 7))` | `6n` — works, and Euclidean |
| `(rem (js/BigInt 17) (js/BigInt 5))` | **throws** |
| `(even? (js/BigInt 4))` | **throws** |
| `(zero? (js/BigInt 0))` | **`false`** |

The last row is the reason. The two that throw announce themselves; `zero?`
returns a confident wrong answer, and `ecc.curve` asks it whether a Jacobian
`Z` is zero — which is how the point at infinity is represented. An
always-false `zero?` makes every addition take the general formula with
`Z = 0` substituted in. It does not throw and it does not return infinity; it
returns a point.

Measured: replacing `zero?` with a constant `false` turns **1,767**
assertions red across ten tests. The JVM run cannot see this class of bug at
all — every one of those predicates is correct there — so a version of this
library that called them directly would be green on the JVM and quietly
broken under ClojureScript.

`js*` is not available under nbb either, which evaluates rather than
compiles. The operations in that file are the ones that were checked, not the
ones that would be natural to write.

## The parameters are asserted, not trusted

They were read out of the JVM's own tables
(`scripts/extract_curve_params.cljk`) rather than typed from a document, and
then checked against properties no wrong constant survives:

| check | catches |
|---|---|
| `G` is on the curve | a wrong `b`, `gx` or `gy` |
| `n * G` is the point at infinity | a wrong `n` |
| `a = p - 3` | a wrong `a`, and pins the curve family |
| field length matches `p` | a wrong `p` |

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
kbb -M:oracle                                                      # + java.security
```

**5,331 assertions on the JVM.**

### The corpus is Wycheproof, whole

`test/ecc/wycheproof_ecdh.cljk` is **generated** by
`scripts/extract_wycheproof_ecdh.cljk` from the three
`ecdh_secp*_ecpoint_test.json` files, each pinned by sha256. All **1,806**
cases, no sampling — the generator refuses if a declared count and an
extracted count disagree, and the suite asserts it again at run time.

The `_ecpoint_` variant is the right one: its public keys are raw
uncompressed points, which is what RFC 9180 §7.1.1 serialises. The plain
`ecdh_secp*_test.json` wrap the same keys in ASN.1, and parsing DER to run a
curve test puts a parser between the corpus and the thing under test.

What those cases are:

| | |
|---|---|
| `EdgeCaseDoubling` | **1,399** additions that are really doublings |
| `EdgeCaseSharedSecret` / `EdgeCaseEphemeralKey` | 284 extreme representations |
| `InvalidCurveAttack` | **48** points not on the curve |
| `AdditionChain` | 44 scalars that stress the ladder |
| `CompressedPoint` / `WrongCurve` / `InvalidEncoding` | 31 malformed inputs |

**Every rejection is asserted by reason, and the reasons were measured rather
than guessed.** The compressed and wrong-curve points all fail on *length*,
because a compressed point is half a point plus a byte and the length check
runs first — so the prefix check needs a hand-made case or it is a branch
nothing reaches. It has one.

### What the suite discriminates

| break | failures | which tests go red |
|---|---|---|
| `zero?` answers `false`, as ClojureScript's does | **1,767** | ten tests, including the corpus and the oracle |
| return `y` instead of `x` from `ecdh` | **1,769** | the corpus and the oracle |
| skip the on-curve check | **88** | the invalid cases **only** |
| one wrong digit in P-256's `gy` | **4** | the parameter invariants and the oracle — **the corpus stays green** |
| never take the doubling branch | **3** | the branch test **only** |
| *(restored)* | **0** | none |

The bottom two rows are the ones worth reading. Neither is visible to 1,806
adversarial ECDH cases, and each needed a test written for it specifically.

## Why an invalid point must be refused

An unchecked public key lets a peer hand over something that is not on the
curve. The scalar multiplication then happens in whatever group that point
generates — and an attacker can choose a small one, read the result modulo
its order, and repeat with different small groups until the private scalar is
determined. The cofactor is 1 on all three curves, so on-curve and
not-infinity is the whole check; it is not optional, and `bytes->point` is
the only way in.

## Not here

**Signature malleability normalisation.** `(r, s)` and `(r, n-s)` are both
valid ECDSA signatures over the same message, and some protocols require the
lower `s`. MLS and TLS do not, so `verify` accepts both — and Wycheproof's
corpus agrees, which is why no case here turns on it. A protocol that needs
low-`s` must say so and check it; this does not decide for it.

**RFC 6979.** See above.

**Point compression.** RFC 9180 §7.1.1 serialises uncompressed, so a peer
cannot have sent anything else. Accepting an encoding no peer produces is
surface for nothing.

**Constant time.** `scalar-mult` is double-and-add and branches on the bits
of the scalar; `BigInteger` and `BigInt` branch and allocate on magnitude. No
implementation over host big integers can claim otherwise, and this one does
not. Appropriate for protocol work on data the process already holds; not for
a setting where an attacker can measure this process.

## ECDSA (`ecc.ecdsa`)

Signing and verification on all three curves, with DER-encoded signatures —
what RFC 8446 §4.2.3 and RFC 9420 §5.1.2 require.

```clojure
(require '[ecc.ecdsa :as ecdsa])
(ecdsa/verify c public-point digest der-signature)  ; => {:ecc/valid? true} | error
(ecdsa/sign   c private-scalar nonce digest)        ; => {:ecc/bytes der …}
```

### Verification is the direction that matters

A signature is checked far more often than it is made, by parties who did not
choose its bytes. Wycheproof agrees: of the **1,530** cases across these three
curves, **930 are invalid** — and most of those are malformed DER rather than
bad arithmetic.

All 1,530 run, and every rejection is asserted by reason. The refusals spread
across **sixteen** distinct reasons rather than one:

| | | | |
|---|---|---|---|
| `expected-integer` 330 | `r-out-of-range` 153 | `negative-integer` 105 | `signature-mismatch` 56 |
| `s-out-of-range` 50 | `length-too-large` 38 | `truncated` 36 | `indefinite-length` 33 |
| `trailing-bytes-in-sequence` 30 | `expected-sequence` 24 | `non-minimal-length` 20 | `trailing-bytes` 19 |
| `point-at-infinity` 15 | `reserved-length` 9 | `non-minimal-integer` 6 | `empty-integer` 6 |

A verifier that rejected everything for one reason would pass a test that only
checked "did it refuse". That distribution is what says these refusals
distinguish what they claim to.

### What the ECDSA tests discriminate

| break | failures | which tests go red |
|---|---|---|
| truncate every digest to 256 bits | **427** | the corpus, and the P-521 test |
| allow trailing bytes after the SEQUENCE | **14** | the corpus and the DER test |
| accept non-minimal INTEGERs | **8** | the corpus, the DER test, the reason spread |
| accept negative INTEGERs | **3** | the corpus and the DER test |
| skip the `r`/`s` range checks | **2 errors** | the corpus |

The range-check row is worth its own note: removing it does not produce wrong
answers, it produces **exceptions** — `s = 0` has no inverse, and without the
check that reaches the arithmetic. A range check on a peer's input is not
only a correctness rule; it is what keeps a malformed signature from becoming
a crash.

One attempted break produced zero failures and was not a break at all:
rewriting `(if (pos? excess) (shr x excess) x)` as `(shr x (max 0 excess))`.
Shifting by zero is the identity, so the two are the same function. The real
break — a fixed 256-bit truncation, correct for P-256 and wrong for the other
two — turns 427 red.

### DER strictness is a security property

If two byte strings decode to the same `(r, s)`, a system that records or
deduplicates signatures by their bytes sees two — and one can be replayed past
a check that already saw the other. That is what DER is *for*: exactly one
encoding per value. So `ecc.der` refuses non-minimal lengths and integers,
indefinite lengths, negative integers, and anything trailing.

### The nonce is a parameter

`k` is not generated here, for the same reason `hpke.dhkem/encap` takes its
ephemeral. It matters more here: **a repeated `k` under one key reveals the
private key** from two signatures, by elementary algebra. A test asserts the
hazard directly — two signatures with one `k` come out with identical `r`.

RFC 6979's deterministic derivation is not implemented. It would remove the
hazard rather than expose it, and it is a specification of its own.

### P-521 is where the digest truncation goes wrong

FIPS 186-4 takes the leftmost `bitlen(n)` bits of the digest. For P-256 with
SHA-256 that is all of it; for P-521 with SHA-512 the digest is **shorter**
than the order, so nothing is dropped — and a shift applied unconditionally
would corrupt every P-521 signature while leaving P-256 correct. Both
directions are asserted.
