# cloud-itonami-iso3166 Integration

`cloud-itonami-iso3166-*` repositories publish independent-operator
public-sector market-entry & procurement-compliance blueprints keyed by
jurisdiction. `kotoba-iso3166` declares what technology capabilities are
required to run them.

Runtime flow:

```text
cloud-itonami-iso3166-{code}
        |
        v
kotoba.iso3166/execution-plan
        |
        v
kotoba.technology/stack
        |
        v
concrete repos and operator services
```

The ISO 3166 blueprint should not import a capability implementation
directly. It should request the capability contract from `kotoba-technology`.

## Maturity & readiness

`kotoba.iso3166/maturity-summary` and `execution-plan` expose per-country
maturity and UI/export readiness so an operator console can show them.

| Maturity tier | Meaning |
|---|---|
| `:implemented` | source actor exists (reference implementation) |
| `:blueprint` | blueprint repo published (`:repo` set) |
| `:spec` | registry entry only (blueprint repo pending) |

Current state (full 193/193 current-UN-member country coverage + 19/19
Japan agency-level coverage, ADR-2607040100 through ADR-2607040500 — Japan
agency blueprint coverage is COMPLETE, 19/19 — plus incremental country
promotion batches through ADR-2607042800; see the README's blueprint
table for the current full country list):

- Total entries: 227 (193 countries + 19 Japan agencies + 15 USA agencies)
- `:implemented` 16 · `:blueprint` 128 · `:spec` 83 · total 227
- Total entries: 227 (193 countries + 19 Japan agencies + 15 USA agencies)

`kotoba.iso3166/children` resolves the agency-level entries under a country
(currently non-empty only for `"JPN"`), mirroring the shared organism
substrate's `children(family, code)` contract (ADR-2606301900).

## Organization contacts (HQ / phone / head-role)

`kotoba.iso3166/contacts` and `get-contact` load
`resources/kotoba/iso3166/contacts.edn` — real HQ line/phone/hours and
**institutional** `:head-role` titles. Personal names of current
office-holders are intentionally absent. Agency registry entries also
carry flat `:hq-line-local` / `:hq-phone` / `:head-role` /
`:official-url`. Blueprint repos may ship `organization.edn`.

No `:robotics` requirement on any entry: this is a data/compliance service,
not a physical-domain business (same digital-service exemption class as
`cloud-itonami-6310` and `cloud-itonami-gtin-*`, ADR-2607011000 /
ADR-2607031800).

## Boundary with adjacent etzhayyim / cloud-itonami actors

This registry sits alongside FIVE other things in this workspace that also
touch "country" or "government" and must not be conflated:

- **`com-etzhayyim-ooyake`** (etzhayyim/root) -- a read-only, non-commercial
  civic-wayfinding MIRROR of government structure. Already carries one
  `:gov.unit` record per country (this registry's alpha-3/name source), but
  is constitutionally barred from claiming to BE the government or act as
  an official channel (G3). `kotoba-iso3166` / `cloud-itonami-iso3166-*` is
  commercial and never touches `ooyake`'s civic-map data model.
- **`matsurigoto`** (etzhayyim/root) -- sovereign e-government statecraft,
  either etzhayyim's own covenant self-governance or an ADOPTING
  NATION-STATE's own execution. Two principals, both "the government
  itself," constitutionally gated (no operator master-key, spec-derived
  only, authority-bearing). `cloud-itonami-iso3166-*` is a THIRD, separate
  principal: an independent operator the government CONTRACTS or that
  bids into that government's public procurement -- never the government.
- **`com-etzhayyim-toritsugi`** (etzhayyim/root) -- citizen-facing, member-
  consent-only, non-profit government-procedure concierge for an
  INDIVIDUAL's own benefit/procedure. `cloud-itonami-iso3166-*` never
  touches individual citizen procedures; its client is a business operator,
  not a citizen.
- **`legal-entity.etzhayyim.com`** -- read-only aggregated company-registry
  data across 190+ countries, no execution. `cloud-itonami-iso3166-*` is
  commercial and executes (gated) filings.
- **`cloud-itonami-M6910`** (cloud-itonami org) -- helps a client BECOME a
  legal entity in a jurisdiction (company formation/incorporation, ISIC
  6910); jurisdiction is internal per-country DATA
  (`formation.facts/catalog`), not a blueprint-per-country split.
  `cloud-itonami-iso3166-{code}` is the NEXT phase: an ALREADY-incorporated
  operator (e.g. a `cloud-itonami-cofog-04.5` fire-inspection business)
  navigating THAT country's public-procurement portal, local-content/
  licensing rules, and public-sector invoicing/tax mapping to actually win
  and service a government contract. Different regulatory domain (company
  law vs. public-procurement law), different client lifecycle stage.
- **`cloud-itonami-cofog-{code}`** (cloud-itonami org) -- a
  jurisdiction-AGNOSTIC operator template for ONE public function (fire
  inspection, waste collection, ...). `cloud-itonami-iso3166-{code}` is the
  orthogonal axis: jurisdiction-SPECIFIC market-entry mechanics that apply
  regardless of which COFOG function the operator performs. The two
  compose: an operator forks a COFOG-function blueprint AND an ISO3166
  jurisdiction blueprint to actually operate a licensed civic-tech business
  in a given country.

## Coordinator + leaf: `cloud-itonami-iso3166-jpn-{code}` (Japan only, ADR-2607040100)

`cloud-itonami-iso3166-jpn` remains the COUNTRY-level coordinator (general
Japan market-entry). `cloud-itonami-iso3166-jpn-{code}` repos are AGENCY-level
leaves for a specific ministry/agency/independent-commission's regulatory
domain within Japan -- narrower and deeper than the country-level blueprint,
not a replacement for it. An operator typically needs the country-level
blueprint (general market entry) plus zero or more agency-level blueprints
(only the agencies whose regulatory domain actually applies to that
operator's specific contract). This mirrors `com-etzhayyim-isco` /
`com-etzhayyim-cofog`'s coordinator + per-code-organism split
(ADR-2606301900), applied to the commercial-operator side instead of the
non-adjudicating organism-actor side.
