# shidemori_registry_directory

Death-registration **directory wayfinding** cell for `shidemori` (死出守),
per [ADR-2605263800](../../../../90-docs/adr/2605263800-shidemori-memorial-cemetery-tier-b-actor-r0.md).

Routes a bereaved member to the **official** death-registration authority /
civil-registry office / burial-cremation-permit issuer for their jurisdiction,
querying the worldwide seed directory at
[`20-actors/shidemori/registry/registries.seed.json`](../../../../20-actors/shidemori/registry/registries.seed.json)
(130 registries / 31 jurisdictions at R0).

## Constitutional ceiling (immutable)

shidemori is death-record **wayfinding** only — it renders **no advice (UPL
boundary)** and makes **no eligibility/obligation determination**:

- `rendersAdvice` / `isEligibilityDetermination` are hard-wired `False` with no
  code path to flip them. The registry's own `procedure` text quotes the
  official process; it is not counsel.
- An unknown `recordKind` is structurally unroutable (the resolver raises).
- No ranking beyond the registry's own `confidence` then `title`; unknown
  jurisdiction → `[]` (no guessing). No surveillance, no PII persistence beyond
  the jurisdiction string.

## R0/R1 boundary

- **`registry_match.py`** — the **pure** directory-query core. Stdlib-only,
  deterministic, no network. **Landed + tested now** (R0). Importing/testing it
  does **not** activate the deployable cell.
- **`cell.py`** — the deployable Pregel graph. **Inert** (raises `RuntimeError`
  on import) until the Council attests the shidemori activation chain.

## Tests

```sh
cd 20-actors/kotoba-kotodama/cells/shidemori_registry_directory
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest test_registry_match.py -q
```
