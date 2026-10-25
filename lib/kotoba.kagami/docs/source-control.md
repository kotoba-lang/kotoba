# Agent source records and grouped publication

ADR: `com-junkawasaki/root/90-docs/adr/2610151430-agent-source-changes-snapshots-and-group-publication.kotoba`.

The entrypoint is `kbb --backend sci --classpath src bin/source.cljk COMMAND`.
The existing `bin/kagami.cljk` commands retain their contracts. This is the
existing operational CLJK/kbb runtime, not a native/Q9 migration or a claim
that a distributed source service is deployed.

## Records

`change` creates a stable ChangeID descriptor; `revision` binds that Change
to a base Snapshot and exact old/new SHA-1 commits; `candidate` applies only
those changes to produce a candidate Snapshot. `verify` validates the entire
record, supported version, canonical identity and closed shape.

Each envelope has `:source/version`, `:source/kind`, `:source/value` and
`:source/cid`. Its CIDv1 raw/sha2-256 addresses the versioned canonical payload
returned by `source/canonical-str` over the first three fields. The envelope's
printed EDN bytes include the CID and are a transport representation, not the
raw block named by that CID. Map iteration order does not affect identity;
vector order is part of the v1 contract. The existing io-multiformats and
kotoba.bytes dependencies own hashing/encoding. This does not equate native
semantic commit CIDs with byte-exact Git object CIDs owned by bonsai.

`snapshot --manifest REPO --at FULL_COMMIT --lock LOCK.edn --out SNAPSHOT.edn`
reads registry and west from that Git commit, not the working files. The lock
is an explicit owner-resolver export:

```edn
{:lock/version 1
 :lock/resolver "<CID identifying the owning resolver contract>"
 :lock/complete? true
 :lock/dependencies {"org/app" ["org/lib"] "org/lib" []}
 :lock/revisions {"org/app" "<exact full commit>" "org/lib" "<exact full commit>"}}
```

The graph must name exactly the captured repositories, including leaf nodes;
every dependency must resolve. This validates/traverses an owner-supplied lock,
not a second package resolver or an independent proof that an arbitrary graph
is complete. Publication requires these exact lock bytes committed at
`manifest/source-lock.edn`. Forge paths remain explicit v1 repository IDs;
RID adoption needs a verified mapping, not fabricated identities.
The revisions in the export must exactly equal the captured source commits.
Candidate creation requires a fresh export for the candidate inputs; a lock
covering only the base commits is refused. Inputs contain exactly one EDN
value, so extra trailing forms cannot be hidden after a valid record.

### Operational source checkout export

`bin/source-export.cljk` exports a limited channel from committed West pins:

```bash
kbb --backend sci --classpath src bin/source-export.cljk \
  --manifest /absolute/west-manifest --at FULL_COMMIT \
  --root /Users/junkawasaki/github --roots kotoba-lang/kagami \
  --out /Users/junkawasaki/github/workspaces/codex/task/export
```

The versioned `:cljk-operational` profile traverses top-level `:deps` in
committed `deps.edn` and `nbb.edn`; it excludes aliases. It records descriptor
CIDs and exact declared Git/Maven artifacts in `export.edn`. Source checkout
edges resolve against the captured West version set. Existing package tools
continue selecting package artifacts; a checkout pin is not a claim that a
package resolver selected that version. Unknown dependency forms, abbreviated
Git OIDs, missing descriptors, unregistered repositories and unsupported
materializations refuse the export. GitHub SSH/HTTPS transports may name the
same owner; another host or repository is not interchangeable.

Outputs are a scoped `west.yml`, registry, complete source lock and replayable
report. `--pins MAP.edn` projects explicit full-OID overrides for a candidate;
publication independently checks upstream reachability and forward ancestry.
Use the same complete repository set in base and candidate exports. This
profile does not cover test aliases, native compiler inputs or a whole-fleet
package resolution. Channel enrollment is a separately reviewed authority step.

```text
change --id TASK --actor ACTOR --title PURPOSE --repos org/app,org/lib --out CHANGE
revision --change CHANGE --base BASE --changes CHANGES.edn --actor ACTOR --out REVISION
candidate --base BASE --revision REVISION --lock CANDIDATE_LOCK --out CANDIDATE
verify --record CANDIDATE
```

CHANGES is a vector of maps with `:repo/id`, `:revision/old` and
`:revision/new`; each Git OID is `{:algorithm :sha1 :hex <full 40-hex>}`.
An optional `--parent` names a verified Revision file for the same Change.
Record creation grants no edit, merge, execution or publication permission.
Output objects are create-only; a different existing file is refused.

## Fixed workspaces

```text
workspace --snapshot SNAPSHOT --roots org/app --root /Users/junkawasaki/github
          --agent codex --task TASK --apply true
```

Omit `--apply true` to plan without mutation. The closure comes from that
Snapshot's graph. The forest factory creates
`github/workspaces/west/TASK/.west/config`; selected repositories are detached
Git worktrees reusing canonical owner object stores. The generated manifest
points only at the captured commits. Owner HEAD, WIP and stashes are preserved.
An owner must be a real, non-shallow checkout with a matching remote. Missing
objects are fetched by exact OID without depth or working-branch updates.

Submodule and DataLad materialization currently refuse before creating a task.
This v1 uses materialized detached worktrees, not a virtual filesystem or a
filesystem enforcement of read-only dependency files. The creation receipt
attests the initial exact HEADs; subsequent edits require a new Revision.
A verified draft or candidate Snapshot can also create a workspace; its receipt
does not prove that the Snapshot has been authorized for publication.

An incomplete operation retains `.source-workspace.edn` and created worktrees.
`--resume true --apply true` requires the same Snapshot and plan and rechecks
every existing worktree; dirty or mismatched paths are held. It never removes
WIP or guesses how to repair broken Git metadata. A complete operation returns
its Snapshot-bound receipt and supports an unchanged retry.
Materialization/resume holds an exclusive task lock. A crash lock is retained
for explicit process/journal inspection; its age never authorizes breaking it.
Resume also checks the factory's recorded initial config or the exact generated
config and refuses local `.west/config` edits. Control directories/files cannot
be symlinks; redirected projection paths are refused before writing through them.

## Group publication policy and proofs

This writer is opt-in. The current accepted manifest commit must already hold
`manifest/source-policy.edn`, `manifest/source-lock.edn`, a matching genpon/west
projection and a valid signed fleet head. No policy/key/default-route activation
is installed by the implementation.
The v1 base head must name `fleet-db`, have a positive safe integer sequence
and use the existing non-expiring record format (`:pin/valid-until nil`).

Policy v1 has the following closed fields:

| Field | Meaning |
| --- | --- |
| `:policy/version`, `:policy/channel`, `:policy/ref` | Version 1, channel name, accepted `refs/heads/...` |
| `:policy/required` | Nonempty vector of required check names |
| `:policy/publishers`, `:policy/runners` | Nonempty vectors of trusted Ed25519 DIDs |
| `:policy/reviewers` | Repository ID to allowed reviewer DIDs |
| `:policy/inputs` | `:inputs/toolchain`, `:inputs/environment`, `:inputs/checks` CIDs and `:inputs/target` |
| `:policy/sources` | Authority map (may be empty); an absent repo entry uses GitHub's default branch |
| `:policy/delta-path` | Optional committed delta-log path for existing head hashing |

A source entry is `{:provider :github}` or
`{:provider :git :url <approved URL> :ref "refs/heads/main"}`. The Git provider
fetches the approved remote's full accepted history into isolated scratch;
it never treats a dirty canonical checkout as source-authority evidence.
File URLs are explicit policy-bound local authorities used by integration
fixtures. Public GitHub checks reuse west-pin-put's default-reachability and
forward-ancestry predicates. Unknown results reject the entire group.

`evidence --manifest REPO --expected COMMIT --snapshot CANDIDATE
--revision REVISION --checks RESULTS.edn (--key PEM|--kagi NAME) --out EVIDENCE`
uses the existing kagami.ci signing/verification contract. RESULTS contains
actual runner results (`{:name "check" :outcome :pass|:fail|:skip}`). The trusted
runner attests those results; this command itself does not execute checks.
Required names, exact inputs, check-plan and policy come from committed policy.

`review --manifest REPO --expected COMMIT --snapshot CANDIDATE
--revision REVISION --repos org/app,org/lib (--key PEM|--kagi NAME) --out REVIEW`
signs one owner's approval. Group completeness requires authorized coverage
for every changed repository. REVIEW input to prepare can be one review or
a vector aggregating independently signed reviews. Keys come from explicit
files or Kagi and never enter records or output. Key paths are not private keys.
The direct signing CLI accepts `--kagi-command /absolute/bin/kagi` with
`--kagi NAME --root FOREST` for an explicitly selected clean provider checkout.
The generic forest source tool does not accept this option or signing commands.

## Prepare, inspect, publish

```text
publish-prepare --manifest REPO --expected COMMIT --base BASE
  --snapshot CANDIDATE --revision REVISION --lock CANDIDATE_LOCK
  --evidence EVIDENCE --reviews REVIEWS
  (--key PEM|--kagi NAME) --root FOREST --out PREPARED.edn

publish-apply --manifest REPO --prepared PREPARED.edn --root FOREST
  --out RECEIPT.edn
```

Prepare checks committed policy, exact base, source authorities, CI and owner
reviews. It generates west, genpon, append-only signed pin events and the signed
head and candidate resolver lock together with Snapshot/Revision/proof records in one Git commit. A local
`refs/source/prepared/<publication-CID>` preserves object custody. It leaves
the accepted remote ref and the occupied working checkout unchanged. Inspect
the prepared commit with `git show` and send it through normal review/checks.
After the first publication, use the accepted commit's
`manifest/source-snapshot.edn` as BASE. Recapturing the same pins with a new
manifest basis creates a different Snapshot and cannot replace that chain head.

Apply treats the prepared file as untrusted: it verifies signatures, subjects,
parent, file allowlist/digests, complete generated state and source authorities
again. It uses one normal, non-forced push from the expected parent. Existing
branch protection can reject that push; the writer never bypasses checks.
Concurrent ref changes refuse without partial pin writes. A lost acknowledgement
is recovered by remote readback. Reapplying the same currently accepted commit
is idempotent. A published commit followed by a failed local receipt write is
reported explicitly as published, not as an unapplied operation.
Publication signatures also bind the selected remote URL. Apply refuses a
prepared-file or remote-config redirect and pushes to and reads back from that
exact URL. A separate `pushurl` cannot route the transaction to another server;
tag following and recursive submodule pushes are disabled for this one-ref update.

The transaction makes the published version set atomic. Source-repo merges
can still be partial; consumers keep the old Snapshot until the entire group
qualifies. v1 does not silently upgrade policies, epochs or authority keys;
such migrations need an explicit owner-reviewed transition.
All writers admitted to an activated channel must maintain the Snapshot/lock
contract. A legacy pin write that leaves those records stale is held as drift,
not silently imported into a claimed verified Snapshot. Enrolling that writer
or changing channel authority is a separate activation decision.

## Verification

```sh
kbb --backend sci --classpath src:test run-tests.cljk
SOURCE_TEST_TMPDIR=/absolute/github/workspaces/codex/source-tests \
SOURCE_FOREST_COMMAND=/absolute/github/com-junkawasaki/west-manifest/bin/forest-maintenance \
kbb --backend sci --classpath src:test run-source-tests.cljk
```

The source suite uses real local Git repositories/remotes and generated fixture
keys. It covers exact workspaces/WIP, occupied paths, interruption/resume,
two-repo publication, signed-chain continuation, missing reviews, unmerged
sources, stale parents, concurrent updates and proof/file substitution. These
are local fixture results; they do not establish a deployed distributed VCS,
qualified native runtime, production signer activation or performance gains.
