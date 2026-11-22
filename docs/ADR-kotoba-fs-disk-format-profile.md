# ADR — kotoba fs / disk format: hosted profile over Awai FS

- **Status**: Draft (spec text only; nothing here is implemented, measured, or qualified)
- **Date**: 2026-11-22
- **Scope**: AWAI + KOTOBA only. GFTD / MITHRIL are out of scope. JUN is referenced, not redefined.
- **Parent design**: [AWAI-161](https://linear.app/kotobalabs/issue/AWAI-161) (Awai FS design, In Progress)
- **Format contract**: [AWAI-531](https://linear.app/kotobalabs/issue/AWAI-531) (Done — CARv2 / Kotoba Pack / Prolly Tree / Range Scan)
- **Disk draft**: [AWAI-3111](https://linear.app/kotobalabs/issue/AWAI-3111) (Done — Awai Disk Format / Disk System draft in network-awai-apex docs; discrepancies fixed by AWAI-3120)
- **Plan**: kotoba fs Phase 1 plan (investigation + planning, 2026-11-22 worker report to coordinator)

## Context

Awai FS owns the distributed content-addressed filesystem design (AWAI-161)
and its v2 format contract (AWAI-531: canonical CARv2 interchange, native
sealed Kotoba Pack, deterministic Prolly Tree, ordered range scan with B+/LSM
comparison). The on-disk side — superblock, manifest, segment/pack, index,
WAL, write-and-finalize ordering, recovery, media placement, block export —
is drafted as the Awai Disk Format / Disk System (AWAI-3111), reconciled
against the live physical forms (catalog-v1, AWVZ003, AWZP003) and the NBD
block export (AWAI-3105).

On the KOTOBA side there is filesystem implementation but no filesystem spec:
`lib/kotoba.fs` (Layer 3 stdlib — pure path ops plus `IFilesystem` /
`IAsyncFilesystem` protocols plus `mem-filesystem`, with the real-OS binding
isolated in `kotoba.lang.fs-host` behind mandatory `:root` confinement),
`lib/kotoba.awaiFs` (the executable authority for the AWAI-531 logical-file /
chunk-profile v1 contract), `lib/kotoba.prollyTree` (shared CLJC Prolly Tree
over CID-addressed dag-cbor blocks, storage-injected), and
`lib/kotoba.kotobaseStorage` (provider-neutral `IBlockStore` / `IRefStore` /
`IBackendCapabilities` contract). Amu owns the native capability edge
(`src/kotoba/compiler/filesystem.kotoba`, `filesystem-wire` forms 0–18,
`:fs/app-data` / `:fs/browse`, typed-cap-call). There is no KOTOBA umbrella
issue for kotoba fs or its disk format (verified 2026-11-22); the closest
tracked items are KOTOBA-437 (scoped fs/browse wire 34), KOTOBA-463
(keyword-intern vs FS-lock runtime state), KOTOBA-400 (native SQLite engine),
and the fifteen KOTOBA-676–691 `[repo] kotoba-lang/fs-*` initial-tidying items.

This ADR draws the line between what kotoba fs reuses unchanged and what it
specifies itself, so later implementation phases cannot silently fork the
format, the CID identity, or the authority model.

## Decision

kotoba fs / disk format is specified as a **hosted profile** of Awai FS and
the Awai Disk Format, plus a small closed set of kotoba-specific contracts.
It defines no new interchange format, no new codec, no new CID scheme, and no
new cryptography.

### R1 — Reused unchanged (redefinition is a spec violation)

1. **Interchange and identity**: CARv2 as the canonical interchange;
   CIDv1/raw/SHA2-256; canonical DAG-CBOR bytes. A kotoba fs node MUST verify
   bytes/CID parity and CARv2 round-trip exactly as AWAI-531 accepts them.
2. **Logical file model**: `lib/kotoba.awaiFs` `src/awai/fs/logical_file.kotoba`
   is the executable authority (chunk profile `{"kind":"fixed","version":1,
   "leafSize":N}`, ≤1024 chunks, contiguous offsets, canonical key order,
   tag-42 links). Changing media or repacking MUST NOT change the logical
   inputs or the ID; a rechunk yields another manifest/ID.
3. **Index structure**: deterministic Prolly Tree rules (boundaries keyed on
   the child's CID, never on max-key; real IPLD links so generic DAG-CBOR
   tooling can walk the tree). On-disk node bytes vs in-memory decoded layout
   stay separated per AWAI-533.
4. **Storage contract shape**: `IBlockStore` / `IRefStore` /
   `IBackendCapabilities` from `lib/kotoba.kotobaseStorage`, including the
   mandatory exactly-one ref profile (`:linearizable-ref` vs
   `:single-writer-ref`). Untrusted bytes stay untrusted until the existing
   IPLD/CID verification passes.
5. **On-disk framework**: superblock, manifest, segment/pack, index, WAL,
   write-and-finalize ordering, recovery procedure, and media placement follow
   the AWAI-3111 draft. Any deviation is recorded as an explicit delta against
   that draft (the AWAI-3120 fix list is the model for how deltas are tracked).
6. **Delegated semantics** (referenced, never restated): Kotoba Form / DefCID /
   IPLD selfhost reach (JUN-950/962), private filesystem and query semantics
   (AWAI-173/174), keys / crypto backends / independent nodes (AWAI-415 =
   JUN-23), owner-only E2EE and copy-only raw migration (AWAI-2798/2799),
   tiered placement and Pack recovery (AWAI-532), replica/EC/scrub/repair
   (AWAI-534), and the end-to-end cost-based optimizer (AWAI-535).

### R2 — Kotoba-specific normative scope (the only new spec surface)

1. **Capability-confined filesystem (K1)**: the `kotoba.fs` split — pure path
   ops callable by anyone, effectful ops only behind an injected
   `IFilesystem` handle — is normative for kotoba fs. A confined cell MUST NOT
   touch the OS except through a granted handle; the real-OS binding lives in
   `kotoba.lang.fs-host` (or its native successor) and MUST enforce `:root`
   confinement, NUL/traversal/symlink refusals, and byte bounds. `mem-filesystem`
   is the reference implementation for spec conformance vectors.
2. **Hosted-file vs raw-block distinction (K2)**: this profile standardizes
   kotoba fs as files placed by a hosted OS (the single-node hosted proof
   comes first, consistent with AWAI-532). Bare-metal raw-block drivers
   (AIUEOS direction) are a separate profile and MUST NOT be smuggled into
   this one's conformance claims.
3. **Amu wire contract (K3)**: `filesystem-wire` forms 0–18, the wire-34
   browse / wire-35 app-data scope separation, and the browse adapter format
   (`NAME<TAB>D`, UTF-8 bytewise ordering, omission of `.` / `..`) are frozen
   as specified behavior; KOTOBA-437 owns the native proof.
4. **Engine boundary (K4)**: the native SQLite engine (KOTOBA-400) is a client
   of kotoba fs, not a storage backend. It MUST NOT bypass the refusal
   vocabulary or the commit/fsync ordering.
5. **Refusal vocabulary (K5)**: `:fs/escape` and the surrounding refusal/error
   keywords (`eventual-error-type`) are shared across sync, async, and native
   handles; an async or native handle MUST NOT accept what the sync handle
   refuses.

### Non-goals

- No POSIX/FUSE surface beyond what AWAI-409 already decided (inclusion is an
  owner decision, Q4 below).
- `kotoba.diskspace` (macOS usage inventory) and
  `kotoba.comAppleFileprovider` (Finder adapter) are referenced boundaries,
  not merged members.
- No performance, durability, or production qualification is claimed by this
  profile; AWAI-531/532/534 acceptance gates (100k small files, large blobs,
  sequential/random workloads, fault injection, RPO/RTO) are re-applied, not
  redefined, when the kotoba profile seeks them.

## Consequences

- Implementation phases proceed in order: parent-issue proposal (proposal
  only, no new issue created by workers) → this spec draft → library
  consolidation (`kotoba.fs` as canonical home; the fifteen `fs-*` split
  repositories resolved per owner decision Q1) → hosted-profile deltas + spec
  test vectors over `mem-filesystem` → conformance re-application of the
  AWAI-531 gates → native/Amu connection (KOTOBA-437/463/400 as their own
  acceptance owners).
- Every phase keeps the guardrails: AWAI/KOTOBA only; code in feature
  worktrees/branches, never force-pushed; PRs opened but merged only by owner
  decision; no product-readiness claims without real-device, separate-node,
  and fault-injection evidence.

## Open questions (owner decisions required)

- **Q1**: The fifteen `kotoba-lang/fs-*` split repos — archive vs keep as
  re-export shims (public API compatibility policy)?
- **Q2**: Canonical home for the finished spec — this repo's `docs/` vs apex
  docs vs a Linear document?
- **Q3**: Is the hosted profile sufficient, or does kotoba fs need an
  independent on-disk format?
- **Q4**: Is POSIX/FUSE (AWAI-409) in scope for kotoba fs?
- **Q5**: Is dango authorization / E2EE boundary normative in this spec or a
  reference?
- **Q6**: Owner/assignee and priority for the proposed KOTOBA umbrella issue
  (all current KOTOBA fs items are unassigned)?
- **Q7**: Ordering against in-flight AWAI-532/534/535 — where does the
  single-node hosted proof gate this profile's conformance phase?
