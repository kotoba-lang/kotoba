# Operator guide

## Running a real tick

`bin/tick.cljk` is the live entry point — it mints/reuses this actor's own
CACAO identity, fetches from Common Crawl, calls murakumo for extraction +
embeddings, and ingests into **production** `kotobase.net`. Run it from a
workspace where the sibling `.cljc` deps are checked out next to this repo
(the standard west layout, `orgs/kotoba-lang/*`):

Sibling paths are `../../kotoba-lang/<name>`, not `../<name>` — this repo
moved to the `net-kotobase` org in 2026-08 while every sibling below
stayed under `kotoba-lang` (see `deps.edn`'s `:dev` alias comment).
`authority` is needed transitively (`org-chainagnostic-cacao` requires
`authority.scope`) even though nothing in this repo requires it directly.

```bash
COMMONCRAWL_MURAKUMO_TOKEN=<murakumo /v1/messages+/v1/embeddings bearer token> \
CF_CATALOG_TOKEN=<Cloudflare R2 Data Catalog token, see below> \
  kbb --backend sci --classpath "src:../../kotoba-lang/langgraph/src:../../kotoba-lang/langchain/src:../../kotoba-lang/langchain-store/src:../../kotoba-lang/org-chainagnostic-cacao/src:../../kotoba-lang/org-ietf-ed25519/src:../../kotoba-lang/org-ietf-cbor/src:../../kotoba-lang/authority/src" \
  bin/tick.cljk --budget 1
```

Flags:

- `--budget N` — max seeds attempted this tick (default 3,
  `commoncrawl.loop/default-budget-cap`). Keep this small.
- `--store PATH` — where the durable state file lives (default
  `.commoncrawl/store.edn`, gitignored).
- `--db-name NAME` — the net-kotobase tenant database name pages are
  ingested into (default `webpages`, matching `web.ingest`'s own default).

### Iceberg sync (R2 Data Catalog) — optional, degrades independently

Every committed page is also mirrored into `net_kotobase.commoncrawl_page`
(Cloudflare R2 Data Catalog, bucket `net-kotobase-datalake`) — see
`docs/DESIGN.md`'s "The Iceberg projection" section for why this is safe
to skip. Needs:

- `CF_CATALOG_TOKEN` — a Cloudflare API token with **both**
  `R2 Data Catalog: Edit` and `Workers R2 Storage: Edit` (skill
  `secrets-location-map`, `references/cloudflare.md`: the Keychain item
  `gftd.cf`/`API_TOKEN` already carries both).
- `python3` on PATH with `pyiceberg` + `pyarrow` installed (this is the
  ONLY non-nbb runtime dependency in this whole repo — see
  `scripts/iceberg_append.py`'s own docstring for why: nbb has no Iceberg
  writer).

If `CF_CATALOG_TOKEN` is absent, every tick's `:iceberg` field reports
`{:ok? false :error :could-not-answer ...}` — the tick and its
net-kotobase ingest still complete normally; only the Iceberg mirror is
skipped for that tick (nothing queues or retries — the next tick's own
rows simply append on top once the token is present again).

The first run creates `.commoncrawl/identity.edn` (a fresh Ed25519 seed +
its derived `did:key`) — **never commit this file or this directory.**
Subsequent runs reuse the same identity/DID.

### Auth token

`COMMONCRAWL_MURAKUMO_TOKEN` authenticates against `api.murakumo.cloud`'s
`/v1/messages` and `/v1/embeddings` (both gated by the same bearer-token
check). Skill `secrets-location-map` in the parent workspace documents this
as kagi item `MURAKUMO_CRITIC_TOKEN` (compartment `gftdcojp`). **Present and
working as of 2026-08-28** (`KAGI_HOME=$HOME/.kagi <kagi bin> get
MURAKUMO_CRITIC_TOKEN`) — the 2026-07-19 note below that it was absent
described that session's vault access, not a standing gap. If you have
`bin/kagi` available and the item exists in your vault, set
`KAGI_BIN=/path/to/kagi` and `commoncrawl.live-http` will fetch the token
itself for a manual run; the scheduled path (see "Scheduling" below) reads
it from a plain file instead, since kagi cannot run under launchd.

## Live verification status (2026-07-19, initial implementation)

What was actually proven against PRODUCTION services in this session
(not offline fixtures):

- ✅ **Common Crawl CDX index query** — real `GET
  index.commoncrawl.org/CC-MAIN-2026-25-index?url=...` against
  `https://www.sec.gov/`, 113 real captures returned.
- ✅ **WARC range fetch + gunzip + envelope strip** — a real ranged `GET`
  against `data.commoncrawl.org`, real gzip decompression, 223,075
  characters of real page text extracted (this fetch ALSO found and fixed
  a real bug: the newest capture by timestamp was a contentless 301
  redirect stub, not a 200 response — see `commoncrawl.cdx/
  latest-response-capture`'s docstring and its regression tests).
- ✅ **CACAO self-mint** — a real Ed25519 identity, a real signed CACAO
  (`cacao.core/mint`), independently `cacao.core/verify`-checked.
- ✅ **`web.ingest` against production `kotobase.net`** — a real POST,
  `{:ok true :status 200 :datom_count 5}`.
- ✅ **`web.search` against production `kotobase.net`** — a real POST
  confirming the just-ingested page is now findable (score 10.21, correct
  url/title/snippet).
- ⚠️ **NOT live-verified**: the `:advise` step's `murakumo-main` LLM
  extraction and the `/v1/embeddings` call — no working bearer token was
  obtainable non-interactively in that session (see "Auth token" above).
  The ingested test page therefore carried no `extracted_category`/
  `extracted_summary`/`extracted_entities`/`embedding` fields (all
  optional/additive per the lexicon, so the ingest itself still succeeded
  honestly, just without that enrichment). Both legs ARE covered by the
  offline test suite (`test/commoncrawl/llm_test.cljk`,
  `test/commoncrawl/embeddings_test.cljk`) and the nbb smoke test
  (`test/nbb_smoke.cljk`) against mocked responses — re-run
  `bin/tick.cljk` with a working token to complete this leg's live
  verification.

## Current status (2026-08-28) — read this before assuming anything above is stale

Two things landed since 2026-07-19: the Iceberg sync (`commoncrawl.iceberg` /
`commoncrawl.live-iceberg`, see "Iceberg sync" above and `docs/DESIGN.md`)
and real scheduling (`bin/scheduled.cljk` + the LaunchAgent, see
"Scheduling" below). Both are now live-verified for their own mechanics,
but **no page has ever actually reached `:commit` since this actor was
built**, so the full chain (fetch real content → advise with a real LLM →
govern → commit → Iceberg sync) has never been proven end to end. This is
not a code gap — it is one external outage:

- **Common Crawl's CDX index (`index.commoncrawl.org`) is down.** Every
  fetch this actor has attempted since (at least) 2026-08-28 gets
  `curl: (52) Empty reply from server` — confirmed repeatedly, at
  different times of day, across multiple seeds. `commoncrawl.org` and
  `data.commoncrawl.org` both respond normally, so this is specific to the
  index subdomain, upstream, not this workspace's network. There is
  nothing to fix here except wait and re-check.
- **Consequently**: every tick since has HELD on `:fetch-miss`, the
  `net_kotobase.commoncrawl_page` Iceberg table has never been created
  (confirmed absent via `iceberg_append.py --count` as of 2026-08-28), and
  the `:advise` LLM/embeddings leg above is *still* not live-verified —
  not because the token is missing (it now works, see "Auth token" above,
  and `~/.gftd/commoncrawl-actor-murakumo-token` supplies it to every
  scheduled tick automatically), but because no page has ever reached that
  step with real content.
- **What IS proven live on 2026-08-28**: `bin/scheduled.cljk`, run for
  real by launchd (not by hand), resolved both credentials non-interactively
  and completed a full tick with exit 0 (`launchctl print` showed
  `last exit code = 0`) — the scheduling and credential-resolution
  machinery works; only the upstream fetch is blocked. A separate smoke
  test appended, read back, and dropped a throwaway row in the real
  `net-kotobase-datalake` catalog, proving the Iceberg write path itself
  works independently of this actor's fetch pipeline.

**Resume point for whoever picks this up next**: check whether
`index.commoncrawl.org` answers again
(`curl -sS -o /dev/null -w '%{http_code}\n' https://index.commoncrawl.org/collinfo.json`).
Once it does, the hourly schedule needs no further action — the next tick
that gets a real capture will commit a real page, create
`net_kotobase.commoncrawl_page` on first write, populate
`extracted_category`/`extracted_summary`/`extracted_entities`/`embedding`
for the first time, and complete this section's live verification. If it
still doesn't answer after a few days, that is itself worth escalating
(a Common Crawl outage this long would be unusual) rather than continuing
to assume it is transient.

## Growing the seed list

Add an entry to `resources/seeds.edn`:

```edn
{:domain "www.example.com" :url "https://www.example.com/" :label "why this domain is seeded"}
```

That's the entire scope-widening operation — no code change. Removing a
domain (or adding it to an exclude set passed to `commoncrawl.loop/tick!`'s
`:exclude` opt) immediately blocks it again via `commoncrawl.policy`'s hard
seed-scope/exclude checks.

## Scheduling

This actor is designed to be invoked by a scheduler, not run as an
always-on process. As of 2026-08-28, `bin/scheduled.cljk` + the LaunchAgent
`net-kotobase.commoncrawl-actor-tick` (`ops/net-kotobase.commoncrawl-actor-tick.plist`)
is the live implementation of that design — before this, the actor had only
ever been run by hand.

`bin/scheduled.cljk` resolves both real credentials the way a LaunchAgent
actually can (neither `kagi` nor an interactive Keychain prompt is
available under launchd — see the ns docstring):

- `CF_CATALOG_TOKEN` from the Keychain, `gftd.cf`/`API_TOKEN`.
- `COMMONCRAWL_MURAKUMO_TOKEN` from `~/.gftd/commoncrawl-actor-murakumo-token`
  (mode 600 — write the value of kagi item `MURAKUMO_CRITIC_TOKEN` there
  once: `KAGI_HOME=$HOME/.kagi <kagi bin> get MURAKUMO_CRITIC_TOKEN >
  ~/.gftd/commoncrawl-actor-murakumo-token && chmod 600 ~/.gftd/commoncrawl-actor-murakumo-token`).

Neither credential's absence stops a tick — see the ns docstring for why
that's safe — so install without either present if needed and backfill
later; the tick just logs a `WARN` per missing one.

```bash
cp ops/net-kotobase.commoncrawl-actor-tick.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/net-kotobase.commoncrawl-actor-tick.plist
tail -40 /tmp/commoncrawl-actor-tick.log   # watch
launchctl bootout gui/$(id -u)/net-kotobase.commoncrawl-actor-tick   # stop
```

Cadence is hourly, `--budget 1` (override with `COMMONCRAWL_TICK_BUDGET`).
The plist carries no logic — edit `bin/scheduled.cljk` instead, since
`launchctl` needs a bootout/bootstrap cycle on every plist change.

If you'd rather use a different scheduler (the `schedule` skill's
cron-based routine, or any external cron), point it at `bin/scheduled.cljk`
too, not `bin/tick.cljk` directly, unless that scheduler already supplies
both env vars itself.

## Reviewing what happened

```bash
kbb -M:dev:run  # for a quick illustrative ledger (offline)
```

Or, against the real store file:

```clojure
(require '[commoncrawl.store :as store] '[commoncrawl.report :as report])
(def st (store/file-store ".commoncrawl/store.edn"))
(println (report/render-ledger (store/ledger st)))
(println (report/render-ticks (store/tick-log st)))
```
