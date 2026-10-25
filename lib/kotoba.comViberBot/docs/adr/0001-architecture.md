# ADR-0001 — com-viber-bot architecture: a portable Viber REST Bot API boundary

- Status: Accepted
- Date: 2026-07-16
- Context tags: viber-api, portable-cljc, vendor-client, webhook-verify
- Builds on: `kotoba-lang/com-line-messaging` (the sync/async signature
  split precedent, the events+client module shape)

## Context

Owner asked to expand messenger-app coverage further with verification
against live services deferred to later. Viber has an official, free Bot
API with a webhook delivery model similar in shape to LINE's (a signed
POST per event) — the closest existing precedent in this workspace is
`com-line-messaging`, not `com-meta-webhook` (Viber's signature scheme and
webhook-registration direction both differ from Meta's, see below).

## Decision

Four namespaces mirroring `com-line-messaging`'s shape: `signature`
(`:clj`-only sync `javax.crypto.Mac`), `async-signature` (`.cljs`-only
`js/Promise` via `crypto.subtle`), `events` (pure `.cljc`, one event per
webhook call — Viber doesn't batch), `client` (portable `.cljc`, DI'd
`:http-fn`, `send-message!` + `set-webhook!`).

## Two structural differences from every Meta product this workspace integrates

1. **One token, not two.** WhatsApp/Messenger/Instagram each have a
   separate App Secret (verifies webhooks) and access token (sends
   messages) — two distinct credentials. Viber has only `bot-token`: it
   authenticates `send-message!`/`set-webhook!` calls AND is the HMAC key
   `signature`/`async-signature` verify inbound webhooks with. A consumer
   expecting a `VIBER_APP_SECRET`-shaped env var (by analogy to
   `WHATSAPP_APP_SECRET` etc.) would be looking for something that doesn't
   exist — documented prominently in both this ADR and the `signature.cljc`
   docstring specifically because it's an easy wrong assumption to import
   from the Meta-product precedent.
2. **Webhook registration is caller-initiated, not receiver-verified.**
   Meta products call *your* webhook URL with a `GET`
   `hub.challenge`-style verification handshake when you register it in
   their dashboard. Viber has no equivalent inbound handshake — instead
   *your* backend calls Viber's own `POST /set_webhook` API with your URL.
   `client/set-webhook!` is that one-time setup call. There is no `GET`
   route for a consuming Worker to implement for Viber (unlike
   `cloud-manimani`'s `GET /webhook/{whatsapp,messenger,instagram}`
   handshake routes).

## Consequences

- `gftdcojp/cloud-manimani`'s `POST /webhook/viber` route needs no
  matching `GET` handshake route — a real deployment instead runs
  `set-webhook!` once (a setup script, not a request-path route) pointing
  Viber at the Worker's URL.
- This library does not acquire the bot token or register the bot in the
  Viber Admin Panel — both owner-side, out-of-band.
