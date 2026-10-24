# haishin 配信

Cross-platform syndication for this workspace's creator output — Instagram,
YouTube, TikTok, X, Vimeo, LinkedIn — as a portable `.cljc` library with **no
transport and no credential handling**.

```clojure
(require '[haishin.core :as haishin])

(def p (haishin/plan artifact [:youtube :instagram :x] {:at "2026-08-04T09:00:00Z"}))

(println (haishin/summary p))
;; haishin plan for dougaka-2026-08-04-001 — 2 target(s), 1 skipped
;;   → youtube :youtube/videos-insert
;;   → instagram :instagram/media-create  (2 warnings)
;;   ✗ x — X text is 412 chars, limit 280

(haishin/execute! p {:grant #{:youtube} :senders {:youtube my-sender}})
```

## Why this exists

The `*ka` creator actors — dougaka (動画家), mangaka (漫画家), animeka (アニメ家),
ongakuka (音楽家) — generate and publish, but only ever to **app-aozora**, their
own appview. Nothing carried a finished work from there to anywhere else.

What did exist was scattered and one-sided:

- `kotoba-lang/social-publication` drafts observation posts, but is
  **dry-run-only by charter** (`build-live` throws) and has no platform-specific
  code at all. Twelve governance actors depend on exactly those invariants, so
  it is the wrong place to add live posting.
- `kotoba-lang/com-youtube` is a real, tested upload client — the protocol was
  already solved for one platform.
- `com-x` covers replies and DMs, not publishing. `com-vimeo` is a clean-room
  API-compatible *server*, not a client. Instagram had only DM send. TikTok and
  LinkedIn had nothing.
- `cloud-itonami`'s twenty-odd social API hosts are **advertising** APIs, a
  different plane entirely.

So the missing piece was never the transport. It was the layer that maps one
canonical work onto six platforms' incompatible rules, decides what each will
accept *before* anything is sent, and records what actually happened.

## Design

```
canonical artifact  (haishin.artifact — one shape, no platform keys)
        │
        ▼
   haishin.plan/plan          pure · no clock · no network · always available
        │                     ├─ entries   : validated request descriptions
        │                     └─ rejected  : target + why, per target
        ▼
   haishin.execute/execute!   requires :grant AND caller-supplied :senders
        │
        ▼
   receipts                   one per attempted target, including failures
```

### This library cannot post on its own

There is no HTTP client here, no JSON codec, no environment read, no credential
lookup — and `deps.edn` has no dependencies to hide one in. `execute!` calls
functions the caller passed in `:senders`, which close over their own auth.

That is not indirection for its own sake. A library that *could* reach the
network is one that has to be trusted not to; here the capability is absent
rather than restrained. It also keeps the existing clients employed — a
`:youtube` sender is a short adapter onto `kotoba-lang/com-youtube`, which
already implements resumable upload correctly, not a reimplementation of it.

### Grants fail closed

`execute!` requires `:grant`, the set of targets being authorised right now.

- planned but not granted → **skipped, with a receipt**
- granted but no sender → **skipped, with a receipt**
- sender throws → **failed, with a receipt** — and the other targets still run

An under-specified grant means nothing goes out. It never means something goes
out unreviewed. This mirrors the Kotoba runtime's `capability-grant-mismatch`.

### Rejection is per target, not per batch

A 4-minute vertical video is a valid YouTube upload and an invalid X post. The
answer is to publish it to YouTube and report why X was skipped — not to publish
nothing. `plan` returns `:plan/entries` and `:plan/rejected` side by side, and
`summary` reads as: what will go out, what will not, and why not.

### Plans are reproducible

`plan` reads no clock — `:at` is supplied by the caller. Planning the same
artifact twice yields an identical value, which is what makes a plan reviewable
by a governor and assertable in CI. (This is also the rule workflow scripts in
this workspace run under, where `Date.now()` is unavailable by design.)

## The tamaki seam — `:executable?` is the grant

The `*ka` actors already emit a **secret-free publication handoff**:
`dougaka.manifest/artifact-manifest` plus `publication-plan`, contractually
never uploading and never carrying credentials. Their `:executable? true` means
*publish-ready AND a human approved it* — exactly the condition under which
targets may be granted:

```clojure
(haishin/syndicate! artifact-manifest publication-plan
                    {:public-url "https://aozora.app/media/ep-001.mp4"
                     :senders {:youtube my-sender}
                     :at now})
;; publication-plan :decision :approval-required
;;   => {:run/tally {:skipped 1}
;;       :haishin/grant-note "no grant — plan decision is :approval-required;
;;                            human approval boundary not crossed"}
```

The approval boundary holds by construction, not by remembering to check a flag.
`:aozora` is dropped from the grant: that is the producer's own appview, which it
publishes to itself.

## Targets

| target | kinds | text limit | notes |
|---|---|---|---|
| `:youtube` | video | 5000 (title 100) | limits corroborated by `com-youtube` |
| `:instagram` | video, image | 2200, ≤30 hashtags | two-phase; **pulls the asset from a URL** |
| `:tiktok` | video | 2200 | |
| `:x` | text, image, video | 280 | raise via `:body-chars-override` on a higher tier |
| `:vimeo` | video | 5000 (title 128) | |
| `:linkedin` | text, image, video | 3000 | |

### Limit provenance is part of the data

Platform limits drift, and a number with no date on it is a number nobody can
audit. Every constraint carries `:constraint/checked-at`, `:constraint/source`
and `:constraint/provenance`:

- `:in-repo-corroborated` — an independently written client in this workspace
  encodes the same value. Only `:youtube` currently qualifies: `com-youtube`
  clamps title/description to exactly 100/5000, ported 1:1 from a working Python
  client.
- `:vendor-doc` — read off the vendor's published reference.
- `:unverified` — recorded from general knowledge and **not yet checked**.

> **The other five targets are `:unverified` as of 2026-08-04.** Planning
> deliberately still works on them — planning is offline and free, and a wrong
> limit surfaces as a rejection you can read. But **check a target's limits
> against its vendor doc before using it for live posting.** `haishin.core/unverified-targets`
> returns the set so your own suite can assert on it, and every plan entry for
> such a target carries a `:target/limits-unverified` warning.

## Install

```clojure
;; deps.edn
haishin/haishin {:local/root "../haishin"}          ; west path: orgs/kotoba-lang/haishin
```

Consumers require `haishin.core` and nothing else — the same single-entry
discipline `kotoba-ui` uses. Reaching into `haishin.target` or
`haishin.constraints` directly is an opt-out that wants a reason, since those are
where platform detail lives.

## Test

```bash
kbb --backend sci run_tests.cljk     # primary path
kbb -M:test        # JVM, secondary
```

20 tests / 82 assertions, green on both runtimes.

## Non-goals

- **Not a scheduler.** When to publish is the actor's cadence loop's business.
- **Not an auth broker.** Tokens never enter this library.
- **Not an analytics reader.** Receipts record what was sent, not how it performed.
- **Not a replacement for `social-publication`.** That library's dry-run-only
  charter serves twelve governance actors and stays exactly as it is.
