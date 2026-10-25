# kotoba-lang/org-ietf-srtp

**SRTP — the Secure Real-time Transport Protocol,
[RFC 3711](https://www.rfc-editor.org/rfc/rfc3711) — in portable
`.cljc`.**

The packet transform (Figure 1's layout: RTP header | encrypted payload
| optional MKI | authentication tag), the 48-bit packet index and ROC
rollover-counter arithmetic (§3.3.1, Appendix A's guessing algorithm),
key derivation (§4.3 — `PRF_n`, the six label constants, AES-CM as the
default PRF), and the replay window (§3.3.2). Depends on
`kotoba-lang/org-ietf-rtp` (SRTP transforms RTP packets, so this
re-parses nothing RTP already parses), `kotoba-lang/bytes` (real, tested
HMAC-SHA1), and `kotoba-lang/org-nist-aes` (real, Wycheproof-tested
AES block cipher).

## Crypto scope — read this before trusting the numbers

**AES-CM (SRTP's counter-mode variant of AES-CTR) is implemented**, in
`srtp.aes-cm`, as a keystream-generation wrapper around
`org-nist-aes`'s existing `aes.core/expand-key` +
`aes.core/encrypt-block` — no S-box, MixColumns, or key schedule is
reimplemented here; only the counter-increment-and-XOR loop that
`org-nist-aes` deliberately does not provide (its own README: *"GCM, CTR
and CCM never invoke the inverse cipher ... for a mode this workspace
does not have and cannot currently test against a consumer"* — this repo
is now that consumer). This is why AES-CM is implemented as real,
tested code rather than left as a caller-supplied provider seam: it is a
*mode of operation* over an already-real block cipher, not a cipher
primitive being hand-rolled from nothing, and it is verified below
against RFC 3711's own published vectors rather than only against
itself.

**HMAC-SHA1 is not reimplemented at all** — `kotoba-lang/bytes`
(`kotoba.bytes.sha1/hmac-sha1`) already has a real, portable
implementation tested against a published RFC 2104 vector, so
`srtp.packet` depends on it directly.

**AES-f8 (§4.1.2) is not implemented.** SRTP's alternate cipher mode
(used by 3GPP/UMTS profiles) has no test-vector cross-check available
in this codebase and no consumer in this workspace; `protect`/`unprotect`
implement only the default `AES_CM_128_HMAC_SHA1_80` suite (§8.2).

## Test vectors — provenance

**[RFC 3711] Appendix B.2 (AES-CM keystream) and Appendix B.3 (key
derivation)** are used verbatim, fetched from
`https://www.rfc-editor.org/rfc/rfc3711.txt` on 2026-08-30, and were
**independently cross-checked byte-for-byte against
`openssl enc -aes-128-ecb -nopad`** during development before being
committed to the test suite — each keystream/derived-key block in both
appendices is a single AES-ECB encryption of a hex input the RFC itself
walks through, and `openssl` (a third, independent AES implementation)
was used to confirm the RFC's published output before trusting it as a
test oracle. This caught two of this codec's own transcription bugs
during development (see below) — the vectors were correct; two 32-hex-
character values had been hand-copied one character short.

**The AES-128 key-schedule/CTR test vector this codec's keystream tail
deliberately reuses** — RFC 3711's own note: *"this test case is
contrived so that the latter part of the keystream segment coincides
with the test case in Section F.5.1 of \[AES-CTR\]"* (NIST SP 800-38A)
— is exercised as the `near-wrap` case in `srtp.aes-cm-test`.

**Appendix A's index/ROC-guessing pseudocode** is transcribed verbatim
into `srtp.index`'s docstring and implemented directly from it, but the
RFC gives no worked numeric example for that algorithm (pseudocode
only) — the specific sequence-number values in `srtp.index-test` are
**constructed**, exercising the algorithm's three branches (steady
state, forward wrap, late-reordered-pre-wrap packet), not spec text.
**`srtp.packet-test`'s RTP packets and the replay-window fixtures are
likewise constructed** — RFC 3711 has no worked full-packet
protect/unprotect example.

## Two transcription bugs this test suite caught, honestly

While writing the AES-CM keystream test against Appendix B.2, the first
block's expected hex string was hand-copied as
`E03EAD0935C95E80E166B16DD92B4EB` (31 hex digits — one short) instead of
the RFC's actual `E03EAD0935C95E80E166B16DD92B4EB4` (32). The truncated
value is invalid as a 16-byte hex string in the first place (odd digit
count), so this failed loudly (a JVM `NullPointerException` deep inside
`aes.core`, from an oddly-sized key elsewhere caused by the same
transcription error) rather than silently — the two errors were found
and fixed by re-deriving the exact substring length from the RFC's raw
fetched text (`awk '{print length($2)}'`) rather than eyeballing it a
second time. Documented here rather than quietly fixed, per this
workspace's own rule that a test suite's failures are worth showing.

## Surface

```clojure
(require '[srtp.kdf :as kdf] '[srtp.packet :as p] '[srtp.index :as idx])

(def ctx (assoc (kdf/derive-srtp-keys master-key master-salt) :roc 0))

(p/protect rtp-packet-bytes ctx)     ;; => {:status :ok :bytes <srtp-bytes>}
(p/unprotect srtp-packet-bytes ctx)  ;; => {:status :ok :bytes <rtp-bytes>}
;;                                       | {:status :error :reason :srtp/authentication-failure}

(idx/guess-index roc s-l seq)        ;; Appendix A
(idx/check replay-window index)      ;; :ok | :srtp/replayed | :srtp/too-old
```

| namespace | |
|---|---|
| `srtp.aes-cm` | `keystream` `xor-keystream` — AES-CM built on `aes.core` |
| `srtp.kdf` | `derive-key` `derive-srtp-keys` `labels` — §4.3 |
| `srtp.index` | `sender-index` `guess-roc` `guess-index` `advance-roc`, replay window (`new-window` `check` `record`) |
| `srtp.packet` | `protect` `unprotect` `header-length` `compute-iv` |

## Verify-then-decrypt, not decrypt-then-verify

`unprotect` computes and checks the HMAC tag before touching the
ciphertext with AES-CM. **The tag covers `Authenticated Portion || ROC`
(§4.2)** — the 32-bit rollover counter is folded into the authenticated
bytes even though it is never transmitted on the wire, so the same wire
bytes authenticated under a different (mis-synchronized) ROC fail
verification. See "Discrimination proof" in the project report for the
break/restore cycle that confirmed this specific line matters — removing
the ROC from the HMAC input still passes every *positive* round-trip
test (both sides of a same-process test agree with each other), and is
only caught by a test that authenticates the same bytes under two
different ROC values and asserts they disagree.

## Errors

Returned, never thrown. `:srtp/authentication-failure` (tag mismatch —
per §4.2's own required audit message name), `:srtp/packet-too-short`,
`:srtp/invalid-rtp-packet` (protect: the input isn't valid RTP per
`org-ietf-rtp`), `:srtp/replayed` / `:srtp/too-old` (replay window).

## Verify

```sh
kbb -M:test   # JVM only — this repo's git deps (org-ietf-rtp,
                   # kotoba-lang/bytes, org-nist-aes) are not yet
                   # cross-verified on the ClojureScript path here.
```

## Not here

**SRTCP** (§3.4/§4.2's SRTCP-specific packet format, index and key
labels) — this codec implements SRTP proper; the SRTCP labels exist in
`srtp.kdf/labels` but no SRTCP packet transform is built on them.
**MKI-based key lookup** (multiple concurrent master keys identified by
an MKI field) — `srtp.packet` takes one already-selected key context per
call; MKI framing itself is not emitted or parsed. **AES-f8** (see
"Crypto scope" above). **Key-derivation-rate-triggered re-derivation
scheduling** — `srtp.kdf/derive-key` takes `kdr` and computes the
correct `r`, but nothing in this repo automatically re-derives session
keys as `index` crosses a boundary; a caller using non-zero `kdr` must
re-derive and swap in new keys itself.
