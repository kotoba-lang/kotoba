# danjo_source_directory

Public-accountability fiscal-source **directory wayfinding** cell for `danjo`
(弾正), per [ADR-2605301600](../../../../90-docs/adr/2605301600-danjo-public-accountability-oversight-tier-b-actor-r0.md).

Routes a member to the **official** public-accountability data source for their
jurisdiction — audit institutions, budget portals, legislature records,
procurement systems, open-spending datasets, international aggregators —
querying the worldwide seed directory at
[`20-actors/danjo/registry/sources.seed.json`](../../../../20-actors/danjo/registry/sources.seed.json)
(166 sources / 34 jurisdictions at R0).

## Constitutional ceiling (immutable)

danjo is the **"censor's eye, no sword"** — observational, non-adjudicating:

- `isAdjudication` / `assertsWrongdoing` are hard-wired `False` with no code
  path to flip them. danjo finds + observes; it never rules, sanctions, or
  imputes wrongdoing. Surfacing a source is wayfinding to the official dataset.
- Observational, public-source-only — no surveillance, no private-target
  dossier. No ranking beyond the registry's own `confidence` then `title`;
  unknown jurisdiction → `[]` (no guessing).
- An unknown `sourceKind` is structurally unroutable (the resolver raises).

## R0/R1 boundary

- **`source_match.py`** — the **pure** directory-query core. Stdlib-only,
  deterministic, no network. **Landed + tested now** (R0). Importing/testing it
  does **not** activate the deployable cell.
- **`cell.py`** — the deployable Pregel graph. **Inert** (raises `RuntimeError`
  on import) until the Council attests the danjo activation chain.

## Tests

```sh
cd 20-actors/kotoba-kotodama/cells/danjo_source_directory
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest test_source_match.py -q
```
