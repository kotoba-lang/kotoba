# Bounded rootfs metadata plan candidate (JUN-776)

`fune.rootfs-plan` maintains a caller-owned in-memory table for at most 128
explicit paths, 255 ASCII bytes per path and 64 MiB of regular-file payload.
A directory must appear before its children. A later layer can replace a regular
file with a regular file or repeat a directory; it cannot change a path's type.
Duplicate entries in the same layer, missing parents, whiteouts, dot components,
special mode bits and over-limit inputs refuse. These intentionally restrictive
limits and semantics are not a claim of general OCI compatibility.

`rootfs-plan-add` returns zero on success and a negative value on refusal. It
leaves the supplied state unchanged on a single-entry refusal. The state is
trusted mutable state: callers must not forge or modify it and must present
layers in order. It is not an externally verifiable admission token.

`fune.rootfs-snapshot-plan/verify-layer-plan-hold` verifies a layer digest and
tar structure in the same sealed snapshot, then traverses from offset zero and
feeds its entries to the planner. It checks an actual zero terminator instead
of treating every cursor refusal as end-of-archive. Success leaves the snapshot
open for the caller to consume and close. On failure the caller must discard the
entire plan, since earlier entries in that layer may already have been added;
the function closes the snapshot on a planner/cursor refusal. A provider trap
terminates the process rather than returning a result. The caller is responsible
for processing all layers of the same authenticated manifest in manifest order.

No file is extracted, no worker is connected and no program is launched.
Whiteout/delete, type replacement, implicit parents, links, compression,
filesystem transactions and complete OCI semantics remain open. These APIs do
not establish isolation or authorization and must not be used to launch an
image. The snapshot provider is the draft Amu PR #1785 dependency; native x86,
project linking and exact-head CI remain unqualified.

## Local ARM64 observations, 2026-11-02

The native `rootfs_plan_gate.kotoba` checked missing parents, directory and file
insertion, same-layer duplicates, traversal, whiteouts, special modes, type
changes, cross-layer replacement, layer order, the 64 MiB boundary, 128-entry
boundary and unchanged state after refusals. Removing either the duplicate or
quota check in separately compiled controls made the gate fail.

The composed `rootfs_snapshot_plan_gate.kotoba` used independent digest-pinned
tar/manifest fixtures on the Amu candidate Linux ARM64 compiler. It refused a
file whose parent was missing, then accepted a directory and its child as two
consecutive planner inputs. It also refused a duplicate-path tar twice, showing
that refusal had closed the snapshot and permitted a fresh open. It checked the
zero-terminator distinction at header, valid terminator and out-of-range offsets.
The two accepted layer fixtures had separate manifests; this was not a test of
a complete multi-layer OCI image or the eventual worker integration.

For reproduction, stage the fixtures with `test/fune/stage_layer_fixtures.py`
into a fresh task-owned directory. Source-compose the existing SHA2, JSON,
manifest, layer-tar, snapshot and snapshot-archive bodies followed by
`rootfs_plan.kotoba`, `rootfs_snapshot_plan.kotoba` and the integration gate,
removing their namespace declarations and alias qualifiers as in SNAPSHOT.md.
Compile with the regenerated ARM64 Amu compiler from PR #1785. Run with the
fixture directory granted to FS2, `KEXE_COMMAND=1`, structured reporting unset,
and arguments in this order: directory tar, manifest and manifest digest;
regular-file tar, manifest and digest; duplicate tar, manifest and digest. The
staging script prints the digests. Compile the pure planner and its gate as a
second source-composed image. Both test processes must exit zero. These local
source compositions are test harnesses, not the project linker or CI.
