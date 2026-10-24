# crypto source co-location

`kotoba-lang/crypto` remains the owner of its existing protocol, transport,
capability or crypto boundary. Its same-family definition repositories now live
in this repository's source tree under their unchanged namespaces. Definition
identity and release/admission authority are separate from Git placement.
No implementation forms or protocol identities have been changed by this move.

`family-imports.json` records the original owner commit/tree/source digests and
all imported repository commits/trees/files/licenses/modes. Original project
metadata is retained under `maintenance/family-imports/`. Only Git dependencies
whose definitions were imported are removed. All other runtime dependency
values and test aliases remain unchanged; the SCI manifest now declares the
same runtime dependencies as `deps.edn`.

Run `node scripts/check-family-imports.mjs` to verify exact source and reviewed
configuration. This is a provenance check, not signature admission or runtime
qualification. Existing tests remain the behavioral gates. GitHub archive is
recorded separately after main and branch/WIP verification; importing a default
snapshot does not retire novel work. Consumer pins and signed locks are not
rewritten. No service, daemon or runtime state is changed by co-location.

The organization-wide consolidation goal remains open in
[JUN-267](https://linear.app/kotobalabs/issue/JUN-267).

The Node test fixture explicitly injects a digest from node:crypto. Production
defaults keep refusing without host injection; the refusal has its own test.
The fixture uses the [documented Node hash API](https://nodejs.org/api/crypto.html#cryptocreatehashalgorithm-options).
