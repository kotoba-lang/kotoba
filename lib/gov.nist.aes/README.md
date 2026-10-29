# kotoba-lang/org-nist-aes

**AES ([FIPS 197](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.197-upd1.pdf))
and AES-GCM ([NIST SP 800-38D](https://doi.org/10.6028/NIST.SP.800-38D)) in
portable `.cljc`.** No dependencies.

128, 192 and 256-bit keys. Any IV length. 128-bit tags.

```clojure
(require '[aes.gcm :as gcm])

(gcm/seal key iv aad plaintext)
;; => {:status :ok :bytes (ct ++ tag) :ciphertext … :tag …}

(gcm/open key iv aad sealed)
;; => {:status :ok :bytes plaintext}
;;  | {:status :error :reason :authentication-failed}
```

`seal` and `open` mirror `chacha20.aead` exactly, so a caller that holds an
AEAD as a value can hold either. That is what this repository is for: RFC
9180 names three AEADs and `org-ietf-hpke` could offer one, because AES-GCM
had no portable implementation in this workspace — every AES in the tree was
Node's `crypto`, reached through a seam.

## Why it exists now

TLS-ECH configs in the wild advertise **AES-128-GCM**, and RFC 9230 names
`X25519 / HKDF-SHA256 / AES-128-GCM` as ODoH's mandatory suite. HPKE's other
consumers are not blocked on HPKE; they are blocked on this.

## Two places GCM is easy to get wrong

**A 96-bit IV is a special case, not the general one.** With twelve bytes,
`J0` is the IV with a counter of 1 appended. With any other length it is a
GHASH of the IV — a second code path that nearly nothing exercises, because
nearly every protocol uses twelve bytes.

**The counter is 32 bits wide inside a 128-bit block.** It wraps
independently of the leading twelve bytes. Incrementing the whole block
instead is a change no short message can detect.

Both are measured below rather than asserted.

## What authenticates what

GHASH is not a MAC. It is a keyed hash whose key `H` is `E(K, 0^128)`, and it
is unforgeable only because its output is masked by `E(K, J0)`. One
consequence is worth stating plainly:

**A nonce reused under one key loses the authentication, not merely the
confidentiality.** Two ciphertexts under the same `J0` let an attacker solve
for `H`, after which tags can be forged for messages that were never sent.
With a stream cipher the usual intuition is "the plaintexts leak"; here the
key's integrity guarantee ends too.

An empty IV is refused (`:empty-iv`) rather than treated as a degenerate
case, because it makes `J0` a constant and every message under the key shares
a keystream.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
kbb -M:oracle                                                      # + javax.crypto sweeps
```

**1,368 assertions on both runtimes; 1,667 with the oracle.**

### The corpus is Wycheproof, whole

`test/aes/wycheproof_gcm.cljk` is **generated** by
`scripts/extract_wycheproof.cljk` from Project Wycheproof's `aes_gcm_test.json`,
pinned by sha256 (`985e5ecc…dfe7`). All **316** cases, every group, no
sampling — a truncated adversarial corpus is the subset that happened to
pass, so the generator refuses if the count the file declares and the count
extracted disagree, and the suite asserts it again at run time.

Wycheproof is chosen because it attacks rather than demonstrates: 81 forged
tags, 36 counter-wrap cases, IVs from 8 bits to 2056, 6 empty IVs, across all
three key sizes.

**Every rejection is checked by reason.** A test that accepts any failure
counts a run that broke for an unrelated cause as a run that discriminated —
so the empty-IV cases must fail with `:empty-iv` and the forged tags with
`:authentication-failed`, and a swap between them is a red test.

The `javax.crypto` oracle covers what a fixed corpus cannot: message lengths
0–200, AAD lengths straddling the GHASH block, and **IV lengths 1, 8, 11,
12, 13, 15, 16, 17, 32, 64, 129** — the boundary either side of the special
case.

### What the suite discriminates

Measured by breaking one thing at a time:

| break | failures | which tests go red |
|---|---|---|
| `Rcon[j]` written as `x^j` instead of `x^(j-1)` | **866** | the valid cases |
| increment the whole block instead of the low 32 bits | **54** | the valid cases |
| take the GHASH path for 96-bit IVs too | **456** | the valid cases |
| compare only the first tag byte | **108** | the **invalid** cases only |
| keep MixColumns in the final round | **866** | the valid cases |
| *(restored)* | **0** | none |

The 54 and the 108 are the interesting rows. The counter break is invisible
to every message short enough not to carry, and only 54 of 1,368 assertions
can see it; the tag break lets forgeries through while leaving every correct
decryption correct, so it shows up **only** in the cases that are supposed to
fail. A suite without adversarial cases would have called that one green.

**The `Rcon` row is not hypothetical.** It is the bug this implementation
shipped with on its first run: the cipher was still a permutation, still
round-tripped against itself, and agreed with nothing else in the world.
That is the exact failure a derived table is supposed to prevent and does
not — deriving protects against a mistyped constant, not against an
off-by-one in the index.

### The tables are derived, not transcribed

The S-box is computed the way FIPS 197 §5.1.1 defines it — multiplicative
inverse in GF(2^8) modulo `x^8 + x^4 + x^3 + x + 1`, then the affine
transform — rather than copied as 256 magic bytes. The round constants are
successive powers of `x`. `org-nist-sha2` made the same choice for the same
reason.

## Native port and gate (JUN-553, JUN-352)

`kotoba/aes/core.kotoba` (`aes.core`) and `kotoba/aes/gcm.kotoba` (`aes.gcm`) are the AES
forward cipher (FIPS 197, 128-, 192- and 256-bit keys) and AES-GCM (SP 800-38D, any
non-empty IV, 128-bit tags) written in native `.kotoba`. Bytes are `:vector-i64` of
0..255.

- `seal key iv aad plaintext` gives ciphertext ++ tag, or an empty vector for a bad key
  length, an empty IV or a value outside 0..255.
- `open key iv aad sealed` gives the plaintext, or the one-element vector `[-1]` when the
  parameters are bad, the input is shorter than a tag or the tag does not verify (an
  empty plaintext is valid, so failure is not the empty vector). Nothing is decrypted
  before the tag passes.
- A GHASH block is four 32-bit words in i64, so no shift meets a sign bit; the counter is
  the low word and wraps alone.

`kotoba/aes/native_gate.kotoba` is generated by `tools/gen_gate.py`. It takes 61 cases
from the Wycheproof corpus in `test/aes/wycheproof_gcm.cljk`, covering every flag and
all three key sizes. Every case is re-checked against `tools/reference.py`, a Python AES and
GCM written from the two standards, which passes all 316 corpus cases and FIPS 197
Appendix C. A valid case must seal to the published bytes and open back; an invalid one
must open to `[-1]`. There are three groups, each its own image:

| group | pass | checks |
|---|---|---|
| `group-a` | 15 | Ktv and Pseudorandom cases, FIPS 197 Appendix C for every key size, the S-box against its definition |
| `group-b` | 7 | SmallIv, LongIv and SpecialCase cases |
| `group-c` | 7 | CounterWrap (counters starting at 2^32 - 1, - 2, - 3), ModifiedTag, ZeroLengthIv |

Built as modules and measured 2026-10-30 on Apple M1 Max with the Amu Mac root of main
`91faa123`:

| image set | change | a / b / c |
|---|---|---|
| gate | none | **15 / 7 / 7** |
| ctl-sbox | one S-box entry changed | 0 / 0 / 6 |
| ctl-mixcol | MixColumns row 0 loses the `3 a1` term | 8 / 0 / 6 |
| ctl-rcon | round constant incremented, not doubled | 8 / 0 / 6 |
| ctl-sub8 | AES-256 key schedule without the extra SubWord | 8 / 0 / 6 |
| ctl-gfred | GHASH reduction constant 0xE1 -> 0xE0 | 12 / 0 / 6 |
| ctl-carry | the counter carries into the next word | 15 / 7 / 6 |
| ctl-ivlen | a non-12-byte IV hashed without its length | 12 / 0 / 6 |
| ctl-tagcmp | open does not check the tag | 15 / 7 / 5 |

Not yet: the other 255 corpus cases natively, decryption of single blocks (GCM does not
need it), AES-GCM-SIV, and a measurement of timing (the S-box is a table lookup).


**Decryption.** GCM, CTR and CCM never invoke the inverse cipher: they
encrypt a counter and XOR. `InvMixColumns` and an inverse key schedule would
add a second round function and a second set of ways to be wrong, for modes
this workspace does not have. CBC or ECB decryption is a known, bounded piece
of work if it is ever needed.

**Tags shorter than 128 bits.** SP 800-38D permits 96, 104, 112 and 120, and
they exist to save bytes on constrained links. Nothing here is on one, and a
truncated tag is a weaker forgery bound that a caller can select by accident.

**A table-driven GHASH.** The 4-bit and 8-bit table forms are four to sixty-four
kilobytes per key and, in the usual construction, indexed by secret data. The
shift-and-add loop is slower and does not have that property. Throughput here
is bounded by `aes.core` regardless.

**Constant-time AES.** This is not one, and no table-lookup implementation in
a garbage-collected runtime can honestly claim to be. The S-box lookup is
data-dependent. That is a real limitation and it belongs in the open: this is
appropriate for protocol work on data the process already holds, and not for
a setting where an attacker can measure this process's cache.
