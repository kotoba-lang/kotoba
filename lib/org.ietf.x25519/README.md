# kotoba-lang/org-ietf-x25519

**[RFC 7748](https://www.rfc-editor.org/rfc/rfc7748) X25519 — Diffie-Hellman
on Curve25519 — in portable `.cljc`, with no dependencies.**

Written because the workspace's dependency ledger named it. HPKE (RFC 9180)
is the last cryptographic gap that composes out of parts already here — HKDF
in `kotoba-lang/crypto`, ChaCha20-Poly1305 in `kotoba-lang/noise` — and
DHKEM(X25519) was the one piece missing. Every mention of x25519 in this
workspace was a call site; none was an implementation.

## Use

```clojure
(require '[x25519.core :as x])

(def priv (x/unhex "77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a"))
(x/public-key priv)          ; X25519(k, 9)
(x/x25519! priv their-pub)   ; 32 bytes
(x/contributory? shared)     ; false when the peer sent a low-order point
```

Bytes are `Sequential` collections of ints in 0..255, in and out. `x25519`
returns `{:status :ok :bytes […]}` or `{:status :error :reason kw}`;
`x25519!` throws. The reason keywords — `:bad-scalar-length`,
`:bad-u-length` — are contract.

## Two things to know

**An all-zero output means a low-order point.** RFC 7748 §6.1: a peer can
send a u-coordinate of small order and the shared secret is then zero
whatever your private key is. `x25519` returns those bytes, because the RFC
makes the check optional and where it belongs depends on the protocol —
`contributory?` is here so a caller who needs it writes one call rather than
a comparison against a 32-byte literal, which is the kind of thing that gets
written once and copied wrong.

**This is not constant-time.** The ladder swaps with an arithmetic mask and
the field avoids branching on secret values where it reasonably can, but
timing is a property of machine code and no portable Clojure can promise
anything about what two JITs emit. Where a timing side channel is in scope,
use the platform's X25519 and treat this as the reference it is checked
against. About 76 ms per scalar multiplication on the JVM, against roughly
50 µs for a native implementation.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
kbb -M:oracle                                                      # + differential vs BouncyCastle
```

**Known answers**: RFC 7748 §5.2 and §6.1 verbatim, the one-round and
thousand-round values of §5.2's iteration, and the all-zero results for
low-order u. **Every one was reproduced with BouncyCastle 1.78.1
(`org.bouncycastle.math.ec.rfc7748.X25519`) before this implementation was
written** — the oracle existed before the code rather than being fitted to it.

**Differential**: `kbb -M:oracle` runs 40 comparisons against
BouncyCastle over a fixed LCG spread, plus 20 on the base point, plus the
thousand-round vector — which lives there rather than in the fast suite
because at 76 ms a multiplication it is over a minute. BouncyCastle is scoped
to the alias and never reaches `:deps`.

**Both runtimes.** The field is a `long-array` on the JVM and a
`Float64Array` here, and those hold intermediates differently: a JVM long
wraps at 2^63 while a JavaScript number stops being an exact integer at 2^53.
Every product and carry is sized to stay under the smaller.

Truncating the carry instead of flooring it — the one-line defect the field's
own docstring warns about — turns **65 assertions red**. That was measured.

## How the arithmetic is done, and the 230× that was hiding in it

A field element is sixteen limbs of sixteen bits in a flat array. The JVM has
`BigInteger` and ClojureScript has `BigInt`, and they are not the same type
with the same operations, so a portable file cannot name either. Limbs need
neither.

`aget` with a **boxed index falls back to reflection**. `rd` is the innermost
operation here — about 650,000 calls per scalar multiplication — and without
`(int i)` one X25519 took **24 seconds**. With it, 105 ms; with the hot
multiply loop's array access written out rather than routed through `rd`,
76 ms. The correctness of the result never changed, which is why this is a
comment in the source and a paragraph here rather than something a test
could have caught.

## Not here

**X448.** RFC 7748 defines it too, over a different prime with a different
limb layout — a second field implementation, not a parameter. Nothing in this
workspace asks for it.

**Ed25519 signing.** Same curve, different representation and a different
RFC (8032). `kotoba-lang/org-ietf-ed25519` owns key encoding and did:key for
that side.
