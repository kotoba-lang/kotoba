# kazaori_agency_directory

Civilian disaster-agency **directory wayfinding** cell for `kazaori` (風折),
per [ADR-2605263200](../../../../90-docs/adr/2605263200-kazaori-disaster-response-tier-b-actor-r0.md).

Routes a consenting member to the **official public civilian** disaster-management
agency / early-warning system / public-alert channel for their jurisdiction,
querying the worldwide seed directory at
[`20-actors/kazaori/registry/agencies.seed.json`](../../../../20-actors/kazaori/registry/agencies.seed.json)
(139 agencies / 35 jurisdictions at R0).

## Constitutional ceiling (immutable)

kazaori **issues no alerts of its own, commands no response, and is NOT an
official emergency service** (it is not 119 / 110 / 911 / a municipal EOC).
This cell is a wayfinding directory only:

- `issuesAlerts` / `commandsResponse` / `isOfficialEmergencyService` are
  hard-wired `False` with no code path to flip them.
- **Civilian-only (G5)** — a non-civilian / armed-force `agencyKind` is
  structurally unroutable (the resolver raises rather than guessing).
- No surveillance (G6), no commercial disaster-AI / Murakumo-only (G7),
  community-scale (G3), no nearest-neighbour guessing (unknown jurisdiction → `[]`).

## R0/R1 boundary

- **`agency_match.py`** — the **pure** directory-query core. Stdlib-only,
  deterministic, no network. **Landed + tested now** (R0). Importing/testing it
  does **not** activate the deployable cell.
- **`cell.py`** — the deployable Pregel graph. **Inert** (raises `RuntimeError`
  on import) until the Council attests the kazaori activation chain.

## Tests

This machine auto-loads an entrypoint pytest plugin that pulls a broken
`pydantic`; disable plugin autoload to run the pure-core suite:

```sh
cd 20-actors/kotoba-kotodama/cells/kazaori_agency_directory
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest test_agency_match.py -q
```
