# Canonical Mach-O 64-bit object source

Tracking: [JUN-201](https://linear.app/kotobalabs/issue/JUN-201),
[JUN-200](https://linear.app/kotobalabs/issue/JUN-200), Kotoba Labs.

`src/kotoba/object/macho64.kotoba` ports the entire public boundary of owning
`macho64.cljk` at main `9510241bf8892a2d700877ad5fa784f410dcbd51`, reference blob
`d98d70ae94b5ddecdeaf919d2f8513523cdb4e5c`. It imports only this component's
canonical `unsigned.kotoba`. Target selection, entry/ABI policy and actual
instruction/data bytes remain caller decisions.

This is an unqualified source candidate: 358 lines, 46 functions, SHA-256
`bb4571bd367156c323f2808875241ed3a9528b1a4354f36cdaba1a1c2135fa85`, blob
`31ff1ee074e5aeeea29f294b74fecef6fa58fabf`.
No encoder, generator, compiler build, emitted object, linker, native runtime
or test was executed. Existing suites were read as contract inventory only.

## Complete public boundary

| Entry | Typed arguments | Retained meaning |
| --- | --- | --- |
| `little-endian` | value document, width i64 | Strict unsigned widths 1/2/4/8, full uint64 domain, overflow refusal |
| `align-up` | value document, exponent i64 | Arbitrary natural value, exponent 0..15, round up to 2^exponent |
| `encode-object` | options document | Complete ARM64/x86-64 MH_OBJECT, all sections/symbols/relocations/build metadata |

All three return `:kotoba.object.macho64/result`: `bytes`, `value`, `error`,
`field`. Only `error=:ok` authorizes consumption. Alignment returns its number
in `value`; serializers return bytes. Failures expose no partial object/value.
Native consumers must adapt the explicit result API and propagate errors.

Natural numbers use ordinary nonnegative i64 documents or the shared explicit
u32 limb documents described in [the unsigned source record](pe32plus-kotoba-port.md).
The compatibility `{:elf64/u64 [low32 high32]}` representation is accepted.
Strict width/range checks precede the shared truncating serializer, preserving
the Mach-O/PE distinction. Public alignment retains values beyond uint64;
no float, hosted bigint or i64-only value restriction replaces that domain.

## Complete object path

The port retains both machine types/subtypes, all eleven existing platforms,
three load commands, flags, and packed minimum-OS/SDK version triples. Defaults
apply to missing keys; explicit null versions/flags/description refuse.
Internal metadata stays in typed section/layout/string-table records with
literal record selectors. Symbol indexes use document map association,
including a valid zero index, rather than set construction.

Sections retain caller order and independent address/file alignment. Names
retain 1..16 printable ASCII bytes and fixed zero padding; flags are uint32.
Symbols retain caller order, underscore-prefixed 2..255 printable ASCII names,
duplicate refusal, one-based sections and section-relative values including
the section end. Undefined symbols require a truthy external flag and zero
value. Defined symbols add the laid-out section address; description is
uint16. External flags preserve the reference's truthiness: only null/false
are false. The string table starts with NUL, records every name offset and is
padded to eight bytes.

| Machine | All retained relocation types | Width / PC relative |
| --- | --- | --- |
| ARM64 | unsigned=0, branch26=2, page21=3, pageoff12=4 | unsigned: 8/false; branch/page21: 4/true; pageoff12: 4/false |
| x86-64 | unsigned=0, signed=1, branch=2, got-load=3, got=4, tlv=9 | unsigned: 8/false; all others: 4/true |

Relocation descriptors require exactly `offset`, `type`, `symbol`; unknown
types/symbols, extra/missing keys and a fixup extending beyond section bytes
refuse. The complete external relocation word retains symbol index, PC
relative, width exponent, external bit and type code. Each nonempty relocation
region is aligned to four bytes; empty regions retain zero offset. The symbol
region is aligned to eight bytes after all relocation regions.

The original limits remain: 1..32 sections, 1..4096 symbols, at most 65535
relocations per section and 64 MiB per object. Byte regions validate every
byte. Bounded placement and aggregate object-size checks precede filling large
gaps/materializing the final object; names are length-checked before UTF-8
allocation. Vector/list collections and explicit byte documents are supported
at the data boundary. Malformed document shapes refuse explicitly. Diagnostic
precedence is not claimed identical to the previous throwing implementation.

## Source review and remaining acceptance

The static source reader found balanced delimiters, matching own/import call
arities after thread expansion, known heads and no local data-as-function
calls. The record reader inspected ten own constructors and 43 own accesses,
with no undeclared fields, count mismatch or computed record selector. These
readers do not invoke Kotoba code or generate IR/machine bytes.

The source field ledger has all three original export names and records:
header 32 bytes; segment command base 72; section 80 (two 16-byte names plus
48 numeric/reserved bytes); build-version and symtab commands 24 each; symbol
16; relocation 8. It also reads both CPU cases, eleven platform cases and ten
relocation cases. These are literal source layouts, not observed output bytes.
Layout review used Apple's primary
[Mach-O declarations](https://github.com/apple-oss-distributions/xnu/blob/main/EXTERNAL_HEADERS/mach-o/loader.h),
[ARM64 relocation definitions](https://github.com/apple-oss-distributions/cctools/blob/main/include/mach-o/arm64/reloc.h),
and [x86-64 relocation definitions](https://github.com/apple-oss-distributions/cctools/blob/main/include/mach-o/x86_64/reloc.h).
The supported subset and resource caps are this component's retained policy.

ELF64, PE32+ and Mach-O now all have complete public source candidates in this
draft. Native source admission/types, Definition CIDs, allocation behavior,
emitted bytes, positive/refusal/resource behavior, target consumer adaptation,
owning-main landing and exact Amu source/lock pins remain open. No object has
been linked or executed. Keep the existing hosted sources as migration
provenance until consumer/qualification work permits retirement; there is no
permanent twin, host fallback, C-loader pin or KBB-first condition. Retired
legacy CI is not replaced by a claimed native gate.
