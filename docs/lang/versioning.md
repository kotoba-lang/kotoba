# Kotoba Language Profile Versioning

`kotoba-lang` uses two related version numbers:

- the source contract version in `resources/kotoba/lang/source_contract.edn`
- the launcher/package version published by the host repository

The profile version is the compatibility contract for source-processing tools.
The launcher/package version is the distribution version.

## Compatibility Rules

- Patch-compatible changes may add documentation, fixtures, or tests without
  changing accepted source behavior.
- Minor-compatible changes may add source forms or new positive conformance cases
  when existing valid source keeps the same meaning.
- Major/profile-version changes are required when an existing accepted source
  extension, reader target, reader branch order, namespace priority, or fixture
  expectation changes incompatibly.
- Removing a source extension or reader target is incompatible.
- Reordering reader fallback branches is incompatible.
- Reordering namespace extension priority is incompatible unless guarded by a new
  reader target or a new profile version.

## External Implementations

An implementation conforms to profile version 1 when it can consume
`resources/kotoba/lang/source_contract.edn`, classify the declared source
extensions, preserve explicit `.cljc` reader targets, and reject unsupported
source extensions. The executable compiler/runtime suite is owned by the CLJC
authority in `kotoba-lang/kotoba-lang`; this repository verifies that host
launchers pass the normalized source request into that authority.

Implementations may support a subset of targets only if they report unsupported
targets explicitly. Silent fallback to another target is non-conforming.

## Maturity Gate

M6 requires:

- constants and docs (`M0`)
- machine-readable profile (`M1`)
- positive fixtures (`M2`)
- negative fixtures (`M3`)
- manifest-driven runner (`M4`)
- external implementation suite contract (`M5`)
- this version/profile compatibility policy (`M6`)
