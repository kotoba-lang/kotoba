# kotoba-lang/org-ietf-rfc3161

**[RFC 3161](https://www.rfc-editor.org/rfc/rfc3161.html) time-stamp protocol** —
build a request, parse and verify a token. Portable `.cljc` on `org-ietf-cms`.

```clojure
(require '[rfc3161.core :as ts] '[cms.jvm :as jvm])

(ts/request {:digest sha256-of-thing :nonce (random-63-bit) :cert-req? true})
;=> DER TimeStampReq — POST it to a TSA yourself

(def token (ts/parse-token (:token-der (ts/parse-response response-bytes))))
(ts/verify-token token {:digest sha256-of-thing :nonce sent-nonce-hex
                        :digest-fn jvm/digest :verify-fn jvm/verify
                        :trusted? my-accredited-roots?})
;=> {:verified true :trusted true :gen-time "2026-07-30T13:49:55Z" …}
```

## Why

A signature says who agreed. It does not say **when** — the only time in it is
one the signer wrote down. A timestamp authority signs that a digest existed
before a moment, which is the difference between a claim and evidence.

Japan's 電子帳簿保存法 names the 総務大臣認定タイムスタンプ as one of three ways
to satisfy the tamper-evidence requirement for retained electronic transaction
data; eIDAS names RFC 3161 for a qualified timestamp. **Neither names a
blockchain anchor** — an anchor proves "no later than", which is not what the
regulation asks for.

## No default TSA

There is no built-in URL and no fallback. Shipping one would produce timestamps
that look official and are accredited nowhere, and the difference is invisible
in the token. `request` builds bytes; the transport and the choice of an
accredited TSA are yours.

## `:verified` and `:trusted` are separate

A structurally perfect token signed by a certificate nobody vouched for is
exactly what an attacker produces with `openssl ts` and their own CA — which is
what this repo's own test fixture *is*. Collapsing the two into one boolean is
how a self-issued timestamp reads as an accredited one.

With no `:trusted?` predicate the answer is `:unknown`, never `true`.
`accredited-note` gives the sentence a UI must carry when it is not `true`,
because every caller has that obligation and the phrasing is the part that gets
softened.

## Two checks that are easy to skip

- **The TSA certificate's EKU must be critical and contain
  `id-kp-timeStamping` and nothing else** (§2.3). The exclusivity is the part
  implementations drop — a key that is also a TLS key is one whose holder can be
  induced to sign something that is not a timestamp.
- **The nonce must come back unchanged.** Without it a token is a recording: an
  old response for the same digest replays as a fresh one. `request` will not
  invent one for you, because a nonce a library chose is one the caller cannot
  check.

Time comes back as a string and is never compared to a clock. "Recent enough"
has a different answer for a contract than for a log line.

## Test

```bash
kbb -M:test    # against `openssl ts` request/response, byte-identical request
kbb -M:lint
```

Apache-2.0.
