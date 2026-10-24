# kotoba-lang/org-ietf-jws

**[RFC 7515](https://www.rfc-editor.org/rfc/rfc7515.txt) — JSON Web Signature,
Compact Serialization, portable `.cljc`.** The structure only; signing and
verifying are **injected**.

```clojure
(require '[jws.core :as jws] '[ed25519.core :as ed])

(def token
  (jws/sign {"alg" "EdDSA"} payload-string
            {:sign (fn [input] (ed/sign seed input))
             :json-encode json/write-str}))

(jws/verify token {:expected-alg "EdDSA"
                   :verify (fn [input sig] (ed/verify pub input sig))
                   :json-decode json/read-str})
;=> {:valid? true :header {"alg" "EdDSA"} :payload "…"}
```

## The verifier is told the algorithm; it does not read it

§4.1.1 requires `alg` to be present and understood, and §10 requires it
"accurately represents the algorithm used". Reading the algorithm out of the header
and then using it to decide *how to verify* is the classic algorithm-substitution
flaw: the header comes from whoever produced the token, so a verifier that trusts
it lets the attacker choose the check.

`verify` therefore **requires `:expected-alg`** and refuses a mismatch by name — a
token may be perfectly signed with an algorithm this caller doesn't accept, and
that's a different fact from a bad signature. Callers who accept several pass a
set, which forces them to write down *which*.

**`alg: none`** (§6, Unsecured JWS) is refused unconditionally and cannot be
enabled, on both sign and verify. RFC 7515 stops short of prohibiting it; there's
no use here for a signature-shaped object with no signature.

**`crit`** (§4.1.11): a critical header this implementation doesn't understand makes
the JWS **invalid**, not ignored. The producer used `crit` precisely to say "reject
this if you don't handle it".

## Why the crypto is injected

A JWS library that owns the cryptography ends up owning key custody too, and the
algorithms worth supporting already exist next door: `kotoba-lang/org-ietf-ed25519`
for `EdDSA`, and the P-256 primitives in `kotoba-lang/org-w3-vc-data-integrity` for
`ES256` (whose signature is already the IEEE P1363 `r‖s` form JOSE wants). One test
wires the real Ed25519 primitive rather than only the toy signer, because the point
of an injection seam is that a real thing fits through it.

## Malformed throws; invalid returns false

A bad signature, an unexpected `alg`, an unsupported `crit` → `{:valid? false
:reason …}`. A token that isn't three dot-separated parts **throws** — a caller may
well want to log those differently.

`decode-header` is named so it can't be mistaken for verification. It exists for
selecting a key by `kid`, which necessarily happens *before* the signature is
checked, so nothing it returns is trustworthy yet.

## Test

```bash
kbb -M:dev:test
kbb -M:lint
npm install && npm run smoke     # the :cljs branch
```

Both suites pin the **same** Signing Input literal. §5.1 signs those exact bytes,
so a host disagreement would surface as `:jws/bad-signature` — pointing at the key
when the problem is the encoding.

## License

MIT. See `LICENSE`.
