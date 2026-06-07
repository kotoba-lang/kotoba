# kataribe_channel_directory

Publication-channel **directory wayfinding** cell for `kataribe` (語部),
per [ADR-2605263600](../../../../90-docs/adr/2605263600-kataribe-press-publishing-translation-tier-b-actor-r0.md).

Routes a member to the **official** public publication channel for their
jurisdiction — official gazettes, legal publications, open-access archives,
press-freedom organisations, translation resources — querying the worldwide seed
directory at
[`20-actors/kataribe/registry/channels.seed.json`](../../../../20-actors/kataribe/registry/channels.seed.json)
(151 channels / 33 jurisdictions at R0). Distinct from kataribe's **own**
publishing cells (chronicle / doctrine commentary / translation / whistleblower).

## Constitutional ceiling (immutable)

This cell is wayfinding to **external/official** channels only:

- `isOriginalPublication` / `assertsContentAccuracy` are hard-wired `False`
  with no code path to flip them — kataribe is not the publisher here and
  vouches for no channel's content accuracy/authenticity.
- No editorial or eschatological framing (G4 + Charter §1.15); no ranking
  beyond the registry's own `confidence` then `title`.
- An unknown `channelKind` is structurally unroutable (the resolver raises);
  unknown jurisdiction → `[]` (no guessing). No surveillance, no PII
  persistence beyond the jurisdiction string.

## R0/R1 boundary

- **`channel_match.py`** — the **pure** directory-query core. Stdlib-only,
  deterministic, no network. **Landed + tested now** (R0). Importing/testing it
  does **not** activate the deployable cell.
- **`cell.py`** — the deployable Pregel graph. **Inert** (raises `RuntimeError`
  on import) until the Council attests the kataribe activation chain.

## Tests

```sh
cd 20-actors/kotoba-kotodama/cells/kataribe_channel_directory
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest test_channel_match.py -q
```
