# Design

## Why an actor layer at all

An LLM extraction step is great at drafting a category/summary/entity list
from raw page text — but it has no notion of *scope* (which domains this
actor is even allowed to touch), *budget* (how much it may fetch per tick),
or *trust* (whether its own output is confident enough to publish). Letting
it write straight to net-kotobase invites exactly the failure this ADR
retracted a fabricated predecessor over: an actor that claims to be
"governed" but isn't actually gated by anything real. This project seals the
LLM into a single `:advise` node and wraps it with an independent
`commoncrawl.policy` Governor and an immutable audit ledger
(`commoncrawl.store`).

## Modules

| ns | responsibility |
|---|---|
| `commoncrawl.seeds` | the configured seed domain list (`resources/seeds.edn` + embedded fallback) |
| `commoncrawl.cdx` | CDX index query + WARC-envelope stripping (pure, injected fetch-fn) |
| `commoncrawl.extract` | minimal HTML → title/text extraction |
| `commoncrawl.llm` | LLM extraction (category/summary/entities/confidence), `murakumo-main` |
| `commoncrawl.embeddings` | murakumo `/v1/embeddings` client (response parsing) |
| `commoncrawl.identity` | CACAO self-mint (Ed25519 seed persistence, `cacao.core/mint`) |
| `commoncrawl.kotobase` | `web.ingest`/`web.search` XRPC client (payload building + parsing) |
| `commoncrawl.policy` | the Governor: seed-scope / exclude / budget (hard), confidence (soft) |
| `commoncrawl.store` | this actor's OWN bookkeeping: ledger, dedupe index, cursor, lease, budget |
| `commoncrawl.operation` | the StateGraph: intake → fetch → advise → govern → decide → commit/hold |
| `commoncrawl.loop` | the durable outer loop: one bounded, budgeted, leased tick |
| `commoncrawl.report` | human-readable ledger/tick rendering |
| `commoncrawl.sim` | offline demo runner |
| `commoncrawl.live-http` | the ONLY ns doing real network/gzip IO (nbb-only, `.cljs`) |
| `commoncrawl.iceberg` | row-shaping for the Iceberg projection (pure) |
| `commoncrawl.live-iceberg` | the Iceberg catalog commit (nbb-only, `.cljs`) |
| `bin/scheduled.cljk` | the launchd entry point — resolves both live credentials, then runs `bin/tick.cljk` |

## The injection boundary

Every capability that touches the outside world is an argument, not a
hardcoded call:

- `commoncrawl.operation/build`'s `:advise-fn` / `:embed-fn` / `:fetch-fn` /
  `:warc-fetch-fn` / `:ingest-fn`.
- `commoncrawl.cdx`'s `fetch-fn` / `warc-fetch-fn`.
- `commoncrawl.llm`'s `complete-fn`.
- `commoncrawl.embeddings`'s `embed-fn`.
- `commoncrawl.kotobase`'s `http-fn`.

This is the same "Store / Advisor / Phase are all swaps" discipline
`gftd-talent-actor`/`robotaxi-actor` use, extended one step further: real IO
itself is a swap. `commoncrawl.sim` (offline) and `bin/tick.cljk` (live)
build the exact same graph from `commoncrawl.operation/build` — they only
differ in which functions they pass in.

## Why no approval/interrupt node

`talent.operation` (gftd-talent-actor) has a `:request-approval` node with
`interrupt-before` for a human decision on a soft (escalate) verdict. This
actor doesn't — a wrong category/summary tag on a search result is a much
lower-stakes mistake than an HR action, so both hard and soft policy
violations resolve straight to `:hold` (tagged distinctly via
`commoncrawl.policy/hold-fact`'s `:soft?` field for observability). A future
version could add a human-approval node for the soft path without changing
this contract.

## Durability: what survives across ticks

`commoncrawl.store`'s `Store` protocol holds everything that must survive
between separate `commoncrawl.loop/tick!` invocations: the append-only
decision ledger, a URL dedupe index, the seed round-robin cursor, a
per-tick fetch-budget counter, a best-effort single-runner lease, and a
per-tick summary log. Two backends: `MemStore` (in-process, used by tests/
`commoncrawl.sim`), and `DatomicStore` (`langchain.db`-backed via
`kotoba-lang/langchain-store`'s shared codec/identity-schema/event-stream
helpers — no 191st hand-rolled `enc`/`dec*` pair, ADR-2607141600).
`commoncrawl.store/file-store` adds a third option: a `MemStore` whose atom
persists to a single EDN file across separate OS process invocations — the
practical default for `bin/tick.cljk` without standing up a real
kotoba-server pod behind `DatomicStore`.

**Lease caveat, stated plainly**: the lease is a best-effort single-runner
guard for one process/file, not a distributed lock. It is the mechanism
that lets a crashed tick's slot be reclaimed once its TTL elapses
(`commoncrawl.store`'s `acquire-lease!`), not a guarantee against two
concurrent schedulers racing on the same store.

## The Iceberg projection: a second, read-optimized copy — never the premise

Every committed page is searchable the moment `:commit` returns — that is
`web.ingest` against net-kotobase, and it is the ONLY write the governed
graph performs. Since 2026-08-28 each tick also mirrors its committed
pages into `net_kotobase.commoncrawl_page`, an Apache Iceberg table in
Cloudflare R2 Data Catalog (bucket `net-kotobase-datalake`, account
`4da88288dc30d9ee257f319d3c33ecf0` — the same account `cloud-itonami/otent`
uses for its own tables), so the corpus can be queried with Spark/DuckDB/
PyIceberg without going through `web.search`.

This is deliberately a PROJECTION, not a second premise (superproject
ADR-2608039700's "delete and rebuild" test): drop the table and it can be
rebuilt from `commoncrawl.store/ledger` (which URLs were committed, when)
plus a re-fetch from Common Crawl. It is the mirror image of
`cloud-itonami/otent`'s own rule (`otent.catalog`'s ns docstring) that bulk
observations stay OUT of the kotobase datom plane and IN Iceberg — here the
datom-shaped write (`web.ingest`) already happened, and Iceberg is the
additive, optional one.

Shape:

- `commoncrawl.iceberg` (pure `.cljc`) — `row-for-result`/`rows-for-tick`
  turn a tick's committed seed results into the table's flat, all-string
  row shape (`->row`), same "everything is text, the reader casts"
  discipline `otent.observation/->row` uses and for the same reason: a
  numeric/struct column would make this layer decide, per page, whether a
  missing confidence is null or zero.
- `commoncrawl.live-iceberg` (nbb-only `.cljs`) — writes one NDJSON batch
  per tick and shells out to `scripts/iceberg_append.py` (vendored from
  `cloud-itonami/otent`, same script, same contract: schema pinned from
  the first batch, drift refused rather than null-filled, `--create` safe
  on every run because the writer only actually creates an absent table).
- `commoncrawl.loop/tick!` batches: ONE Iceberg commit per tick (all of
  that tick's committed rows), not one per page — the sync-fn is injected
  (default `commoncrawl.iceberg/default-sync-fn`, a no-op that reports
  `:disabled? true`, distinguishable from a real "attempted, appended
  zero" tick) and its own success/failure never touches a seed's
  `:disposition` or the decision ledger: net-kotobase ingestion has
  already happened by the time the sync runs, so a catalog outage degrades
  the tick summary's `:iceberg` field, never a page's commit.
- `bin/tick.cljk` wires the real `commoncrawl.live-iceberg/sync-fn` and
  needs `CF_CATALOG_TOKEN` (a Cloudflare API token scoped to `R2 Data
  Catalog: Edit` + `Workers R2 Storage: Edit`) in its environment — see
  `docs/operator-guide.md`.
