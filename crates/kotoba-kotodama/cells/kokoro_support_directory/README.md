# kokoro_support_directory

Mental-health support-line **directory wayfinding** cell for `kokoro` (心),
per [ADR-2605263700](../../../../90-docs/adr/2605263700-kokoro-mental-health-tier-b-actor-r0.md).

Routes a consenting member to the **official** crisis hotline / emergency number /
support line for their jurisdiction, querying the worldwide seed directory at
[`20-actors/kokoro/registry/support-lines.seed.json`](../../../../20-actors/kokoro/registry/support-lines.seed.json)
(127 lines / 31 jurisdictions at R0).

## Constitutional ceiling (immutable)

kokoro is community/spiritual/relational mental-health **support routing** —
**NOT clinical psychiatry, NOT licensed psychology, NOT diagnosis or treatment**
(Charter §1.13 Wellbecoming). This cell is a wayfinding directory only:

- `rendersClinicalOpinion` / `isDiagnosis` / `isTreatment` are hard-wired
  `False` with no code path to flip them.
- An unknown `supportKind` is structurally unroutable (the resolver raises
  rather than routing an unknown service).
- No commercial mental-health AI (Murakumo-only), no surveillance, no
  ranking beyond the registry's own `confidence` then `title`, and unknown
  jurisdiction → `[]` (no guessing). Emergency-triage ordering is a caller/cell
  concern, never invented by the pure query.

## R0/R1 boundary

- **`support_match.py`** — the **pure** directory-query core. Stdlib-only,
  deterministic, no network. **Landed + tested now** (R0). Importing/testing it
  does **not** activate the deployable cell.
- **`cell.py`** — the deployable Pregel graph. **Inert** (raises `RuntimeError`
  on import) until the Council attests the kokoro activation chain.

## Tests

```sh
cd 20-actors/kotoba-kotodama/cells/kokoro_support_directory
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest test_support_match.py -q
```
