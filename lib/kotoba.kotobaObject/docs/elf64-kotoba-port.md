# Canonical ELF64 encoder source

Tracking: [JUN-201](https://linear.app/kotobalabs/issue/JUN-201),
[JUN-200](https://linear.app/kotobalabs/issue/JUN-200).

`src/kotoba/object/elf64.kotoba` ports all seven public exports of the owning
ELF64 module, main `9510241bf8892a2d700877ad5fa784f410dcbd51`, source blob
`b451737ac85629e9a5d64a149b0aa4e8cc8d57c0`. It has no namespace imports,
host exceptions, FFI, process, filesystem or legacy-runtime calls. Pure typed
records/documents/vectors and i64 bit operations implement the complete record
boundary. Target layout, relocation selection, image policy and file writing
remain consumer responsibilities.

This is a source candidate. No encoder, compiler build, native admission,
artifact generation, byte comparison, runtime or test was executed. Static
source inventory: 193 lines / 29 functions, balanced delimiters, own-call
arities after thread expansion, known heads and no local data-as-function calls.
Own record inventory read five constructors and seventeen field accesses without
field-count/key mismatches. Source SHA-256:
`898ac7a77018f496c46c0673666ea0876a3a643aa805b2c66e308f71c3691f1a`.
The high/low byte selector now branches between literal record fields, as
required by the current owning validator, instead of using a computed key.

## Complete public boundary

| API | Typed inputs | Source field-width total |
| --- | --- | --- |
| `little-endian` | `value :document`, `width :i64` | 1, 2, 4 or 8 |
| `pad-to` | `bytes :vector-i64`, `size :i64` | Complete requested size |
| `encode-header` | `options :document` | 64 |
| `encode-program-header` | `options :document` | 56 |
| `encode-section-header` | `options :document` | 64 |
| `encode-rela` | `options :document` | 24 |
| `encode-symbol` | `options :document` | 24 |

The export names match the reference exactly. A literal source-width ledger
read field order/widths, including the 16-byte identification prefix; no encoder
was called to obtain those totals. The record layouts correspond to the
[ELF header](https://gabi.xinuos.com/elf/02-eheader.html),
[symbol table](https://gabi.xinuos.com/elf/05-symtab.html) and
[relocation](https://gabi.xinuos.com/elf/06-reloc.html) specification. Source
structure is not proof of native byte/ABI compatibility.

Every API returns `:kotoba.object.elf64/result` with `bytes`, `error`, `field`.
Only `error=:ok` permits consuming bytes. Failure returns empty bytes, a named
error and the actual failing input field. Native consumers must inspect and
propagate that result explicitly; it does not coerce to the legacy byte vector
or throw a hosted exception. No partial record is returned on failure.

## Entire integer domain

Ordinary `document-i64` values retain signed two's-complement semantics and
the reference's mixed signed/unsigned width bounds:

| Width | Minimum signed input | Maximum unsigned input |
| --- | --- | --- |
| 1 | -128 | 255 |
| 2 | -32768 | 65535 |
| 4 | -2147483648 | 4294967295 |
| 8 | -9223372036854775808 | 18446744073709551615 |

For positive values above i64 maximum, the canonical document is
`{:elf64/u64 [low32 high32]}`. Each limb is an i64 in 0..4294967295; the map
has exactly this one key and the vector exactly two limbs. This covers every
unsigned 64-bit value, without rounding, an out-of-range literal, a promoting
multiply or a new small-value-only limit. For example, limbs `[0 2147483648]`
represent 2^63, and `[4294967295 4294967295]` represent 2^64-1. The same form
is allowed in numeric header/section/symbol/relocation fields. Narrow widths
require high32=0 and the remaining value to fit. Caller literal/API conversion
is explicit integration work, not claimed existing source compatibility.

Logical i64 shifts extract signed values' two's-complement bytes. Unsigned
values select a limb and shifts 0..24 within it; no intermediate 2^64 is formed.
Width, shape and range errors refuse rather than silently truncating. Padding
has no arbitrary new size cap: it requires a nonnegative i64 size, admitted
byte input, and an input length no larger than that target. Actual allocation
and resource behavior still need whole native qualification.

## Options, enums and records

Map field presence is explicit: a missing key receives the documented default;
an explicitly null numeric field is refused. A null options document acts as
the reference's empty options map. Non-map options refuse. Program-header
physical-address keeps the reference null/false fallback to virtual-address,
while explicit zero remains zero. Header program-entry size is zero only for
zero program-header count, otherwise 56. Other reference defaults and ignored
unknown keys are retained.

All nineteen named enum entries are retained: object/machine/program/section
kinds, including null=0. Nonnegative numeric enum values remain available for
processor/OS/reserved types, subject to their actual field width. This module
does not invent a target/grant admission policy.

RELA emits offset64, type32, symbol32 and addend64 in that order, including
the high-bit symbol-index cases. Relocation type remains strictly unsigned32.
Other fields keep the reference generic width contract; in particular its
symbol-index helper also admitted representable signed32 bit patterns. No
unbounded wide product is constructed for r_info. Symbol info/other/section
fields retain their 1/1/2-byte widths and value/size their 8-byte widths.

The fallible API, explicit unsigned representation, malformed options/tag
refusals and non-byte padding refusal are intentional boundary changes. Native
positive/negative behavior, diagnostic precedence and Definition CIDs are open;
reading the former suites does not execute or qualify them.

## CDCI cleanup and remaining closure

The removed `.github/workflows/test.yml` used JVM/Clojure and a pinned CLJK
compatibility loader. Its remote workflow id 330439398 was already
`disabled_manually`; main protection returned 404 and repository rulesets were
empty. This patch prepares removal of that obsolete definition and the KBB
development instruction. It changes no protection setting and supplies no
replacement hosted or unconditional-green gate.

The target is canonical Kotoba / Amu selfhost only. Complete native compiler
and consumer source admission, byte/refusal/resource execution, Definition CIDs,
reviewed owning-main/source/lock integration and self-rebuild remain required.
The [PE32+ candidate](pe32plus-kotoba-port.md) and
[Mach-O candidate](macho64-kotoba-port.md) now supply their complete public
source boundaries. Complete consumer closure remains open; these source
modules do not qualify the whole repository's native migration.
Existing hosted files are migration provenance, without a permanent twin or
fallback requirement. Native CDCI may be enabled only with its actual full
compiler/consumer evidence. No existing service or production route was changed.
