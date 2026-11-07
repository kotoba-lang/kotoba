# Canonical Linux-static assembler source port

Tracking: [JUN-201](https://linear.app/kotobalabs/issue/JUN-201),
[JUN-200](https://linear.app/kotobalabs/issue/JUN-200).

## Source and scope

Base: owning main `535ca0a3e7ec1c4b4496c8ea12b18436838cbb47`.
Reference: `src/kotoba/native/linux_static.cljk`, Git blob
`0ab7132ae38f4fd6fb75b107909c1854559160cf`, register tables and the complete
two-ISA size/encode/assemble implementation. This port adds canonical
`src/kotoba/native/linux_static_assembler.kotoba` without executing or importing
the hosted implementation. It has no namespace dependencies, FFI, loader,
external assembler or process calls.

All 29 register-IR operations are retained on both ISAs. This is a source
port of that complete assembler component. It is not the complete Linux
static packager, native backend or compiler, and it does not yet retire the
hosted packager entrypoint. The old source and fixtures remain migration
inventory. No implementation or test harness was run for this change.

## Typed boundary

`instruction` constructs a `:linux.static/instruction` record with
`op aux d s b i n label data`. Unused keyword fields may be `:none`; unused
`n` and `data` may be zero and an empty vector. Register names and aliases
remain those of the old virtual register table. Label names remain keywords,
including qualified generated labels.

| Existing IR | Typed fields used |
| --- | --- |
| `[:label name]` | `label=name` |
| `[:li d imm]` | `d`, `n=imm` |
| `[:la d name]` | `d`, `label=name` |
| `[:mov d s]` | `d`, `s` |
| `[:ld d b off]`, `[:st s b off]` | destination/source respectively in `d`, base in `b`, displacement in `n` |
| `[:ldb d b i]`, `[:stb s b i]` | destination/source respectively in `d`, `b`, `i` |
| `[:alu operation d s]`, `[:alui operation d imm]` | `aux=operation`, `d`, and `s` or `n=imm` |
| `[:shli d n]`, `[:shri d n]` | `d`, `n` |
| `[:not d]`, `[:neg d]`, `[:push d]`, `[:pop d]` | `d` |
| `[:bcc condition name]` | `aux=condition`, `label=name` |
| `[:b name]`, `[:call name]` | `label=name` |
| `[:ld-sp d off]`, `[:lea-sp d off]` | `d`, `n=off` |
| `[:udiv10 quotient remainder source]` | `d=quotient`, `b=remainder`, `s=source`; the old scratch-register behavior is retained |
| `[:ret]`, `[:syscall]`, `[:trap]`, `[:save-lr]`, `[:restore-lr]` | `op` only; LR operations remain zero-sized on x86_64 |
| `[:bytes bytes]` | `data=bytes` |
| `[:align alignment]` | `n=alignment`; alignment uses the absolute PC |

`label` constructs an external label with a nonnegative absolute address.
`instruction-size` returns a size or `-1` for an unknown ISA/operation; it is
not operand admission. `assemble` accepts the ISA (`:x86_64` or `:aarch64`),
nonnegative base, typed instruction list, external label list, and a caller's
nonnegative output-byte limit. The caller derives that limit from the
applicable profile; the assembler grants no capability or resource budget.

The result holds `bytes`, the resolved `labels`, `error`, and `at`. Only
`error=:ok` is success. Failures contain no partial output bytes; `at` identifies
the offending instruction or external label, or is `-1` for invocation errors.
The label list uses explicit traversal instead of a host hash map; this
changes its representation without introducing a fixed label-count subset.

## Encoding and refusal review

The source preserves the x86 REX/ModRM/SIB encodings, stack forms, relative
displacements, little-endian immediates, division scratch sequence, and both
ISAs' register aliases and condition/ALU maps. The AArch64 port retains
four-word immediate materialization, short/long ALU immediate selection,
ADR and branch PC conventions, scaled load/store, LR save/restore and its
division scratch sequence. Native binary bit primitives replace variadic
host operations; no hosted numeric conversion remains.

The two-pass checks retain duplicate/undefined labels, size-table agreement
and final layout agreement. Additional typed-boundary refusals make malformed
or unencodable inputs explicit: unknown ISA/register/operation/condition/ALU,
invalid raw byte/alignment/immediate, unaligned AArch64 instruction, relative
range/alignment overflow, invalid external labels, output limit and signed
address overflow. Such inputs must not silently truncate into a valid-looking
artifact. Valid source formulas have been reviewed against the reference;
emitted-byte parity has not been measured.

Static source inventory records the same 29 encoder case names and the same
27 register aliases per ISA, balanced delimiters, no unresolved call heads,
and binary arities for the native bit primitives. Candidate source SHA-256:
`cc0943562e25c0772e11d68cf1d96b9412cc02eadc8492e4d6d1fff78a23c13a`.
These are source observations, not executed encoder results. No test was
added or run, and no compiler build or generated artifact was executed.

## Remaining dependency chain

1. Admit and build this whole component with Amu selfhost, account for its
   Definition CIDs and qualify all positive/refusal behavior and exact emitted
   bytes on both ISAs. No legacy host or C loader is an accepted fallback.
2. Qualify the [complete image source composition](linux-static-image-port.md)
   connecting canonical planning, prelude/handler IR, both assembly passes,
   sealed decision placement, context binding and owning ELF framing. Those
   source components are present; the hosted entry still does not call them.
   The owning ELF source candidate and exact reviewed pins remain dependencies.
3. Complete the compiler's required vector/string/byte and I/O runtime helper
   closure. The old static packager's implemented-slot list is smaller than
   the seed runtime profile; an assembler port cannot fill that gap.
4. Integrate the pinned packager and runtime into native bootstrap and the full
   compiler/build/launcher closure. Record actual loaderless artifacts and
   compiler generations, process traces, source/lock and output digests, then
   self-rebuild the complete compiler. A scalar seed ELF or source admission
   alone cannot establish this acceptance.

No new CI, success status, app deployment, service stop or production cutover
is introduced. The shared checkout's unrelated WIP is preserved.
