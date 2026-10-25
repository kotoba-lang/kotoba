# ADR-0001 — com-gmail architecture: a portable Gmail API v1 boundary

- Status: Accepted
- Date: 2026-07-06
- Context tags: gmail-api, portable-cljc, vendor-client
- Builds on: `kotoba-lang/com-cloudflare` (client/`:http-fn` injection
  pattern), `gftdcojp/local-manimani` (`server/src/gmail.ts`, the TS Gmail
  boundary this library gives a portable `.cljc` counterpart to)

## Decision

Give Gmail the same treatment `com-cloudflare` gave the Cloudflare API: one
tested `client` namespace (auth + HTTP + JSON envelope, injectable
`:http-fn`) plus one namespace per capability area (`threads`, `labels`,
`drafts`), all pure `.cljc` except the JVM-only default transport and
`java.util.Base64`-dependent MIME builder.

## Why extract rather than build fresh per host

manimani's own Gmail wiring lives in TypeScript (`server/src/gmail.ts`) and
isn't reachable from `.cljc` hosts (a babashka runner, `kotoba-procedure-clj`
consumers, a future actor). A chat assistant's own ad hoc Gmail connector is
frequently granted read-only scope and can't perform the label/draft writes
a triage workflow needs. Rather than hand-roll thread-list/label-modify/
draft-create HTTP calls again per project, this library is the one place
that logic lives, tested against stubs.

## Module boundaries

```
client      auth (Bearer access token) + HTTP (injectable :http-fn) + JSON request/response envelope
threads     list / get / modify (label add-remove) / archive / trash / untrash / delete
labels      list / create / find-or-create (by display name, resolving to a label id) / delete
drafts      RFC 2822 plain-text message builder + get / list / create / update / delete (optionally thread-scoped)
history     users.history.list -- cursor-based "what changed since historyId" (incremental sync)
mime        decode an INBOUND message payload: body data (base64url) / headers (case-insensitive) / plain-text + html body / attachment descriptors
attachments download an inbound attachment's raw bytes (users.messages.attachments.get, under /messages not /threads)
```

## Non-goals

- The OAuth2 consent/refresh flow itself -- callers supply a valid access
  token (env `GMAIL_ACCESS_TOKEN` or explicit `:token`), mirroring
  `cloudflare.client`'s `CLOUDFLARE_API_TOKEN` convention.
- HTML draft bodies -- `drafts/->raw-message` builds a plain-text body only
  (multipart/mixed for file attachments is supported as of the 2026-07-13
  addendum below; multipart/alternative for an HTML+plain-text body pair is
  not).

## Consequences

- `gftdcojp/local-manimani`'s babashka/`.cljc` path (its own README already
  treats this as canonical over the TS `server/`) can depend on this library
  instead of shelling out or re-deriving Gmail HTTP calls.
- `kotoba-lang/kotoba-procedure-clj` procedures whose steps are "reply to
  this thread" or "wait for the counterparty's Gmail reply" can drive Gmail
  state through this library without a code dependency between the two
  (same "shared vocabulary, no shared code" relationship as
  `kotoba-issue-clj`/`kotoba-ledger-clj`).

## Addendum (2026-07-13): `gmail.history`

`kotoba-lang/tayori`'s own `tayori.channel.email/list-new-messages` (ADR
2607061500) returns `[]` unconditionally, with a code comment explaining why:
Gmail's `threads.get`/`threads.list` have no "since" filter, so polling by
`q`/date alone can't distinguish "new since last time" from "everything
again" -- a real implementation needs `users.history.list` against a
persisted `historyId` cursor, which this library didn't yet expose. Added
`gmail.history/list-history` to close that gap (consumed first by
`kotoba-lang/mail-archive`'s incremental sync; wiring it into tayori's own
`list-new-messages` is a separate follow-up, not done here).

**Known limitation carried over from `gmail.client/request!`**: its
query-string builder (`(map (fn [[k v]] (str (name k) "=" v)) query)`)
serializes one value per key and does not URL-encode. Gmail's
`historyTypes` filter is a *repeated* query param
(`historyTypes=X&historyTypes=Y`), which this shape cannot express --
`gmail.history/list-history` intentionally does not expose a `history-types`
param rather than silently mis-serializing one. Any caller needing to
narrow the returned records to specific change types should filter the
`:history` response client-side. Fixing this properly (real query-string
encoding, repeated-key support) would touch `client.cljc`'s core request
builder and is out of scope for this addition.

## Addendum (2026-07-13): `drafts/->raw-message` gains `:cc` and `:references`

A real reply-into-an-existing-thread case (multiple Cc'd recipients, more
than one prior message) needed both: `:cc` accepts a single address string
or a collection (joined with `", "`); `:references` lets a caller supply the
full RFC 2822 References chain instead of the previous behavior of always
mirroring `:in-reply-to` alone -- Gmail's own threading heuristic (and other
clients') considers the whole chain, not just the immediate parent, so
always collapsing References to one Message-ID under-informed threading on
deep replies. `:references` is optional; omitting it preserves the old
mirror-`:in-reply-to` behavior exactly, so this is additive/non-breaking.

## Addendum (2026-07-13): `drafts/->raw-message` gains `:attachments`

A reply needed to carry reference diagrams (SVG) alongside the text body.
`:attachments` is a collection of `{:filename :content-type :bytes}`;
when present the message becomes `multipart/mixed` (a `text/plain` part
plus one part per attachment, base64-encoded with RFC 2045 line wrapping
via `Base64/getMimeEncoder` -- a *different* encoding layer than the
URL-safe, unwrapped encoding the outer `message.raw` field itself needs;
conflating the two silently produces a draft Gmail can't render). Omitting
`:attachments` keeps the exact prior single-part plain-text shape
(verified byte-for-byte via a dedicated test), so this is additive/
non-breaking. This namespace does no filesystem I/O -- callers read
attachment bytes themselves, keeping `->raw-message` testable with plain
byte arrays and no real files.

## Addendum (2026-07-13): `client/jvm-http-fn` gains `:delete`, `drafts/delete-draft!`

`jvm-http-fn`'s method dispatch only built `:get`/`:post` requests --
anything else threw `"Unsupported HTTP method"`, discovered when trying to
retire a superseded draft before creating its replacement. Added `:delete`
(`HttpRequest.Builder/DELETE`) and `drafts/delete-draft!` (`DELETE
/drafts/{id}`, matching `create-draft!`'s injectable-`:http-fn`
convention). Gmail's `drafts.delete` returns an empty 204 body, which
`client/request!` already treats as `nil` rather than a JSON parse
target -- no change needed there.

## Addendum (2026-07-13): `gmail.mime` -- decode INBOUND messages

Every namespace so far acted on Gmail *metadata* (thread ids, label ids,
history records) or built *outbound* MIME (`drafts/->raw-message`). Nothing
read an inbound message's actual content: `threads/get-thread` (format=full)
returns each message's `:payload` as a base64url-encoded body inside an
arbitrarily nested `:parts` tree, and callers were left holding those raw
strings with no portable way to answer "what did they say, and did they
attach anything?". `gmail.mime` is the read counterpart to the drafts
encoder:

- `decode-body-data` -- base64url *decode* (the URL-safe alphabet Gmail uses,
  the inverse of `drafts`' own outgoing encoder; the standard decoder would
  reject a `-`/`_`), nil/blank-safe.
- `header` (case-insensitive lookup -- RFC 2822 header names are
  case-insensitive even though Gmail preserves sender casing) and `headers`
  (flat `{name value}` map; documented to collapse genuinely multi-valued
  headers like `Received` to their last instance -- callers needing every
  hop filter the raw `:headers` vector).
- `plain-text-body` / `html-body` -- a single recursive part walk that
  handles single-part `text/plain`, `multipart/alternative` (returns the
  right half), and `multipart/mixed` (returns the body part, skips
  attachments) uniformly, so the caller doesn't branch on message shape.
- `attachment-parts` -- collects `{:filename :mime-type :attachment-id
  :size}` for every part with a non-blank `:filename` (Gmail's marker for an
  attachment vs. a body part), the descriptors `gmail.attachments` then
  fetches by id.

Pure `.cljc` shape; the base64 decode is JVM-only (`java.util.Base64`), the
same single-platform posture as the drafts encoder.

## Addendum (2026-07-13): `gmail.attachments` -- download attachment bytes

Gmail does not inline a large attachment's bytes into the message payload --
the attachment part carries only a `:body {:attachmentId ... :size N}`
descriptor (surfaced by `mime/attachment-parts`), and the bytes are fetched
on demand from `users.messages.attachments.get`. That endpoint lives under
`/messages/{messageId}/attachments/{attachmentId}` (NOT `/threads/...`), but
`client/api-base` already ends in `/users/me`, so the path is just that tail.
`get-attachment` returns the raw `{:size :data}` envelope; `attachment-bytes`
adds the base64url decode and returns a raw `byte[]` (deliberately NOT
stringified -- attachments are binary), ready to write to a file or hand back
to `drafts/->raw-message`'s `:attachments :bytes` to re-attach. Together with
`gmail.mime` this makes the library able to fully *read* an inbound message,
not just act on its metadata.

## Addendum (2026-07-13): `drafts` gains `get-draft!` / `list-drafts!` / `update-draft!`

`drafts` could create and delete but not read or edit. The gap that forced
the fix: editing a draft's body meant `delete-draft!` + `create-draft!`,
which churned the draft id (breaking any reference a caller held) and briefly
left the thread with no draft at all. `update-draft!` (Gmail's `drafts.update`,
`PUT /drafts/{id}`, same `message`/`->raw-message` construction as
`create-draft!`) keeps the id stable and the edit atomic. `get-draft!`
(`GET /drafts/{id}`) and `list-drafts!` (`GET /drafts`, paginated via the
same `:max-results`/`:page-token` -> `maxResults`/`pageToken` convention as
`threads/list-threads`) round out read access. `update-draft!` needs a `PUT`
transport, so `client/jvm-http-fn` grew a `:put` branch alongside the earlier
`:delete` one (same shape as `:post`).

## Addendum (2026-07-13): `labels/delete-label!`, `threads` trash/untrash/delete

Destructive lifecycle operations the library was missing, with Gmail's own
reversible-vs-permanent distinction preserved explicitly rather than
conflated:

- `labels/delete-label!` (`DELETE /labels/{id}`) -- removes a *user* label
  from every thread that carried it (system labels can't be deleted).
- `threads/trash-thread!` (`POST /threads/{id}/trash`) -- **reversible**;
  Trash retains the thread (~30 days) and `threads/untrash-thread!`
  (`POST /threads/{id}/untrash`) restores it. `untrash-thread!` is exposed
  *alongside* `trash-thread!` on purpose -- a trash without an untrash is a
  trap, stranding a caller with no programmatic recovery path.
- `threads/delete-thread!` (`DELETE /threads/{id}`) -- **PERMANENT**, bypasses
  Trash entirely, no undo (and needs the broad `https://mail.google.com/`
  scope; `gmail.modify` can trash but not delete). The docstring says so
  loudly and points callers at `trash-thread!` as the default.

## Addendum (2026-07-13): `client/request!` now percent-encodes query values

The query-string builder emitted `(str (name k) "=" v)` with **no encoding
at all**, so a `:q` value with a space (`"after:2024/01/01 in:inbox"`) or any
`&`/`+`/`=`/non-ASCII character corrupted the URL -- exactly the kind of
Gmail search string a real caller passes. Fixed by percent-encoding each
*value* (keys stay literal -- they're always simple identifiers like
`q`/`maxResults`/`pageToken` here). `java.net.URLEncoder` was deliberately
avoided: it is form-encoding, which serializes a space as `+` (a literal `+`
in a URI, ambiguous -- Gmail wants `%20`) and over-encodes `:`/`/`, the two
characters Gmail search syntax most needs readable and that RFC 3986 already
allows unencoded in a query. Instead a small byte-wise encoder keeps RFC 3986
`unreserved` plus `:`/`/` literal and percent-encodes every other UTF-8 byte,
so the delimiters space/`&`/`=`/`+`/`#` can never be misread as syntax
(verified: a space round-trips to `%20` not `+`, and literal `+`/`&` escape
to `%2B`/`%26`). This is a strictly smaller, uncontroversial bug fix and does
**not** add repeated-key support -- that larger design decision (needed for
`historyTypes` and other array params) remains documented as out of scope in
the `gmail.history` addendum above, unchanged.

## Addendum (2026-07-13): `gmail.retry` -- opt-in retry/backoff, wired into `client/request!`

Nothing in this library shared a retry/backoff utility before -- a caller
hitting Gmail's transient failures (a 429 rate limit, a 5xx backend hiccup)
had to hand-roll its own loop. `gmail.retry` is the first reusable one:

- `retryable-status?` -- `429` and `500/502/503/504` only. A 4xx other than
  429 (400/401/403/404) is a caller/permission/not-found problem retrying
  can't fix, so it is deliberately excluded (as is a `nil` status -- the case
  when the thrown exception carried no `:status`, e.g. a plain programming
  bug, which must not be looped on).
- `backoff-delay-ms` -- **full-jitter** exponential backoff: an exponential
  ceiling `base-ms * 2^attempt`, capped at `max-ms`, then a *uniform random*
  draw in `[0, capped]`. The jitter is the point (AWS's "Exponential Backoff
  And Jitter"): without it, concurrent retriers all wake on the same doubling
  boundary and re-stampede the API in lockstep -- the thundering-herd failure
  mode of naive fixed-doubling backoff. Defaults: `base-ms` 500, `max-ms`
  30000, `max-attempts` 5, all configurable via an opts map.
- `with-retry` is the one `#?(:clj ...)`-wrapped form (a synchronous loop with
  `Thread/sleep`); the decision logic above is pure, portable `.cljc`. It
  takes a 0-arg `thunk` that throws `ex-info` carrying `{:status N}` on
  failure -- the **exact shape `client/request!` already throws** -- and
  re-throws the *original* exception untouched once attempts are exhausted or
  the status is non-retryable, so a caller sees the same error it would
  without retry, just later. `:sleep-fn` is injectable (default
  `#(Thread/sleep %)`) so tests pass a no-op and stay fast, the same
  injectable-fn discipline as `:http-fn`.

Wired into `client/request!` as an **opt-in** `:retry` opt (`true` for
defaults, or a map of `with-retry` opts). **Omitting `:retry` preserves the
prior behavior exactly** -- one request, throw immediately on the first
non-2xx (verified by a test asserting a single `:http-fn` call and an
immediate throw when `:retry` is absent) -- so this is additive/non-breaking
for every existing caller, and for `com-cloudflare`/`com-wise` which share the
sync `:http-fn` convention. The refactor only lifts the per-request body into
a local `do-request` thunk so `with-retry` can re-invoke it; the no-retry
branch calls that thunk once, byte-identically to before.

## Addendum (2026-07-13): `gmail.watch` -- `users.watch` / `users.stop`

Gmail push-notification lifecycle, the same thin-wrapper shape as
`gmail.history`'s addition:

- `watch!` -- `POST /watch` with `{:topicName "projects/<p>/topics/<t>"
  :labelIds [...]}` (`:label-ids` optional -- filters which label changes fire
  a notification); returns `{:historyId ... :expiration ...}`. `:expiration`
  is a Unix-ms string ~7 days out; a watch must be renewed before it or
  notifications silently stop. `:historyId` seeds `gmail.history/list-history`
  -- the notification payload only carries a `historyId`, so the actual
  changes are still read via the history cursor.
- `stop!` -- `POST /stop`, no body, empty response (surfaced as `nil`);
  cancels all push notifications for the mailbox.

**Explicitly out of scope** (documented in the ns docstring, the README, and
here), mirroring how OAuth2 token acquisition is out of scope for
`gmail.client`: this namespace **only** makes the two Gmail-side API calls. It
does **not** (1) provision the Cloud Pub/Sub topic, (2) grant the Gmail push
service account `gmail-api-push@system.gserviceaccount.com` the Pub/Sub
Publisher role on that topic, or (3) run the receiving webhook/subscriber. All
three are caller-side GCP infrastructure prerequisites; `watch!` assumes the
topic already exists and is publishable-to. Tested with a stub `:http-fn` like
every other namespace.

## Addendum (2026-07-13): a parallel async cljs read surface (`gmail.async-*`)

This repo is JVM-only despite the `.cljc` extension -- every function is
`#?(:clj ...)`-wrapped and there are no `:cljs` branches anywhere. The reason
it can't simply "also run under cljs" is a contract tension, not laziness: the
`:http-fn` convention used throughout this library (and shared with
`com-cloudflare`/`com-wise`) is **synchronous** -- `{:url :method ...} ->
{:status :body}`, a plain return value -- but `js/fetch` under nbb/cljs is
inherently **async** (returns a Promise). An abandoned sketch in
`kotoba-lang/browser`'s `src/browser/net/http.cljc` had already named this
exact blocker in its own docstring.

Decision (made, not revisited here): do **not** change the synchronous
`:http-fn` contract -- it must stay byte-identical, zero risk to the
`com-cloudflare`/`com-wise` code that shares it (a breaking change there is
exactly what's being avoided). Instead add a **separate, additional,
cljs-only, read-only** surface that is async-native (returns `js/Promise`)
from day one, in its own namespaces so there is never ambiguity about which
functions are sync (existing, JVM) vs async (new, cljs):

- `gmail.async-client` (plain `.cljs`, no reader-conditional -- there's no JVM
  branch to share) -- its own minimal request core: `fetch-http-fn` (js/fetch
  wrapped to resolve to `{:status :body}`, the *same field shape* as the sync
  contract, just inside a Promise) and `request!` (same opts-map shape --
  `:method :body :http-fn :token :query` -- but returns a `js/Promise` of the
  parsed body, **rejecting** on non-2xx with the same `{:status :path :body}`
  data the sync client throws). Reuses `gmail.client/api-base` (a plain,
  portable `def`) rather than redefining it.
- `gmail.async-threads` -- `list-threads` / `get-thread`.
- `gmail.async-history` -- `list-history`.

**Scope is read-only inbound polling only** -- the historical use case that
motivated `gmail.history` (`kotoba-lang/tayori`'s incremental sync, exactly
the nbb-not-JVM kind of loop). This is deliberately **NOT a port**: drafts /
labels / mime / attachments / watch / retry are *not* mirrored on the async
side. Every function still takes an injectable `:http-fn` (a stub returns
`(js/Promise.resolve {:status .. :body ..})`), preserving this library's one
non-negotiable convention across both surfaces.

Two implementation notes worth recording:
- **Rejection via `js/Promise.reject`, not `throw`, inside a `.then`.** Under
  nbb/SCI a `(throw (ex-info ...))` inside an interpreted `.then` callback gets
  wrapped in an `sci/error` whose `ex-data` *hides* the original
  `{:status :path :body}` (a caller's `.catch` then can't read the status).
  Returning a rejected promise carries the raw ex-info through intact, and
  behaves identically under a compiled cljs build -- so `request!` rejects that
  way. (Verified: a stubbed 401 rejects with `(:status (ex-data e))` = 401.)
- **nbb test infra.** This repo had none; added a minimal `package.json`
  (only `nbb` as a devDependency -- no unrelated npm deps) and `nbb.edn`
  (`{:paths ["src" "test"]}`), matching `kotoba-lang/mail-archive`'s shape. The
  async tests follow mail-archive's `datascript_contract_test.cljs`
  convention -- a self-contained nbb script with a manual `check`/failures atom
  and `js/process.exit 1` on mismatch (this repo's nbb pattern, **not**
  cljs.test) -- extended to await Promises via a sequential `.then` chain. Run
  with `npm run test:nbb` (which chains `npx nbb test/gmail/async_*_test.cljs`);
  CI grows a Node step alongside the existing `kbb -M:test`/`-M:lint`. The
  reused `.cljc` (`gmail.client`) loads fine under nbb because its `#?(:clj
  ...)` forms simply drop out under cljs, leaving only the portable
  `api-base`.
