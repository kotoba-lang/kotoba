# Canonical Linux-static process/spawn handler source

Tracking: [JUN-201](https://linear.app/kotobalabs/issue/JUN-201),
[JUN-200](https://linear.app/kotobalabs/issue/JUN-200).

`src/kotoba/native/linux_static_spawn.kotoba` ports the complete C3 process/spawn
mechanism from `linux_static.cljk`, owning main
`535ca0a3e7ec1c4b4496c8ea12b18436838cbb47`, blob
`0ab7132ae38f4fd6fb75b107909c1854559160cf`. Canonical Kotoba source builds
the same register IR for Linux x86_64 and AArch64. Program/env/budget/refusal
policy stays in the admitted compiled owning handler decisions.

This is a source candidate. No generator, assembler, compiler build, native
admission, artifact, syscall, child process or runtime code was executed.
No test was added or run. Source SHA-256:
`e0264ac64da092bc0ef2bb573a51ef81e8ba0beaef7f4e6b3ab8a1514675a0a8`.
Static inventory: 547 lines / 63 functions, balanced delimiters, own/import
call arities after structural thread expansion, known heads and no local value
used as a function. A source record inventory also read all four own record
constructors and 42 field accesses, with matching declared field counts/keys.
State/register, argument, fd, deadline, resource and result
dataflow were read; native type admission, emitted bytes and behavior remain
unqualified.

## API and admitted authority

`routine [isa source-plan layout]` returns `:linux.static.spawn/result` with
`code`, `binding`, `error`; only `error=:ok` permits consuming code, with
binding `:ls.cap/spawn`, handler id 10. Failure returns empty code and binding
`:none`. The C3 candidate now composes all ten existing handler bodies and
the conditional hash body. Compiled sealed decisions and real common trap
paths remain required external labels.

The caller must first admit the complete artifact, narrowed grants, canonical
spawn plan, native decision exports, context ABI, matching ISA and computed
image layout. This source API's document/region checks do not attest those
inputs or create execution authority. Planner admission still owns distinct
canonical absolute programs, unambiguous optional basename lookup, and allowed
environment names. Local text checks only protect constant/IR construction.
Per-context calls stay serialized. Actual execution requires the C1 gate and
full request-handle/UTF-8 admission; direct machine entry grants nothing.

## Complete request and child path

The request is `<program>[ARG_SEP<arg>]...`. A first pass counts non-overlapping
separators, embedded NULs, program length and the complete NUL-terminated argv
byte count. Owning op 33 decides shape/argv-budget admission; explicit buffer
checks bound all string bytes and the pointer array. A second pass preserves
empty/trailing arguments, constructs every string in buf-a and a terminated
argv vector in buf-b. No shell parsing, quoting or interpolation is added.

Every planned program is compared in bytes by full path and basename, then
real op 34 selects it using the slash/lookup rules. Op 35 names a missing
program/path-lookup refusal. The chosen exec path is the exact NUL-terminated
sealed constant, not a request string or inherited PATH lookup. Unicode
bytes are preserved. The parent's inherited environment is scanned for exact
granted `NAME=` entries; op 36 admits each, and buf-c receives the complete
terminated pointer vector. A shorter inherited name stops at its NUL, avoiding
the reference's read past that string during comparison.

Three CLOEXEC pipes provide stdin at EOF, captured stdout, and an exec-status
channel. Native clone(SIGCHLD) forks without shared memory. In the child:
dup3 supplies stdin/stdout; close_range marks descriptors >=3 CLOEXEC;
PR_SET_NO_NEW_PRIVS is required; the captured scope root is entered when
available; execve receives the chosen program and bounded argv/envp vectors.
The existing setup failure path remains for unavailable kernel mechanisms or
failed stdio/root setup; no weaker execution path is substituted.

Each of five pre-exec failure stages sends its packed step/errno word through
the status pipe and exits 127. Its write loop handles owning EINTR decisions
and positive short writes. Successful exec closes that channel via CLOEXEC.
Op 42 maps a reported stage to exec-failed, isolation-unavailable or setup-failed.
Partial status words ending at EOF are reaped and refused as setup failures.

## Deadline, output, exit and result

The monotonic deadline starts immediately before clone. Owning ops 10 and 39
derive clock nanoseconds and remaining time; op 41 constructs ppoll timespecs.
Status waiting, stdout polling and exit waiting all revisit this same deadline
after EINTR. Status reads accumulate up to the complete eight-byte report.
The reference's blocking status read is therefore bounded by the same policy,
without an independent replacement timeout.

Owning op 37 supplies the output limit from the complete names region minus
one sentinel byte. That capacity is checked before pipes/fork so an unusable
capture region cannot launch a child before refusal. The complete stdout
stream is captured until EOF, with at most budget+1 bytes admitted into scratch
to detect overflow. Reads check actual returned spans. After EOF, wait4 with
WNOHANG and the owning op-40 sleep slice wait under the same deadline; the
reaped pid must match the created child. Op 38 derives the exit field.

Timeout/output-budget paths SIGKILL the created child, close remaining capture
fds and reap it before their named refusal. These operations are generated
mechanisms only; no existing service or process was stopped during this work.
The successful result is the full `<exit>\n<stdout>` string, with `-1` for
signal exit per owning policy, checked output-size arithmetic and real op-6
pool admission. A checked pair is allocated once for its already-filled span;
C3's common finish validates the final handle and UTF-8 bytes.

All eight reference refusal names and configured refusal exit code remain.
All needed scratch/pool windows and pairwise separation are checked locally;
the admitted whole image still owns actual mappings and complete disjointness.
The status/poll/fd, short-result, early-capacity and bounds corrections change
some malformed-input/refusal timing. Exact diagnostic precedence and native
resource behavior are not claimed from source review.

## Remaining closure

Full native positive/negative execution, Definition CIDs, emitted-byte and ABI
parity, full [prelude/context](linux-static-prelude-port.md) integration and ELF construction, sealed decision
placement, owning hash routing/profile, reviewed pins and whole compiler
self-rebuild remain open. The hosted packager does not call these candidates.
Source presence does not qualify a loaderless compiler or native CDCI.
