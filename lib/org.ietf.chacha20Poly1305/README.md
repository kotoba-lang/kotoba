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

## Native port and gate (AWAI-117)

`kotoba/chacha20/{core,poly1305,aead}.kotoba` are RFC 8439 ChaCha20, Poly1305 and
AEAD_CHACHA20_POLY1305, and XChaCha20-Poly1305 (draft-irtf-cfrg-xchacha-03: `hchacha20`,
`xseal`, `xopen`, with a 24-byte nonce), written in native `.kotoba`; `aead` uses the existing
`chacha20.aead-params` for the length check. Bytes are `:vector-i64` of 0..255. A word
is an i64 in 0..2^32-1 masked after every operation, and Poly1305 keeps five 26-bit limbs
so no product or sum leaves the i64 range.

- `seal key nonce aad plaintext` gives ciphertext ++ tag, or an empty vector for a bad
  key or nonce length or a value outside 0..255 (a sealed empty plaintext is 16 bytes,
  so empty is unambiguous).
- `open key nonce aad sealed` gives the plaintext, or the one-element vector `[-1]` when
  the parameters are bad, the input is shorter than a tag or the tag does not verify. The
  tag comparison ORs the XOR of all 16 bytes, and nothing is decrypted before it passes.

`kotoba/chacha20/native_gate.kotoba` is generated by `tools/gen_gate.py` from
`tools/reference.py`, a Python RFC 8439 written from sections 2.1-2.8. The generator
asserts the reference against the RFC's printed values (sections 2.3.2, 2.4.2, 2.5.2,
2.8.2 and Appendix A.3 #5-#9) and the XChaCha draft's (2.2.1 and A.3.1), and OpenSSL 4.0.3 agreed (`enc -chacha20` on the 2.3.2
block and 2.4.2, `mac POLY1305` on 2.5.2 and A.3 #5-#9). The gate holds no strings, and
`main` returns a bitmask, 255 = pass:

1. the 2.3.2 block; 2. the 2.4.2 encryption; 4. 2.5.2 and A.3 #5-#9 (the `h >= p`
reductions); 8. the 2.8.2 seal, and open giving the plaintext back; 16. a changed
ciphertext, tag, AAD or nonce byte opening to `[-1]`; 32. Poly1305 and seal / open at 0,
1, 15, 16, 17, 63, 64, 65 and 129 bytes, and an empty plaintext with empty AAD; 64. the
refusals; 128. XChaCha20-Poly1305: the 2.2.1 subkey, the A.3.1 seal, open back, a changed
nonce byte opening to `[-1]` and a 23-byte nonce refused.

Built as modules (source paths and a KSL lock) and measured 2026-10-30 on Apple M1 Max
with the Amu Mac root of main `91faa123`:

| image | change | exit |
|---|---|---|
| gate | none | **255** |
| ctl-rotl | first quarter-round rotation 16 -> 15 | 84 |
| ctl-rounds | 9 double rounds instead of 10 (block and HChaCha20) | 84 |
| ctl-clamp | r limb 0 not clamped | 211 |
| ctl-final | the final `h >= p` subtraction skipped | 251 |
| ctl-tagcmp | open does not check the tag | 111 |
| ctl-hround | HChaCha20 outputs word 11 instead of 12 | 127 |
| ctl-lenpad | the ciphertext length field carries the AAD length | 87 |

Not yet: Wycheproof, and a measurement of timing.


**ChaCha20 with a 64-bit nonce** (the original construction, before RFC 8439
fixed the split at 96/32). Nothing in this workspace speaks it.
