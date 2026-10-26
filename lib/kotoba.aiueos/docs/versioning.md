# aiueos Compatibility Policy

`aiueos` is pre-1.0 (Phase-0, per `CHANGELOG.md`). Its compatibility surface
is the `:aiueos/*` EDN data contract — manifests, policy/grants, the
`aiueos/component` Wasm Component Model boundary, and the CLI command
contract — not a package/library semver on its own, since the surface is
data (EDN) consumed by multiple host adapters (`kototama.tender`,
browser-native `actor-host.js`), not a single language's API.

## Compatibility Rules

- **Patch-compatible**: documentation, examples, internal implementation
  changes to `aiueos.broker`/`aiueos.execute`/`aiueos.launcher` that don't
  change accepted `:aiueos/*` manifest/policy shapes or the
  `resources/aiueos/*.edn` contract tables, and new tests that don't change
  an existing validator's/reasoner's behavior.
- **Minor-compatible**: adding a new optional `:aiueos/*` manifest key with a
  backward-compatible default, a new deployment surface/provider in
  `aiueos.surface`, a new CLI command/option in `resources/aiueos/cli.edn`,
  or a new capability kind — as long as every existing manifest/policy file
  that validated before still validates identically.
- **Breaking (major)**: changing an existing `:aiueos/*` key's required
  shape or default, changing `resources/aiueos/component_boundary.edn`'s
  import/export contract, changing `aiueos.broker/verify-one`'s grant/deny
  outcome for a manifest that previously validated, or removing a CLI
  command/option.
- **The contract data is the compatibility surface, not the CLJC code.**
  `src/aiueos/*.cljc`'s internal representation may change freely (new
  helper functions, refactored internals) as long as
  `test/aiueos/*_test.cljc` — the executable spec every consumer must keep
  passing — still passes unchanged, and the `resources/aiueos/*.edn`
  contract tables are unchanged or only extended per the rules above.

## External Implementations / Consumers

A host adapter conforms when it consumes `aiueos.broker/verify-one` (or
`aiueos.cli/command-result`) results without special-casing beyond what
`:aiueos/run-plan`/`:aiueos/run-receipt` document, and never bypasses a
`:denied` verdict. Current consumers: `kotoba-lang/kototama`'s
`kototama.aiueos-adapter` (JVM, in-process via `aiueos.cli`) and
`kotoba-lang/kototama`'s browser-native `actor-host.js` (via the `kbb -M:decide`
subprocess bridge, `aiueos.decide`). See `docs/coverage.edn` for maturity
evidence per stage.
