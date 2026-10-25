# watchlist-screen

Sanctions/PEP watchlist screening for kotoba-lang. Ingests real, public,
freely-licensed government sanctions data (OFAC SDN List, UN Security
Council Consolidated List, Japan MOF 資産凍結等対象者一覧) into normalized
EDN, and screens a name against it with a tiered, confidence-scored,
staleness-aware match.

This is genuinely real: `resources/watchlist/lists/` in this repo ships an
actual snapshot fetched from the live sources (not synthetic data), and
`scripts/refresh_lists.cljk` re-fetches it. The match algorithm, staleness
tracking, and `aml.ports/IAmlScreening` integration are all real, tested
code — but read "Honesty boundary" below before relying on this for
anything with real compliance weight.

**This is not a 反社 (organised-crime / anti-social forces) database.** No
Japanese authority publishes such a list in machine-readable form, and none
is reconstructed here. Every source below is an economic-sanctions /
asset-freeze list. If you came looking for 反社チェック, this answers a
different question, and saying so is the point.

## Usage

```clojure
(require '[watchlist.adapters.edn-index :as idx]
         '[watchlist.core :as core])

(def index (idx/edn-index "resources/watchlist/lists"))
(core/screen index "some name to check" (System/currentTimeMillis))
;;=> {:watchlist/candidates [{:tier :fuzzy-high :confidence 0.83 ...}]
;;    :watchlist/stale? false
;;    :watchlist/list-age-days 2.1
;;    :watchlist/checked-sources [:ofac-sdn :un-consolidated]
;;    :watchlist/checked-at 1753000000000}
```

Refreshing the data:

```bash
# The classpath comes from `kbb -Spath`, not `-cp src`: the MOF adapter
# requires csv.core (kotoba-lang/org-ietf-csv), a git dep.
kbb --backend sci -cp "$(kbb -Spath)" scripts/refresh_lists.cljk --out resources/watchlist/lists
kbb --backend sci -cp "$(kbb -Spath)" scripts/refresh_lists.cljk --sources jp-mof   # one source
```

Publishing the snapshot to R2 (a serving copy — see "R2 is a projection"
below):

```bash
kbb --backend sci -cp "$(kbb -Spath)" scripts/publish_r2.cljk --bucket watchlist-snapshots
kbb --backend sci -cp "$(kbb -Spath)" scripts/publish_r2.cljk --dry-run
```

## Sources

Counts below are the committed snapshot's, and the committed manifests are
authoritative over this prose — `resources/watchlist/lists/*.manifest.edn`
carries each source's `:manifest/entity-count`, `:manifest/fetched-at` and
`:manifest/sha256`.

- **OFAC SDN List** — `https://www.treasury.gov/ofac/downloads/sdn.xml`,
  freely downloadable, no authentication.
- **UN Security Council Consolidated List** —
  `https://scsanctions.un.org/resources/xml/en/consolidated.xml`, freely
  downloadable, no authentication.
- **Japan MOF 資産凍結等対象者一覧** — the consolidated CSV linked from
  `https://www.mof.go.jp/policy/international_policy/gaitame_kawase/gaitame/economic_sanctions/list.html`,
  freely downloadable, no authentication. Asset-freeze targets designated
  under the 外為法 (Foreign Exchange and Foreign Trade Act). UTF-8 with a
  BOM, 32 columns, both Japanese and romanized names per row.

  **The URL moves.** MOF puts the publication date in the filename
  (`shisantouketsu<YYYYMMDD>.csv`) and keeps no stable alias, so
  `watchlist.adapters.jp-mof/latest-csv-link` reads the index page and finds
  the current one. A hardcoded URL would not merely 404 — it would keep
  serving one frozen snapshot while every refresh reported success.
- **EU Consolidated Financial Sanctions List** — **not implemented**. The
  EU's machine-readable source (the FSD/FSF API) requires a registered
  access token; every unauthenticated fetch attempt during this repo's
  development returned HTTP 500. See
  `src/watchlist/adapters/eu_consolidated.cljk`'s module doc. Provisioning
  a token is an owner action, not something this repo scripts around.

## Honesty boundary (read before relying on this for anything real)

- **Data ingestion**: real. Every parser was built and tested against the
  actual live file, not reconstructed from memory or a stale spec — each
  namespace's doc comment says so and names the exact URL.
- **Name matching**: real, deterministic, tested (including Jaro-Winkler
  verified against Winkler's own published reference vectors) — but a
  known, documented false-negative risk: anything scoring below 0.80 on
  every signal is not surfaced as a candidate at all, and diacritics are
  stripped rather than transliterated (`watchlist.match`'s module doc).
  This is narrower coverage than a commercial compliance vendor
  (ComplyAdvantage, Refinitiv World-Check, Dow Jones) that tunes match
  quality as an ongoing operational job.
- **Japanese matching**: `watchlist.match/normalize` folds halfwidth
  katakana (with its voicing marks), fullwidth ASCII, and hiragana into
  katakana, and keeps CJK ideographs. So ｱﾙ･ｶｰｲﾀﾞ, アル・カーイダ and
  ＡＬ－ＱＡＩＤＡ all reach the same entity. It does **not** know readings:
  山田 and ヤマダ are the same name and this returns different strings for
  them — that needs a dictionary, not a codepoint table.
- **A defect this change fixed, recorded because the shape recurs.** Before
  the script fold existed, every non-Latin name normalized to `""`, and
  Jaro-Winkler of two empty strings is `1.0` — so any two names the
  normalizer could not represent scored `:fuzzy-high` at `0.92`. Measured:
  `(score-name "山田太郎" "アル・カーイダ")` returned a 0.92-confidence hit
  on two unrelated names. It was latent only because no indexed name was
  non-Latin yet; adding the MOF list would have activated it on 2,866
  entries. `score-name` now floors an unrepresentable name to "no
  candidate", and the regression test pins that it is still exercising the
  empty path rather than passing because two strings happen to differ.
- **Staleness**: every screening result carries `:watchlist/stale?` and
  `:watchlist/list-age-days` — a caller cannot mistake a result checked
  against 6-month-old data for one checked against current data, and an
  index that never loaded at all fails closed (`:watchlist/stale? true`),
  never silently looking like a clean check.
- **`:non-adjudicating` always** — mirrors `ekyc`/`aml`/`identity`'s
  existing convention. A `:deny`/`:challenge`/`:review` level from
  `watchlist.adapters.aml-port` is evidence for a human/compliance-officer
  decision, never an automated final adjudication.
- **Not yet wired into `aml.core/screen`'s routing** —
  `aml.model/routes` is `[:yabai :malak]`, a closed vector this repo does
  not own. `watchlist.adapters.aml-port/screening-port` is directly
  callable standalone (`(screen! port request :watchlist)`); adding
  `:watchlist` as a real third route requires a small follow-up PR to
  `kotoba-lang/aml` itself.
- **Performance**: the bundled XML parser (`watchlist.adapters.xml`, a
  hand-rolled zero-dependency reader shared by the org's other XML-
  consuming libraries) is a straightforward char-scanning implementation —
  parsing the full ~19,000-entity OFAC file takes on the order of tens of
  seconds on the JVM, longer under nbb's interpreter. Fine for a periodic
  batch refresh job; not tuned for a hot path.

## Two runtimes, two suites

```bash
kbb -M:test                                  # JVM: every namespace
kbb --backend sci -cp "test:$(kbb -Spath)" test/run.cljk   # nbb: every portable one
```

Both are required before landing. Every adapter here is `.cljc` and every
one of them executes under nbb inside `scripts/refresh_lists.cljk`, so the
JVM suite alone tests one of the two runtimes this code runs on.

That is not hypothetical. `watchlist.match` used `(int c)` to read a
character's code unit. On the JVM that is the code unit; in ClojureScript it
truncates a one-character *string* to `NaN` and yields `0`, so every
codepoint comparison in the script folds compared against zero and every
fold became a no-op — under nbb, `(normalize "ｱﾙ･ｶｰｲﾀﾞ")` silently dropped
the voiced ﾀﾞ and `(normalize "ＡＬ－ＱＡＩＤＡ")` returned `""`. The JVM
suite was green throughout. Reverting `watchlist.match/char-code` today
fails 8 assertions under nbb and 0 on the JVM.

`watchlist.adapters.edn-index` is `.clj` on purpose (`clojure.java.io`), so
its test is JVM-only by design and is the one namespace `test/run.cljk` does
not carry.

## Where this data lives besides git

`scripts/publish_r2.cljk` publishes the committed snapshot to an R2 bucket:
each entities file under the sha256 of its own bytes, one mutable pointer
per source (`watchlist/<source>/latest.edn`), and one
`watchlist/index.edn`. Every put is read back and hashed before the source
is reported as published — a PUT that exited 0 is not evidence that the
bytes arrived.

**Git remains the source of truth.** Delete the bucket and nothing is lost:
`git checkout` plus `scripts/refresh_lists.cljk` rebuilds every byte. That
delete-and-rebuild test is what separates a projection from a premise
(superproject ADR-2608039000 / ADR-2608039700), and this is a projection.

**R2 Data Catalog is a different thing, and it now also holds this data.**
The object publication above writes plain objects; R2 Data Catalog is an
Iceberg REST catalog serving Parquet tables. Both exist:

| where | what | written by |
|---|---|---|
| `resources/watchlist/lists/*.edn` | the source of truth | `scripts/refresh_lists.cljk` (this repo) |
| R2 objects, content-addressed | serving copy of the same EDN | `scripts/publish_r2.cljk` (this repo) |
| Iceberg, `cloud-itonami-datalake`, namespace `cloud_itonami` | four analytic tables | `scripts/watchlist-datalake-export.cljs` + `scripts/datalake-sync.py` (the `com-junkawasaki/root` superproject) |

The Iceberg tables are `watchlist_entity` (one row per entity),
`watchlist_name` (every primary name and alias, with `normalized_name`),
`watchlist_attribute` (one row per nationality and per program), and
`watchlist_manifest` (source, fetch time, count, sha256, and the commit of
this repo the snapshot was read at). `watchlist_manifest` is a table so a
query can answer *how old is the data behind this answer* by JOIN — the same
thing `:watchlist/stale?` guarantees on the screening side.

`normalized_name` is `watchlist.match/normalize`'s own output, computed by
the exporter. If readers of the table reimplemented the folds, the
datalake's answer and this library's answer would diverge the first time
either was fixed.

All three are projections of the first. Delete the bucket, the objects and
the tables and nothing is lost: `git checkout` plus
`scripts/refresh_lists.cljk` rebuilds every byte.

See `MATURITY.md` and `90-docs/adr/*-kotoba-lang-watchlist-screen.edn` (in
the `com-junkawasaki/root` superproject) for the full design rationale.
