# Preserved text profile inputs

This directory retains the imported `kotoba-lang/text` profile sources for
provenance. Their maintained source homes are now at
[`hermes/profiles/`](../../../hermes/profiles/) in `kotoba-lang/kotoba`.
The canonical root agent registry resolves that repository's ordinary
`hermes/profiles/<profile>/` layout.

`lib/profile-homes.json` binds the complete copied trees byte-for-byte.
The move preserves the profile bodies, configuration, identities, cron
expressions and helper scripts, including dirty-worktree checkout refusals.
Library import does not load or activate profiles. Host materialization,
scheduler operations and runtime infrastructure remain separate operations.
