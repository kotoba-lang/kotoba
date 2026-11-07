# Canonical Linux-static prelude and context source

Update: [bytes primitive composition](linux-static-bytes-port.md) extends the
source to twenty slots, per-value byte/string limits and named value paths.

Update: [complete vector arena composition](linux-static-vectors-port.md)
adds actual vector pointers/counters/capacities, eight routines and distinct
table/item exhaustion paths. Initial counts below are historical source data.

Tracking: [JUN-201](https://linear.app/kotobalabs/issue/JUN-201),
[JUN-200](https://linear.app/kotobalabs/issue/JUN-200).

`linux_static_prelude.kotoba` and `linux_static_context.kotoba` port the full
startup/signal/trap/slot composition and initialized-data boundary from
`linux_static.cljk`, owning main `535ca0a3e7ec1c4b4496c8ea12b18436838cbb47`,
blob `0ab7132ae38f4fd6fb75b107909c1854559160cf`. Both Linux ISAs remain covered
by the canonical typed register IR; budgets, grants, trap names and exit codes
come from the admitted plan/profile.

These are source candidates. No generator, compiler build, native admission,
assembler, emitted artifact, syscall, signal installation, guest/runtime
execution or test was performed. Static source inventories found balanced
delimiters, own/import call arities after thread expansion, known heads and no
local data-as-function calls. Own record field counts/keys were also read.

| Source | Lines / functions | SHA-256 | Own constructors / accesses |
| --- | --- | --- | --- |
| `linux_static_prelude.kotoba` | 277 / 41 | `a6fd071191141780b5985402aeff24ddeffef06ba17d51ef9745249d97c1a0a2` | 6 / 15 |
| `linux_static_context.kotoba` | 170 / 18 | `2d8eb87cd8860ca47265a91b3f53caa2148c3b87e0ff77963ac50416351ba8b7` | 3 / 5 |

Native type admission, generated label/layout/byte behavior and runtime
qualification remain open. Source checks are not that evidence.

## Prelude API and complete composition

`routine [isa source-plan layout]` returns `:linux.static.prelude/result`, with
`code`, `bindings`, `externals`, `error`. Only `error=:ok` permits using the
result; failure has empty code/maps/sets. `bindings` maps every context slot to
either its real admitted body or an explicit named-refusal stub. The fixed
internal labels are `:ls/start`, `:ls/handler` and `:ls/text-end`.

The entry captures kernel argc and argv from the original stack. It installs
the alternate signal stack and all five SIGILL/SIGTRAP/SIGBUS/SIGFPE/SIGSEGV
handlers, checking every syscall result before proceeding. A failure goes to
the real non-returning bad path. For a capability plan it composes C3's common
argv/envp/private-context/clock and cwd/root startup exactly once, before the
guest. Pure plans emit no capability startup/body or decision externals.

The guest call clears the four visible arguments/context and sets its hidden
context register to the admitted image data base. Its i64 return is formatted
as signed decimal plus newline, including the two's-complement minimum via
unsigned-magnitude division. Output is written to stdout and exits with the
profile's `:ok` code. Both default output and fatal-message paths retry EINTR
and positive short writes with explicit pointer/length windows, then exit;
other write failures do not create an alternate execution path.

The signal path reads the metered flag and actual ABI fuel field: zero fuel
when metered selects the profile's fuel trap, otherwise the actual signal or
unknown signal is named. Fuel/cell/byte traps preserve the existing arena
messages. All messages are emitted with explicit byte lengths, removing the
host-side symbolic-immediate/message-length rewrite. Trap-exit accepts
p1=message pointer, p2=remaining byte count, t5=configured exit code.

Only plan-admitted pair/string slot bodies are installed; typed-cap-call binds
the full C3 candidate when admitted. Every unadmitted context slot gets its
own named refusal. Admitting a missing implementation fails source generation.
The C3 code's common bad/cell/byte/no-handler/trap-exit externals are supplied
by this prelude. Remaining externals are actual guest main and, for capability
plans, the three sealed native decision exports. No green stub or host callback
stands in for a missing body.

## Context API and all initialized fields

`context-bytes [source-plan layout labels bindings code-address code-length]`
returns `:linux.static.context/result`, with `bytes`, `error`. Only `error=:ok`
permits consuming exactly 1024 initialized file bytes; failure returns no
partial bytes. `labels` must be the real assembler result and `bindings` the
matching prelude result. Slots and the signal handler resolve to actual
prelude addresses before guest code; no zero pointer or unresolved label is
accepted as a replacement implementation.

The context includes version 11, initial fuel, pair-used/pairs/validation
pointers, the shared zero vector-state pointers, every admitted/stub slot
pointer, all 256 allow-mask bits, and the cells/bytes/meter/code/pool state.
The signal action and alternate-stack templates carry the actual handler,
SA_ONSTACK/SA_RESTORER, zero signal mask, mapped alternate-stack base and
16384-byte stack size. Other initialized bytes are zero. Private state beyond
the file payload still requires the real image's zero-filled memory mapping.

The signal numbers, flags and templates follow Linux UAPI definitions:
[generic signal layout](https://github.com/torvalds/linux/blob/master/include/uapi/asm-generic/signal.h),
[signal flags](https://github.com/torvalds/linux/blob/master/include/uapi/asm-generic/signal-defs.h),
[x86 layout](https://github.com/torvalds/linux/blob/master/arch/x86/include/uapi/asm/signal.h),
[AArch64 definitions](https://github.com/torvalds/linux/blob/master/arch/arm64/include/uapi/asm/signal.h).
The handler never returns. Actual kernel/CPU signal-frame/stack behavior still
needs qualification; a fixed stack size does not prove all machines supported.

Every ABI/slot word is aligned and stays before state offset 512. Word-word
and word-bitmap overlaps refuse; slot offsets must match the ABI declaration.
Grant IDs are checked in 0..255 and the mask is produced byte by byte with
only shifts 0..7, preserving all four words without floating-point conversion.
Fuel and resource initial values, code and arena spans/order, handler/slot
bindings and full page arithmetic are checked. Serialization uses logical
little-endian extraction from i64 words and local vector construction.

## Authority, corrections and unfinished integration

These APIs consume the complete admitted plan/profile, sealed artifact,
matching ISA/decision exports and exact computed layout. Their local structural
checks neither attest supplied documents nor authorize an arbitrary binding,
mapping or capability. Version 11 is an implemented native format; it imposes
no C-loader pin requirement.

Signal-registration return checks, complete short-write handling, explicit
message lengths, stricter exit-code/offset/collision refusals and real binding
checks are mechanism changes. Exact historical malformed-input/diagnostic
precedence and emitted-byte parity are not claimed from source review.

The [complete image source candidate](linux-static-image-port.md) now supplies
sealed decision placement, both-pass prelude/guest composition, actual context
binding and final ELF framing. It imports the complete owning ELF64 candidate
from kotoba-object #8, head `c8b97ec9e3dbc6a8cba1e6ac4a66dadc36a9a0f7`,
source blob `59a2d23705a5850326eb6fc2be6dae9fc7f38f83`. That lower draft
is not on owning main or native's current dependency pin yet; exact reviewed
source/lock integration remains open. A native-local encoder copy is not a
substitute. Native verification/Definition CIDs, actual hash routing/profile,
general vector/byte/runtime helper closure and whole compiler self-rebuild
remain required. The hosted packager is unconnected to these source candidates;
no native CDCI success is claimed.
