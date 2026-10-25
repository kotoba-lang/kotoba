# kotoba-component

Amu's Component **仕立て** — lifts core modules through the Canonical ABI.

This is compile-time composition, not kototama's runtime link. It does not
parse `.kotoba` source, execute components, or decide grants.
[`amu`](https://github.com/kotoba-lang/amu) weaves; this is one finishing
pass of that weave. See root ADR-2608139980.

**Tier**: `T2`  **Role**: `backend` of amu

Split out of the overloaded core repos by ADR-2607266000 so that each
responsibility has exactly one owner and the dependency direction is
checkable from outside.

## Owns

- `kotoba.component.core`
- `kotoba.component.composition`
- `kotoba.component.admission`
- `kotoba.component.artifact`
- `kotoba.component.wit`

## Does not own

- parse .kotoba source
- execute components
- decide grants

## Depends on

- `kotoba-lang/osaho` (formerly `kotoba-kir`)
- `kotoba-lang/kotoba-wasm`

## Structural union boundary

`option<T>` and `result<T, E>` identity exports use the same active-case
Canonical ABI validation as sealed variants. Payloads may be canonical
scalars, bounded strings/keywords, or finite sealed records recursively
containing those leaves. Validation is case-dependent: malformed inactive
joined slots are ignored, while malformed leaves in the selected case trap.

Bounded lists of scalars, strings/keywords, structural options/results, or
finite records recursively containing those leaves additionally validate item
count, alignment, pointer overflow, and every outer and inner arena range in
the selected case. Each item's in-memory discriminant is range-checked before
only its active union case is visited. Bool fields and string/keyword byte
bounds are checked for every active item.
All indirect leaves in one value share KIR's 1 MiB aggregate byte budget, and
all nested list nodes share one 16,384-item budget. Per-node limits therefore
cannot multiply into a host-memory or traversal denial of service. Recursive
validation uses depth-specific loop locals, so an inner traversal cannot
clobber its outer cursor. Identity lowering borrows the complete item graph
through Canonical lift; it neither frees nor mutates that graph, and
post-return resets the arena only after lift has finished.

Nested `option`/`result` payloads recursively validate each inner
discriminant and only the selected inner case before storing the same nested
in-memory union shape. Recursive nominal records remain fail-closed; nested
structural lists are admitted under the shared cardinality/depth budgets.

Non-identity `option`/`result` matches can consume scalar payloads and finite
records whose recursive leaves are `s64`, `float32`, `float64`, or `bool`.
Record binders remain sealed: branch code may access them only through a
statically resolved `record-get` chain to an admitted scalar leaf. Every bool
leaf in the selected case is validated even when the branch does not read it;
inactive joined slots are never interpreted. Branch expressions still use the
shared typed core-Wasm emitter rather than a Component-specific compiler.

Those match modules may also call scalar named capabilities. Every
`typed-cap-call` must resolve to an explicit standard32 WIT import; canonical
adapters never fall back to the generic host ABI. The match adapter, ordinary
scalar helpers, fuel global, and capability calls remain in one core module,
so composition does not introduce a second expression compiler or ambient
WASI authority.

An `option<list<T>>` match may reconstruct its selected list, pass that bounded
value to a named capability with the same request/result descriptor, and
immediately match the returned option when `T` is `s64`, `float64`, `string`,
`keyword`, `bool`, a finite record recursively containing numeric and bool
fields, or another bounded list recursively ending in `s64`/`float64`. The
branch still compiles through the shared core-Wasm expression module; the
generated standard32 adapter validates the request and returned list bounds
and uses caller-allocated result storage. It visits every active inline bool,
indirect string-like item, and nested pointer/count graph even though the
branch observes only the outer count. Bool bytes must be 0/1; strings reject
pointer overflow or out-of-memory ranges and share the 1 MiB byte budget;
all nested nodes share the 16,384-item budget. Other aggregate
branch/capability shapes fail closed until their Canonical codec is admitted
explicitly.

A symmetric `result<list<T>, list<T>>` match has the same property for both
`ok` and `err`, including string-like, record bool-field, and nested-list
validation. The request case is explicit, and the returned discriminant and
complete active list graph are validated before either branch can observe its
count.

The same bounded indirect codec handles `string` and `keyword` payloads for
option and symmetric result matches. UTF-8 byte bounds use payload alignment
1 while the enclosing union result area retains its independent Canonical
alignment; both are checked before `string-byte-length` is exposed.

An `option` carrying a sealed finite scalar record may likewise reconstruct
the selected record, call a named capability, and project one scalar field
from the returned `some`. The request uses the record's canonical flat slots;
the returned option result area, discriminant, and every active bool field are
validated even when the projected field is different.

A direct named capability may also transport one bounded structural
`option`/`result` unchanged. Its leaves may be scalars, strings/keywords,
finite sealed records, nested structural unions, or bounded lists recursively
containing any of those admitted values (including other lists). Both
application and provider use the same recursive Canonical ABI layout, validate
the selected case, every active record bool, and every nested pointer/length
pair. All active indirect leaves share the 1 MiB byte budget and all active
list nodes share the 16,384-item budget; the bounded arena is sized for the
widest permitted active payload. Bare nominal records remain on the
schema-aware variant path; recursive nominal records and unsupported aggregate
shapes fail closed instead of falling back to an ambient host ABI.

Selected string/keyword leaves may feed `string-byte-length` without becoming
host objects. The shared core emitter consumes their Canonical `(ptr,len)`
slots and checks the declared byte bound, unsigned end-pointer overflow, and
the module's actual memory size. Every selected indirect leaf is validated
even when branch code ignores it; inactive union slots remain uninterpreted.
Raw indirect binders and unrelated string operations remain fail-closed.

Selected `list<s64>`/`list<f64>` leaves may likewise feed only their matching
count operation. The shared core emitter checks pointer alignment, item
bounds, unsigned byte-size/range overflow, and actual memory size. Selected
but unread lists are still validated; inactive union slots stay lazy.
Their matching `vector-at`/`vector-f64-at` operation is also admitted. It
reuses the same checks, validates the unsigned index against the selected
count, and only then loads one scalar element; other list operations remain
closed.
The non-trapping `vector-get`/`vector-f64-get` forms validate the selected
list just as strictly, then return their explicit fallback for a negative or
out-of-range index without forming a memory address.

Top-level `vector-drop`/`vector-assoc`/`vector-conj` and their f64 forms
produce owned Canonical list results. They validate the complete borrowed
input, allocate and copy a fresh output buffer, apply the bounded transform,
write the standard pointer/count result area, and release transient storage
through post-return. No transform mutates or aliases the input buffer.

`option`/`result` matches may also return an owned `list<s64>` or
`list<float64>`. Each branch can copy a selected payload list, another vector
parameter, or a bounded vector literal, optionally applying the corresponding
`drop`, `assoc`, or `conj`. All ordinary vector parameters are validated at
entry; payload validation remains selected-case-only and covers every bool,
string, and list leaf even when the branch does not read it. Both paths then
share the same fresh-buffer, result-area, and post-return ownership contract
as the top-level transforms.

## Test

```bash
kbb -M:test
```

## Execution contract entrypoints

Neutral descriptors are imported from `kotoba.core.execution` (core-contracts).
Component/WIT profiles and unchanged mixed v1 identity/lease codecs are imported
from `kotoba.abi.component` (abi). The old `kotoba.abi.contract` facade remains
readable for existing callers; new production imports select their owner.
The [integration contract](spec/execution-profile-integration.edn) records this
cutover. Existing v1 blocks/WIT/CIDs remain unchanged; v2 neutral identities
require a verified target binding and fresh CID/signature. This change does not
enable v2 runtime admission or claim Q9/native qualification.
