# authentication

Authentication decision substrate. It combines factor results from FaceID,
TouchID, WebAuthn, OTP, CACAO, OAuth/OIDC/SAML, or host-defined factors.

Ethereum wallet sign-in is a first-class `:siwe` factor through
`authentication.adapters.siwe-edge`. It verifies strict EIP-4361 messages and
EIP-191 secp256k1 signatures, then authenticates the chain-bound
`did:pkh:eip155:<chain-id>:<address>` principal. Hosts must issue and atomically
consume the nonce; a valid signature alone is intentionally only
`:single-factor`, not a substitute for a phishing-resistant passkey.

`docs/IDENTITY-BAAS.md` describes the Clerk-shaped identity service built on
top of it (`authentication.identity`, `authentication.identity-service`);
`docs/PRODUCTION-HARDENING.md` describes the fail-closed contracts a host must
apply before exposing that service publicly.

## Where decisions are kept

`authentication.schema` declares every attribute once, in Datomic's
installation tx-data dialect. A real Datomic connection transacts it as-is;
`langchain.db/schema-from-tx-data` converts it for the in-memory store. Each
entity carries its identity as a `:db.unique/identity` attribute — a string
`:db/id` is a tempid scoped to one transaction, so it could never have made
two transactions about the same decision refer to one entity.

`authentication.adapters.journal-ledger` is the durable `IDecisionLedger`:
[`langchain.db`](https://github.com/kotoba-lang/langchain) holds the index and
answers the Datalog, [`journal`](https://github.com/kotoba-lang/journal) holds
the append-only history, and the connection replays that history on open — so a
restarted process answers the same queries the previous one did, and the replay
invariant (one decision per request id) is a query rather than a set maintained
by hand.

```clojure
(def ledger (jl/journal-decision-ledger {:path "authn.journal.edn"}))
(ledger/persist-decision! ledger decision {:request-id "r1"})
(jl/decision ledger "r1")   ;; the decision, factors nested
(jl/history io)             ;; what happened, in order
```

## Two hosts, two verifier shapes

Factor verification is synchronous where the platform API is
(`IFactorVerifier`) and Promise-returning where it is not
(`IAsyncFactorVerifier`) — every WebCrypto-backed edge verifier is the latter,
because `crypto.subtle` returns Promises. `authentication.async/authenticate!`
takes a verifier map holding either kind and reaches the same decision
`authentication.core/decide` would, so a Cloudflare Worker and a JVM host stay
on one decision path instead of two.

That distinction is why `cacao` has two production adapters, not one:

| adapter | host | crypto |
|---|---|---|
| `authentication.adapters.cacao` | JVM / Node | `cacao.core` (`node:crypto`, `js/Buffer`) |
| `authentication.adapters.cacao-edge` | Cloudflare Workers, browsers | `cacao.edge.verify` (WebCrypto `crypto.subtle`) |

Both verify the same wire format. The edge adapter additionally carries the
policy the crypto layer deliberately does not — audience binding, required
capability URIs, and the **per-DID issuer check**: when a factor request names
a subject, the CACAO's issuer must equal it, so a crypto-valid CACAO from one
DID can never authenticate another (ADR-2607177000's structural rule, applied
at the authentication layer rather than re-derived per product Worker).

## Tests

```bash
kbb -M:test                                   # JVM: models, policy, decisions
kbb --backend sci --classpath "src:test:../org-chainagnostic-cacao/src" \
    test/authentication/cacao_edge_smoke.cljk     # edge CACAO, real WebCrypto Ed25519
kbb --backend sci --classpath "src:test:../org-chainagnostic-cacao/src" \
    test/authentication/siwe_edge_smoke.cljk      # edge SIWE, real EIP-191/secp256k1
```

The `.cljs` smokes are not reachable from `kbb -M:test` (they are CLJS-only
by construction) and are not yet wired into CI.
