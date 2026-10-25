# toshokan (図書館)

Read-only reference/archive actor — harvests public bibliographic metadata
from national library catalogs and preserves it, per the pattern in
[ADR-2607072300](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607072300-actor-public-data-git-journal-kotobase-index.edn)
(this repo's own git history is the source of truth; kotobase.net is a
derived, rebuildable index over it) and
[ADR-2607113500](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607113500-kotobase-net-ingestion-cloud-itonami-lei.edn)
(the pull-based batch fold job shape). Full design rationale, the 5-source
research, and the real end-to-end verification numbers are in
[ADR-2607199900](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607199900-toshokan-national-library-catalog-ingestion.edn).

**Default plane is metadata-only** (title / creator / publisher / date /
identifiers / subject from national library catalogs). It never bypasses
paywalls or access controls.

**Public-domain full text** is a second plane (ADR-2607255100 fulltext
addendum): Project Gutenberg works with gutendex `copyright: false` only.
Bodies live under `fulltext/gutenberg/<id>/` as **git-annex** content (B2);
metadata quads live in `80-data/public/gutenberg.journal.edn`. In-copyright
full text is never stored.

## Self-growing resident loop (2026-07-25, ADR-2607255100)

The repo now grows itself on a schedule instead of only via manual
`scripts/harvest.cljk` one-shots:

| file | role |
|---|---|
| `seeds.edn` | query seed list (hand-editable; daemon also appends grown seeds) |
| `scripts/daemon.cljk` | one tick: harvest → dedupe → journal append → seed grow → optional fulltext + push + kotobase ingest |
| `state.edn` | cursor / exhausted pairs (daemon-managed) |
| `scripts/query.cljk` | local DataScript query over journals |
| `scripts/fulltext-gutenberg.cljk` | public-domain full text (Gutenberg / gutendex) |
| `fulltext/gutenberg/` | annex bodies + per-work meta.edn |
| `deploy/com.kotoba-lang.toshokan-tick.plist` | macOS LaunchAgent for murakumo-fleet host residency |

```bash
# one tick (catalog harvest only)
kbb --backend sci --classpath src scripts/daemon.cljk --once

# one tick + public-domain fulltext + git push + kotobase fold (LaunchAgent)
kbb --backend sci --classpath src scripts/daemon.cljk --once --fulltext --push --ingest

# fulltext only (a few classics / seed-driven)
kbb --backend sci --classpath src scripts/fulltext-gutenberg.cljk --id 1342
kbb --backend sci --classpath src scripts/fulltext-gutenberg.cljk --from-seeds --limit 1

# local query surface
kbb --backend sci --classpath src scripts/query.cljk stats
kbb --backend sci --classpath src scripts/query.cljk sample 10
kbb --backend sci --classpath src scripts/query.cljk fulltext
```

Residency on the murakumo fleet host is a LaunchAgent (same class as
`com.gftd.fleet-ci-murakumo-tick` / `com.gftd.itonami-qwen36-tick`), not a
WASM `on-tick` guest yet — that waits on ADR-2607252400 CID capabilities.
`RunAtLoad` + `StartInterval=21600` (6h). Install:

```bash
cp deploy/com.kotoba-lang.toshokan-tick.plist ~/Library/LaunchAgents/
# ensure ~/.gftd/run-toshokan-tick.cljs exists (wrapper cds to TOSHOKAN_ROOT)
launchctl bootout gui/$(id -u)/com.kotoba-lang.toshokan-tick 2>/dev/null || true
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.kotoba-lang.toshokan-tick.plist
launchctl kickstart -k gui/$(id -u)/com.kotoba-lang.toshokan-tick
```

## Sources

| source | status | endpoint | auth |
|---|---|---|---|
| `ndl` — National Diet Library (Japan) | implemented | `ndlsearch.ndl.go.jp/api/sru` (SRU, dcndl schema) | none |
| `loc` — Library of Congress (US) | implemented | `www.loc.gov/search/` (JSON API) | none |
| `dnb` — Deutsche Nationalbibliothek (Germany) | implemented | `services.dnb.de/sru/dnb` (SRU, oai_dc schema) | none |
| `bnf` — Bibliothèque nationale de France | implemented | `catalogue.bnf.fr/api/SRU` (SRU, dublincore schema) | none |
| `kb-nl` — Koninklijke Bibliotheek (Netherlands) | implemented | `jsru.kb.nl/sru/sru` (SRU, dcx schema over GGC catalog) | none |
| `libris-se` — Libris (Sweden, KB union catalog) | implemented | `libris.kb.se/xsearch` (XSearch, MODS schema) | none |
| `nb-no` — Nasjonalbiblioteket (Norway) | implemented | `api.nb.no/catalog/v1/items` (JSON, metadata embedded in search results) | none |
| `iccu-it` — OPAC SBN / ICCU (Italy) | implemented, **unofficial endpoint** | `opac.sbn.it/opacmobilegw/search.json` (JSON, undocumented mobile-app backend on ICCU's own domain) | none |
| `korea-nl` — National Library of Korea | implemented, **blocked on a key** | `www.nl.go.kr/NL/search/openApi/search.do` | `NL_GO_KR_API_KEY` — register at nl.go.kr (manual, per-account approval; unverified whether non-Korean applicants can register) |
| `iran-nlai` — National Library of Iran | **`:spec`, not implemented** | none exists | — |
| `russia-rsl` — Russian State Library / National Library of Russia | **`:spec`, not implemented** | none exists | — |

Coverage is being extended incrementally (one new jurisdiction at a time,
each with a real working harvester verified against live data before
being added to this table — not just a stub) via a recurring background
task. Each addition's own commit message is the record of what changed
and what was verified; this repo's own git history is authoritative for
that per ADR-2607072300, so per-jurisdiction additions don't each get a
new superproject ADR.

**Checked and ruled out (2026-07-19), so future iterations don't re-spend
time on these**: British Library's `sru.bl.uk` no longer resolves (DNS
failure, service appears retired). Spain's BNE (`catalogo.bne.es/UNICORN/sru`)
redirects into an Ex Libris Alma instance with no working SRU endpoint at
the old URL (404 Alma error page). Switzerland's swisscovery (SLSP) is
Alma-based behind a login redirect, no open SRU found without deeper
digging. Korea's Trove-equivalent pattern (a real API gated on
registration) also showed up for Australia's Trove (`api.trove.nla.gov.au`,
401 "No API key found") -- same shape as `korea-nl`, a future addition
would need the same "wire it, block cleanly on a human registration step"
treatment rather than a live-verified entry. Finland's Finna.fi API
(`api.finna.fi`) returns a Cloudflare bot-check challenge page (403,
"Just a moment...") even on a plain API request -- not attempted further,
since working around bot detection is out of scope regardless of API
documentation quality.

**Second pass (2026-07-19, later)**: New Zealand's DigitalNZ API
(`api.digitalnz.org`) is real and keyless, but for library-catalog-shaped
queries it mostly surfaced digitized newspaper articles (Papers Past) with
a `fulltext` OCR field as the actual payload, not book-style bibliographic
records -- filtering `and[category][]=Books` returned zero results for
several test queries. Adding it would mean either storing full-text OCR
(violates this repo's metadata-only scope) or shipping a source that
rarely returns what this project means by "library catalog data" -- not
added; revisit if a query shape is found that reliably surfaces NLNZ book
records specifically rather than the wider GLAM aggregation. Czech
National Library's Aleph endpoint (`aleph.nkp.cz`) IP-allowlists access
(403 "Access from IP address ... not allowed") -- a real access control,
not attempted around. Guessed SRU/API endpoints for Portugal (BNP/PORBASE),
Ireland (NLI), Canada (LAC), and Iceland (Landskerfi) either don't resolve,
403, or redirect into a UI rather than an API -- none confirmed reachable
without more specific documentation research than a first-pass endpoint
guess; worth a dedicated look rather than more guessing.

**Third pass (2026-07-19, later still)**: Denmark's Royal Library data
lives behind the DBC Open Platform (`openplatform.dbc.dk`) -- confirmed
via its own documentation this requires a Client id/secret, and
registration is explicitly restricted to "a Danish library or a partner
via a library," so unlike Korea (unverified) this one is a **confirmed,
not just probable, dead end** for a non-Danish-library registrant. Not
wired as a coded-but-blocked source like `korea-nl`, since there's no
realistic path to ever unblock it the way Korea's might be.

Iran and Russia have no official API, OAI-PMH, SRU, or bulk export — only
unofficial third-party HTML scrapers exist for either, and both sit in
sanctions-sensitive territory that hasn't had legal review for this use.
See `src/toshokan/sources/iran_nlai.cljk` and `russia_rsl.cljs` for the
full reasoning; calling `search` on either throws immediately rather than
silently no-op'ing.

`iccu-it` is a different, lower-stakes kind of caveat: it's real data
served directly from Italy's own official ICCU/OPAC SBN domain (not a
third-party scrape of somebody else's system), but it's the *mobile app's*
undocumented JSON backend, not ICCU's formally published protocol (which
is Z39.50). See `src/toshokan/sources/iccu_it.cljk` for the full caveat —
more likely to change/break than this repo's other sources.

## Usage

All scripts run under [nbb](https://github.com/babashka/nbb) per this
workspace's runtime priority rules (kotoba wasm → clojurewasm → cljs →
nbb). From this repo's root:

```bash
# harvest a source into this repo's own 80-data/public/<source>.journal.edn
kbb --backend sci --classpath "src" scripts/harvest.cljk ndl 'title="夏目漱石"' 20
kbb --backend sci --classpath "src" scripts/harvest.cljk loc "natsume soseki" 20
kbb --backend sci --classpath "src" scripts/harvest.cljk dnb "WOE=soseki" 20
kbb --backend sci --classpath "src" scripts/harvest.cljk bnf 'bib.title all "soseki"' 20
kbb --backend sci --classpath "src" scripts/harvest.cljk kb-nl soseki 20
kbb --backend sci --classpath "src" scripts/harvest.cljk libris-se soseki 20
kbb --backend sci --classpath "src" scripts/harvest.cljk nb-no soseki 20
kbb --backend sci --classpath "src" scripts/harvest.cljk iccu-it soseki 20
NL_GO_KR_API_KEY=... kbb --backend sci --classpath "src" scripts/harvest.cljk korea-nl "소세키" 20

# fold every local journal into kotobase.net (self-mints an Ed25519
# identity into scripts/.kotobase-ingest-toshokan-identity.hex on first
# run -- gitignored, back it up, losing it orphans the graph)
NODE_PATH="<path-to>/kotoba-lang/kotobase-client/node_modules" \
  kbb --backend sci --classpath "<path-to>/kotoba-lang/kotobase-client/src:src" \
  scripts/kotobase-ingest-toshokan.cljk

# tests (fixture-based, no live network)
kbb --backend sci --classpath "src:test" scripts/run-tests.cljk

# one Kotoba policy test definition, executed on KIR/JVM + restricted ESM + Wasm
cd ../compiler
kbb -M:run test ../toshokan/src/toshokan/portable_effect.kotoba

# build the restricted ESM policy imported by the workerd adapter
cd ../toshokan
scripts/build-portable-effect.sh
node workerd/portable-effect-host.test.mjs
```

## Schema

Quads use the `[entity attr value tx op]` shape from ADR-2607072300.
Entities are namespaced by source: `ndl:<bib-id>`, `loc:<lccn-or-id>`,
`dnb:<idn>`, `bnf:<ark-id>`, `kb-nl:<ppn>`, `libris-se:<libris-id>`,
`nb-no:<sesam-id>`, `iccu-it:<iccu-code>`, `korea-nl:<control-no>`.
Attributes: `:library/source`,
`:library/source-url`, `:library/title`, `:library/creator` (many),
`:library/publisher`, `:library/date`, `:library/language`,
`:library/format`, `:library/ndc` / `:library/lccn` / `:library/isbn`,
`:library/subject` (many), `:library/retrieved-at`. See
`src/toshokan/quad.cljk` and each `toshokan.sources.*` namespace.

## Scope not yet covered

Bulk/continuous harvesting (NDL's Free Data Service + weekly JAPAN/MARC
dumps, LOC's 2017 25M-record bulk set, OAI-PMH resumption-token paging),
scheduling, and Korea NL's key registration are all deliberately out of
scope for this first cut — see ADR-2607199900's Consequences.
