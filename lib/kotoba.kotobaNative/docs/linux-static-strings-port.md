# Canonical Linux-static pair/string runtime source

Tracking: [JUN-201](https://linear.app/kotobalabs/issue/JUN-201),
[JUN-200](https://linear.app/kotobalabs/issue/JUN-200).

`src/kotoba/native/linux_static_strings.kotoba` ports the complete seven-slot
pair/string portion of `slot-routines`, plus its handle, UTF-8, allocation and
copy helpers, from owning main `535ca0a3e7ec1c4b4496c8ea12b18436838cbb47`'s
`linux_static.cljk` (blob `0ab7132ae38f4fd6fb75b107909c1854559160cf`).
The source imports only the canonical assembler's instruction constructor.
Its output is the same register-IR format for x86_64 and AArch64, without a
host encoder, process, C/FFI, runtime collection call or syscall in the emitted
routines.

This is a source candidate. No generator, assembler, compiler build, native
admission, generated code or runtime operation was executed. No test was added
or run. Definition CIDs, exact bytes, runtime/refusal behavior and whole-component
native qualification are open. The hosted packager does not call this module yet.

Source SHA-256:
`7414292f236f0d09b2fb906ebe20ed4318d559005997eb64573cace1c84b3f0a`.
Static inventory: 384 lines, 44 functions, balanced delimiters, own-call
arities after structural thread expansion, no unresolved source call heads
and no local data values used as function heads. Machine register/dataflow,
source slot coverage and budget/window formulas were reviewed, not executed.

## Generator API and binding

| Export | Boundary |
| --- | --- |
| `supported-slots []` | The seven pair/string slot names below; no grant or admission |
| `external-labels []` | Required external trap labels: `:bad -> :ls/bad`, `:cells -> :ls/trap-cells`, `:bytes -> :ls/trap-bytes` |
| `routine [context slot]` | Emit one supported slot and its entry binding; unknown slots, including `:all`, fail |
| `routines [context]` | Emit all seven once, with their entry bindings |
| `read-string-fragment [context prefix]` | Inline C3 handle/window/UTF-8 admission: s0=context and s1=handle become s2=pointer/s3=length |
| `intern-string-fragment [context prefix]` | Inline C3 copy/pool/cell mechanism: s0=context, s1=trusted bytes, s2=length become t0=handle |
| `pool-pair-fragment [context]` | Allocate an unvalidated pair for an already admitted/advanced pool span, s4=~offset and s2=length; t0 becomes its handle |

The result record is `:linux.static.strings/result`, with `code`, `bindings`
and `error`. Only `error=:ok` authorizes using code/bindings. Failure yields
empty code and bindings, with `:context-abi-version`, `:context-base-offset`
or `:unknown-slot`.

The context must be the owning caller's admitted ABI document, version 11.
The pair and validation base-word offsets must be distinct, nonnegative,
eight-byte aligned and at most 504, below the reference state area at 512.
This checks the generator's needed fields, not the entire ABI/artifact/layout
contract; the caller must perform that full admission and establish the actual
mapped regions. Version 11 is an implemented native format, not a C-loader
pin requirement. Other required native ABI versions remain work.

Entry labels use `:ls.strings/<slot>-entry`; private control-flow labels use
that same namespace with distinct call-site prefixes. The caller must install
only profile-admitted entry bindings in the context, retain refusal stubs for
unadmitted slots, and connect all external traps to its real signal/cell/byte
outcomes. Emitting a routine does not authorize making its slot callable.
Do not append both the all-slot output and an overlapping per-slot output:
the assembler must refuse their duplicate labels. These typed entry/trap labels
replace the hosted namespace's implicit labels and need explicit integration.

## Machine ABI and preserved behavior

All slots receive the existing explicit `ctx` argument, use the reference
state/arena layout and return in `ret`. Each saves/restores `t4..t8` and
AArch64 LR, as the reference did. These temporary aliases are x86's saved
rbx/r12..r15; they are distinct caller registers on AArch64, where preserving
them also retains the reference behavior. No AArch64 s0..s4 register is used.
Other temporaries are scratch. Traps transfer to the owning non-returning trap
path rather than returning a fabricated result.

| Slot | Arguments after ctx | Behavior |
| --- | --- | --- |
| `pair-new` | first, second | Store the two i64 words in a checked new pair, clear its validation byte, return the one-based handle |
| `pair-first` | handle | Check handle in `(0,pair-used]`, return first word |
| `pair-second` | handle | Same admission, return second word |
| `string-equal` | two handles | Resolve both byte windows, compare exact length/bytes, return 0/1; retain the reference's absence of UTF-8 validation here |
| `string-index-of` | haystack, needle | Reject an empty needle, validate both full UTF-8 windows, return the first byte offset or -1 |
| `string-substring` | handle, start, end | Require ordered nonnegative byte cuts within length and on code-point boundaries; share the backing bytes in a new validated pair |
| `string-concat` | two handles | Validate both, append in place when A is the pool tail; otherwise copy both into a new pool span; always return a new validated pair |

A string pair stores an offset and byte length. Nonnegative offsets address
the admitted artifact code/literals; negative values encode `~pool-offset`.
Both paths prove offset within its current code/pool window and length within
the remaining window before pointer addition. The trusted context/layout owns
the bases and complete mapped spans; these routines do not accept raw pointers
from guests or make arbitrary integers into string handles.

Validation caches one byte per admitted handle. It accepts canonical UTF-8
and rejects malformed continuation, truncated sequences, overlong encodings,
surrogates and values above U+10FFFF, preserving the reference's rules (see
[RFC 3629 section 4](https://www.rfc-editor.org/rfc/rfc3629.html#section-4)).
The byte pool is append-only from the guest's perspective; the caller must
keep the admitted code and each validated string span immutable.

Pairs charge the cell arena. Concat charges only B's bytes on the A-tail path
and A+B on the copy path, with the same allocation/refusal ordering as the
reference. Substring allocates a pair without charging bytes. Addressable
windows, remaining UTF-8 bytes and byte capacity use subtraction comparisons;
concat also refuses a total length above signed i64 before forming the sum.
This adds explicit overflow refusals rather than permitting a wrapped bound.
Exact malformed-input refusal precedence is not claimed identical.

## Remaining closure

The inline fragments share the slots' exact handle/validation/pair helpers.
They require the caller to preserve s0..s4 and LR, use distinct private label
prefixes, and own the complete mapped context and source spans. Interning
requires prior op-6 byte-charge admission from the sealed owning decision
artifact; its extra arithmetic checks do not replace that authority. The source
bytes must be stable and disjoint from the new pool tail. The mechanism checks
remaining capacity, copies, advances pool-used and allocates a pair with a clear
validation byte; the caller must then validate the result handle. It is not a
general guest-address API or an approval callback.

The pool-pair fragment is for mechanisms that already filled and advanced a
bounded pool span, including stdin. The caller must prove the complemented
offset/length lies within those admitted bytes and preserve the state protocol.
It performs the same checked cell allocation and clears validation; C3 must
still validate the completed result. It does not admit a raw source pointer,
charge bytes twice or accept an unchecked guest handle.

The [C1/C3 source candidate](linux-static-capability-port.md) now calls those
fragments around its native hash computation and real op-6 decision call. The
owning decision routing/profile, full image assembly and native qualification
remain unfinished; wire 3 is still unavailable in the current profile. This
component does not implement the compiler's missing vector/byte/I/O helpers.

The [prelude/context source](linux-static-prelude-port.md) now composes the admitted
slots and binds initialized data. Native source admission/Definition CIDs/behavior,
complete prelude/context integration,
decision code/message placement and ELF construction, reviewed source/lock pins,
and whole compiler self-rebuild remain open under JUN-200/202. The legacy
packager and C loader are migration inventory until their canonical replacement
is integrated and qualified. No hosted CDCI or protection/service change is
introduced by this component.
