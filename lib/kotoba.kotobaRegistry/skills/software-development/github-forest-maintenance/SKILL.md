---
name: github-forest-maintenance
description: Audit and safely organize local repositories, worktrees, WIP, stashes and integrated branches across the github org/repo forest; reconcile the independently owned west manifest through CLI or MCP. Use for scattered agent workspaces and fleet checkout cleanup.
metadata: {"hermes":{"version":"1.0.0","author":"com-junkawasaki","source":"https://github.com/com-junkawasaki/west-manifest/tree/e481916ad720e10af8526774d668a6dae0cae488","compatibility":{"hermes":"0.21.5","desktop":"0.7.14"}}}
---

Published skill and MCP definitions are discovered through [Kotoba Registry](https://github.com/kotoba-lang/kotoba-registry) and its [catalog](https://raw.githubusercontent.com/kotoba-lang/kotoba-registry/main/index.json). Read the [registry agent contract](https://raw.githubusercontent.com/kotoba-lang/kotoba-registry/main/llms-full.txt) when installing or updating a client. Verify a selected entry's checksum from one pinned registry commit; discovery grants no permissions. This repository remains the command and west-manifest authority.

Use `forest-maintenance` on PATH (provided by `github/com-junkawasaki/west-manifest/bin/forest-maintenance`), or MCP `github-forest` tools `forest_audit`, `forest_plan`, `forest_apply`, `forest_verify`, `forest_workspace`, `forest_pin`, `forest_register`, `forest_start`, `forest_job_status`. Use persisted jobs for fleet-sized operations that exceed client deadlines. CLI and MCP share the same implementation. Read [the command and recovery reference](references/forest-maintenance.md) for the selected operation.

Repositories belong at `github/<org>/<repo>`, task worktrees at `github/wt/<agent>/<task>`, scratch at `github/workspaces/<agent>/<task>`. Use `forest_workspace` for new tasks. Separate west workspaces belong at `github/workspaces/west/<task>` with their own `.west/config`. Keep agent credentials, settings, databases, sessions and caches in application directories.

`com-junkawasaki/root` is one repository. Registration/pin authority is `com-junkawasaki/west-manifest/manifest/repos.edn` and its generated `west.yml`. Do not invoke obsolete root registration writers or broad shared west updates.

For cleanup, audit with fetch enabled and save the JSON under a task workspace. Produce a plan, inspect its actions and holds, then apply only the explicitly selected repository paths within the user's authorized scope. Recheck results with verify. An audit of Git metadata/content does not constitute code review, successful tests or merged/deployed behavior.

The command refuses shallow/unknown ancestry, existing stashes, active cwd, novel WIP, ignored collisions and stale state for synchronization. Preserve broken worktrees with missing metadata. Integrated idle local branches can be archived and retired; this grants no authorization to delete unrelated remote branches, close PRs, discard stashes or merge unreviewed work. Untracked directories require content review, not an assumption that they are generated. Re-run audit after resolving a hold; never bypass the guard to achieve a clean count.

For a root-staged component, establish its actual owning org/repo from current remote metadata and architecture, distinguish shared root data/contracts from independent implementation, transfer tracked files with provenance and check source parity plus relevant tests. A generic classifier cannot decide ownership or merge novel code. Create an owning GitHub repo only within the requested scope, keep source visibility or use private when undecided, seed/push its default branch, and register it with `forest_register` on a focused manifest branch. A diverged owner checkout must remain intact: validate registration in a separate west workspace instead.

Pin advances use the server-side writer (`forest_pin` defaults to dry-run), never local wholesale regeneration. After pin/registration changes, use Kagami reconcile and signed-head/projection verification; commit and merge the focused manifest changes, then update only named safe checkouts. Record unresolved signatures, reachability, CI and working checkout holds separately.

Report counts, authoritative merged commits, physical moves, local sync, archived refs, remaining WIP/branches and exact holds separately. Link the machine reports. To recover an archived WIP snapshot, apply its reported ref in a fresh correctly placed worktree; never blindly pop a stash into an occupied checkout.
