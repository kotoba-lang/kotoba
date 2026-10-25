# ADR-0001 — com-line-messaging architecture: a portable LINE Messaging API boundary

- Status: Accepted
- Date: 2026-07-16
- Context tags: line-messaging-api, portable-cljc, vendor-client, webhook-verify
- Builds on: `kotoba-lang/com-gmail` (sync-`.cljc` + separate-async-surface
  precedent), `kotoba-lang/com-chatwork` (sibling extraction, same DI shape),
  `kotoba-lang/tayori`'s `tayori.channel.slack` (`{:http-fn :json-write
  :json-read :creds}` DI convention)

## Context

`gftdcojp/local-manimani`'s notification-intake survey (superproject
`90-docs/adr/2607161*-cloud-manimani-*`) found LINE support limited to a
computer-use-driven "Claude reads LINE in Chrome" workflow — no API
integration, no normalized ingest. Unlike Email/Gmail/SMS/Telegram/Chatwork,
LINE's Messaging API is push-only inbound (a webhook, not a pollable
inbox) — a `local-manimani`-only implementation the way `channels.sms` is
device-local doesn't fit, since something needs a public HTTPS endpoint to
receive the webhook, and `local-manimani` (a personal-machine JVM daemon) has
none. `gftdcojp/cloud-manimani` (a Cloudflare Worker, already public) is the
natural receiver, but its runtime is cljs, not JVM — so a naive
JVM-`http-fn`-only client library would not actually be usable by the piece
of the system that needs it most.

## Decision

Split the surface along the actual sync/async fault line, not by an
imagined future scope:

- **`line-messaging.signature`** (`:clj`-only, sync `javax.crypto.Mac`) and
  **`line-messaging.async-signature`** (`.cljs`-only, `js/Promise` via
  `crypto.subtle`) verify `X-Line-Signature` on their respective platforms.
  This is the same split `com-gmail` documents for its own
  `gmail.client`/`gmail.async-client` — Web Crypto's `subtle.sign` cannot be
  made synchronous, so one shared `.cljc` implementation is not possible;
  pretending otherwise (e.g. a callback-based fake-sync API) would be worse
  than two honestly-different-shaped functions.
- **`line-messaging.events`** is pure `.cljc` (no I/O, no crypto) — parses an
  already-verified, already-JSON-decoded webhook body into normalized
  `{:type :line-text :user-id :reply-token :text :ts}` records. Both the
  Worker (cljs) and any future JVM consumer share this unchanged.
- **`line-messaging.client`** (`push!`/`reply!`) is portable `.cljc` with
  injected sync `:http-fn`, the same DI shape as `com-chatwork` — this is
  the piece `local-manimani` (JVM) actually calls, since LINE's *send* API is
  plain request/response HTTP, unlike the inbound webhook's signing step.

## Consequences

- `gftdcojp/cloud-manimani`'s webhook route depends on
  `line-messaging.async-signature` + `line-messaging.events` (cljs Worker
  runtime) to verify and normalize inbound LINE events, then forwards them
  toward kotobase.net the same way its existing kotobase-sync path already
  moves data (ADR: see the superproject's cloud-manimani LINE-webhook ADR).
- `gftdcojp/local-manimani`'s `channels.line` adapter (JVM) depends on
  `line-messaging.client` for `push!`-based replies (chosen over `reply!`
  because `local-manimani`'s ingress is poll-based against kotobase, not a
  live webhook handler — by the time a poll picks up a LINE message and a
  human/LLM decision resolves, the ~1-minute `replyToken` window has almost
  certainly expired; see the `client.cljc` docstring). This library does not
  bridge cloud→local itself — that plumbing lives in the two consumer repos.
- No cljs-side `push!`/`reply!` (unlike `com-gmail`'s async surface, which
  mirrors *read* operations for a real nbb consumer). Not built here because
  no consumer needs it yet — `cloud-manimani` only receives and forwards,
  it does not itself send LINE replies. Add a `line-messaging.async-client`
  if and when that changes, following the same `.then`/`js/Promise.reject`
  pattern `com-gmail`'s async surface documents, rather than speculatively
  building it now.
