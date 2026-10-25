# Maturity

**Level: R2 live adapter**

Implemented:
- Authentication request, factor result, and decision models.
- Factor type validation.
- Assurance-level aggregation for single-factor, multi-factor, and phishing-resistant flows.
- Datom emitters for factor and decision records, with identity carried as a `:db.unique/identity` attribute rather than a per-transaction `:db/id` tempid, and absent attributes dropped rather than asserted as nil.
- One canonical schema (`authentication.schema`) in Datomic installation tx-data, converted for the in-memory store by `langchain.db/schema-from-tx-data`.
- Host verifier orchestration for factor requests.
- Factor verifier adapter boundary.
- Static local factor verifier implementation.
- Step-up challenge planner for required assurance level and risk.
- Replay-resistant decision ledger adapter boundary.
- Durable decision ledger on `langchain.db` + `journal`: an append-only EDN history replayed into a queryable index on open, with duplicate request-id rejection evaluated as a Datalog query rather than a bookkeeping set kept alongside the data.
- Production factor adapters for `faceid`, `touchid`, `webauthn`, `onetime`, OAuth, OIDC, and SAML.
- Production adapter for `cacao` (JVM/Node, via `cacao.core`).
- Edge production adapter for `cacao` (`authentication.adapters.cacao-edge`),
  the Cloudflare Workers path: WebCrypto Ed25519 via `cacao.edge.verify`,
  plus the authentication policy the crypto layer deliberately does not
  carry — audience binding, required capability URIs, and the per-DID
  issuer check (a caller can only ever authenticate as itself).
- Async verifier port (`IAsyncFactorVerifier`) and `authentication.async`,
  so a decision can combine Promise-returning edge verifiers with the
  synchronous JVM/Node ones.
- Contract tests for multi-factor success, factor-request verification, factor payload mapping, local factor verification, step-up planning, external factor normalization, and — for the ledger — nested factor pull, replay rejection, cross-transaction entity identity, restart recovery, journal history, and reference resolution from decision to factors.

Not yet R2:
- None.
