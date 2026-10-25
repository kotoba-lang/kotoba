# kotoba-lang/org-openid-oid4vp

**[OpenID for Verifiable Presentations 1.0](https://openid.net/specs/openid-4-verifiable-presentations-1_0.html)
— the Verifier side, portable `.cljc`.** Build an Authorization Request, validate
the Authorization Response envelope.

```clojure
(require '[oid4vp.core :as oid4vp])

(def query
  (oid4vp/dcql-query
    [(oid4vp/credential-query {:id "membership" :format "ldp_vc"
                               :claims [["credentialSubject" "role"]]})]))

(def request
  (oid4vp/authorization-request
    {:client-id "redirect_uri:https://verifier.example/cb"
     :response-mode "direct_post"
     :response-uri "https://verifier.example/cb"
     :nonce  from-your-csprng     ; stored with the session
     :state  from-your-csprng     ; see §5.3 below
     :dcql-query query}))

(oid4vp/request->url "openid4vp://" request your-json-encoder)

;; …later, when the Wallet posts back:
(oid4vp/validate-response response {:state stored-state :nonce stored-nonce
                                    :holder-binding? false})
;=> {:valid? true :vp-token "…" :state "…" :envelope-only? true}
```

## Why only the Verifier side

The Wallet side needs a holder key that can sign a presentation over a
Verifier-supplied nonce. A **WebAuthn Passkey cannot**: it signs its own
`authenticatorData || clientDataHash` and nothing else, so it cannot produce a
key-binding proof over bytes a Verifier chose. Shipping a Wallet side here would
mean shipping the interesting half missing. The Verifier side has no such problem
and is complete.

## The one invariant worth reading twice

**§5.3 — when a presentation carries no key binding, the `nonce` is not echoed
back.** There is no proof to bind it into. Session binding then rests entirely on
`state`, which becomes REQUIRED, must carry ≥128 bits of entropy, be fresh per
request, be stored in the session, and be checked on return.

So `:holder-binding?` **defaults to `false`** — the weaker assumption. A caller
who has not thought about binding gets the strict `state` requirement rather than
a silently replayable exchange, and `authorization-request` refuses to build a
request that expects unbound presentations with no `state`.

## What this deliberately does not do

`validate-response` checks the **envelope** — `state` against the session,
`vp_token` presence — and hands back the raw `vp_token`. It does not walk inside
it, does not verify any presentation, and does not match returned credentials
against the DCQL query. The result says so: `:envelope-only? true`.

That is a boundary, not an oversight. The normative text defining how `vp_token`
is keyed when `dcql_query` was used could not be retrieved from the published
specification while this was written, and guessing at the internal shape of a
structure whose contents gate an authorization decision is worse than declining
to. **A `:valid? true` does not mean the Wallet answered your query** — match the
claims yourself, and verify each presentation with
`kotoba-lang/org-w3-vc-data-integrity`.

Also absent: JAR (`request_uri`), `direct_post.jwt` response *decryption* (the
mode is accepted as a value; unwrapping the JWT is the caller's), Digital
Credentials API bridging, and `transaction_data` semantics beyond passing it
through.

## No ambient authority

`authorization-request` does not generate the `nonce` or the `state`. Both come
from the caller's own CSPRNG, alongside the session they are stored in — a
library that minted them would be inventing session state it cannot see. The
entropy floor is enforced by length, counted in characters rather than bits
because the parameter is a string and the encoding is the caller's: 22 characters
is 128 bits of base64url, so that is the bound that is safe without pretending to
know the alphabet.

`request->query-params` takes a JSON encoder as an argument for the same reason:
this library has no JSON dependency and does not want one.

## Fail-closed inputs

Each throws `ex-info` carrying an `:oid4vp/error` key:

| `:oid4vp/error` | Cause |
|---|---|
| `:oid4vp/missing-client-id` `:oid4vp/missing-nonce` | REQUIRED parameter absent |
| `:oid4vp/bad-response-mode` | not `fragment` / `direct_post` / `direct_post.jwt` |
| `:oid4vp/weak-nonce` `:oid4vp/weak-state` | cannot carry 128 bits |
| `:oid4vp/state-required-without-holder-binding` | §5.3 |
| `:oid4vp/both-query-and-scope` `:oid4vp/no-query` | exactly one is required |
| `:oid4vp/missing-response-uri` `:oid4vp/missing-redirect-uri` | mode's companion parameter |
| `:oid4vp/dcql-*` | query shape (§6.1): non-empty `credentials`, `id` + `format` per entry, non-empty claim `path`, unique ids |
| `:oid4vp/no-session` `:oid4vp/session-without-state` | the *caller's* bug — validating against nothing |

A response that simply does not match is `{:valid? false :reason …}`, not an
exception: a Wallet replying to the wrong session is an ordinary thing to happen.

## Test

```bash
kbb -M:test                              # JVM
kbb -M:lint
kbb --backend sci --classpath src test/nbb_smoke.cljk      # the :cljs branch
```

The `:cljs` branch needs its own run. The one reader conditional is `form-encode`,
and the two hosts do **not** agree by default: `java.net.URLEncoder` is
`application/x-www-form-urlencoded` (space → `+`, escapes `~`) while
`encodeURIComponent` is RFC 3986 (leaves `~`). The smoke test therefore pins the
property that matters — reserved characters in a `client_id` are escaped — rather
than a byte-for-byte URL.

## License

MIT. See `LICENSE`.
