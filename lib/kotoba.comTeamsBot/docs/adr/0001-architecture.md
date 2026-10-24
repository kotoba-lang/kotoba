# ADR-0001 — com-teams-bot architecture: a portable Bot Framework boundary

- Status: Accepted
- Date: 2026-07-16
- Context tags: teams-api, bot-framework, portable-cljc, vendor-client,
  webhook-verify, oauth2
- Builds on: `kotoba-lang/com-viber-bot`/`com-line-messaging` (events +
  client module shape), `kotoba-lang/com-meta-webhook` (webhook-verify
  split precedent, extended here for asymmetric JWT instead of symmetric
  HMAC)

## Context

Owner asked to expand messenger-app coverage further with verification
against live services deferred to later; Microsoft Teams is the largest
remaining enterprise-chat gap (parallel audience to Slack/Chatwork/
Mattermost, already covered). Teams' integration model — OAuth2
client-credentials auth, JWT-signed inbound webhooks, no fixed send
endpoint — is structurally the most different from every channel this
workspace has integrated so far, closer to "a distinct enterprise auth
system" than "one more REST API with a bearer token."

## Decision

Four namespaces: `jwt` (pure `.cljc`, structural parsing + claims
validation, no crypto), `jwt-verify` (`.cljs`-only, RS256 signature
verification via Web Crypto + JWKS fetch), `events` (pure `.cljc`, one
Activity per webhook call), `client` (portable `.cljc`, `fetch-token!` +
`send-message!`).

## Why split JWT verification into a pure layer and a crypto layer

Every other webhook-verify scheme in this workspace (`meta-webhook`,
`line-messaging`, `com-viber-bot`) is symmetric HMAC — one signature
namespace, one crypto call, done. A JWT carries structured, independently
meaningful claims (issuer, audience, expiry) that are worth validating on
their own regardless of whether the cryptographic signature check has
even run yet — and unlike the signature check, claims validation needs no
crypto API at all, so it can be fully portable and JVM-testable. Splitting
`jwt` (pure) from `jwt-verify` (crypto, `.cljs`-only) follows this
workspace's established sync/async split (extended: here it's really a
pure/crypto split, since the "sync" half needs to be pure `.cljc`, not
just JVM-sync) and means claims logic gets real unit-test coverage that a
combined "verify everything or nothing" function couldn't offer as
cleanly.

## Auth and send-endpoint are both structurally novel here

- **No static bot token.** `fetch-token!` is an OAuth2 client-credentials
  exchange, not a lookup of a pre-issued secret. The fetched token is
  short-lived (~1h) and this library deliberately does not cache or
  auto-refresh it — that's caller state, the same design choice
  `channels.discord`'s `:after-id` cursor and `channels.slack`'s `:seen`
  set already make (stateful concerns live in the consumer, not the
  client library).
- **No fixed send endpoint.** Every other channel's send URL is either a
  constant (Messenger's `/me/messages`) or built from a stable id
  (Instagram's `ig-user-id`, Discord's `channel-id`). Teams' is
  `{service-url}/v3/conversations/{conversation-id}/activities`, and both
  `service-url` and `conversation-id` are only available from the inbound
  Activity being replied to — `teams.events` surfaces both explicitly so
  a consumer can carry them through to the reply call (analogous to how
  `cloud-manimani.line`'s `:from "line:" + userId` convention carries the
  reply target through storage, but here it's two fields, not one).

## Honesty about verification depth (also in the README)

`jwt-verify`'s RS256 signature check and JWKS fetch are implemented per
Microsoft's published Bot Framework authentication documentation, but
**have never been exercised against a real Bot Framework token issuer** —
no Azure Bot deployment exists to generate a genuine signed JWT to test
against. This is a categorically different verification gap from
"no real credentials configured yet" (every other channel's situation):
asymmetric signature verification against a third party's live public
keys cannot be validated with a self-generated known-answer vector the
way this workspace's HMAC schemes were. `jwt.cljc`'s pure claims logic
(`valid-claims?`) IS fully unit-tested; the crypto half is
code-reviewed-correct-per-spec, not field-verified.

## Consequences

- `gftdcojp/cloud-manimani`'s `POST /webhook/teams` route needs both
  `jwt-verify` (crypto) and `jwt` (claims) to accept an inbound Activity —
  a consumer skipping either check accepts unverified requests.
- This library does not perform the Azure AD App Registration, Azure Bot
  resource creation, or messaging-endpoint configuration — all
  owner-side, out-of-band, and larger in scope than any other channel's
  setup in this workspace.
