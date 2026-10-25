# ADR-0001 — com-matrix architecture: a portable Matrix Client-Server API boundary

- Status: Accepted
- Date: 2026-07-16
- Context tags: matrix-protocol, portable-cljc, vendor-client, self-hosted,
  federated
- Builds on: `kotoba-lang/com-mattermost` (the `:creds :base-url`
  self-hosted precedent), `kotoba-lang/com-discord-bot` (the
  REST-not-realtime scope-cut precedent)

## Context

Owner asked to expand messenger-app coverage further with verification
against live services deferred to later. Matrix is an open, federated,
non-vendor-gatekept protocol (no ToS/App-Review gate at all, unlike every
Meta product this workspace already integrates) with a well-documented
Client-Server API — a good coverage addition with none of the access-tier
or approval-process friction other channels carry.

## Decision

One namespace, `matrix.client`: `sync!` + `send-message!`. Same DI shape
as every sibling client, plus `:creds :base-url` (Matrix is self-hosted/
federated like Mattermost, no fixed API host).

`sync!` deliberately uses `timeout=0` rather than Matrix's native
long-polling `/sync` semantics — every channel adapter in this workspace
polls on its own interval against a synchronous `:http-fn` contract, which
isn't shaped for holding a connection open server-side for up to 30s
waiting on new events. A consumer wanting genuine push-latency delivery
should implement real long-polling directly against this same endpoint
(just don't pass `timeout=0`) — not built here, matching
`com-discord-bot`'s Gateway-vs-REST scope cut for the same underlying
reason (real-time delivery is a materially different implementation shape
than "poll periodically," and this workspace's channel adapters only need
the latter).

## Event flattening — a map's own keys need no id-type reconciliation

`sync!`'s response nests message events three levels deep
(`rooms.join.{room-id}.timeline.events[]`), with `room-id` as a dynamic
map key (like Mattermost's post ids). Unlike `mattermost.client/list-messages`
— which cross-references two independently-obtained collections (`:order`
strings vs `:posts` map keys) and can silently mismatch types — `sync!`
only ever destructures `rooms`' own entries directly (`(for [[room-id room]
rooms] ...)`), so whatever type the caller's `:json-read` produced for
that key, `room-id` already has the right value with no separate lookup
to get wrong. `(name room-id)` normalizes it to a plain string for the
output regardless.

## Consequences

- `gftdcojp/local-manimani`'s `channels.matrix` adapter stores the
  `:next-batch` cursor between polls (like Discord's `:after-id`) rather
  than client-side deduping by seen-id (like the cloud-manimani-bridged
  channels) — Matrix's own sync cursor already guarantees no
  re-delivery, so a second dedup layer would be redundant.
- This library does not acquire the access token or manage a homeserver
  deployment — both owner-side, out-of-band.
