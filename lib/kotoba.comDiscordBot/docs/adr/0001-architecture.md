# ADR-0001 — com-discord-bot architecture: a portable Discord Bot API boundary

- Status: Accepted
- Date: 2026-07-16
- Context tags: discord-api, portable-cljc, vendor-client
- Builds on: `kotoba-lang/com-chatwork` (sibling extraction, same DI shape
  and error-shape convention), `kotoba-lang/com-x` (the disambiguation
  precedent for naming around an unrelated same-named repo)

## Context

Owner asked which globally-used messenger apps were still missing after
Chatwork/Slack/LINE/WhatsApp/Messenger/X/Instagram. Discord has a mature,
free, official Bot API and no App-Review-style approval gate for basic
message read/send — the lowest-friction remaining gap. `kotoba-lang/com-discord`
already exists but is an unrelated clean-room re-implementation of
Discord's own platform (relocated from `etzhayyim/root/20-actors/discord-compat`,
ADR-2607041500), not a client for the real API — the same trap
`kotoba-lang/com-line-api` was for LINE, resolved there by naming the real
client `com-line-messaging`. This library is named `com-discord-bot` for
the same reason: unambiguous, doesn't collide with the existing repo.

## Decision

One namespace, `discord.client`, matching `com-chatwork`'s "collapsed to
what a channel adapter needs" shape: `list-messages` + `send-message!`.
`:http-fn`/`:json-write`/`:json-read`/`:creds` DI, no default transport
shipped (fully `.cljc`-portable). Failure returns an explicit
`{:ok false :status :error}` map from `send-message!` (the
`com-x`-bugfix convention, ADR reference: local-manimani's ADR-0040
addendum documents the bug this convention prevents) and `[]` from
`list-messages` (fail-open, matching `x.client/search-recent-mentions`'s
posture for a polling fetch).

## REST polling, not the Gateway — a deliberate scope cut

Discord's own recommended integration path for a bot is the persistent
Gateway WebSocket (real-time event push, required for slash commands,
presence, etc.). This library uses REST polling
(`GET /channels/{id}/messages`) instead, for one reason: every other
channel adapter in this workspace (`chatwork.client`, `x.client`,
`tayori.channel.slack`) is poll-based, and a personal-scale single-channel
watch has no need for the Gateway's real-time guarantees or its
substantially larger implementation surface (persistent connection
lifecycle, heartbeat/reconnect logic, sharding for large bot deployments).
A consumer that later needs real-time delivery across many
channels/guilds should build Gateway support separately — deliberately not
attempted here (YAGNI), since REST polling with an `:after` cursor already
satisfies "watch one channel, surface new messages within a poll interval."

## Consequences

- `gftdcojp/local-manimani`'s `channels.discord` adapter is a direct poll
  (`gw/Channel`), no cloud-manimani bridge needed — unlike LINE/WhatsApp/
  Messenger/Instagram, Discord's REST API supports listing recent messages
  directly, so there's no webhook-only constraint to work around.
- This library does not acquire the bot token, register the Discord
  application, or handle the OAuth2 bot-invite flow — all owner-side,
  out-of-band actions.
