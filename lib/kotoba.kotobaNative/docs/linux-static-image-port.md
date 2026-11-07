# Canonical complete Linux-static image source

Update: [complete vector arena composition](linux-static-vectors-port.md)
adds real table/item regions, sixteen implemented source slots and complete
vector budget metadata. Earlier source counts are labelled provenance.

Tracking: [JUN-201](https://linear.app/kotobalabs/issue/JUN-201),
[JUN-200](https://linear.app/kotobalabs/issue/JUN-200), Kotoba Labs.

`src/kotoba/native/linux_static.kotoba` connects the complete canonical
planner, register-IR assembler, prelude and context sources to the owning
ELF64 encoder. Reference: `linux_static.cljk`, main
`535ca0a3e7ec1c4b4496c8ea12b18436838cbb47`, blob
`0ab7132ae38f4fd6fb75b107909c1854559160cf`.
The new source is 326 lines / 46 functions, SHA-256
`2822b1575732fbeacf12bfe4e10f7ad325f47069d5e705ff321eb06e15819a44`, blob
`bed19a291bb3fe60fb63340c3c77e675b8cb32ea`.

This is an unqualified source candidate. No package/encoder/generator, compiler
build, native admission, assembler/emitted artifact, ELF loader, syscall,
guest/runtime or test was executed. Static readers inspect source forms as
data; they do not evaluate Kotoba or generate IR/bytes.

## Public API and complete returned contract

All six original export names remain. `targets []` and `implemented-slots []`
are explicit typed accessors for the former values. `plan`, `image-layout`
and `slot-names` delegate to the complete owning planning source and return
its typed result. No smaller planning policy is introduced here.

`package [artifact profile overrides]` returns
`:linux.static.image/result`: `bytes`, `value`, `error`, `data`. The caller
passes an empty override document for the former two-argument convenience
call. Only `error=:ok` permits consuming the complete ELF bytes and metadata
in `value`; failure exposes neither partial bytes nor metadata. Plan,
assembler, context and ELF errors propagate with stage/field/position details.
Native consumers must adapt this typed API; the old hosted entry is unchanged.

The metadata retains all 23 non-payload keys: format, target, entry and source
entry, both entry addresses, text/prelude/code/data offsets/sizes, budgets,
fuel, slot states, section names, empty imports, null interpreter/dynamic,
grant, fs-scope, spawn policy and decision-code regions. The original payload
key is the result record's separate `bytes` field. Decision region addresses
are file offsets, while external assembler labels use virtual addresses.
Both target profiles and the original fixed image base/page layout remain.

## Full sealed code and two-pass composition

The public package entry calls the real owning artifact seal verifier before
planning or assembling. It accepts only a listed Linux-static target and a
zero-arity exported entry, checks the actual entry offset inside guest bytes,
and obtains the full plan/profile admission. Capability plans retain the
planner's independent real seal/ISA/export checks on both decision artifacts.
There is no injected verifier, cached approval or always-valid seal path.

Pure plans append no decision code. Capability plans place the complete C1
and handler decision bodies after guest bytes at independent 16-byte
boundaries. All three actual exports (`cap-admitted`, C1 `decide`, handler
`decide`) resolve to checked offsets within their owning code. Their bytes,
padding and both region records are preserved. Guest and decision integer
code values retain low-byte normalization; explicit byte documents and
vector/list code containers are supported. Malformed shapes refuse.

The provisional full prelude is assembled at the real text base using the
zero-text provisional data layout and provisional external addresses. Its
actual byte count and `text-end` label determine guest placement. Final
decision placement and complete text size determine the real data/arena/
scratch layout. A new complete prelude then uses that layout and actual guest
entry/decision addresses. Assembly must reproduce both the first size and
the exact text-end label. Context serialization receives the final assembler
labels and corresponding prelude slot bindings, not provisional pointers.

The checked 1024-byte initialized context comes from the existing canonical
context component, including real handler/slot pointers and all 256 grant
bits. The complete text is prelude + unchanged normalized guest + complete
decision tail. Checked sums/alignment reject overflow before placement or
large filling. The assembler limit is the available positive-i64 address
domain, not a new frozen small-image cap. Runtime allocation behavior still
requires qualification. ABI v11 remains the implemented reference format;
other required ABI support remains work and is not a C-loader pin condition.

## Complete owning ELF framing

The canonical owning encoder supplies the 64-byte ELF64 header, all three
56-byte program headers and four non-null 64-byte section headers. The image
retains RX text, RW initialized/BSS data and non-executable GNU_STACK; the
five section entries are null/text/data/bss/shstrtab. It retains the exact
name table, name indexes, alignments, 1024 initialized file bytes, page-based
BSS start and full memory size. Owning padding fills text/data/section gaps;
the expected final file length is checked. No local ELF encoder, interpreter,
dynamic segment, host assembler or C loader is used by this source.

Lower dependency: [kotoba-object #8](https://github.com/kotoba-lang/kotoba-object/pull/8),
head `c8b97ec9e3dbc6a8cba1e6ac4a66dadc36a9a0f7`, ELF source blob
`59a2d23705a5850326eb6fc2be6dae9fc7f38f83`. It is draft/open/unmerged.
The source graph review reads that candidate; native's current owning pins
have not been advanced to it. Owning-main landing and exact reviewed source/
lock integration are real open dependencies. PE/Mach-O target consumer work
is not a Linux-static selfhost blocker.
The [artifact pin review](linux-static-artifact-pin.md) selects owning artifact
main's canonical core, the same core blob in Amu's existing root revision.
Root pin/lock normalization, digest semantics and the real hash provider remain
unqualified.

## Source evidence and actual remaining work

Static own-source/record review found balanced delimiters, known heads,
matching call arities and eight own constructors / 26 own accesses. A graph
reader inspected all 13 canonical Linux-static modules plus owning ELF64
and pinned canonical artifact core: 32 schemas, 531 imported calls, 414 record
uses and 556 explicit type argument positions after thread expansion, with
no source-contract findings. It reads the owning `artifact/valid-seal?` API;
the hash capability, digest semantics and runtime remain unqualified.
The export/metadata/frame ledger reads all six original names, 23 metadata
keys, three program-header calls and four section-header calls. These are
source observations, not native type or output-byte proof.

Whole native source/type admission, Definition CIDs, emitted positive/refusal/
byte/resource behavior, actual verifier/image execution, general vector/byte/
I/O runtime helper coverage and required ABI support remain open. The actual
hash provider/profile route is still missing in the previously read owner;
source computation/placement does not make it available. Keep real seal
checks. Reviewed owning-main/pins, Amu-produced compiler generations and whole
self-rebuild remain under JUN-200/201/202 before native-only CDCI qualification.
No workflow, protection setting, service or production route changes here.
