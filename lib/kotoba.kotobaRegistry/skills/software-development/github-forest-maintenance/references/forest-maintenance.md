# GitHub forest maintenance

The CLI and the `github-forest` MCP server use the same implementation in
`scripts/forest-maintenance.mjs`. Node 22+, Git, west and authenticated `gh` are
needed; pin/registration operations also use kbb and the manifest's CLJK writers.
The implementation uses Node's built-in modules, without downloaded runtime
dependencies. MCP uses the official [newline-delimited JSON-RPC stdio transport](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports).

`com-junkawasaki/root` is a project, not the forest manager. Registration policy
belongs to `com-junkawasaki/west-manifest/manifest/repos.edn`. The generator writes
`manifest/west.yml`; Kagami maintains the fleet database, ledger and signed head.

## Public discovery

The [Kotoba Registry](https://github.com/kotoba-lang/kotoba-registry) publishes
this command's skill and MCP connection definition in Hermes Registry format.
Use its [index.json](https://raw.githubusercontent.com/kotoba-lang/kotoba-registry/main/index.json)
and [llms.txt](https://raw.githubusercontent.com/kotoba-lang/kotoba-registry/main/llms.txt)
for discovery, then read the selected entry from one pinned registry commit and
verify its folder checksum. The runtime remains in this repository; the MCP
definition invokes the installed `forest-maintenance mcp` command on PATH.
Catalog publication and client configuration are separate steps.

See [the ownership ADR](adr/0001-kotoba-registry-reference.md). Repository
registration and pins remain in this repository's `manifest/repos.edn` and
signed genpon; extension discovery is separate from Kotoba language package
admission and from runtime permissions.

## Install for Codex, Claude and Hermes bots

After these files are merged and the canonical manifest checkout is updated:

```sh
/Users/junkawasaki/github/workspaces/hermes-install/venv/bin/python /Users/junkawasaki/github/com-junkawasaki/west-manifest/scripts/install-forest-clients.py --out /Users/junkawasaki/github/workspaces/codex/forest-review/client-plan.json
/Users/junkawasaki/github/workspaces/hermes-install/venv/bin/python /Users/junkawasaki/github/com-junkawasaki/west-manifest/scripts/install-forest-clients.py --apply --out /Users/junkawasaki/github/workspaces/codex/forest-review/client-install.json
```

The installer uses native Codex/Claude registration commands and Hermes' atomic,
comment-preserving raw-config writer. It adds only this MCP entry and links the
canonical skill in every existing Hermes profile plus Codex/Claude. Different
existing entries/skills/commands are held. Complete credential-bearing config
backups remain in each application's backup directory, never in project output.
It installs `~/.local/bin/forest-maintenance`; the CLI can also be invoked by its
canonical `bin/forest-maintenance` path. Existing agent processes are not restarted;
new sessions load the registrations. Inspect native client connection state.

## Audit, plan, selected apply, verify

From an actual repo or a task workspace:

```sh
forest-maintenance workspace --kind scratch --agent codex --task forest-review
forest-maintenance audit --fetch --out /Users/junkawasaki/github/workspaces/codex/forest-review/audit.json
forest-maintenance plan --audit /Users/junkawasaki/github/workspaces/codex/forest-review/audit.json --out /Users/junkawasaki/github/workspaces/codex/forest-review/plan.json
forest-maintenance apply --plan /Users/junkawasaki/github/workspaces/codex/forest-review/plan.json --path cloud-itonami/tasuke --out /Users/junkawasaki/github/workspaces/codex/forest-review/apply.json
forest-maintenance verify --path cloud-itonami/tasuke --out /Users/junkawasaki/github/workspaces/codex/forest-review/verify.json
```

Omit `--fetch` for an offline inventory. Offline observations cannot authorize
sync/branch retirement/rehome. `--path` is repeatable for scoped audits and applies.
Without paths, audit discovers actual `.git` checkouts in org directories (depth
2), worktrees and separate workspaces (depth 5); it stops at a checkout, skips
symlink aliases, hidden/cache/build directories, and preserves invalid `.git`
entries as errors. Repositories outside that bounded discovery need explicit
paths or an independently reviewed relocation. It does not move application
settings, data, sessions or caches.

The audit checks every local branch, all stash SHAs, working/index/untracked
status, worktree use, shallow history, upstream GitHub identity/default branch,
and all open PRs. It fetches an audit ref, not the working branch. A failed fetch,
API request or shallow negative ancestry is unverified, not unlanded proof.
Untracked directories are held for content review. It does not semantically
review every novel code branch or contents inside arbitrary untracked directories.

Plan emits actions and explicit `held` reasons. Apply requires selected paths,
checks the plan digest, source audit and manifest hash, rechecks content/status,
HEAD/stashes/worktrees and process cwd, refreshes upstream/PR guards, and uses a
single exclusive maintenance lock. Plans expire after 24 hours. Audit refs may
refuse a rewritten default branch; do not force them to hide a divergence.

Sync accepts only forward, default-reachable pins and dirty file bytes/modes
already equal to the pin. Existing stashes, novel WIP, conflicts, datasets,
archived repositories, ignored collisions, submodule directories needing review,
shallow/unknown history and active cwd are held. It archives patches plus a
task-owned stash in a unique Git ref before a named `west update`. Only that exact
task stash can be dropped after clean HEAD/pin verification. Original stashes
remain untouched. A failed update leaves its archive/task stash available.

Retirement protects default/main/master/git-annex, checked-out branches, branches
with open PRs and commits from the past 24 hours. It saves the tip in an archive
ref, then uses native `git branch -d`; a Git refusal remains a hold. No remote
branch deletion, PR closing, novel-code merge or conflict resolution is automated.

Rehome moves only idle standalone repositories with a verified GitHub identity.
The owner location is `<org>/<repo>`; occupied owner locations cause a retained
checkout in `wt/legacy-<org>/<task>`. The old path becomes a compatibility link.
HEAD, status and stashes are verified afterward. Linked worktree rehome and
relative dependency coordinates require Git-native move plus explicit review;
the tool holds them rather than pretending metadata repair proves runtime parity.

Apply writes an atomic result journal after every action and after archival
before checkout. `apply.lock` contains its PID/time. Inspect the process and
journal before removing a stale lock. Interruption is not success: inventory
again, inspect archival refs/task stashes, and prepare a new plan.

## MCP and large fleets

Configure a stdio server named `github-forest`:

```json
{"command":"/opt/homebrew/bin/node","args":["/Users/junkawasaki/github/com-junkawasaki/west-manifest/scripts/forest-maintenance.mjs","mcp"]}
```

Tools: `forest_audit`, `forest_plan`, `forest_apply`, `forest_verify`,
`forest_workspace`, `forest_pin`, `forest_register`, `forest_start`,
`forest_job_status`. Input/output fields match the CLI; `paths` is an array and
`out` is an absolute path under `github/workspaces`. Set Hermes entries to
`lazy: true` to avoid starting a process in each idle bot profile.

Fleet-sized calls can exceed a client's request deadline. Use `forest_start`:

```json
{"operation":"audit","options":{"fetch":true,"out":"/Users/junkawasaki/github/workspaces/codex/forest-review/audit.json"}}
```

It immediately returns a persisted `job` path and PID. Poll `forest_job_status`
with `{"job":"<returned job path>"}`. The job runs independently of the client;
read the result only after `state: complete`. A failed/interrupted operation must
be reviewed and re-audited. Apply jobs still require the plan and explicit
selected paths. No periodic job is enabled automatically.

CLI equivalent: save operation arguments to a JSON file under a task workspace,
then run `forest-maintenance start --operation audit --options <file>` and
`forest-maintenance job_status --job <returned job path>`.

## Ownership extraction and registration

Ownership decisions, root source parity, meaningful tests and visibility are
review steps. Establish the owning org/repo before copying code. Keep shared
contracts/datasets root-owned where that is their actual boundary. When a new
owning repo is required, use `gh repo create <org>/<repo> --private`, seed it from
the reviewed tracked source, push its default branch and preserve provenance.
Use public visibility only when the source boundary and request authorize it.
The maintenance tool does not blanket-create public repositories or transfer
ownership based on folder names.

```sh
forest-maintenance workspace --kind worktree --agent codex --task west-register --repo com-junkawasaki/west-manifest --branch forest-register
forest-maintenance register --repo mithril-lang/mithril-fund --entry mithril-fund --worktree wt/codex/west-register --out /Users/junkawasaki/github/workspaces/codex/forest-review/registration.json
```

Registration requires a clean focused manifest branch and default-reachable
source HEAD. It preserves before files, changes only the registration surface,
runs named generation and `--check`, and verifies the produced entry/SHA. Commit,
review/merge and genpon closeout remain explicit work. The evidence file is a
backup, not the command return summary. Entry names must follow the generator's
basename/duplicate policy. A wrong name fails with evidence and edits preserved.

If the canonical owner checkout is diverged or occupied, create a separate west
workspace with `workspace --kind west --agent codex --task registration-check`,
restore the owning repo at its upstream default there, then pass
`--workspace workspaces/west/registration-check`. Do not switch the occupied
canonical owner. `WEST_WORKSPACE_ROOT` works only with an existing `.west/config`.

## Pins and genpon closeout

`forest-maintenance pin --entry tasuke --sha HEAD` is a server-side dry-run.
Add `--apply` only within the authorized pin-change scope. The existing CLJK
writer verifies upstream default reachability and forward movement, with a
GitHub blob-SHA precondition. It does not change local checkouts. For reviewed
bulk advances use `scripts/west-pin-put-bulk.cljk` with an explicit TSV and its
dry-run; inspect every dropped/unresolved row rather than treating exit 0 as
full coverage.

Fetch current manifest main into a focused worktree, verify old fleet-db pins
advance to the current west pins, then invoke Kagami's `reconcile`, `head`,
`head --verify` and `check` commands described in the repository README. Keep
signing material in Kagi; never print/store it in a report. Merge records, fetch
fresh main and repeat projection/signature checks. Shared root WIP and divergent
canonical owners may remain behind their registered pin with an explicit hold.

## Recovery and validation

For an `archive_ref` reported on a sync action, inspect `git show <ref>` and use
`git stash apply <ref>` in a fresh task worktree. The archival stash retains staged
and untracked parents; add `--index` only if reinstating the original index is
appropriate there. For a branch archive, create a new branch/worktree from the
reported ref. Never blind-pop into an occupied checkout.

```sh
FOREST_TEST_TMPDIR=/Users/junkawasaki/github/workspaces/codex/forest-tool-tests node --test scripts/forest-maintenance.test.mjs
TMPDIR=/Users/junkawasaki/github/workspaces/codex/forest-tool-tests kbb --backend sci --classpath .:scripts:scripts/nbb_compat scripts/gen-west-manifest-test.cljk
```

The isolated fixtures test archive recovery, meaningful state/refusal conditions,
safe branch retirement, rehome, MCP stdio calls and persisted background jobs.
Final reports distinguish examined paths from semantic review, pins from local
sync, source transfer from deployment, and preserves/holds from completed work.
