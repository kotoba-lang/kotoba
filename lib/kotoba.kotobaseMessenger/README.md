# kotobase-messenger

[![CI](https://github.com/kotoba-lang/kotobase-messenger/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/kotobase-messenger/actions/workflows/ci.yml)

**A LINE/Signal-style 1:1 and group messenger, built as AT-Protocol lexicons
(`app.aozora.convo.*` / `app.aozora.actor.*`) over kotobase.** This is the
messenger domain logic extracted out of `network-awai/app-aozora` (its original
home and current sole consumer) into a standalone, reusable ClojureScript
library, per ADR-2607092345.

## What's here

- `pds/src/aozora/pds/{convo,actor,prekeys,push}.cljc` — PDS write handlers:
  create/rename a conversation, send/edit/delete/react to a message, mark
  read, set a typing heartbeat, add/remove group members, block/unblock an
  actor, register a Signal-protocol prekey bundle, and fan out Web Push
  notifications for new messages.
- `appview/src/aozora/appview/{convo,actor,prekeys}.cljc` — the matching
  AppView read projections (list/get queries over the same kotobase scan
  substrate every other AppView projection in the consuming app reads from).
- `lexicons/app/aozora/{convo,actor}/*.json` — the AT-Protocol lexicon
  definitions for every NSID the code above implements. Kept alongside the
  implementation deliberately: a consumer needs both the wire format and the
  handler code, and the spec should never drift from what actually ships.
- `ui/src/yoro_ui/{pages/{convo,convo_detail},state/{convos,convo_search,
  blocks},interop/{signal,signal_group}}.cljc` — the Reagent/re-frame
  frontend: the conversation list + detail pages, their re-frame state
  (including E2E-safe search that never scans raw ciphertext), and the
  Signal-protocol session/group interop the UI drives directly.

Every `(ns ...)` form is **unchanged** from its original app-aozora location
— this is a pure relocation, not a rewrite or a rename. Any consumer that
already speaks `app.aozora.convo.*`/`app.aozora.actor.*` (i.e. app-aozora
itself, or a future app choosing to adopt the same protocol) gets full
data-level interop for free, since the NSIDs never changed.

## What's *not* here (and why)

This library depends on generic AT-proto-over-kotobase platform primitives
that stay in the consuming app rather than move here, because they're used
by every collection type in that app, not just the messenger:

- `aozora.pds.repo` (record create/delete/CID/URI — generic CRUD)
- `aozora.pds.per-actor` (per-actor DB routing)
- `aozora.pds.webpush` / `aozora.pds.pushsub` / `aozora.appview.push`
  (RFC 8291/8292 Web Push crypto and subscription management — generic, no
  conversation awareness; the messenger-specific piece is only the *decision
  of when to notify and with what body*, which is what `aozora.pds.push`
  here implements)
- `aozora.appview.{feed,scan}` (the shared kotobase-scan substrate)

A consuming app's shadow-cljs build adds this repo's `pds/src` + `appview/src`
+ `ui/src` to its own `:source-paths`/`deps.edn` paths alongside its own
copies of the namespaces above — the same relative-source-path pattern
`kotoba-lang/org-signal` already established for the crypto layer. See
`network-awai/app-aozora`'s `40-engine/cljs/shadow-cljs.edn` (backend) and
`60-apps/appview/cljs/deps.edn` (frontend, `:deps true` in that dir's
`shadow-cljs.edn` defers entirely to `deps.edn`) for working examples.

## Testing

**This repo does not run its own tests.** The code here still `:require`s
the consuming app's platform namespaces listed above, so a fully standalone
test harness would mean replicating that app's entire PDS/AppView dependency
graph for zero real benefit today (app-aozora is the only consumer). Once
this repo's source-path is added to a consumer's shadow-cljs build, its
`*_test.cljc` files (matching that build's `-test$` `ns-regexp`) run
automatically as part of that consumer's own test suite — no extra wiring
needed. CI here only runs `clj-kondo` (`kbb -M:lint`), which catches
syntax/style issues without needing the full dependency graph. Revisit a
standalone harness if/when a second real consumer exists.

## License

Apache 2.0 — see `LICENSE`.
