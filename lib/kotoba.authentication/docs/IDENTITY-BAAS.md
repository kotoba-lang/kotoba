# Kotoba Identity BaaS

`authentication.identity` is the portable CLJS domain layer for a Clerk-like
identity service. Product Workers provide HTTP, WebCrypto, mail, OAuth token
exchange and persistence; this repository provides one stable model for all of
them.

## Model

- User: one human or service principal.
- Identity: an email, Google, GitHub, Apple, Microsoft, OIDC, SAML, passkey or
  CACAO credential linked to a user.
- Session: an opaque browser credential represented server-side only by its
  digest. Production stores that digest as a Datomic entity so global
  revocation, tenant membership, history, and audit share one D1-backed source
  of truth. OAuth state, email challenges, and other one-time records remain
  ephemeral KV/DO data.
- Tenant and membership: the authorization and billing boundary, separate from
  the human user.
- Application: a relying application with an exact redirect-URI allowlist.

Provider adapters must return `normalized-profile`. Google and GitHub never
write provider-specific claims into the common user record. Claims remain on
the identity and can be refreshed independently.

## Required host flow

1. Generate OAuth state, OIDC nonce and PKCE verifier with WebCrypto.
2. Persist `oauth-transaction` with a short TTL and single-use flag.
3. Exchange the callback code server-side and verify state, PKCE, nonce,
   issuer, audience, signature and token times.
4. Normalize the provider profile.
5. Apply `link-decision`. An email match alone never links identities.
6. Transact user, identity, tenant and owner membership atomically.
7. Issue a random opaque cookie and persist only `session-record` with its
   SHA-256 digest.

Email password, magic-link and OTP delivery are adapters over the same Identity
model. Password derivation, token hashing and comparison belong in a WebCrypto
adapter; raw credentials and OAuth tokens must never enter Datomic.

## Public service surface

```text
POST /v1/email/register       POST /v1/email/login
POST /v1/email/verify         POST /v1/password/reset
GET  /v1/oauth/:provider/start
GET  /v1/oauth/:provider/callback
POST /v1/passkey/*            GET /v1/session
POST /v1/logout               GET /v1/identities
POST /v1/identities/:provider/link
DELETE /v1/identities/:id
```

Before offering this across products, add per-application redirect allowlists,
rate limiting, CSRF protection, global revocation, signing-key rotation, audit
events and account recovery. OIDC discovery/JWKS can then expose
the service to non-Kotoba applications without coupling them to its storage.

## Implemented adapters

- `authentication.adapters.webcrypto`: random opaque tokens, SHA-256 digests,
  S256 PKCE, PBKDF2 credential creation and password verification for Workers,
  browsers and Node.
- `authentication.adapters.oauth`: Google OIDC and GitHub OAuth authorization
  configuration plus normalized profiles. It deliberately leaves code exchange
  and JWKS verification at the trusted host boundary.
- `authentication.adapters.email`: expiring, attempt-limited, single-use records
  shared by email verification, OTP login, magic links and password recovery.

Durable users, identities, memberships, and session-token digests use the
Datomic persistence port. KV/DO is limited to short-lived OAuth and email
challenges. Provider client secrets and mail-provider credentials remain Worker
secrets and are never arguments to this domain API.

## Persistence adapters

- `authentication.adapters.datomic` supplies schema, tuple uniqueness,
  lookup queries, atomic account/link transaction plans, and a durable session
  store using `:identity.session/token-digest` lookup refs. The host injects
  Datomic `db`, `q`, `pull`, and `transact!` functions.
- `authentication.adapters.cloudflare-kv` implements the ephemeral storage
  port for sessions, OAuth transactions and email challenges. JSON keyword
  values cross this wire as strings. Production must inject a Durable Object
  coordinator for atomic put-once and consume; the KV-only fallback is intended
  for local development and tests because KV is eventually consistent.

## Service orchestration

`authentication.identity-service` is the application-facing CLJS API:

- `begin-oauth!` creates state, nonce and S256 PKCE, persists the private
  transaction, and returns only redirect-safe fields.
- `consume-oauth!` checks expiry and atomically consumes state before a host
  exchanges the authorization code.
- `complete-profile!` applies the no-email-auto-link policy, creates or links
  durable identity state and issues an opaque session.
- `issue-session!` requires an application audience and stores only a SHA-256
  digest. `rotate-session!` durably creates the replacement before revoking the
  old digest; `revoke-session!` invalidates the digest record.

The host still owns provider HTTP and signature verification. Its callback
sequence is `consume-oauth!` → code exchange/JWKS verification → normalized
profile → `complete-profile!`. This keeps unverified provider data outside the
durable identity transaction.
