# ADR-0001 — com-x architecture: a portable X (Twitter) API v2 boundary

- Status: Accepted
- Date: 2026-07-16
- Context tags: x-api, twitter-api, portable-cljc, vendor-client
- Builds on: `kotoba-lang/com-chatwork` (sibling extraction, same DI shape
  and code-first/token-later precedent), `kotoba-lang/com-gmail` (OAuth
  acquisition is explicitly out of scope, same non-goal)

## Context

The superproject notification-intake work (`90-docs/adr/2607161*-cloud-manimani-*`)
initially scoped X out entirely (Basic tier read access costs $200/mo+, no
free tier gives meaningful mentions/DM read). The owner asked for it anyway,
explicitly accepting: wire the code now, decide on paying for API access
later. This library is the "wire the code" half — it cannot be exercised
against the real API without a paid token, so it ships tested only against
a stubbed `:http-fn`.

## Decision

One namespace, `x.client`, matching `com-chatwork`'s "collapsed to what a
channel adapter needs" shape (not `com-gmail`'s per-capability split — X's
surface here is small: mentions search, DM read/write, tweet reply).
`:http-fn`/`:json-write`/`:json-read`/`:creds` DI, no default transport
shipped (fully `.cljc`-portable, zero JVM-only code), same as
`com-chatwork`.

## Auth model — two token shapes, not distinguished by this library

X API v2 splits auth by data sensitivity:
- **App-only** (OAuth 2.0 Client Credentials) — sufficient for public data
  (`search-recent-mentions`).
- **User-context** (OAuth 2.0 Authorization Code + PKCE, `dm.read`/
  `dm.write`/`tweet.write` scopes) — required for anything touching a
  specific user's private data (DMs) or posting as that user.

This library takes whichever token the caller has as `:creds {:bearer-token}`
and does not attempt to acquire, refresh, or distinguish between them — the
same non-goal `com-gmail` documents for its own Bearer token. A consumer
wiring a live channel adapter is responsible for the PKCE dance (a one-time,
interactive, human-in-the-loop flow — not something a background daemon
does for itself) and for storing the resulting access/refresh tokens.

## Cost is a first-class fact of this design, not an afterthought

Unlike every other vendor client in this workspace so far (Chatwork, Slack,
LINE, Gmail — all free at the tier a personal-use channel adapter needs),
X's read API costs real money starting at the Basic tier. This library
documents that prominently (README, this ADR) rather than let a consumer
discover it only when a 403 comes back from a free-tier token — the
"code now, pay later" decision this library exists to unblock only works
if the cost is visible up front.
