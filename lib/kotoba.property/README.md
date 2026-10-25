# kotoba-property

[![CI](https://github.com/kotoba-lang/property/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/property/actions/workflows/ci.yml)

**Parcels, listings and leases in pure Clojure.** A
[kotoba-lang](https://github.com/kotoba-lang) capability library for the
[`cloud-itonami-6810`](https://github.com/gftdcojp/cloud-itonami-6810)
community real-estate-agency open business: land-parcel records, property
listings (sale/rent), and lease records with term-overlap detection for
conflict-free tenant scheduling.

No network, no I/O. Amounts are plain numbers in the smallest currency unit.
Portable `.cljc` across JVM / ClojureScript / SCI / GraalVM.

## Public ownership collection

`resources/property/open_data/` defines a provenance-first EDN interchange
for publicly attributable land and building ownership claims. It is designed
for both Datomic and DataScript. The repository does not publish names of
natural-person owners, private-register data, or data whose upstream licence
does not permit redistribution.

Each imported claim must identify its property, holder, source, observation
time, licence, and disclosure class. `:ownership/disclosure` is `:public`
only when the upstream publisher makes that attribution publicly available.
Use `:not-published` for parcel data where ownership is not released.

```clojure
(require '[kotoba.property.ownership :as ownership])

ownership/public-claims-by-parcel-query
;; Run this Datalog vector unchanged with datomic.api/q or datascript.core/q.

(ownership/validate-claim
 {:ownership/id "nyc:mappluto:example"
  :ownership/parcel "nyc:borough-block-lot:1000010001"
  :ownership/holder "Example public authority"
  :ownership/holder-kind :public-body
  :ownership/source "nyc-mappluto"
  :ownership/observed-at "2026-07-10"
  :ownership/licence "NYC Open Data Terms of Use"
  :ownership/disclosure :public})
;; => {:ownership/valid? true}
```

`sources.edn` is a reviewed source catalog, not a mirror of the referenced
datasets. Add a data extract only after confirming the source's publication
scope, licence, jurisdiction, and refresh date.

## UBO and natural-person data

Natural-person names are not property-owner records in this project. They can
only be ingested as a beneficial-ownership relation to a corporate owner when
the jurisdiction/source pair is allowlisted in
`resources/property/open_data/sources.edn`. The initial allowlist is the UK
Companies House PSC product. It deliberately excludes residential addresses,
full dates of birth, identity-verification material, and protected records.

The UBO records belong in a governed database or a source-derived local
snapshot, never in this repository. See `DATA-GOVERNANCE.md` before enabling
an importer.

```bash
# Requires a Companies House Public Data API key and a corporate-owner number.
COMPANIES_HOUSE_API_KEY=... kbb -M:collect --company 00000006
kbb -M:query --company 00000006
```

The collector writes `var/kotoba-property/gb-ubo.edn`, which is ignored by
Git. It retains only the reduced UBO fields defined by the schema.

After accepting the relevant HMLR data licence and downloading CCOD or OCOD,
import only corporate-owner records and join them to PSC by company number:

```bash
kbb -M:collect-hmlr --csv /licensed/CCOD_FULL.csv \
  --source hmlr-uk-corporate-property --observed-at 2026-07-10
kbb -M:query --parcel GB-HMLR:TITLE_NUMBER
```

NYC-owned parcels require no credentials and can be collected immediately.
They are kept separate from natural-person ownership data. The preferred
runtime is `kotoba` contracts -> ClojureScript -> `nbb`; the nbb scripts own
the capability boundary for network and local-file I/O.

```bash
kbb --backend sci -cp src scripts/collect_nyc.cljk --limit 500
kbb --backend sci -cp src scripts/query_owned_property.cljk \
  --parcel US-NY-NYC:BBL:1017900009.0
```

Both nbb query commands execute Datalog through the npm DataScript runtime;
their query strings use explicit namespaced attribute names, preserving the
same EDN contract used by Datomic/DataScript clients.

## Corporate graph

GLEIF Level 2 is credential-free and provides accounting-consolidation parent
relations between legal entities. It is not a natural-person UBO registry.

```bash
npm install
kbb --backend sci -cp src scripts/collect_gleif.cljk --lei 529900T8BM49AURSDO55
kbb --backend sci -cp src scripts/query_corporate_parent.cljk --lei 529900T8BM49AURSDO55
```

To expand global legal-entity coverage without credentials, collect bounded
GLEIF Level 1 pages by jurisdiction. Increase `--pages` deliberately because
jurisdictions can contain hundreds of thousands of records.

```bash
kbb --backend sci -cp src scripts/collect_gleif_jurisdiction.cljk \
  --jurisdiction US --pages 2 --page-size 100
```

## The whole LEI universe (Golden Copy)

The paginated API above is a lookup path: at 200 records per request the full
LEI universe is >16,000 requests. GLEIF publishes the same data daily as a
Golden Copy full file under the same CC0 terms, which is the supported way to
obtain all of it — 3,391,413 legal entities in the 2026-08-01 publish.

```bash
# 1. fetch the publish index, download the CSV archive (~474 MB)
curl -s 'https://goldencopy.gleif.org/api/v2/golden-copies/publishes?format=json' \
  | jq -r '.data[0].lei2.full_file.csv.url'
curl -L -o ~/.cache/gleif/lei2-golden-copy.csv.zip '<url from above>'

# 2. stream it into an EDN-lines corpus (line 1 is a provenance manifest)
kbb --backend sci -cp src scripts/collect_gleif_golden_copy.cljk \
  --zip ~/.cache/gleif/lei2-golden-copy.csv.zip \
  --out ~/.cache/gleif/gleif-lei-corpus.edn

# 3. ask the corpus universe-scale questions (filters and counts, no joins)
kbb --backend sci -cp src scripts/query_gleif_corpus.cljk --corpus ~/.cache/gleif/gleif-lei-corpus.edn \
  --group-by company/jurisdiction --top 20

# 4. project the slice you want to join into the workspace query plane
kbb --backend sci -cp src scripts/project_gleif_corpus.cljk --corpus ~/.cache/gleif/gleif-lei-corpus.edn \
  --jurisdiction JP --status ISSUED --out data/gleif-lei-jp.datoms.edn
```

Neither the archive nor the corpus belongs in Git (~474 MB and ~1.2 GB). What
is committed is `data/*.datoms.edn`: bounded projections, each carrying the
publish id and source hash it came from, small enough to load into the
workspace query plane and join against financial, ToS and property data on
`:company/lei`.

**A projection is a join boundary, and it is the only one.** An LEI that is
not in a committed projection cannot be joined in Datalog — it is reachable
only by scanning the corpus, which cannot join. Widen the join surface by
widening a projection, never by adding a second store. The plane's measured
cost is why the whole corpus is not loaded: 200k entities take 85 s and
614 MB, 600k take 290 s and 1.2 GB, so 3.4M would be ~30 min and ~6 GB on
every query.

## Every Japanese legal entity (法人番号 全件データ)

GLEIF answers "who is this legal entity" for the 3.4M entities that have an
LEI; in Japan that is a few thousand. The National Tax Agency publishes the
whole domestic registry — **5,816,535 entities in the 2026-07-31 publish** — as
a monthly full file. `cloud-itonami-isic-8291`'s Web-API client is the *lookup*
path for the same authority (one company at a time, and it needs an Application
ID the NTA issues to a named operator over ~2-4 weeks); this is the *ingest*
path, and it needs no account at all.

```bash
# 1. download this month's national file (~266 MB) and stream it into a corpus
kbb --backend sci -cp src scripts/collect_houjin_bangou_zenken.cljk --download

# 2. ask the corpus registry-scale questions (filters and counts, no joins)
kbb --backend sci -cp src scripts/query_houjin_bangou_corpus.cljk \
  --corpus ~/.cache/houjin-bangou/houjin-bangou-corpus.edn \
  --group-by company/nta-kind

# 3. project the slice you want to join into the workspace query plane
kbb --backend sci -cp src scripts/project_houjin_bangou_corpus.cljk \
  --corpus ~/.cache/houjin-bangou/houjin-bangou-corpus.edn \
  --kind 101,201 --latest-only --active-only \
  --out <jp-go-nta-houjin-bangou>/data/houjin-bangou-public-bodies.datoms.edn
```

Two things differ from GLEIF, and both are load-bearing:

- **The licence is not CC0.** 公共データ利用規約（第1.0版） requires attribution
  and requires a derived work to say it is derived, so every corpus and
  projection manifest carries `:source/attribution` with the exact wording.
- **The projections are not committed here.** They go to the private
  `com-junkawasaki/jp-go-nta-houjin-bangou`, because a `joined` tier is
  *selected by which companies this workspace is interested in* — the rows are
  public, the selection is not. This repo (public) holds the collector, the
  projector and their tests; it holds no JP company data.

`:company/registration-no` carries the same 13 digits as
`:company/houjin-bangou`, because that is the attribute GLEIF's Golden Copy
already uses for a JP entity's national registry number — so a GLEIF record
and an NTA record join with no translation layer.

**同名は住所で解く。** 官報の公告も落札公示も住所を持っているのに、名寄せは長い間
名前しか見ていなかった。同名 2 社はほとんどの場合**県が違う**（株式会社うるるは
中央区と香取郡東庄町）。県で絞り、同一県なら市区町村で絞る。実測 2026-08-19:

| | 名前だけ | 住所つき |
|---|---:|---:|
| 決算公告 607/915 → | ambiguous 206 | **658/915**、ambiguous 155 |
| 落札公示 365/673 → | ambiguous 138 | **458/673**、ambiguous 45 |

市区町村は**切り出さず前方一致**で見る —— registry は「さいたま市大宮区」
「香取郡東庄町」「中央区」をどれも 1 単位で持つので、切り出す正規表現はどれかを
必ず取り違える。**住所がどの候補とも一致しなければ絞らない**（曖昧なままにする）。
どう決めたかは `:company/name-match`（`:exact` / `:exact+address` …）に残る。

**Name resolution is the part that is easy to get quietly wrong.** A JP company
name is not a key: 株式会社うるる is two different companies in this file. The
projector keeps `:exact`, `:core` (form-insensitive) and `:ambiguous` apart, and
an ambiguous name resolves to *nothing* and is reported by name in `--report`.

## Is this company a registered invoice issuer (適格請求書発行事業者)

A second NTA site, a second monthly full file, and one question the corporate
registry cannot answer: is this counterparty registered to issue a qualified
invoice, since when, and is that registration still live.

```bash
# 法人 + 人格のない社団等 only (the default)
kbb --backend sci -cp src scripts/collect_invoice_zenken.cljk --download
# also the sole proprietors — node-local corpus only, see below
kbb --backend sci -cp src scripts/collect_invoice_zenken.cljk --download --kinds all

kbb --backend sci -cp src scripts/project_invoice_corpus.cljk \
  --corpus ~/.cache/invoice-kohyo/invoice-corpus.edn \
  --number-file <法人番号 the plane already has> --latest-only \
  --out <jp-go-nta-houjin-bangou>/data/invoice-joined.datoms.edn
```

For a corporation the registration number is `T` + its 法人番号, so every
corporate row joins to the 法人番号 registry, to GLEIF, and to everything else on
`:company/registration-no` with no translation.

**A sole proprietor's number is not a 法人番号**, and
`invoice-zenken/projectable?` refuses those rows — the projector counts each
refusal instead of filtering silently, and the projections repo re-checks the
committed artifact. Measured on the 2026-07-31 publish: 5,069,446 registrations,
of which 2,491,986 are individuals; the individual archive publishes no names at
all (0 of 200,000 sampled rows carry `name` or `tradeName`), so what is being
kept off the shared plane is a person-linked identifier, not a name list.

Two details that cost a run each to learn, kept here so the next reader does not
pay for them again:

- the CSV quotes its registration number (`1,"T1030005007532",01,…`) while the
  法人番号 file quotes only text fields;
- **取消 (`disposalDate`) comes before 失効 (`expireDate`)** in the column order,
  which is the opposite of the order a reader expects, and swapping them
  silently swaps two dates that both mean "this registration ended". The column
  names come from the JSON publish of the same records — the only artifact the
  authority ships that states the order unambiguously.

## Which subsidies exist (jGrants)

```bash
kbb --backend sci -cp src scripts/collect_jgrants.cljk --out <jp-go-digital-jgrants>/data/jgrants-catalog.datoms.edn
```

デジタル庁's public API, no key. Measured 2026-08-18: 18 keywords, **3,751
programmes**, **308 open**, details fetched for the open ones only.

**It is the 公募 side and nothing else.** No `:company/houjin-bangou`, no
`:company/lei` — so "has this counterparty ever received a subsidy" is *not*
answerable from it. That answer lives in per-programme 採択者一覧 spreadsheets,
which are not ingested. Coverage is a union of keyword queries because the API
requires a 2+ character keyword and has no enumeration (an empty one is HTTP
400), so the keyword set is recorded in the artifact.

## What the state gave, bought and recorded (gBizINFO)

```bash
GBIZINFO_TOKEN=... kbb --backend sci -cp src scripts/collect_gbizinfo.cljk \
  --numbers <法人番号 one per line> --aspects subsidy,procurement,finance \
  --out <jp-go-gbiz-info>/data/gbizinfo-joined.datoms.edn
```

One request per company per aspect, keyed on 法人番号 — so the allowlist is the
cost and the unit is "the companies this plane already carries", not a universe.
It answers what neither NTA registry can: 補助金交付, 調達, and **決算期**
(`:company/fiscal-year-end-month`, parsed from `fiscal_year_cover_page`).

A real pass needs the operator's own token: the 利用申請 registers the operator's
identity with 経済産業省, so an agent must not obtain it. `--demo` uses the
動作確認 token the public OpenAPI document publishes **under a request cap** —
a verification that could silently become a bulk pass on a shared token is not a
verification, so the cap is enforced in code and the token kind is written into
the artifact's manifest.

Measured 2026-08-18 (16 companies, 48 requests, demo token): 23 procurement
awards, 4 fiscal-year-ends, 0 subsidies. `finance` returns nothing for most
companies — gBizINFO carries filings only where they exist, so absence is
normal and is *not* recorded as a zero.

## 決算期 for companies that file no securities report (官報決算公告)

gBizINFO's finance is EDINET-derived, so it answers 決算期 for listed companies
and nobody else. The only public route for the rest is the Companies Act art.
440 announcement, printed in 官報 every publication day.

```bash
kbb --backend sci -cp src scripts/collect_kanpou_kessan.cljk --back 14 --out <repo>/data/kanpou-kessan.datoms.edn
```

Measured 2026-08-18, 14 publication days: **1,303 決算公告 headlines → 472
records (36%)**, ~34 companies a day landing with a fiscal year end, a period
number, an address and paid-in capital.

Three constraints, all load-bearing:

- **Only the last 90 days are free.** There is no archive behind it, so this is
  data you accumulate — an uncollected day is lost, which is the first thing in
  this repository that genuinely needs a daily cell.
- **The 36% is the parser, not the day.** The remainder are mostly vertical-set
  notices with kanji numerals (公益信託 and similar). The collector prints
  headlines *and* records every run, because a parser that quietly dropped two
  thirds would look exactly like a quiet day.
- **The notices carry no 法人番号** — only a name and an address. Linking them to
  the corporate registry is name resolution, which
  `houjin-bangou-projection/resolve-names` already does, including refusing to
  resolve a name two companies share.

Representative directors' names appear in every notice and are dropped on the
way in, for the same reason `gbizinfo/basic-record` drops them.

## Who won which government contract (官報 政府調達版)

gBizINFO aggregates 調達 from ministry publications; the 落札者等の公示 in 官報's
政府調達版 is the **primary** notice the buyer itself published, so reading it
removes that dependency.

```bash
kbb --backend sci -cp src scripts/collect_kanpou_chotatsu.cljk --back 30 --out <repo>/data/kanpou-chotatsu.datoms.edn
```

Measured 2026-08-18, 30 days / 20 procurement issues: **673 awards, ¥289.4bn
total, largest ¥51.1bn**, 365 linked to a 法人番号. Records use the **same
`:grant/*` attributes as gBizINFO's procurement rows**, so "what has the state
given this company" is one query across both, and `:source/dataset` says which
notice it came from.

Only WTO-agreement-scale contracts appear in 官報 — **absence is not evidence of
no award**, it is evidence of a smaller one.

Three things this parser had to learn, each of which produced valid-looking
garbage first:

- **The field numbers are PUA characters.** The 国立印刷局 PDFs use the
  `Adobe-Npb1` CID collection, so digits, commas, hyphens and the circled field
  markers come out as U+E000-block code points while the kanji come out fine.
  `kotoba.property.kanpou-pua` maps only the ones confirmed against values
  printed elsewhere on the page (issue number 152, the date, page numbers).
- **`(int c)` is NaN in ClojureScript** — the markers then pass through as
  invisible characters, which looks exactly like whitespace in the output. Same
  trap as the gBizINFO fiscal month; `code-point` now handles both runtimes.
- **The winner's address is not always in parentheses.** With only the paren
  form, 403 of 589 names failed to resolve because the address was still glued
  to the name. Splitting on a prefecture name too took resolution from 131 to
  254.

## Press releases from the distributors (PR TIMES)

Only 41 of the 1,040 companies we track publish a feed on their own site; in
Japan press releases collect on distributors. This reads the distributor's own
public feed and keeps the citation, not the release:

```bash
kbb --backend sci -cp src scripts/collect_press_wire.cljk --out <repo>/data/press-wire.datoms.edn \
  --names-out /tmp/issuers.txt                       # then resolve the names…
kbb --backend sci -cp src scripts/project_houjin_bangou_corpus.cljk --corpus <c> \
  --name-file /tmp/issuers.txt --latest-only --report /tmp/res.edn --out /tmp/scratch.edn
kbb --backend sci -cp src scripts/collect_press_wire.cljk --out <repo>/data/press-wire.datoms.edn \
  --report /tmp/res.edn                              # …and link them
```

**robots.txt was read before any of this.** PR TIMES allows crawling (`Allow: /`,
three narrow exclusions) and publishes RSS 1.0 at `/index.rdf`. **ValuePress
disallows `/rss/`, so its feed is not used**, and DreamNews' robots.txt answers
503 — permission unverifiable, so it is not used either. 共同通信PRワイヤー and
@Press welcome crawlers but expose no feed to discover.

Measured 2026-08-19, and the first measurement was wrong: one snapshot's 200
items spanned 6.8 days, which read like a window — but two fetches five seconds
apart are identical while two a few minutes apart differ by 129–165 items, and a
later snapshot spanned 28 days. **The feed is a rotating sample of roughly the
last month, not the newest 200**, so no per-day rate and no polling interval can
be derived from it. Daily is chosen for politeness and diminishing returns; every
poll adds roughly 130–165 releases the store has not seen. Of 192 distinct issuers, **119 (62%) resolve to a
unique 法人番号** by name alone; the feed carries no address, so that is the
ceiling for this join. Unresolved issuers are kept with their name: a
distributor's byline is a brand or trading name as often as a registered one.

**The release body is not stored** — only title, URL, date and issuer. The text
belongs to the issuer; this is the same `fair-use-quote` line newsfeed draws.

## Who owns whom (Level 2 / RR)

Level 1 says who a legal entity is. It carries no edge, so no Level 1
projection at any size can answer "who ultimately controls this counterparty".
That answer is in the RR file, published daily beside LEI2 under the same CC0
terms — 483,263 relationships in the 2026-08-03 publish, two orders of
magnitude smaller than the entity universe and therefore tractable whole.

```bash
# 1. download the RR archive (~24 MB) from the same publish index
curl -s 'https://goldencopy.gleif.org/api/v2/golden-copies/publishes?format=json' \
  | jq -r '.data[0].rr.full_file.csv.url'
curl -L -o ~/.cache/gleif/rr-golden-copy.csv.zip '<url from above>'

# 2. stream it into an EDN-lines corpus (~5 min, 181 MB)
kbb --backend sci -cp src scripts/collect_gleif_rr_golden_copy.cljk \
  --zip ~/.cache/gleif/rr-golden-copy.csv.zip \
  --out ~/.cache/gleif/gleif-rr-corpus.edn

# 3. project the edges that touch LEIs the query plane already knows
kbb --backend sci -cp src scripts/project_gleif_rr_corpus.cljk \
  --corpus ~/.cache/gleif/gleif-rr-corpus.edn \
  --lei-file /tmp/plane-leis.txt \
  --out data/gleif-relationship-joined.datoms.edn
```

`--lei-file` matches **either** end of the edge, because knowing the child
answers "who owns this?" and knowing the parent answers "what does this own?".
Matching only the child would silently drop every subsidiary of a company the
plane already holds.

Relationship types in the 2026-08-03 publish:

| Type | Count |
| --- | --- |
| `IS_FUND-MANAGED_BY` | 148,759 |
| `IS_ULTIMATELY_CONSOLIDATED_BY` | 132,241 |
| `IS_DIRECTLY_CONSOLIDATED_BY` | 126,087 |
| `IS_SUBFUND_OF` | 72,849 |
| `IS_INTERNATIONAL_BRANCH_OF` | 1,940 |
| `IS_FEEDER_TO` | 1,387 |

**Every edge keeps its evidence tier.** `:corporate-relation/validation` is
GLEIF's own: `FULLY_CORROBORATED` (327,207) means the managing LOU checked the
claim against a source; `ENTITY_SUPPLIED_ONLY` (139,111) means the company
asserted its own parent and nobody verified it; `PARTIALLY_CORROBORATED` is the
remaining 16,945. Do not present a self-declared edge as a verified one — 29%
of this file is self-declaration, and a consumer that flattens the distinction
is reporting a guess as a fact.

Ownership percentage (`:corporate-relation/quantifier-amount`) is present on
51,664 of 483,263 edges. Its absence means unknown, never zero.

## `var/` and `data/`

- `var/` — a collector's working store, rewritten in place on each refresh,
  Git-ignored. A cache, not a publication.
- `data/` — committed projections in EDN-lines form, one record per line,
  readable without holding the file in memory. Only extracts that pass the
  publication review in `DATA-GOVERNANCE.md` go here: today public-body
  property claims and corporate identity records, neither of which contains
  natural-person data.

```bash
kbb --backend sci -cp src scripts/collect_nyc.cljk --limit 5000
kbb --backend sci -cp src scripts/export_ownership_datoms.cljk   # var/ -> data/
```

Authority coverage is recorded in
`resources/property/open_data/coverage.edn`. Unlisted jurisdictions default to
`:unknown`; they are never silently collected.

```bash
npm run query:coverage
npm run query:coverage -- --status allow-login-free
```

When a licensed HMLR store and a GLEIF store contain the same UK company
registration number, join them directly:

```bash
kbb --backend sci -cp src scripts/query_property_parent.cljk \
  --parcel GB-HMLR:TITLE_NUMBER
```


## Maturity

| | |
|---|---|
| Role | capability |
| Tests | 20 assertions, all green |
| Operator console (UI/UX) | yes |
| Export (CSV/JSON) | yes |
| Shared CSS design system | yes (css.core/operator-theme) |

## Contract

```clojure
(require '[kotoba.property :as prop])

(prop/parcel "P1" :address "1 Main St" :area-m2 120 :zoning :residential)
(prop/listing "L1" "P1" :rent 1000)
(prop/lease "LS1" "P1" "tenant" "landlord" 1000 "2026-01-01" "2026-12-31")
(prop/term-overlaps? lease-a lease-b)   ; => true/false
```

## Operator console (UI/UX)

A read-only HTML dashboard renders parcels, listings and leases (with term-overlap warnings) for an operator. Built on
[`kotoba-lang/html`](https://github.com/kotoba-lang/html) (Hiccup→HTML) +
[`kotoba-lang/css`](https://github.com/kotoba-lang/css) (EDN→CSS). Pure data
→ markup; the console never exposes a write surface (no `<form>`/`<button>`)
— writes stay behind the governor.

```clojure
(require '[kotoba.property.ui :as ui])

(ui/dashboard
  {:parcels [(prop/parcel "P1" :address "1 Main St")]
   :listings [(prop/listing "L1" "P1" :rent 1000)]
   :leases [(prop/lease "LS1" "P1" "tenant" "landlord" 1000 "2026-01-01" "2026-12-31")]})
;; => "<html>...read-only · governor-gated...</html>"
```

## Export (CSV / JSON)

Audit-grade CSV (RFC-4180 quoting) and JSON (quote/backslash/newline
escaped) for parcels, listings and leases (term-overlap flagged).

```clojure
(require '[kotoba.property.export :as ex])

(ex/parcels->csv parcels)
(ex/leases->csv leases)      ; term-overlap flag
(ex/leases->json leases)
```

## License

Apache License 2.0.

## Test

```bash
kbb -M:test
```
