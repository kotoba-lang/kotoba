# ADR-0001 — com-meta-webhook architecture: shared Meta Graph API webhook boundary

- Status: Accepted
- Date: 2026-07-16
- Context tags: whatsapp-api, messenger-api, meta-graph-api, webhook-verify,
  portable-cljc
- Builds on: `kotoba-lang/com-line-messaging` (the exact split this library
  mirrors: sync `.cljc` signature / async `.cljs` signature / pure `.cljc`
  event parsing / DI'd `.cljc` send client), `kotoba-lang/tayori`'s
  `tayori.channel.whatsapp` (existing WhatsApp send-side, not duplicated
  here)

## Context

The superproject's notification-intake work added a LINE webhook
(`kotoba-lang/com-line-messaging` + `cloud-manimani`'s `POST /webhook/line`)
and, per an owner follow-up, needed the same for WhatsApp and Messenger.
Both are Meta Graph API products and — unlike LINE, Slack, Chatwork — share
byte-for-byte identical webhook plumbing: the same `X-Hub-Signature-256`
HMAC-SHA256 scheme, the same `hub.mode`/`hub.verify_token`/`hub.challenge`
GET setup handshake. Building two separate signature/handshake
implementations (one per product) would be pure duplication of logic that
is, by Meta's own design, product-agnostic.

## Decision

One library, `com-meta-webhook`, covering the product-agnostic webhook
plumbing (`signature`, `async-signature`, `handshake`) plus one
events-parsing namespace per product (`whatsapp-events`,
`messenger-events` — these DO differ, WhatsApp's payload shape is not
Messenger's). WhatsApp's send-side already exists
(`tayori.channel.whatsapp`) so this library does not re-implement it;
Messenger has no existing send client in kotoba-lang, so
`messenger-client` fills that specific gap rather than the whole surface.

## Why not fold this into com-line-messaging instead

LINE's signature scheme (base64 HMAC-SHA256, no handshake step — LINE
verifies webhook URLs differently, via a "Verify" button in the console
that just checks for a 200 response) is a different, LINE-specific
protocol, not a Meta one. Naming a shared library `com-line-messaging` and
then adding Meta's unrelated crypto/handshake scheme to it would misname
the boundary; `com-meta-webhook`'s name accurately scopes it to "whatever
Meta Graph API products share," which is exactly WhatsApp + Messenger (and
would extend to Instagram Messaging, which uses the identical scheme, if a
consumer needs that later — not built now, YAGNI).

## Consequences

- `gftdcojp/cloud-manimani` gains `POST /webhook/whatsapp` and
  `POST /webhook/messenger` routes, each following the same shape
  `POST /webhook/line` already established (verify raw body BEFORE the
  generic JSON-body dispatch, since a Request body stream reads once).
- `gftdcojp/local-manimani` gains `channels.whatsapp` and
  `channels.messenger` — both poll-based `gw/Channel`s against
  cloud-manimani's `/inbox` (WhatsApp/Messenger, like LINE, have no
  conversation-history polling endpoint of their own — inbound only ever
  arrives via the webhook push), the identical companion-side pattern
  `channels.line` established.
- Neither this library nor its consumers acquire the App Secret / page
  access token / WhatsApp access token themselves — Meta App creation, App
  Review (required for Messenger's `pages_messaging` permission and
  WhatsApp's message-template/production-access approval), and token
  issuance are all owner-side, out-of-band actions.

## Addendum (2026-07-16): Instagram Messaging

A third consumer appeared (owner asked to fill remaining messenger-app gaps
after X/WhatsApp/Messenger; Instagram Messaging is the same Meta Graph API
family this library already exists to share). `meta-webhook.signature`/
`async-signature`/`handshake` need zero changes — verified identical scheme
across all three Meta products. Added `instagram-events` (separate
namespace from `messenger-events` despite an identical payload shape today,
since Instagram's webhook also carries story-mention/story-reply events
Messenger doesn't — keeping them separate avoids an awkward retrofit if
this ns grows to normalize those) and `instagram-client` (send-side;
Instagram's send endpoint is scoped to the connected IG Business/Creator
account id, `/{ig-user-id}/messages`, unlike Messenger's fixed `/me/messages`
— different enough to not share `messenger-client` directly, same DI
contract). Requires its own App Review (`instagram_manage_messages`
permission) and its own verify-token/app-secret pair, same posture as
WhatsApp/Messenger above.
