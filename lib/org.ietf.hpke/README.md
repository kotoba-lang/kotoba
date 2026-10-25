# kotoba-lang/org-ietf-hpke

**[RFC 9180](https://www.rfc-editor.org/rfc/rfc9180) HPKE — Hybrid Public Key
Encryption — in portable `.cljc`.**

**Everything RFC 9180 defines that this workspace can run**: five KEMs,
three KDFs, four AEADs including export-only, four modes.

| axis | |
|---|---|
| KEM | `dhkem/p256-hkdf-sha256` `p384-hkdf-sha384` `p521-hkdf-sha512` `x25519-hkdf-sha256` `x448-hkdf-sha512` |
| KDF | `kdf/hkdf-sha256` `hkdf-sha384` `hkdf-sha512` |
| AEAD | `hpke/aes-128-gcm` `aes-256-gcm` `chacha20-poly1305` `export-only` |
| mode | base, PSK, Auth, AuthPSK |

## Use

```clojure
(require '[hpke.core :as hpke] '[hpke.dhkem :as dhkem])

(def kp  (dhkem/derive-key-pair recipient-ikm))
(def eph (dhkem/derive-key-pair fresh-random-32-bytes))   ; ONE per message

(def s (hpke/setup-base-sender (:public kp) info eph))
(def m (hpke/seal (:context s) aad plaintext))
;; send (:enc s) and (:bytes m)

(def r (hpke/setup-base-recipient (:enc s) kp info))
(hpke/open (:context r) aad (:bytes m))
```

A suite is a value, and it is an optional leading argument. Omitted, it is
`default-suite` — X25519 / HKDF-SHA256 / ChaCha20Poly1305, what this library
had when it had one — so every existing call site means what it used to:

```clojure
(def s (hpke/suite dhkem/p256-hkdf-sha256 kdf/hkdf-sha512 hpke/aes-128-gcm))
(hpke/setup-base-sender s (:public kp) info eph)
```

Nothing branches on an identifier. The KEM carries its own Diffie-Hellman and
its own KDF; the KDF carries its MAC and its `Nh`; the AEAD carries `seal`,
`open` and `Nk`. What is left in `hpke.core` is RFC 9180 §5 and nothing else.

The other three modes are the same shape with the inputs they add:

```clojure
(hpke/setup-psk-sender       pk-r info psk psk-id eph)
(hpke/setup-auth-sender      pk-r info eph kp-s)
(hpke/setup-auth-psk-sender  pk-r info psk psk-id eph kp-s)

(hpke/setup-psk-recipient      enc kp-r info psk psk-id)
(hpke/setup-auth-recipient     enc kp-r info pk-s)
(hpke/setup-auth-psk-recipient enc kp-r info psk psk-id pk-s)
```

`seal` and `open` return a **new context** alongside the bytes. A context is
a value; a mutable counter shared by two callers is how a nonce gets reused,
and the AEAD underneath is a stream cipher.

`hpke/export` derives an independent secret and does **not** advance the
sequence number — exporting is not sending.

## What each mode authenticates

| mode | the recipient learns | the sender learns |
|---|---|---|
| **base** | nothing about who sent it | nothing |
| **PSK** | the sender holds the pre-shared key | the opener holds it too |
| **Auth** | the sender holds `skS` | nothing |
| **AuthPSK** | both | the opener holds the PSK |

Auth mode's guarantee is **deniable**: both parties compute the same secret,
so a transcript proves nothing to a third party. That is a property of the
mode, not a shortfall — a signature is the thing to reach for when
transferability is wanted.

Auth mode also does not fail loudly on a wrong sender key. `auth-decap` has
nothing to compare against, so it derives a *different* shared secret and the
rejection surfaces as the first `open` returning `:authentication-failed`.
The tests assert exactly that sequence, because "no error from setup" reads
like success.

## The rule the construction depends on

**A fresh ephemeral key pair per setup.** Reusing one gives two
encapsulations the same key and the same base nonce. Randomness is a
capability, so this library *takes* the ephemeral rather than making one —
which also means a caller who reuses one is doing so visibly rather than by
accident.

`open` advances the sequence number **only on success**: a rejected message
must not consume a nonce, or an attacker can desynchronise the two sides by
injecting garbage.

**PSK inputs are checked, not coerced** (`psk-inputs-error`, RFC 9180
`VerifyPSKInputs`). A PSK without an id, an id without a PSK, a PSK handed to
a mode that ignores it, and a mode that needs one and did not get it are four
distinct refusals. The third matters most: a silently dropped secret is worse
than an absent one, because the caller believes it is in force.

## The KEM has its own KDF, and it is not the suite's

RFC 9180 §7.1.3 is explicit, and **Appendix A.4 is the case that proves it**:
DHKEM(P-256, **HKDF-SHA256**) paired with **HKDF-SHA512**. The KEM derives
with SHA-256 and the key schedule derives with SHA-512, in the same suite.

A library that read one KDF for both would be right about six of the seven
appendices. Measured: making every KEM use HKDF-SHA512 turns **1,439**
assertions red, and the test named for A.4 is one of them.

## What the RFC anchors, and what it does not

The seven appendices cover **X25519**, **P-256** and **P-521**; HKDF-SHA256
and **HKDF-SHA512**; all four AEADs. They do **not** cover **P-384**, **X448**
or **HKDF-SHA384**.

Those run on their primitives' own evidence — the complete Wycheproof corpora
in `org-nist-ecc` and `org-ietf-x448`, and RFC 4231 for HMAC-SHA-384 — and
`the-registries-list-only-what-runs` gives them a round-trip that **says it is
a round-trip**. A reader should not have to work out which of two adjacent
tests is anchored to a specification and which is not.

## Dependencies — six, all first-party, all implementations

| | |
|---|---|
| `org-nist-sha2` | SHA-256/384/512 and their MACs |
| `org-ietf-x25519` | one KEM's Diffie-Hellman |
| `org-ietf-x448` | another |
| `org-nist-ecc` | the three NIST ones |
| `org-ietf-chacha20-poly1305` | one AEAD |
| `org-nist-aes` | the other two |

**Not `kotoba-lang/crypto`**: its `hkdf` hardcodes a **zero salt**, and RFC
9180's key schedule passes a real one (`LabeledExtract(shared_secret,
"secret", psk)`), so a fixed-salt Extract computes a different function. Its
default digest is also a JVM `MessageDigest`.

**Not `kotoba-lang/noise`**: its AEAD is host-injected through
`provider/{jvm.clj, noble.cljs, node.cljs}` — on ClojureScript, through
`@noble` itself. Both were listed in this workspace's dependency ledger as
first-party replacements for `@noble/ciphers`, and both were seams. That
error is what this library's dependency list exists to correct.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
kbb -M:oracle                                                      # + differential vs BouncyCastle
```

**2,423 assertions, both runtimes, 0 failures. 2,610 with the oracle.**

### Where the vectors come from

`test/hpke/rfc9180_vectors.cljk` is **generated** by
`scripts/extract_rfc9180.cljk` from RFC 9180's plain text, pinned by sha256
(`f45a8b7c…f1f8f6`). It carries **all seven appendices** verbatim, four modes
each: every `ikm` and the key pair it derives to, `enc`, `shared_secret`,
`key_schedule_context`, `secret`, `key`, `base_nonce`, `exporter_secret`, six
encryptions and three exports.

The suite for each appendix is built **from the identifiers the vectors
themselves declare**, looked up in this library's registries. So the tests
also check that `kems`, `kdfs` and `aeads` map an identifier to the
implementation the RFC means by it — which a hand-written suite constant
could not, because it would agree with the same mistake.

A.7 is export-only and has no Encryptions subsection at all, so the extractor
checks for one rather than assuming the shape. Assuming it would have read
A.7's exports as ciphertexts and produced a table of empty strings that the
suite would then assert nothing about.

**Transcription is mechanical because transcription is the step that failed
here.** An earlier suite claimed its vectors were A.2 verbatim and they were
not — the recalled `ikmR` was A.1's. The pairing was internally consistent,
so nothing caught it except an assertion on `pkRm`. The generator refuses
rather than regenerating if the source hash ever moves: a fixture rebuilt
from a different document is a different claim.

The sequence numbers asserted are the RFC's — 0, 1, 2, 4, **255 and 256**.
The last two are the point: they are where a byte-at-a-time nonce counter
carries, and `compute-nonce` builds its bytes by division so that it can.

### What the suite discriminates

Measured by breaking one thing at a time and running it:

| break | failures | which tests go red |
|---|---|---|
| drop the mode byte from `key_schedule_context` | **245** | all four modes, and `modes-do-not-collide` |
| swap `pkRm`/`pkSm` in the auth `kem_context` | **64** | auth and auth-psk **only** |
| drop the second DH from `auth-encap` | **64** | auth and auth-psk **only** |
| every KEM uses HKDF-SHA512 instead of its own KDF | **1,439** | six appendices, and the test named for A.4 |
| P-521's bitmask is `0xFF` instead of `0x01` | **272** | every appendix |
| export-only derives a key anyway | **16** | A.7 |
| the rejection-sampling condition accepts everything | **11** | the boundary test **only** |
| salt `LabeledExtract(…"secret"…)` with the psk instead of the shared secret | **235** | all four modes |
| *(restored)* | **0** | none |

The two 64s are the ones worth reading. Base and PSK stay **green** while
auth breaks, which is what makes them evidence about the added code rather
than about something shared underneath it.

### The BouncyCastle oracle covers base mode only

`kbb -M:oracle` runs 50 `DeriveKeyPair` comparisons and 12 base-mode
setups against BouncyCastle 1.78.1, including **eight cases where
BouncyCastle decrypts what this implementation sealed**. It has not been
extended to the three added modes, and that is stated rather than implied: a
second opinion on base mode is not a second opinion on auth mode. For A.2 the
RFC is now the primary evidence and the oracle is corroboration.

### Both runtimes

Everything underneath is per-runtime somewhere. HPKE adds one of its own: the
RFC's sequence limit is 2^96, which a JVM long cannot hold and a
ClojureScript number cannot represent exactly, so `compute-nonce` builds its
big-endian counter by division rather than against powers of 256 — the
obvious form throws at namespace load, before any nonce is computed.

## Not here

**Key generation.** `derive-key-pair` is deterministic in its input, which is
what makes a test vector possible. Producing the 32 random bytes is a
capability, and a leaf does not have one.

**A registry beyond what runs.** Five KEMs, three KDFs, four AEADs — every
one of them executes. A suite table listing identifiers nothing can execute is
the kind of completeness that reads as capability.

**AES-256-GCM as a known-answer test.** RFC 9180 has no X25519 +
AES-256-GCM section, so that suite is covered by a round-trip and a
suite-separation check and is labelled as such in the test that does it. A
reader should not have to work out which of two adjacent tests is anchored
to a specification and which is not.

**The consumers.** TLS-ECH, ODoH and MLS are what RFC 9180 was written for,
and none of them exist in this workspace yet. This is the primitive they
would each sit on.

### Two attempted breaks that were not breaks

Both produced **zero** failures, and neither was a missing test.

**The zero salt's length cannot be observed.** RFC 5869 §2.2 makes an absent
salt `Nh` zero bytes. Substituting a fixed 32 changes nothing measurable:
HMAC zero-pads a key shorter than its block to the block, and 32, 48 and 64
are all shorter than 64 or 128. The equivalence is now asserted — along with
the boundary where it stops holding, at 200 zero bytes, which is past the
block and gets hashed instead.

**The rejection-sampling branch is unreachable from any ikm.** RFC 9180
§7.1.3 draws candidates until one lands in `[1, order)`. For P-256 a masked
candidate falls outside with probability about 2^-32; for P-521 the bitmask
leaves 521 bits against an order within 2^-260 of that. No test can search
for one. Forcing the condition to accept everything left the whole RFC suite
green.

The condition is now a named predicate, `dhkem/candidate-acceptable?`,
checked at the boundary — zero, one, `order-1`, `order`, `order+1` — and the
break turns 11 red. Writing the test also caught an assertion of mine that
was wrong in an instructive way: masking P-521's leading byte to `0x01` and
setting the rest to ones gives `2^521 - 1`, the **field prime**, which is
still above the group order. Masking brings a candidate to the right *size*;
it does not bring it into *range*. That gap is exactly why the loop exists.
