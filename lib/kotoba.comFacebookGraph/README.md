# com-facebook-graph

Portable (`.cljc`) Meta Marketing API (`graph.facebook.com`) client + MCP tool
surface — the `kotoba-lang/<reverse-canonical-api-host>` provider repo for
Facebook, Instagram, Messenger and Audience Network named in
`gftdcojp/cloud-itonami`'s ADR-0023 (media-network domain adapters). Meta Ads
is ADR-0023's stated "preferred independent fallback" provider (Google Ads is
the primary path but blocked on external Developer Token approval).

## Why this exists, and why it's a rewrite

A prior implementation of this exact provider existed at this path as an
uncommitted Python (pytest/venv) project. Investigating it (2026-07-25) found:

- Zero `.py` source files, but real `.pytest_cache`/`__pycache__` bytecode
  remnants (`mcp_server.cpython-311.pyc`, `config.cpython-311.pyc`,
  `client.cpython-311.pyc`, plus a `test_adapter.py` with real test names like
  `test_mutations_default_to_dry_run_and_validate_budget`) — code was written
  and tested, then the source was deleted (or never committed) before any
  `git init`.
- No trace in this superproject's git history, and no `kotoba-lang/com-facebook-graph`
  (or any of the other 12 ADR-0023 provider names except `com-unity-ads`) repo
  on GitHub.
- The prior implementation was in raw Python, which is not the convention this
  workspace's other `kotoba-lang/com-*` vendor-adapter repos use (see
  `com-cloudflare`, `com-retool`, `com-midjourney`, etc. — all `.cljc`/`.kotoba`).

So ADR-0023's maturity claims for this provider ("Marketing API account/campaign
reads, dry-run-first pause/resume/JPY-budget mutation and onboarding MCP are
implemented") were not backed by anything durable or reviewable as of that
date. This repo is the actual, committed, registered replacement — see
`90-docs/adr-ledger/adr-ledger.edn` for the ledger entry recording the gap and
this fix (ADR-0023 itself, being `accepted`, is not hand-edited).

## Design

```text
facebook-graph.client      -- auth (FACEBOOK_ACCESS_TOKEN) + HTTP (injectable :http-fn) + error envelope
facebook-graph.accounts    -- ad account list/read + this provider's capability map
facebook-graph.campaigns   -- campaigns list/create/pause/resume/budget, dry-run-first
facebook-graph.mcp         -- MCP tool list + call-tool dispatcher, per ADR-0023's 10-op provider contract
```

Query/request construction and response parsing are pure `.cljc`. The actual
HTTP call is JVM-only by default (`java.net.http`) but every function takes an
injectable `:http-fn` (`{:url :method :headers :body} -> {:status :body}`,
the same convention `com-cloudflare` uses) — every namespace here is tested
with a stub, never only against a live account.

## Honesty constraints this library follows (ADR-0023)

- **Dry-run by default.** `campaigns/create!`, `pause!`, `resume!` and
  `update-budget!` never touch the network unless called with
  `:dry-run? false` — an accidental live call cannot start ad delivery.
- **No implicit budget ceiling.** `update-budget!` throws without an explicit
  `:budget-ceiling-minor-units` in every call — ad account currencies differ,
  so this library refuses to guess a "safe" default the way a single-currency
  deployment might.
- **No feature fiction.** `creatives.validate` only checks field-shape, not a
  live creative-upload call (image/video hashing is out of scope here) —
  `facebook-graph.accounts/capabilities` marks it `:schema-validation-only`,
  not `:implemented`. `operations.status` is honest that Meta campaign/adset/ad
  mutations are synchronous (nothing to poll) and only routes the one real
  async surface (Insights report-runs) to a live endpoint.
- **Provider-native errors preserved.** `client/call!` throws with the Graph
  API's own `:code`/`:fbtrace_id` intact, and treats a 200-status response
  containing `:error` as a failure (Graph API does this; checking HTTP status
  alone is not sufficient).
- **No credentials in this repo.** `FACEBOOK_ACCESS_TOKEN` is read from the
  environment only; nothing here ever writes a token to an EDN/JSON resource.

## Current status

`:implemented-unauthenticated` (see `facebook-graph.accounts/capabilities`
for the full per-operation map) — request/response shapes and dry-run
semantics are real and tested; there is no live-account, production-write
receipt yet. Getting one requires a real Meta Business/App access token,
which this repo does not have and cannot provision itself.

## Usage

```clojure
(require '[facebook-graph.campaigns :as campaigns])

;; FACEBOOK_ACCESS_TOKEN in the environment, or pass :token explicitly.
;; Dry-run by default -- this makes no network call.
(campaigns/create-campaign! "act_123"
  {:name "Q3 launch" :objective "OUTCOME_TRAFFIC"}
  {})
;; => {:ok? true :mode :dry-run :op :campaigns.create :would-send {...}}

(require '[facebook-graph.mcp :as mcp])
(mcp/call-tool "facebook_graph.capabilities.get" {})
```

## Test

```sh
kbb -M:test
```

Stubbed `:http-fn` throughout — no `FACEBOOK_ACCESS_TOKEN` or live account
needed to run the suite.
