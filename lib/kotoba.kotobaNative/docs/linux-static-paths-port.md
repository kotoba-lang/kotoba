# Canonical Linux-static scope, path and parent mechanism

Update: [complete scope-absence work](linux-static-scope-absence.md) adds
explicit scope-denial state, full-span NUL refusal, root-scope metadata and
all-component no-symlink resolution. Initial source digest/counts below are
provenance, not the current revision's admission or runtime evidence.

Tracking: [JUN-201](https://linear.app/kotobalabs/issue/JUN-201),
[JUN-200](https://linear.app/kotobalabs/issue/JUN-200).

`src/kotoba/native/linux_static_paths.kotoba` ports the complete shared
resolve-path, open-at, open-parent and cwd/scope startup portions of
`linux_static.cljk`, owning main `535ca0a3e7ec1c4b4496c8ea12b18436838cbb47`,
blob `0ab7132ae38f4fd6fb75b107909c1854559160cf`. It uses canonical typed IR
and the shared I/O operand/decision/syscall emitters on both ISAs, without a
hosted path library, C/FFI, shell or alternate filesystem runtime.

This is a source candidate, not an available filesystem provider. No generator,
assembler, compiler build, native admission, artifact, syscall or path operation
was executed. No test was added or run. Source SHA-256:
`b811143a1bc5683d8d8b4fa79b96acfd4240ad009006cb22eef5e9b09fa415c6`.
Static inventory: 321 lines / 41 functions, balanced delimiters, own/import call
arities after structural thread expansion, known heads and no local data used
as a function. Source register/state/path dataflow was reviewed. The shared
reference tables match all 87 state offsets and all 30 syscall numbers per ISA;
these observations do not establish generated code or runtime/refusal parity.

## API and composition

All exports return `:linux.static.paths/result` with `code`, `start` and `error`.
Only `error=:ok` permits consuming the output. Failures have empty code/start
and name ISA, planned handlers, context ABI, scope shape, layout/scratch region
or path-state-key problems. The caller must first admit the whole artifact,
plan, narrowed grants, decision code and layout through their owning sources.
These checks do not attest arbitrary documents or establish mapped memory.

| Export | Source-building contract |
| --- | --- |
| `startup [isa source-plan layout]` | `code` holds the root/dot constants; `start` captures cwd and scope root |
| `resolve-path [isa source-plan layout prefix fail target length-key relative-key]` | Inline s1/s2 path bytes become normalized s4 target, with stored length and rooted relative pointer |
| `open-at [isa source-plan layout relative flags mode]` | Inline openat2 under the captured root; relative is a typed shared operand and t0 receives the result |
| `open-parent [isa source-plan layout prefix form target length-key fd-key base-key negative]` | Inline parent/base admission and rooted parent open, storing its fd and basename pointer |

`resolve-path` supports the reference's two state/buffer arms: buf-b with
len-a/rel-a, and buf-c with len-c/rel-c. Parent splitting uses the same arm
and its admitted root-length word. Other output/state choices are refused.
Callers choose distinct private label prefixes for each inline use; duplicate
insertions must fail assembly. External failure/negative labels must retain
the owning caller's actual trap/refusal path, not dummy success.

The C3 candidate now appends startup constants and composes scope startup after
the common I/O startup, once before guest code. The browse body now uses these
path fragments; the filesystem candidate also composes them for fs/app-data.
The process component supplies spawn and uses the captured root fd. Context
version 11 is the implemented native format, not a C-loader pin condition.
All source/ISA/assembler and context/layout bindings still require qualification.

## Startup and path admission

Startup initializes both root-fd and fs-root-fd to -1, captures an absolute cwd
in its bounded region, and opens the filesystem anchor with
O_PATH/O_DIRECTORY/O_CLOEXEC. Absent/false scope uses `/`; explicit scope also
sets the separate spawn root-fd, preserving inherited spawn cwd when absent. It
captures the root's kernel spelling by saving the cwd descriptor, fchdir to
the root, getcwd, then fchdir back and close. Failure to restore cwd traps
before main; failure to obtain a real spelling retains the sealed spelling
only. There is no /proc fallback. Absent/false scope retains
unscoped filesystem behavior; a configured scope must be bounded, absolute
and NUL-free, with full canonical admission still owned by the planner.

Path input must already be a stable admitted request byte window, disjoint from
the scratch buffers. Owning handler op 14 decides absolute versus cwd-relative
construction and its 4096-byte bound. The mechanism copies, NUL-terminates and
classifies segments; op 13 decides drop/pop/keep. Dot/dot-dot/slash and root
boundaries retain the owning lexical decisions. Raw POSIX traversal of a
component removed by normalization is not a separate admission requirement.

The normalized path is compared with both sealed and kernel root spellings,
only when owning op 43 admits that spelling. C1 op 8 receives prefix equality,
the next byte, normalized length and the actual admitted root length. The
owning C1 update handles scope `/` using that length; no inline allow rule
replaces it. The admitted spelling length
is stored separately for each buffer arm, and the root itself yields dot as
its relative path. No matching/admitted root transfers to the caller's failure.

## Rooted opening and mutation parents

Every normal open uses the captured descriptor and a 24-byte open_how with
RESOLVE_BENEATH | RESOLVE_NO_MAGICLINKS | RESOLVE_NO_SYMLINKS (14), requesting kernel enforcement
against resolution outside that descriptor and through intermediate symlinks. See the
[kernel flag definitions](https://github.com/torvalds/linux/blob/master/include/uapi/linux/openat2.h)
and [openat2 manual](https://man7.org/linux/man-pages/man2/openat2.2.html).
There is no openat fallback if openat2 is unavailable or refuses a path.
The typed relative operand is saved before populating open_how, including
register operands that might otherwise be overwritten by scratch moves.

Parent splitting scans the last slash and classifies the base. Owning op 15
admits that split; op 19 locates the parent against the actual admitted root
spelling. The mechanism cuts the parent spelling only after those decisions,
opens it beneath the root and stores the basename pointer for the caller's
*at operation. Owning outcome op 12 controls retry/negative/trap behavior.
Mutations of root/parent and symlink/boundary cases remain qualification work;
no filesystem operation or authority is granted by these emitters themselves.

The caller must preserve the C3 s0..s4/private-context protocol, own all actual
mapped scratch and state regions, and serialize per-context operations. Prefix
and NUL bounds, kernel failures, refusal ordering and resource/fd cleanup need
full native qualification. Static review is not that evidence.

## Remaining closure

The [browse body](linux-static-browse-port.md) now uses these fragments;
the filesystem component now supplies fs/app-data, and the process component
supplies spawn. Remaining work includes complete
prelude/context integration (the [source candidate](linux-static-prelude-port.md)
now exists), sealed decision placement, ELF
construction, native verification/Definition CIDs and reviewed pins/self-rebuild.
The owning hash route/profile remains disabled. These sources do not retire
the C loader, restore hosted CDCI, stop a service or change a production route.
