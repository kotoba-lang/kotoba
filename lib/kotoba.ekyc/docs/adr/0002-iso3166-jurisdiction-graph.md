# ADR-0002: `kotoba.ekyc.jurisdiction-graph` — cross-repo regulatory-linkage graph

- Status: Accepted (2026-07-14)
- Repository: `ekyc` (kotoba-lang)

## Context

`kotoba.ekyc` (ADR-0001) models JPN's 犯収法施行規則 第6条第1項 non-face-to-face
identity-verification methods as structural records with real legal-basis
citations, cross-referenced against NIST SP 800-63A-4 IAL levels. It is
currently the ONLY jurisdiction modeled in that library.

Separately, the `cloud-itonami` GitHub org runs a `cloud-itonami-iso3166-*`
family of per-country "Market-Entry Compliance" actor repos
(`marketentry.*` namespaces, Compliance Advisor ⊣ Market-Entry Compliance
Governor). `cloud-itonami-iso3166-jpn`'s own README describes itself as
"the first running actor in the `cloud-itonami-iso3166-*` family."

The task: link `kotoba.ekyc`'s regulatory method data with the
`cloud-itonami-iso3166-*` family via EDN, loadable into both Datomic (JVM)
and DataScript (ClojureScript/in-browser) — a real queryable graph, not
static markdown citations.

## Where this lives

This graph spans 223 candidate country repos plus one capability library —
it does not belong to any single country repo. It is added to
`kotoba-lang/ekyc` itself, as a new `kotoba.ekyc.jurisdiction-graph`
namespace, because: (1) `kotoba.ekyc` already owns the underlying
regulatory-method data this graph reuses (`method-catalog`) and any drift
between a copy and the source would be a correctness bug waiting to
happen — `method-entities` derives from the live catalog var, not a
hand-copy; (2) `ekyc` is already west-managed and has an established
`.cljc` / clojure.test / clj-kondo / CI setup this addition reuses without
inventing a second one; (3) no licensing or dependency-direction conflict
exists — `kotoba-lang/ekyc` is MIT, has no dependency on any
`cloud-itonami-iso3166-*` repo, and a country actor may optionally depend
on `kotoba-lang/ekyc` (the natural direction: capability library ← actor),
never the reverse. A separate new repo was considered and rejected: it
would either duplicate `kotoba.ekyc/method-catalog` (drift risk) or take a
dependency on `kotoba-lang/ekyc` for no benefit over adding a namespace
directly to it.

## Verification method — 223 vs. 188 (do not assume, verify)

The task's own framing named "223 per-country repos." This ADR's author
verified that number directly rather than assuming it, with a material
correction:

```bash
find orgs/cloud-itonami -maxdepth 1 -iname 'cloud-itonami-iso3166-*' -type d | wc -l
# => 223 (real local directory count)
gh api "orgs/cloud-itonami/repos?per_page=100" --paginate --jq '.[].name' \
  | grep '^cloud-itonami-iso3166-' | wc -l
# => 216 (real, LIVE-on-GitHub count, cross-checked with a token carrying
#         'repo' scope -- the 7 not in this list genuinely 404, confirmed
#         individually via `gh api repos/cloud-itonami/cloud-itonami-iso3166-<code>`,
#         not a pagination/permission artifact)
```

223 local directories minus 216 live-on-GitHub repos left a 7-entry gap,
which resolved to two DISTINCT findings, neither previously stated:

1. **`cloud-itonami-iso3166-ind-clean-air` is not a country repo at all.**
   Its own `blueprint.edn` declares
   `:itonami.blueprint/domain :public-interest/airshed-clean-air` (an
   India-specific air-quality project, not `:public-sector/market-entry-
   compliance`) — it matches the directory glob but is a different kind of
   blueprint entirely.
2. **Six directories (`kgz` `lao` `mmr` `tjk` `tkm` `uzb`) are real local
   scaffolds — full `blueprint.edn` + README + docs — with no `.git` of
   their own** (they are plain subdirectories of the west-managed
   superproject checkout, not independent clones) **and 404 on GitHub.**
   They were scaffolded locally but never `gh repo create`d / pushed.

Parsing every remaining `blueprint.edn`'s own
`:itonami.blueprint/domain` field surfaced a THIRD, larger finding: **34 of
the 222 non-`ind-clean-air` directories are Japan/USA AGENCY-level
sub-blueprints, not additional countries** — `cloud-itonami-iso3166-jpn-*`
(19 entries: `audit` `cao` `digital` `fsa` `jftc` `maff` `meti` `mext`
`mhlw` `mic` `mlit` `mod` `moe` `mof` `mofa` `moj` `ppc` `reconstruction`
`statistics`) and `cloud-itonami-iso3166-usa-*` (15 entries: `dhs` `doc`
`dod` `doe` `dol` `dot` `epa` `fcc` `ftc` `gsa` `hhs` `sba` `sec`
`treasury` `va`). Each carries a compound id like `"JPN-FSA"`, which is
not a valid ISO 3166-1 alpha-3 code and is not addressable under this
graph's `:country/iso3166-alpha3` attribute by construction — matching
`kotoba-lang/iso3166`'s own registry, which separately tracks these as
`:parent "JPN"` / `:parent "USA"` entries (34 of them, confirmed via `bb`
against `resources/kotoba/iso3166/registry.edn`), not top-level countries.

**The real number is 188** — verified by parsing all 222 non-`ind-clean-
air` `blueprint.edn` files and filtering to
`:itonami.blueprint/domain :public-sector/market-entry-compliance`. Of
those 188, 182 are confirmed live on GitHub; the same six (`KGZ` `LAO`
`MMR` `TJK` `TKM` `UZB`) are local-only. This ADR reports 188, not 223 —
inflating the count would itself be a small fabrication in a library whose
entire discipline is "never fabricate, report honest coverage."

Each of the 188 country names + ISO 3166-1 alpha-3 codes is the country
repo's OWN self-declared data (`:itonami.blueprint/iso3166` /
`:itonami.blueprint/name` in that repo's `blueprint.edn`), not re-derived
or fuzzy-matched from a third source. ISO 3166-1 alpha-2 codes are
cross-referenced by country identity against
`/usr/share/zoneinfo.default/iso3166.tab` (the IANA tz database's
public-domain ISO 3166-1 alpha-2 table) — NOT derived by truncating the
alpha-3 code, which is wrong in general (e.g. `CHN`/China's alpha-2 is
`CN`, not `CH` — `CH` is Switzerland's, whose own alpha-3 is `CHE`).

## Schema design

Three entity kinds:

- **`:country/*`** — one per real country repo: `:country/iso3166-alpha3`
  (unique identity), `:country/iso3166-alpha2`, `:country/name`,
  `:country/repo-url`, `:country/coverage-status`
  (`:researched` | `:not-yet-researched`).
- **`:ekyc-method/*`** — one per `kotoba.ekyc/method-catalog` entry (10
  today), derived programmatically via `method-entities`, never hand-
  copied, so the graph cannot drift from the source catalog.
- **`:recognition/*`** — a REIFIED edge entity, not a direct
  country→method ref. `:country/recognizes-method` (ref, cardinality
  many) points from a country to `:recognition/*` entities, each of which
  refs both the country and the method AND carries its own
  `:recognition/legal-basis` — a jurisdiction-specific citation, distinct
  from the method's own canonical `:ekyc-method/legal-basis`. This
  reification exists because the citation is jurisdiction-specific even
  when the underlying method CONCEPT is shared: a second jurisdiction
  recognizing an equivalent method would cite its own statute, not JPN's
  犯収法施行規則. Today, with only JPN modeled, every recognition's
  legal-basis happens to equal its method's canonical citation (proven
  equal in `recognition-legal-basis-matches-method-citation-test`) — but
  the schema does not hard-code that equality, because it will not hold
  once a second jurisdiction is added.

## Datomic / DataScript dual compatibility — verified, not claimed

The task required proving DataScript compatibility empirically, not
asserting it. Before writing the final schema, the following was
determined against a REAL `datascript.core` conn (`datascript/datascript`
1.7.8 on the JVM — the actual portable `.cljc` DataScript source, the same
code that compiles to run in a browser; matches this workspace's own
precedent in `orgs/etzhayyim/global-energy-datoms`):

```clojure
(d/create-conn {:attr {:db/valueType :db.type/string :db/cardinality :db.cardinality/one
                       :db/fulltext true :db/doc "x"}})
;; => THROWS: Bad attribute specification for #:attr{...},
;;    expected one of #{:db.type/tuple :db.type/ref}
```

This was the significant, non-obvious finding: **DataScript rejects ANY
`:db/valueType` other than `:db.type/ref`/`:db.type/tuple` outright** (a
hard `create-conn`-time error, not a silently-ignored key) — not merely
`:db/fulltext` in isolation, which was the only divergence assumed before
probing. Standalone `:db/doc`, `:db/cardinality`, `:db/unique`, and
`:db/index` were separately confirmed to load and transact cleanly with no
`:db/valueType` present.

A second, independent finding: DataScript's map-form `transact!` does
**not** resolve a lookup ref (e.g. `[:recognition/id "JPN:ho"]`) against a
sibling entity map created earlier OR later in the SAME `tx-data` vector
— both orderings threw `Nothing found for entity id`. Real Datomic
supports this ("forward-referencing upsert" within one transaction);
DataScript does not. `base-tx-data` (countries + methods, no cross-refs)
and `edge-tx-data` (JPN's recognition entities + the
`:country/recognizes-method` backfill, all via lookup refs against
entities `base-tx-data` already landed) are split into two transact calls
specifically because of this, verified in `load-into-real-datascript-test`.

`schema-datascript` is `(derive-datascript-schema schema-datomic)` — a
small, inspectable, mechanical transform (drop `:db/fulltext`; drop
`:db/valueType` unless `:db.type/ref`) — not a hand-maintained parallel
definition that could silently drift from `schema-datomic`.
`test/kotoba/ekyc/jurisdiction_graph_test.cljk` transacts the derived
schema plus real tx-data into a real `datascript.core` conn and runs every
example query in `queries` against it, asserting real result shapes (e.g.
exactly 10 rows for `:jpn-recognized-methods`, matching
`kotoba.ekyc/method-catalog`'s real 10 entries) — 213 assertions across 49
tests, `kbb -M:test`, all green.

`schema-datomic` itself follows standard, documented Datomic schema
vocabulary (`:db/valueType`, `:db/fulltext`, `:db/doc`) but is not
transacted against a real Datomic peer in this repo's CI — this workspace
has no licensed Datomic instance, the same reason the rest of the
`cloud-itonami-*` fleet abstracts through `langchain.db` (a Datomic-API-
compatible in-memory store) rather than a real peer connection. Any real
Datomic peer, or `langchain.db`, or a real DataScript conn via
`schema-datascript`, can all transact `base-tx-data` / `edge-tx-data` —
they are plain EDN, not tied to any one engine.

## `cloud-itonami-iso3166-jpn` software-dependency wiring

`cloud-itonami-iso3166-jpn` is the one `:implemented`-maturity country
actor in principle able to consume this graph as a real code dependency
(`deps.edn` git dep on `kotoba-lang/ekyc`). Concretely: `marketentry.*`
today has no identity/KYC-adjacent check in its Governor or Op set (its
existing HARD check, `japan-resident-rep-missing`, is about a
Japan-resident authorized representative for public-procurement
registration — a different regulatory surface than eKYC identity
verification of the operator's own representative). Forcing an artificial
`kotoba.ekyc` call into that check would misrepresent what the check
actually verifies. The honestly-scoped R0 outcome is the data-graph link
this ADR describes (`cloud-itonami-iso3166-jpn`'s own operator/engagement
model could cite this graph's `:country/recognizes-method` edges for JPN
in a FUTURE identity-verification-of-the-operator-representative check,
should one be added) — see the superproject ADR for exactly what was and
was not wired into `deps.edn`.

## Honesty (matches this fleet's convention)

`:country/recognizes-method` edges exist ONLY for JPN. All 187 other
countries get a structurally complete `:country/*` entity with
`:country/coverage-status :not-yet-researched` — never silently implying
"no requirements." `coverage-report` states this in the same style as
`marketentry.facts/coverage` / `vcfund.facts/coverage`.

## Consequences

(+) A real, queryable, dual-Datomic/DataScript regulatory-linkage graph
with one honestly-researched jurisdiction and 187 honestly-unresearched
ones, structurally ready for whichever gets researched next.
(+) `method-entities` cannot drift from `kotoba.ekyc/method-catalog`
(derived, not copied).
(−) Only JPN has real edges; the other 187 (of the real 188, not the
223 initially assumed) countries are placeholders.
(−) `schema-datomic` is unverified against a real Datomic peer (no
licensed instance in this workspace) — verified instead against the
empirically-confirmed-compatible DataScript derivation, and structurally
follows documented Datomic vocabulary.
(−) Six of the 188 real country repos (`KGZ` `LAO` `MMR` `TJK` `TKM`
`UZB`) are not yet pushed to GitHub; their `:country/repo-url` uses the
family's real, exceptionless naming convention and will resolve once
pushed.

## Related

- `kotoba.ekyc` ADR-0001 (this repo) — the method catalog this graph reuses.
- `orgs/etzhayyim/global-energy-datoms` — this workspace's prior art for
  the schema/tx-data/queries EDN shape and the JVM-`datascript.core`
  compatibility-proof pattern.
- `cloud-itonami-isic-6492`'s `credit.store` / `cloud-itonami-isic-6493`'s
  (planned) `factoring.store` — this fleet's `langchain.db`-backed
  Datomic-API-compatible `Store` protocol convention (attribute naming,
  EDN-string-encoded compound values), referenced for schema style even
  though this graph is a pure data library, not a governed actor's Store.
- Superproject ADR (`90-docs/adr/` in `com-junkawasaki/root`) for the
  `manifest/west.yml` pin advance and the `cloud-itonami-iso3166-jpn`
  wiring decision.
