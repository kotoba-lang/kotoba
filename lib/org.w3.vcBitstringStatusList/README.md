# kotoba-lang/org-w3-vc-bitstring-status-list

**[W3C Bitstring Status List v1.0](https://www.w3.org/TR/vc-bitstring-status-list/)
— revocation and suspension for Verifiable Credentials, portable `.cljc`.**

A credential carries a `credentialStatus` entry naming a status list credential
and an index into it. The list is a bitstring of at least 131,072 bits,
GZIP-compressed and multibase base64url-encoded, so **one fetch answers "is it
still valid?" for 131,072 credentials without revealing which one the verifier
cares about**. That herd-privacy property is the whole reason for the minimum
size, which is why `generate` refuses to go below it rather than padding quietly.

```clojure
(require '[status-list.core :as sl])

;; Issuer: revoke credentials #7 and #9.
(def encoded (sl/generate #{7 9}))          ;=> "uH4sIAAAA…"  (~700 chars)

(def list-cred
  (sl/status-list-credential {:id "https://issuer.example/status/1"
                              :issuer "did:key:z6Mk…"
                              :encoded-list encoded}))
;; then sign it with kotoba-lang/org-w3-vc-data-integrity

;; Issuer: the entry that goes in the credential being issued.
(sl/entry {:index 7 :status-list-credential "https://issuer.example/status/1"})
;=> {"type" "BitstringStatusListEntry" "statusPurpose" "revocation"
;    "statusListIndex" "7" "statusListCredential" "https://issuer.example/status/1"}

;; Verifier, given an already-proof-verified list credential:
(sl/check-status entry list-cred)
;=> {:status 1 :valid? false :purpose "revocation" :index 7}
```

## Bit 0 is the most significant bit of byte 0

§3.1: *"the first index, with a value of zero, is located at the left-most bit"*.
If you read it as the least significant bit instead, the list still decodes
cleanly and simply **reports the wrong credentials as revoked** — the worst
available failure mode, since nothing errors. Pinned directly:

| Set index | Byte 0 |
|---|---|
| 0 | `0x80` |
| 7 | `0x01` |
| 8 | `0x00`, byte 1 = `0x80` |

Multi-bit entries occupy `statusSize` consecutive bits starting at
`statusListIndex × statusSize`, MSB-first.

## Deterministic output

`deflate.core/gzip` fixes MTIME to 0 and OS to 255, so the same input always
produces the same `encodedList`. This matters because the value goes **inside a
signed credential** — a timestamp in the gzip header would change the issuer's
signature on every regeneration of an unchanged list.

The 16 KiB minimum is affordable precisely because a mostly-empty bitstring
compresses: a list with one revocation encodes to well under 1 KB. A test asserts
that, so a regression to stored DEFLATE blocks (~22 KB) shows up as a failure.

## What it will not do for you

`check-status` takes the status list credential **as data, already verified**. It
does not fetch `statusListCredential` and does not check its proof, deliberately:

- A status check that fetched a URL out of credential content would hand every
  verifier an SSRF surface driven by attacker-supplied data.
- One that trusted an unverified list would let anyone un-revoke their own
  credential by serving a list of zeros.

Both are the caller's decisions, made explicitly. Verify the list credential with
`kotoba-lang/org-w3-vc-data-integrity` first.

## Fail-closed inputs

Each throws `ex-info` carrying a `:status-list/error` key:

| `:status-list/error` | Cause |
|---|---|
| `:status-list/too-few-entries` | fewer than 131,072 entries requested — a privacy floor, not bookkeeping |
| `:status-list/status-list-length-error` | §3.2 step 8: a served list shorter than the minimum |
| `:status-list/purpose-mismatch` | entry's `statusPurpose` ≠ the list's, or ≠ the one the verifier asked about |
| `:status-list/bad-multibase` | `encodedList` without the `u` prefix — multibase is self-describing, so guessing could decode into a plausible but wrong bitstring |
| `:status-list/index-out-of-range` | index beyond the bitstring, on either the write or read side |
| `:status-list/bad-status-value` | a value that does not fit `statusSize`, which would corrupt the neighbouring entry |
| `:status-list/status-message-required` | `statusSize > 1` with no `statusMessage`, leaving a status no verifier can interpret |
| `:status-list/bad-status-message` | `statusMessage` not covering all 2^statusSize values |

`statusListIndex` is a base-10 **string**, per spec: it is an arbitrary-size
integer and a JSON number cannot carry one faithfully.

## Dependencies

| Repo | For |
|---|---|
| `kotoba-lang/org-ietf-deflate` | RFC 1952 GZIP, both directions, deterministic |
| `kotoba-lang/io-multiformats` | multibase base64url (no padding) |

## Test

```bash
kbb -M:test          # JVM, release deps (git SHAs)
kbb -M:dev:test      # JVM, sibling west checkouts
kbb -M:lint
npm install && npm run smoke   # the :cljs branch
```

The `:cljs` branch needs its own run, and CI runs both. This library has already
been bitten by exactly the divergence that makes it necessary:
`multiformats.core/base64url-decode` returns a byte-array on `:clj` whose bytes
are **signed**, so the gzip magic `0x8b` arrived as `-117` and a perfectly good
member was rejected as "bad magic", while `:cljs` returned unsigned ints and the
same code was fine.

Because `encodedList` sits inside a **signed** credential, both suites pin the
*same* literal for the same input — a cross-host invariant that cannot be
expressed inside one suite, since a host that gzipped differently would still
pass its own tests while issuing a list the other host's verifier rejects.
Measured identical on both hosts 2026-07-30.

`@noble/hashes` is declared in `package.json` for the `:cljs` path: requiring
`multiformats.core` at all pulls it in, even though this library uses only
`base64url` from it.

## License

MIT. See `LICENSE`.
