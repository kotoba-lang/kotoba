# ADR-0001 — com-chatwork architecture: a portable Chatwork API v2 boundary

- Status: Accepted
- Date: 2026-07-16
- Context tags: chatwork-api, portable-cljc, vendor-client
- Builds on: `kotoba-lang/com-gmail` (extract-a-common-client precedent),
  `kotoba-lang/tayori`'s `tayori.channel.slack` (the `{:http-fn :json-write
  :json-read :creds}` DI shape this library reuses verbatim)

## Context

`gftdcojp/local-manimani` (ADR-0021 常駐ゲートウェイ, see also the
superproject's `90-docs/adr/2607161*-cloud-manimani-*` notification-intake
survey) had Email/Gmail/SMS/Telegram channels but no Chatwork — a channel it
had only ever *named* in its README's extension-points list, never
implemented. Chatwork's REST surface (message list + send, token header
auth) is small and has no existing kotoba-lang home; building it inline
inside `local-manimani/agents/src/channels/chatwork.clj` would strand it
there, unavailable to any other project (e.g. a future actor, or
`kotoba-procedure`-driven correspondence flow) the way `com-gmail` already
serves both `local-manimani` and `tayori`.

## Decision

One namespace, `chatwork.client`, following `com-gmail`'s "one tested client
namespace, injectable I/O" shape but collapsed to Chatwork's much smaller
surface (list + send + `/me`) rather than `com-gmail`'s per-capability
namespace split — there is no separate threads/labels/drafts concern here to
warrant it. I/O is injected `{:http-fn :json-write :json-read :creds
{:api-token}}`, the exact same convention `tayori.channel.slack` already
uses (not `com-gmail`'s own JVM-only `jvm-http-fn` default — this library
ships no default transport at all, so it stays `.cljc`-portable with zero
JVM-only code, unlike `com-gmail`).

## Auth model

Chatwork has no OAuth app / bot concept for a simple room integration — a
personal or room-scoped API token (`X-ChatWorkToken` header) is the normal
shape (My Profile → API Token in the Chatwork web UI). This library takes
the token as `:creds {:api-token "..."}` and does no token acquisition or
refresh — same non-goal `com-gmail` documents for its own Bearer token.

## Consequences

- `gftdcojp/local-manimani`'s `channels.chatwork` adapter (ADR-0021 Stage 3)
  depends on this library instead of re-deriving Chatwork HTTP calls inline,
  matching how `channels.gmail` depends on `com-gmail`.
- Message-send is `POST` with an `application/x-www-form-urlencoded` body
  (not JSON, unlike every other endpoint in this library and unlike
  `com-gmail`) — Chatwork's own API requires this for `/messages`. Encoded
  via `java.net.URLEncoder` (`:clj`) / `encodeURIComponent` (`:cljs`) with a
  `%20`→`+` fixup, deliberately the *opposite* choice from `com-gmail`'s
  `client/request!` (which avoids `URLEncoder` because it needs RFC 3986
  *query-string* encoding, not form-body encoding) — the two libraries pick
  different encoders because they are encoding into different targets, not
  because of an inconsistency.
