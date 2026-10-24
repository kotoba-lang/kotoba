# Council Proposal — release ooyake `reconcile` LIVE mode (G4) for authoritative ingest

**Actor**: ooyake 公 · **ADR**: 2606021600 · **Gate**: §4 G4 (public-data-only) + roadmap R1 · **Status**: PROPOSED (awaiting Council)

> This is a governance request. It is NOT self-executing. ooyake's `reconcile`
> cell LIVE mode (`mode="live"`) raises until a Council Lv6+ attestation + operator
> enablement are present. The agent that authored ooyake has **deliberately not
> enabled it** — releasing a constitutional gate is Council's authority, not the
> operator's or the agent's.

## What is being requested

Authorize the ooyake `reconcile` cell to **fetch public official government
registries over the network** and, on agreement, promote atlas units from
`:sourcing :representative` / `:verification-status :unverified-seed` to
`:authoritative` / `:maintainer-verified`. Today the cell only runs `mode="bundled"`
(offline, against `registry/authority-reference.edn`).

## Why (the axis it moves)

The gov-atlas currently holds **772 units across 178 jurisdictions**, but **0 are
`:authoritative`** — every row is `:representative` (honest R0, G5). The authority
axis cannot move without verification against the official source, which requires a
live fetch. This proposal unblocks that single axis under controls.

## Scope of the LIVE fetch (sources, all public + official)

- 総務省 / J-LIS 全国地方公共団体コード (JP prefectures + 1,718 municipalities)
- ISO 3166-1/3166-2 (country + subdivision codes)
- Wikidata QID reconciliation (`:gov.unit/wikidata`)
- GeoNames admin hierarchy (public dump)
- per-jurisdiction official open-data portals (e-Gov, data.gov, GOV.UK, …)

Promotion rule (unchanged from bundled mode, G5): a unit is promoted ONLY when its
`:gov.unit/wikidata` AND `:gov.unit/official-url` (or official code) **agree** with
the fetched authoritative record; disagreement keeps it unverified and is reported.

## Constitutional controls (must hold for the attestation to stand)

| Gate | Control |
|---|---|
| G3 observational mirror | fetch is READ-ONLY metadata; never acts on a gov's behalf; atlas DIDs stay mirrors |
| G4 public-data-only | only public official sources; honor robots.txt / ToS / rate-limits; **no behind-auth**; no circumvention |
| G5 non-fabrication | promote only on source agreement; `:representative` never counted as coverage; provenance + last-verified on every promoted datom |
| G6 no personal data | org + public role-contact only; never an official's private data |
| G7 Murakumo-only | any inference in reconcile stays on the Murakumo fleet |
| G9 read-side only | reconcile emits a report + datom upserts to the atlas; never files/mutates a gov record |
| G10 never a target-list | civic wayfinding only; no SPOF/attack-surface derivation |
| rate / cadence | bounded concurrency + per-host rate-limit; incremental, resumable; full-world ingest staged, not a burst |

## Required attestation

- **Council Lv6+ ≥3 multisig** attestation referencing this proposal + ADR-2606021600.
- **Operator enablement flag** (`OOYAKE_RECONCILE_LIVE=1` + the attestation CID) — both
  must be present; either alone keeps `mode="live"` raising.
- Re-attestation on any change to the source list or the promotion rule.

## What lands on approval

- `cells/reconcile/cell.py` `mode="live"` implementation activates (fetch + verify +
  promote), gated on the attestation CID being present and valid.
- A staged run promotes the official-coded tiers first (47 JP prefectures, JP
  municipalities by 全国地方公共団体コード, ISO-coded countries) to `:authoritative`,
  then expands jurisdiction-by-jurisdiction.

## What does NOT change

- `mode="bundled"` stays the default and stays non-gated.
- No new vendor / no commercial GPU / no server-held key (ADR-2605215000 / 2605231525).
- The atlas stays read-side; toritsugi/danjo boundaries unchanged.

---

*Filed by the ooyake author-agent as a governance artifact. Council ratification is
pending; the Bootstrap Council Seats 2–5 RFP is open through 2026-06-19 (COUNCIL.md).*
