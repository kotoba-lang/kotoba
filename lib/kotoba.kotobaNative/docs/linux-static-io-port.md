# Canonical Linux-static I/O, process metadata, clock and entropy handlers

Tracking: [JUN-201](https://linear.app/kotobalabs/issue/JUN-201),
[JUN-200](https://linear.app/kotobalabs/issue/JUN-200).

`src/kotoba/native/linux_static_io.kotoba` ports all seven corresponding C3
handler bodies from `linux_static.cljk`, owning main
`535ca0a3e7ec1c4b4496c8ea12b18436838cbb47`, blob
`0ab7132ae38f4fd6fb75b107909c1854559160cf`. It imports the canonical assembler
and shared string/pool fragments, with no hosted emitter, C/FFI, shell command,
subprocess helper or external runtime. The emitted mechanisms use native Linux
syscalls on x86_64 and AArch64 and real calls to the owning decision artifact.

This is a source candidate. No generator, assembler, compiler build, native
admission, generated machine code or runtime operation was executed. No test
was added or run. Source SHA-256:
`0d74803fca75afa16d95ed89937690d49f05829f1c387edb16e9ae4651b746b2`.
Static inventory: 474 lines / 61 functions, balanced delimiters, own/import
arities after structural thread expansion, known call heads and no local
data-as-function calls. Source dataflow, state words, dispatch, Linux syscall
number tables and private label templates were reviewed against the reference;
this is not emitted-byte or runtime/refusal parity.

## API and C3 composition

`routines [isa source-plan layout]` returns `:linux.static.io/result` containing
`code`, `start`, `bindings`, `externals` and `error`. Only `error=:ok` permits
using those values. Failures have empty outputs and named reasons for ISA,
planned handlers, configured refusal code, layout/scratch regions or the shared
context ABI. The caller must use the owning admitted plan and computed layout;
these arithmetic checks do not attest arbitrary supplied documents or mapped
memory. ISA, compiled decision code, context and final assembler must agree.

| Id | Supplied C3 label | Behavior retained |
| --- | --- | --- |
| 1 | `:ls.cap/io-write` | Write all request bytes to stdout and return decimal byte count |
| 2 | `:ls.cap/io-write-error` | Same for stderr |
| 3 | `:ls.cap/io-read` | Empty request reads through EOF; decimal form performs a bounded read with UTF-8 carry |
| 4 | `:ls.cap/cli-args` | Empty request counts arguments excluding argv[0]; decimal index returns that argument or empty past the end |
| 5 | `:ls.cap/env-read` | Validate the requested name using owning op 5, find its exact NAME= entry, return the value or empty |
| 6 | `:ls.cap/clock` | Admit exactly wall/monotonic text forms, ask the kernel for time and owning ops 10/11 for conversion and monotonicity |
| 9 | `:ls.cap/entropy` | Ask owning op 31 for count admission, fill from getrandom and use op 32 for hexadecimal output |

The [C1/C3 gate](linux-static-capability-port.md) now imports and appends this
component, resolves these seven dispatch labels and returns its common `start`
fragment. That gate's candidate API now takes explicit ISA and exposes `start`.
The separate browse component supplies fs/browse, the filesystem component
supplies fs/app-data, and the process component supplies spawn. All
eleven dispatch meanings, including the conditional hash candidate, stay intact.
The hosted packager does not yet call these canonical modules.

Required external labels are the owning `:ls.cap/h-decide`, common validated
`:ls.cap/finish`, real bad/cell/byte trap paths and `:ls/trap-exit`. Each handler
is entered after C1 grant/kind and request string admission, with s0=image data
and the request pointer/length in the reference state words. It stores a result
handle and branches to the common finish, which checks its UTF-8 return. None
of these labels is an independently authorized guest entrypoint.

## Decisions, memory and result ownership

The mechanism retains the five visible decision arguments and separate hidden
private context at data+1072, resetting private fuel before each decision call.
The native decision code must preserve s0..s4. Syscalls use the reference Linux
ABI numbers and argument registers, retaining EINTR/outcome decisions through
op 12 and short-result handling. Unknown outcome codes trap. Additional span,
carry and positive-result guards refuse impossible/wrapped memory bounds.

Decimal parsing remains owning ops 4/3, environment admission op 5, byte charge
op 6, stdin sizing/probe/carry ops 7/8/9, clock ops 10/11, and entropy ops
31/32. No policy is moved into host code or replaced with hardcoded approval.
The seven provided bodies remain behind the real C1 gate and sealed profile;
source presence does not widen grants or make absent handlers available.

Shared source emitters now expose typed literal/register/state-field/label
operands, operand loading, the complete 87-word reference state-offset table,
decision calls and five-argument syscalls for the remaining canonical handlers.
Both ISA tables contain the reference's complete 30 syscall numbers. Unknown
state fields, decisions or syscalls produce explicit -1/invalid operands or
unassemblable IR, never a fabricated successful operation. Argument-register
move ordering and admitted memory/ISA/decision bindings remain the trusted
generator caller's responsibility; only the three owning decision labels are
accepted. These are code-building APIs, not guest capabilities or callbacks.

All ordinary answers ask op 6 before a single private intern routine copies
into the bounded pool, charges actual bytes and allocates a checked pair. That
routine's inline fragment is emitted once, with LR saved/restored; callers use
its private call ABI and then finish immediately. It intentionally clobbers
s3/s4, already saved by the outer C3 frame; it is not a public native function.
Sharing this body avoids duplicating its private copy labels at each answer.
Stdin already fills an admitted pool span and uses the shared pool-pair fragment
without copying or charging its bytes twice. New pairs remain unvalidated until
the common C3 result path admits them.

Bounded stdin retains up to three incomplete UTF-8 bytes for the next call,
keeps its EOF probe and refuses a read that cannot yield a complete code point.
Whole stdin does not silently truncate at pool capacity. Write and random
loops keep partial-result progress/retries; zero-progress or oversized kernel
answers are refused. Entropy's ENOSYS refusal names entropy/unavailable with
the configured capability-refused code; there is no /dev/urandom fallback.
Clock initialization and per-call monotonic checks retain their state behavior.

Kernel argc/argv/envp and their NUL-terminated strings must be actual stable
mapped process-entry data. Length scans rely on that kernel ABI, not arbitrary
guest pointers or an invented small string cap. Pool, scratch and context
regions must come from the owning layout and remain disjoint. These assumptions
need full native image/verifier qualification, including resource and refusal
behavior. Exact malformed-input diagnostic precedence is not claimed identical.

## Startup and remaining closure

Run `start` once after recording kernel argc/argv and before any guest call.
It derives envp with overflow checks, initializes private context version 11
and the -1 monotonic sentinel. BSS zero-fill owns initial carry/pool state.
The existing context ABI remains an implemented native format, not a requirement
to pin a C loader. The companion [path component](linux-static-paths-port.md)
now supplies cwd/root capture and scope setup; the C3 result composes its startup
after this module's common initialization. The filesystem and process components
now supply fs/app-data and spawn source bodies; full image placement remains open.

The [prelude/context source](linux-static-prelude-port.md) now supplies startup,
signal/trap/slot composition and initialized data. Full image integration,
sealed decision text/export placement, hash routing/profile integration, ELF
construction and native admission/Definition CIDs/runtime qualification remain
open. These capability providers do not implement the compiler's missing general
vector/byte/runtime-helper closure. Reviewed pins and whole compiler self-rebuild
remain under JUN-200/202; no C-loader retirement or native CDCI success is claimed.
