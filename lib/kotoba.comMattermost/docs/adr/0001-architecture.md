# ADR-0001 — com-mattermost architecture: a portable Mattermost API v4 boundary

- Status: Accepted
- Date: 2026-07-16
- Context tags: mattermost-api, portable-cljc, vendor-client, self-hosted
- Builds on: `kotoba-lang/com-chatwork`, `kotoba-lang/com-discord-bot`
  (sibling extraction, same DI shape and error-shape convention)

## Context

Owner asked to expand messenger-app coverage further (self-hosted Slack
alternative, popular in privacy-conscious/self-hosted orgs) with
verification against live services deferred to later. Mattermost's REST
API deliberately mirrors much of Slack's own Web API shape, and this
workspace already has two REST-polling precedents (`com-chatwork`,
`com-discord-bot`) to follow.

## Decision

One namespace, `mattermost.client`: `list-messages` + `send-message!`.
Same `:http-fn`/`:json-write`/`:json-read`/`:creds` DI as every sibling
client, **plus** `:creds :base-url` — the one structural difference from
every other client in this workspace, because Mattermost is self-hosted
and has no single fixed API host the way Discord/Chatwork/Slack do.

## A real bug this ADR documents finding during implementation

Mattermost's `GET /posts` response nests posts as
`{:order [id ...] :posts {id {...}}}` — a keyed-by-id map plus a separate
ordering array, not a plain list. `:order`'s entries are always plain JSON
strings; `:posts`' keys are dynamic (post ids) and land as either strings
or keywords depending entirely on the *caller's* `:json-read`
configuration (`:key-fn keyword` vs `:key-fn identity`). A first pass at
`list-messages` did `(mapv posts order)` assuming matching key types —
under this workspace's own convention (every other channel client injects
`#(json/read-str % :key-fn keyword)`), that silently returns `nil` for
every post (a keyword-keyed map has no entry under a string key), and
`list-messages`' fail-open contract (`[]` on failure) means the bug would
have been **invisible** — a channel that "worked" but silently delivered
zero messages, forever, with no error anywhere. Fixed to try
`(keyword id)` first, falling back to the raw string; a regression test
using this workspace's exact `:key-fn keyword` convention would have
caught (and now does catch) the original bug.

## Consequences

- `gftdcojp/local-manimani`'s `channels.mattermost` adapter needs an extra
  `MANIMANI_MATTERMOST_BASE_URL` env var alongside the token, unlike every
  other channel's single-token configuration — documented prominently so a
  consumer doesn't get a confusing "channel silently does nothing" failure
  from a missing base URL.
- This library does not acquire the token or manage a Mattermost server
  deployment — both owner-side, out-of-band.
