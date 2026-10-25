# kotoba-lang/org-ietf-chacha20-poly1305

**[RFC 8439](https://www.rfc-editor.org/rfc/rfc8439) — ChaCha20, Poly1305 and
AEAD_CHACHA20_POLY1305 — in portable `.cljc`, with no dependencies.**

`kotoba-lang/noise` reaches this cipher through
`provider/{jvm.clj, noble.cljs, node.cljs}`: the AEAD is *host-injected*
there, not implemented. The workspace's dependency ledger recorded
ChaCha20-Poly1305 as available on that basis, and it was a call site rather
than an implementation. HPKE (RFC 9180) needs one AEAD it can actually run.

## Use

```clojure
(require '[chacha20.aead :as aead])

(aead/seal! key nonce aad plaintext)   ; -> ciphertext ++ 16-byte tag
(aead/open! key nonce aad sealed)      ; -> plaintext, or an :error
```

| namespace | |
|---|---|
| `chacha20.aead` | `seal` `open` `seal!` `open!` — RFC 8439 §2.8 |
| `chacha20.xchacha` | `seal` `open` `xchacha20poly1305` — XChaCha20-Poly1305 (24-byte nonce; cljs noble shim) |
| `chacha20.core` | `block` `encrypt` `hchacha-subkey` — the cipher, §2.3–2.4 |
| `chacha20.poly1305` | `mac` `clamp` — the one-time authenticator, §2.5 |
| `chacha20.word` | 32-bit words, the only file that knows the runtime |

`key` is 32 bytes, `nonce` 12. Bytes are `Sequential` collections of ints in
0..255.

## Three rules the format depends on

**The nonce must never repeat under one key.** ChaCha20 is a stream cipher:
two messages under the same key and nonce expose their exclusive-or, and the
Poly1305 one-time key comes from the same pair, so a repeat also reveals `r`
and forgery becomes arithmetic rather than search. Nothing here can check
that — it is a property of your counter.

**`open` returns no plaintext on failure**, not even partially. The tag
comparison reduces over all sixteen bytes rather than stopping at the first
difference.

**This is not constant-time.** Timing is a property of machine code and no
portable Clojure can promise what two JITs emit. Where a timing side channel
is in scope, use the platform's implementation and treat this as the
reference it is checked against.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
kbb -M:oracle                                                      # + differential vs BouncyCastle
```

RFC 8439 §2.3.2, §2.4.2, §2.5.2 and §2.8.2 verbatim, every single-bit flip in
a sealed message rejected, and 75 AEAD plus 16 Poly1305 differential
comparisons against BouncyCastle 1.78.1.

## The bug that got through everything except the differential run

The final `h + s` of §2.5.1 is **ordinary addition truncated to 128 bits**,
not addition in the field. Folding a carry out of bit 130 back in as five —
which is correct *everywhere else in Poly1305* — makes the tag exactly five
too large whenever the sum crosses 2^130. Measured: about one input in
thirteen.

It survived **272 assertions**, the RFC's own §2.5.2 vector, and the entire
AEAD suite — because the AEAD's Poly1305 input is always padded to a multiple
of sixteen bytes, and those particular inputs did not cross. Only a
differential run over a spread of message *lengths* saw it.

**The first regression test written for it did not catch it either.** Eight
tags at lengths that are not multiples of sixteen, and all eight happened to
fall in the safe region — a negative test that could not fail. The six
vectors now in the suite were *searched for*: the broken version was run
against BouncyCastle over 300 candidates and the 23 that disagreed were kept.
Reintroducing the wrap turns all six red, and that was measured rather than
assumed.

## The arithmetic, and why these limbs

Poly1305 works modulo 2^130 - 5, which neither runtime has a type for. The
usual implementation (poly1305-donna) uses five 26-bit limbs and 64-bit
intermediates — correct on the JVM and **not exact under ClojureScript**,
where the products reach about 2^56 and a number stops being an exact integer
at 2^53.

The limbs here are **thirteen of ten bits**, which is 130 exactly. A product
of two limbs is under 2^20, a column sum of thirteen under 2^24, and the fold
that follows multiplies by five — nothing approaches 2^53. The modulus
falling on a limb boundary is also what makes the reduction a single
multiply-by-five rather than a shift and mask across a limb.

## Not here

**ChaCha20 with a 64-bit nonce** (the original construction, before RFC 8439
fixed the split at 96/32). Nothing in this workspace speaks it.
