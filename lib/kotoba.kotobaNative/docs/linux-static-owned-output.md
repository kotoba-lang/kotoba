# Owned output lifecycle source candidate

The `linux_static_output.kotoba` component is connected in source to managed
filesystem creation/member/discard and the common normal/fatal exit paths.
This has not been compiled or executed. No cleanup, provider, compiler or
CDCI qualification is claimed.

## Source mechanism

- A single synchronous output-set registry retains its opened parent and
  private directory descriptors, the current member descriptor, full path,
  basename, actual created-member count and cleanup state.
- Preparation records ownership before subsequent policy/result code can
  trap. Only a dedicated managed creation operation may arm it; ordinary
  MKTEMP must retain its existing persistence semantics.
- Managed members match the complete normalized owned path plus the next
  canonical index.tmp. They open exclusively through the retained directory
  FD. A successful open is journaled before a sealed decision or result
  conversion; no per-member reopen after mode application is needed.
- Cleanup closes the current member, attempts every known index.tmp through
  the retained directory FD, and checks device/inode equality with the name
  currently beneath the retained parent before attempting directory removal.
  Missing members after publication are ordinary; other errors are retained.
  It never recursively enumerates/deletes arbitrary directory contents.
- Leaf routines allocate no language values, call no guest code or sealed
  decisions, and do not depend on remaining guest fuel. They save the six C3
  words and use distinct s0..s4/t0..t3 registers on both ISAs. Cleanup has a
  re-entry guard and returns failure when its work is incomplete.
- Planner reserves a real, disjoint 5120-byte workspace in addition to the
  unchanged value/run arenas. Seventeen private words (1752..1880) and explicit
  initial sentinel values carry ownership and exit state; the public ABI is
  unchanged.

The first two stat words (device/inode) were checked against Linux v6.17's
[x86-64 stat definition](https://github.com/torvalds/linux/blob/v6.17/arch/x86/include/uapi/asm/stat.h)
and [generic 64-bit stat definition](https://github.com/torvalds/linux/blob/v6.17/include/uapi/asm-generic/stat.h).

## Source integration

Proposed kind 11 admits begin 17/R and discard 18/S with empty tails, in
addition to stage-member 16/Q. Begin reuses the original private 0700
creation policy with a fixed .kotoba-output- prefix, records successful mkdir
before sealed outcome conversion and captures the retained directory FD
before constructing the response. Ordinary MKTEMP does not arm ownership.
Managed member-open checks the entire normalized owned path and next index,
and journals its descriptor/count before sealed outcome conversion.

Amu write-set! calls begin, stages every member, publishes in caller order,
then calls discard after either Result outcome. Discard accepts only the
exact owned directory. Normal completion and common fatal exits call the
same allocation-free cleanup; installed signal paths reach that fatal exit.
The original result or fatal diagnostic/exit is saved outside the cleanup
workspace. Incomplete cleanup emits a separate diagnostic; an otherwise
successful native exit becomes nonzero, while a fatal exit retains its code.
Single-active staging follows the synchronous IO API; nested begin refuses
without replacing a live registry. No controller or workflow is qualified.

## Error-path descriptor release source change

Probe open/stat, identity mismatch and directory-removal failures now join
one descriptor-release path. It attempts every live member/probe/directory/
parent close, retaining all earlier failures even if later operations succeed.
The probe sentinel is initialized before managed creation, so a failed probe
cannot turn an uninitialized zero into a close of stdin.

Each descriptor journal is consumed before its Linux close syscall. A close
error is recorded and other owned descriptors are still released; close is
never retried. The stage-member path likewise retires its managed cleanup
alias before close, so a fatal close result cannot lead to a second close.
This follows Linux's descriptor-release behavior, including EINTR; it is not
a portability assumption about every operating system. See the Linux
[close manual](https://man7.org/linux/man-pages/man2/close.2.html).

The registry phases are now explicit:

| Phase | Meaning | Cleanup source behavior |
| --- | --- | --- |
| 0 | inactive | success without touching descriptors |
| 1 | parent reserved, directory not created | release parent; success only without close errors |
| 2 | directory created, no captured directory FD | release descriptors and report incomplete; no guessed name removal |
| 3 | captured managed directory | remove known members, verify directory identity, attempt rmdir, release all descriptors |
| 4 | cleanup failed; descriptors consumed | keep reporting failure and reject a new managed begin |

Phase 4 prevents a later successful begin or cleanup from hiding an earlier
failure. It makes no promise that a failed unlink left no staging directory.
The existing result/fatal diagnostic/exit preservation remains unchanged.

`test/kotoba/native/owned_output_cleanup_cases.kotoba` adds 22 canonical golden
inputs/observations for the native fault harness. They include phases 0..4,
probe/stat/identity/unlink/rmdir/close failures, Linux EINTR, no double-close,
published missing members and recursive cleanup. They have not been compiled
or executed, and no consuming native fault harness is currently qualified.
Each vector includes the exact entry descriptor mask and created-member count;
the successful probe is opened during cleanup. Normal completed publication
has no live member FD, whereas interrupted staging may still own one. Close
masks denote actual syscall attempts, not OS teardown on exit. The two-member
vectors require attempts at both canonical names even if the first unlink
fails; they never authorize removing unrelated or published target paths.
Fault injection must preserve real Linux close consumption; returning a fake
EIO without consuming the FD is not an equivalent oracle. The stage-close
case also requires the original fatal diagnostic/exit to survive cleanup.
These vectors extend the required whole-provider corpus; they do not replace
the existing positive/refusal/authority/resource/path/race obligations.

## Correctness still required

Identity inspection followed by unlinkat is not an atomic inode-bound remove
operation. Replacement/rename races, the mkdir/open journaling windows,
signals during those windows, close errors, SIGKILL/process death and actual
filesystem failures are not proven solved. This source must not be promoted
as a guarantee that every crash removes staging or that a directory name
cannot change between inspection and removal. The full owning path/race and
positive/refusal/resource corpus must decide admission; no smaller workload
or newly restrictive parent whitelist is substituted.

In particular, a directory created without a captured FD is phase 2:
cleanup reports incomplete rather than guessing ownership and deleting the
name. It can leave that empty private directory. Signal interruption before
journaling or during capture/cleanup is still part of the open corpus.

The user requested native-only build/execution verification on 2026-10-22.
No currently located loaderless compiler/runner can compile the whole
candidate closure: the historical CLI image paths are missing; available
seed payloads require a C loader, and the standalone ELF evidence is a small
probe. Those routes were not used as a substitute. This component has only
source/API/record/arity/register/layout inspection, with no emitted/runtime
proof. Complete canonical GMIR/lowering/ABI and whole compiler/runner work
remain required before actual self-rebuild and native-only CDCI admission.
