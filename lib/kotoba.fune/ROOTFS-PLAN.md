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

`rootfs-plan-entry` exposes accepted rows in insertion order as kind, mode and
path bytes. A cross-layer replacement updates the stored mode, including when a
directory requires no new creation command. The output-capable layout stream
now sends the final modes after all layers have been applied, in reverse
insertion order so children precede parents. Its draft Amu worker dependency
applies those modes in an isolated temporary tree and rejects later writes.
This still does not launch a workload or establish complete OCI semantics.
The source-composed ARM64 planner gate checked file replacement, repeated
directory mode updates, invalid indices and unchanged state on refusal. A
separately built mutant discarding modes failed that gate. The source-composed
layout producer still passed the native worker readback and refusal fixtures,
including a 1 MiB file and a repeated-directory layer. Project linking, x86
and end-to-end filesystem mode application are not established by those prior observations.

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

## Full manifest planning candidate

`fune.layout-check/verify-layout-plan` applies the bounded layout marker,
index, manifest and config checks, then traverses every manifest layer in
order through `verify-layer-plan-hold`. Each layer's snapshot is closed after
it has been incorporated; the metadata plan is discarded when the call
returns. `ok` therefore describes the bytes observed during this read-only
call, not any later snapshot or rootfs, and must never authorize extraction or
execution. In particular, reopening a blob later requires its digest to be
verified again. There is still no verified-archive-to-worker channel.

On Linux ARM64, the source-composed `layout_plan_runner.kotoba` accepted a
single manifest with three layers: directory, file and replacement of that
file. A layer order putting the file before its parent and a layer with a
duplicate path were rejected as `fune/rootfs-plan`. Corruption in either the
second or third file layer was rejected as `fune/blob-digest`; a control that
stopped after the first layer incorrectly accepted both. The second and third layers have
different bytes and digests. The original snapshot layout route was also rerun:
its existing two-layer fixture passed and its tampered counterpart failed.
These are source-composed local checks, not native x86 or project-linker gates.

Stage `stage_layer_fixtures.py` and `stage_layout_fixtures.py` into fresh
workspace directories. The latter prints each immutable manifest digest and
creates `plan-good`, `plan-parent-missing`, `plan-duplicate`,
`plan-second-tampered`, and `plan-third-tampered`. Compose the dependencies listed above, plus
`image_config.kotoba`, `layout_check.kotoba` and `layout_plan_runner.kotoba`,
with namespace aliases removed as in the existing local examples. Run with the
same Linux runtime settings and a grant scoped to each layout. The good case
must print `ok` and exit 0; both metadata conflicts must print
`fune/rootfs-plan`, and both tampered cases must print `fune/blob-digest`, all
with exit 1. The separate test-only first-layer-only mutant prints `ok` for
the tampered case. No real rootfs is created by these tests.

## Verified snapshot to worker stream candidate

`fune.rootfs-stream` emits the private-root worker's ASCII-hex input protocol
through `:io/write`. The caller invokes `rootfs-stream-start` once, then calls
`emit-layer-hex` in manifest order with one trusted planner state. Each call
verifies the descriptor digest and tar structure, retains that exact sealed
snapshot while it checks paths and streams payload chunks, then closes it.
Directories and new files become `M` and `F`, regular-file replacements `U`;
a repeated directory produces no filesystem command. File payloads over 1 MiB
are refused to match the current worker. This does not validate the OCI layout
marker, index or config; the caller must do that separately.

Earlier valid commands can already have reached the worker when a later entry
or layer fails. A supervisor must reject any failed producer, worker or pipe,
kill/discard the worker and its entire private tree, and never use stdout for
other text or structured reporting. The API does not currently authenticate a
supervisor, check worker acknowledgments, publish a rootfs or
start a process. In particular, producer success alone is not proof of worker
success, and a future reopening of a path is not covered by the old snapshot.
The bounded worker, planner and no-links/whiteouts profile still admit only a
small subset of OCI images.

The ARM64 `rootfs_stream_runner.kotoba` and `observe_rootfs_stream.py` are a
local test, not the missing production supervisor. The Python observer forwards
native producer stdout to native worker stdin unchanged and checks child status
and a diagnostic worker readback. A single authenticated manifest with three
layers created a directory and file, then replaced it with 16,643 bytes that
contain every byte value. Readback matched those bytes; a separate fixture
also streamed and read back the 1 MiB per-file boundary. A corrupt final layer
made the native producer exit 1 with `fune/blob-digest`; closing the pipe made
the worker exit 2 rather than publish its partially populated private tree.
A separately compiled digest-check-removal control incorrectly accepted that
corruption and failed the observation.

A second test-only producer overwrote the original last-layer file *after*
verification and snapshot creation but before streaming its payload. The
observer still read the original 16,643 bytes from the worker; the disposable
source file independently contained `changed` afterward. This exercises the
held-snapshot path, not all possible host races. The test used the draft ARM64
worker in Amu PR #1785. Source composition, local VM observation, and a Python
test observer do not qualify project linking, native x86, a production process
supervisor, an OCI-compliant extractor or workload execution.

## Full-layout stream preflight candidate

`fune.layout-stream/emit-layout-hex` is a separate output-capable module. It
first runs the bounded layout marker, index, manifest, config and all-layer
planner checks without writing a worker stream. After that preflight it reads
the manifest again through a bounded sealed snapshot and checks the caller's
expected digest again. It then verifies each layer again and sends bytes from
that layer's held snapshot. This deliberately does two verification passes;
it avoids treating an earlier path read as a future extraction grant, at the
cost of additional I/O and hashing. `fune.layout-check` remains declared with
only `:fs/app-data`; the stream module separately requests `:io/write`.

On ARM64, a native observer connected this producer to the native worker and
read back the 16,643-byte and 1 MiB fixtures. Bad marker, index, config digest,
unsupported architecture, and a corrupted final layer all failed preflight
before **any** stream byte was emitted. Separately compiled controls that
removed marker validation or config validation accepted their corresponding
bad fixtures and failed the observer. The native candidate supervisor also
passed its good, corrupted-layer and 1 MiB cases with this producer. Prior
read-only layout planning still accepted the good fixture and refused the
corrupt layer when composed without the streaming module.

A test-only producer changed one byte of the final layer *after* preflight,
keeping the layer size unchanged. The second-pass digest check refused it;
the observer saw 59 stream bytes from earlier entries, then the producer and
worker failed. A separate control with digest comparison disabled accepted the
same mutation and failed the observer. This shows why a supervisor must
discard the whole private tree on **every** later failure; preflight does not
make the source paths immutable. The test fixture's original and mutated
layers were independently checked to have equal length and differ by one byte.

The stream still depends on caller-authenticated executable and manifest
digests and the draft Amu supervisor/worker.
It does not publish the rootfs, start a program, support general OCI features,
or establish a same-principal security boundary. `ok` from the producer alone
is not an execution authorization. Source-composed ARM64 and local VM tests do
not qualify source-locked project linking, native x86, hosted CI or a release.

## Terminal operation count

The planner tracks the number of emitted mutation commands, bounded to 512.
Reusing a directory in a later layer does not add a command; a file create or
replacement does. After all layers stream successfully, `emit-layout-hex`
sends one `P` mode-finalization command per retained path, then a terminal
`C` frame carrying the combined command count (at most 640). The draft Amu
supervisor now accepts up to 640 acknowledgments. The worker compares
the count to the number it completed and emits `D` only on a match, after which it refuses more
writes. The native supervisor checks that its worker response ends in `D`;
the caller no longer supplies an acknowledgment count. `D` only closes this
diagnostic command stream: it does not persist a rootfs, authenticate the
producer, or authorize execution. The caller must still authenticate both image
digests, and the supervisor destroys the private tree after the test run.

The native ARM64 planner gate checked the 512-command boundary and confirmed
that a repeated directory does not increase the count. Before mode finalization
was added, a four-layer fixture with a repeated directory produced three
worker acknowledgments followed by
`D`, and the file readback still matched. The native supervisor rejected
separately compiled producer fixtures with an incorrect count and with no
terminal frame. A worker mutant that skipped the count comparison and a
supervisor mutant that ignored `D` each incorrectly accepted the corresponding
fixture, so both negative controls failed. These tests use draft native images
and do not establish an authenticated executable authority or runtime release.

## Final mode stream candidate

A source-composed ARM64 producer and worker built by the newly regenerated
source-pinned compiler passed full-layout byte and final file-mode readback,
bad metadata/layer refusal, repeated-directory and 1 MiB file checks. The
stream observer independently checked child-before-parent mode order and the
combined terminal count. A chmod-disabled worker built with a patched debug
compiler failed the mode readback; an older worker refused the new protocol.
No workload is executed and no tree is published. Project source linking, x86
and a full release remain unqualified.

The independent `test/fune/stage_limit_layout.py OUTPUT` fixture stages four
layers of 128 zero-length files. A native producer and worker completed 512
file create/update operations plus 128 mode operations and read back the final
mode. The previous supervisor rejected that valid 640-operation stream; a
source-pinned Amu candidate accepted it and refused an extra acknowledgment. The fixture is narrowly scoped and
does not prove arbitrary OCI support.

## Process-to-rootfs consistency candidate

`fune.process-rootfs/process-rootfs-problem` checks a digest-bound config against
a trusted final plan. It selects the first entrypoint element, or the first
`Cmd` element when the entrypoint is missing or empty. It requires an absolute,
non-normalized ASCII path to an explicitly planned regular file with at least
one execute bit. The working directory defaults to `/`; a non-root value must
identify an explicit planned directory. Dot, dot-dot, empty components and
unsupported path bytes refuse. This is a separate check: the existing image
validator still accepts data-only images.

`fune.layout-process/verify-layout-process` first verifies the complete layout,
then freshly reads and digest-checks manifest and config and replans every
verified held layer before applying the process check. It discards the plan.
The result is diagnostic: it does not freeze future input, establish a runtime
UID/GID's actual permissions, verify an executable interpreter, prove mount or
namespace isolation, persist a rootfs, or authorize execution. A caller must
bind its own verified snapshot and plan to the eventual execution.

On ARM64 Linux, a source-composed native gate checked entrypoint/Cmd selection,
default and explicit working directories, missing and wrong-type paths, no
execute bit, traversal, config digest tampering and unchanged image admission.
Separate no-execute-check and traversal-check mutants failed the gate. A second
native gate used independently staged OCI layouts: an executable fixture passed;
no-execute, missing executable, missing cwd, a later layer removing execute bits,
and a corrupted layer refused. Generate the fixtures with
`test/fune/stage_process_layouts.py OUTPUT` and supply its printed digests to
`test/fune/layout_process_gate.kotoba`. These tests do not establish source-
locked project linking, x86 behavior or execution of an OCI workload.
