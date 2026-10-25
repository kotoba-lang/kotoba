# Canonical GMIR source port in progress

Owning reference: `1ae0811ec3591bf5a3e3d7bee069df928106feca`.
The legacy root has 28 public exports. Its capability-kind table is still
0..7; byte/chunk proposal metadata elsewhere does not admit new kinds here.

The whole GMIR contract remains the acceptance scope: all instruction and
runtime/action tables, scalar/window/slice/atomic/dequant ceilings, vreg and
function identities, literal decoding, canonical keysets, v1/v2/v3 admission,
labels, phi predecessor/critical-edge/fallthrough rules, full module linkage
and named refusal data. No subset validator or compatibility projection is
an accepted replacement.

## Owning literal boundary

`src/kotoba/gmir/rodata.kotoba` is a canonical source candidate for the
three encodings, alignment, byte decoding and content predicate. Public data
values become typed zero-argument accessors. This draft now has a canonical
owning root delegating to the component; owning main and existing native
callers have not been switched or qualified.

A source review found that the first draft's generic document-vector result
could not represent literals beyond the unchanged **32-item document
container limit**. Wrapping a maximum-size native string in a serialized
document also adds overhead. That draft did not preserve the full literal
boundary. The revised candidate uses nominal inputs and typed byte chunks;
it does not widen document/value/ABI limits or narrow the parent grammar.

- `string-input` uses the native string domain (at most 65,536 UTF-8 bytes
  per value); `chunks-input` carries longer logical UTF-8 text with
  `[:list :bytes]`, including units split across chunks and empty chunks.
- `keyword-input` and `invalid-input` retain the distinction between the
  admitted encoding kind and every other kind. The parent adapter must
  retain the original AST/value for its full diagnostics.
- `rodata-bytes` returns `[:option [:ref :gmir.rodata/decoded]]`. `None`
  means invalid content/encoding. Empty hex is `Some` with zero bytes and
  no payload chunks. No allocation, uniqueness or value failure is caught
  and converted into success or empty data.
- `decoded-chunks`, `decoded-byte-count` and checked `decoded-byte-at`
  expose all bytes. Private output pieces are at most 16 KiB; this is an
  allocation strategy, not a logical literal limit. Mutable local vectors
  are copied with `bytes-from-vector-i64` before crossing helper boundaries;
  normal compiler uniqueness admission is still required.

Hex retains exact order, zero bytes, either letter case and empty success;
odd lengths and non-hex characters refuse. GUID accepts exactly the
8-4-4-4-12 shape, reverses the first 4/2/2-byte fields and preserves the final
eight bytes. UCS-2 preserves admitted BMP scalars, embedded zero and one
final two-byte terminator. Astral scalars, surrogates and malformed UTF-8
refuse. Byte reads are bounded against their own chunks. There is no host
string/Java/JS conversion, regex, filesystem/process access, replacement
character, truncation or successful empty fallback.

The revised canonical self-check source retains all 32 original small
cases, with fixed oracle documents of at most 32 elements, and adds 18
chunk/UTF-8 cases. `main` also checks seven complete output patterns and
three refusals after a long prefix: outputs above 32 bytes, 65,536-byte
native strings, 65,537-byte and 1 MiB logical input, UTF-16 expansion and
piece boundaries. Pattern comparison walks forward through every byte,
including the final terminator. A separate `large-internal-case` constructs
and consumes an 8 MiB decoded hex result and returns only i64.

Long values are constructed and consumed internally. These cases do not
admit a value above the canonical boundary traversal budget across a public
export/capability ABI. Per-leaf/list bounds and native arena/fuel/stack
budgets still apply. Cursor records allocate while decoding, so successful
large-input execution and its resource cost remain unqualified. No decoder
or self-check has been typechecked, compiled or run. Source-data inspection
is not evidence of semantic parity or native resource admission.

The original source and four suites are unchanged. Their parent validator,
keyset, firmware arity and whole-program checks remain required. Root/caller
adaptation and resulting Definition CIDs are open; matching literal bytes
do not imply unchanged definition identity.

## Complete contract tables as a supporting component

`src/kotoba/gmir/catalog.kotoba` carries the owning reference's complete
92 instruction keysets, 37 runtime operation arities, 55 x86 privileged
arities, eight existing capability-kind codes, eight dequant formats,
window/slice/atomic families, version set and numeric ceilings. Large maps
are typed lists of nominal entries; each keyset is a typed keyword list.
List order is an implementation detail: consumers use named lookup and set
membership. Do not treat order as a new instruction encoding or wire index.

The data accessors preserve the original public names. Known-format block
limits derive the minimum admitted packed/unpacked span as before. The
native helper returns `[:option :i64]`; an unknown format has no numeric
limit and returns `None`. Root/caller adaptation must propagate that refusal
and retain appropriate diagnostic facts; it must not manufacture a default
or admit unknown formats. This is an explicit API migration candidate, not a
claim that the old throwing host API has already been replaced compatibly.

`instruction-keys-in` and `operation-allowed-in?` allow a validator to reuse
one table instead of allocating the complete catalog for every instruction.
Version admission retains the exact existing exclusions: v1 excludes phi
and tail-call; v2 excludes call and tail-call; v3 includes every table row.
Function-address still needs separate module validation; a table lookup is
not that check. The indexed-memory set remains window + slice + atomics +
the two lock operations. Capability kinds are still exactly 0..7.

The editorial source-data check compares every copied keyset, arity, format,
set member and literal scalar with the pinned reference's data. It does not
run reference code or a generator/compiler. Derived helper expressions
remain subject to native compilation and runtime verification. The added
`test/kotoba/gmir_catalog_cases.kotoba` self-check covers table counts,
uniqueness, lookup/unknown refusal, every row's version admission, all eight
known format limits and both-span maximality, numeric boundaries, indexed
families and key runtime/firmware arities. It has not been compiled or run.
The original four suites remain unchanged and required.

## Identity/scalar boundary and paged input/refusal data

`node.kotoba`, `identity.kotoba` and `outcome.kotoba` add source candidates
for the five identity/scalar exports and the full-data refusal carrier.
The canonical root now delegates to these and the validator below.

The nominal input carries scalar kind/bits, separate namespace/name, raw
text chunks and paged children. No program or long literal enters a generic
document. Namespace absence and an existing empty namespace remain distinct;
namespace/name components retain their own identity even when two values
would print alike. This follows the reference's
[Named/Symbol representation](https://github.com/clojure/clojure/blob/master/src/jvm/clojure/lang/Symbol.java).
`keyword-literal` is a convenience for reader-canonical native literals;
adapters for arbitrary interned host values must supply their actual parts,
including a slash inside an unqualified name, through `keyword-parts` or
`symbol-parts`. A printed-spelling round trip cannot establish that parity.

Text and children retain existing leaf/list bounds. Each collection may have
multiple child pages, so the per-list 16,384-item bound is not imposed as a
new logical instruction-count limit. `child` and `text-slice` report missing
or invalid ranges explicitly. `text-at` uses -1 for out of range, which is
not a byte. Named equality does not equate unrelated scalar values.

The i64 predicate handles exact native i64 and checked decimal integer data,
including the signed extrema, leading zeros and overflow refusal. Negative
accumulation checks before multiply/subtract so `-2^63` requires no positive
out-of-range intermediate. The vreg constructor also accepts arbitrary-width
nonnegative decimal integers, retains all digits in chunks and normalizes
sign/leading zeros. It does not silently reduce them to i64 or introduce a
small GMIR index ceiling. Actual native allocation/value bounds still apply.

`vreg` returns a typed result. Its refusal preserves phase, problem, message
and the full `{:index original-value}` data in nominal nodes. Parent adapters
must propagate these facts into their final native refusal channel; the old
throwing root and callers have not been replaced. `label?` and `function-id?`
operate on explicit components and canonical UTF-8. The added text helpers
validate split UTF-8 and compare canonical strings in UTF-16 code-unit order,
including astral/BMP ordering, for later sorted-name diagnostics.

The identity self-check source includes 25 scalar cases, constructor and
predicate refusals, namespace/name ambiguity, complete refusal facts, text
slicing and chunk boundaries, 16 UTF-8 vectors and seven text-order cases.
It checks a 33-child collection and provides a separate full-page rollover
entry with 16,385 children. All of these native entries now execute successfully;
see the exact receipt below. The node
constructors are data builders: tags alone do not prove a valid reader value,
well-formed map/set/collection, complete IR admission or authority. Full
reader/tag/UTF-8/shape integration and invalid-representation parity remain
part of full qualification; the validator below adds a final representation
check for semantically admitted input. Native allocation/copy/fuel costs remain
unqualified.

## Owning root and whole-program validator source

`src/kotoba/gmir.kotoba` now exposes every original public name, delegating to
the literal, catalog, identity and `validation.kotoba` components. The legacy
root and four suites remain byte-identical provenance. This is a canonical
source candidate with explicit typed migration APIs, not a release or a
claim that legacy callers, source readers, locks and Definition CIDs have
been migrated. Data values are zero-argument accessors; `vreg`/`validate!`
return typed results and literal/format decoders return options. Callers
must propagate all refusal facts and preserve nominal identity/value kinds.

The validator source implements the complete instruction pass, duplicate
labels/unresolved targets, phi checks and v3 function/module linkage in the
reference's order. It reuses the full keyset/runtime/x86 tables. All 32
reference problem symbols are present across constructor/validator source;
that inventory is not proof of equivalent conditions or runtime behavior.

- Instructions retain closed version/keysets, non-nil general register
  checks, indexed/return registers, call/runtime/x86/capability arities,
  incoming shape, exact i64 constants, data/rodata/function addresses,
  nonnegative indices, every memory ceiling and label identity.
- The reference's generic `keep` skips an explicit nil register field. This
  existing admission behavior is transcribed; repairing it requires a
  separate reviewed change. A final representation check rejects hidden
  namespace/name/child payload on atom tags or invalid canonical text.
- Phi values retain block-entry placement, at least two distinct incoming
  predecessors, equality with unconditional-jump predecessors, critical-edge
  refusal and fallthrough refusal. An unlabeled jump's nil predecessor is
  dropped as the reference's `keep` does. Full join/incoming/jumps data is
  retained as nominal map/sets on mismatch.
- Modules retain exact shapes, valid unique names and entry resolution
  before per-function validation. Each function checks arity, all code,
  argument index bounds/distinctness, function-address linkage and call/tail
  arity in order. Diagnostics retain complete names, labels, indices,
  instructions, calls, expected arity and sorted declared names. Sorting
  compares namespace presence, namespace and name in UTF-16 order.
- Success returns the original program. Semantic failure returns phase,
  problem, message and full original/derived instruction data. Only after a
  semantic success is the nominal tree checked for malformed representation;
  the additional `:non-canonical-value` refusal retains the offending node.
  Constructors/tags alone do not establish admission or authority.

`test/kotoba/gmir_validation_cases.kotoba` adds native self-check source:
all 92 instruction rows with positive, each missing key and extra-field
cases; invalid and nil general-register fields; indexed/return registers;
every applicable window tier and invalid memory maximum; all 37 runtime and
55 x86 arities with correct/incorrect argument counts; all eight existing
capability kinds with wire/argument boundaries; and 60 fixed fixtures for
flat/module/phi/linkage/refusal-order/representation/Unicode diagnostics.
Accepted programs and complete refusal payloads are compared recursively,
including bytes, bits, namespace/name and every child; map/set order is not
used as meaning. Arena scopes contain each independent self-check's data
and return only a scalar result. They have now been executed on the native
selfhost route; public resource/authority qualification remains separate.

The complete new self-check image has been compiled and executed natively.
No legacy host/reference oracle was run. The separate source-data inspector
only reads forms/Git data: it checks root
exports/arities, copied table data, problem-symbol inventory, register field
order, fixture labels/operand keys and local/import/type-position/lexical
shapes. It is not the owning reader or a type/target/runtime gate. Full
upstream-corpus mapping and differential/parity/resource/authority execution
remain required; these new cases are not declared a completed replacement
for the original four suites.

`test/kotoba/gmir_canonical_cases.kotoba` provides `main` that calls all four
new literal/catalog/identity/validator entries and propagates their failure
codes. `large-main` separately calls the 8 MiB internal literal and 16,385-
child rollover cases. All eight component/aggregate entries now execute with
exit zero. These are not registered CI checks, a certified harness, or a claim
of assertion-by-assertion replacement of the four historical suites.

## Additional downstream carrier gap

The current Linux-static draft still has artifact/code-facing `:document`
carriers, including `linux_static.kotoba`'s `package`/plan interface and
`normalized-code`. A generic vector/list of code is bounded to 32 elements;
a bytes document is still bounded by its leaf/serialized representation.
This does not establish the full logical artifact domain. The complete
packager/provider/caller route must migrate to typed payload buffers and
prove resource/refusal behavior. A typed assembler or GMIR supporting
component alone does not close this downstream gap. No downstream code was
changed in this source step.

## Remaining whole-component work

The draft now has all public names and the complete validator source wired
at its owning root. Whole-component acceptance remains open: target reader
and type admission, every upstream regression, native execution and all
caller/data/refusal/CID adapters must be verified. Native source readers
must preserve wide integer and namespace/name data without wrapping,
flattening or a printed-spelling round trip. The full artifact/provider/
packager path and proposed capability kinds 8..11 with matching signature,
type, value, lowering and ABI are still required.
An existing language-side mechanical `.kotoba` projection contains an empty
`i64-value?` body and host forms. It is migration inventory, not an owning
canonical implementation or native proof. Do not fill it with stubs or use
it to bypass owning checks.

The final build/packaging/execution closure must use Amu selfhost-built and
rebuilt tools, without CLJK/CLJC/CLJS, NBB/KBB, Node, Clojure/Java/JVM/Graal,
or C compiler/loader/runtime fallbacks. No qualified independent native
compiler entry is currently located. Native EDN-reader/target predicates,
full positive/refusal/resource/authority corpus, actual execution, owning
pins/CIDs and full self-rebuild remain open. No workflow, protection, live
service or route changes are part of this source work.

This supporting-library port does not replace the adopted Amu compiler
core/lineage or alter its Embench baseline. The measured compiler's complete
frontend, lowering, optimizer and backend behavior must be preserved when
the whole closure is integrated. No benchmark or compiler-core change is
claimed here.

## Native MIR integration, 2026-10-23

The seven GMIR production units are compiled/linked with the complete canonical
MIR root by the measured Amu selfhost successor, using exact source SHA-256
pins and all roots. The full eight-component ordinary MIR aggregate exits
zero; native catalog cases compare all 92 GMIR direct lookup rows with the
public table. Pure scalar helpers reclaim only internal temporaries, map-key
comparison preserves namespace presence and exact bytes, and Option fallbacks
are lazy. These are production-integration results, not execution of every
GMIR historical suite or public CLI/target/resolver/CID admission.

## Whole GMIR native corpus, 2026-10-23

[correctness.json](evidence/native-selfhost-20261023/correctness.json) records
all 12 production/test inputs, both source roots and their exact KSL1 SHA-256
pins. Amu selfhost G7 compiles and links the complete image; all eight exports
exit zero: the ordinary aggregate, four components, two large components and
the whole large aggregate. The same native compiler/packager reruns all eight
MIR ordinary/large entries after the decoder update and they also exit zero.

Literal checks include all 32 fixed and 18 split-chunk cases, ten long cases,
and every output byte of an 8 MiB decoded literal. Identity checks include
16,385 children and full page rollover. Validation checks retain all 92
instruction rows and missing/extra fields, all 37 runtime and 55 privileged
arities (both short and long refusal directions), eight capability kinds and
60 full-data fixtures. Nonempty `vector-new` fixtures were corrected to the
native primitive's declared vector-literal form; byte values/cases are kept.

The initial rodata run exhausted the unchanged pair arena. A private
three-word scalar cursor now advances through immutable input chunks, and
only a completed output piece gets a cursor record. No per-byte nominal
record is retained. Empty chunks, split UTF-8, malformed/astral/surrogate
refusal, hex/GUID byte ordering and terminators remain checked. All original
allocator limits and capability grants are unchanged. This is native corpus
execution, not a public CI/controller registration or full legacy-assertion,
caller/reader/Definition CID qualification. The historical source and all
four suites remain byte-identical.
