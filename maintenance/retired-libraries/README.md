# Retired library repository histories

The dated manifests preserve repository content and review evidence before
GitHub retirement. They are snapshots, not a claim that an old GitHub URL
continues to resolve or that deletion has already happened. Actual operation
results are tracked in JUN-269 and the dated
[deletion receipt](2026-10-22/deletion-receipt.json). The 2026-10-22 operation
confirmed deletion of all 125 candidates and preservation of the 239 holds;
post-deletion import/CLI, portable tests and full bundle restoration passed.

The 2026-10-22 batch covers 125 public source repositories from `kotoba.async`,
`kotoba.log`, `kotoba.scheduler`, `kotoba.store` and `kotoba.string`. The other
239 source repositories remain archived because known consumers still pin
them, directly or transitively. No execution foundation is included.

Every bundle includes the original reachable commit history, local branches,
all current remote branches/tags, and closed PR tips. GitHub metadata includes
the eight closed PRs and their comments/reviews. There were no current WIP,
stashes, linked worktrees, open issues/PRs, releases or wiki contents in this
batch. Source imports, current defaults and reviewed branch adaptations remain
bound by `lib/*/imports.json`, `lib/repository-migrations.json` and branch/WIP
provenance. Squashed/rebased commits are accepted only with matching patch IDs
and byte-identical postimages for every changed path in default history.

Verify without contacting any retired repository:

```sh
node scripts/check-libraries.mjs
node scripts/check-retired-libraries.mjs
node scripts/check-retired-libraries.mjs --restore-workspace /absolute/github/workspaces/retirement-verification
```

To recover one repository, first verify its bundle digest against the manifest,
then use `git clone --mirror <bundle> <new-path.git>`. A worktree can be added at
any preserved branch or commit. The archive contains the original GitHub refs
under `refs/archive/jun269-20261022/heads/`, `tags/` and `pulls/`; original local
and remote-tracking refs are also retained. This does not restore a GitHub
repository's identity, issue URLs, permissions, stars or watchers.

Dotted imports and their declared legacy aliases resolve from the Kotoba
monorepo. They do not redirect arbitrary Git dependencies. The held 239
repositories remain available at their existing URLs.
