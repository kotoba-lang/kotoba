# Merge queue CI

The `main` merge queue runs the existing PR-tier native CI on each merge-group
candidate. The candidate includes the target branch and queued changes, so a
successful PR run alone does not replace the merge-group run.

The required checks cover the Amu selfhost and Kotoba request/controller jobs,
the browser target compile, and the ARM, x86 base, x86 authority, and macOS
broker/history shared-native lanes. The path-filtered native harness remains a
separate PR check. Main and scheduled runs retain their broader native tier.

When adding or renaming required jobs, update the repository ruleset and ensure
the corresponding workflow emits the same check for both `pull_request` and
`merge_group`. A workflow-level path filter on a required PR check can leave it
pending indefinitely. Do not make cached receipts stand in for native checks.
