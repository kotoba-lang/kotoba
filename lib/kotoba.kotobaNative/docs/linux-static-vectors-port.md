# Complete native vector arena source

Update: [complete bytes primitives](linux-static-bytes-port.md) adds four
operations and their real profile/prelude/failure composition. The original
eight vector bodies remain; initial function/slot counts below are provenance.

Tracking: [JUN-241](https://linear.app/kotobalabs/issue/JUN-241),
[JUN-200](https://linear.app/kotobalabs/issue/JUN-200),
[JUN-201](https://linear.app/kotobalabs/issue/JUN-201),
[JUN-202](https://linear.app/kotobalabs/issue/JUN-202), Kotoba Labs.

`linux_static_vectors.kotoba` supplies the complete eight-operation vector
arena component as canonical typed instruction IR for both existing ISAs.
It has no C/FFI, hosted runtime, external assembler or generated-header input.
It is a source candidate. No project implementation, generator, assembler,
compiler, native admission, artifact, syscall, runtime or test was executed;
no tests were added. Source inspection does not qualify a compiler or CDCI.

## Whole component

| Slot | Complete operation |
| --- | --- |
| vector-new-empty | Fresh real handle, zero items, slice at current item top |
| vector-alloc | Bounded nonnegative count, fresh zero-filled slice and handle; zero admitted |
| vector-count | Validate handle and descriptor span, return its own length |
| vector-at | Validate handle/span/index, read exactly one full word |
| vector-conj | Preserve prior slice; tail appends one fresh word, interior slices copy first; fresh handle |
| vector-assoc | Validate index, always copy the full slice before changing one item |
| vector-assoc-in-place | Validate index, store one word, return the same handle, allocate nothing |
| vector-drop | Validate inclusive end bound, publish a suffix view without item allocation; zero admitted |

The f64 aliases share the same full-word storage. No float conversion or
smaller literal-only vector path substitutes for these operations. Compiler
ownership proof is still mandatory for selecting assoc-in-place; the runtime
checks memory safety and does not invent an alias proof. Empty/interior/view
slices retain distinct handles and their own lengths. Fuel at source
constructors remains owned by compiler lowering, without a second helper
charge.

The descriptor's offset/length is proved inside the used item window before
forming an address. Capacity checks compare subtraction remainders rather
than wrapping sums. All copying destinations are the fresh item tail. A
published handle cannot observe an uninitialized slice. Invalid handles,
indices, lengths and unknown slots refuse, without a zero/empty fallback.
The single-vector length limit, table exhaustion and item exhaustion remain
separate conditions; the latter two name arenas vectors and vector-items.

## Actual planner, context and prelude composition

The planner recognizes all eight mechanisms, bringing implemented source
slots to sixteen including the existing pair/string/capability slots. The
profile still decides which slots are admitted. A profile declaring a slot
without an implementation fails closed.

When vector slots are admitted, table/item budgets and maxima come from the
owning native profile; explicit overrides are vectors and vector-items.
Missing/malformed bounds and out-of-profile budgets refuse. A legacy profile
admitting no vector slots has zero vector arenas and refuses vector budget
overrides. No unsupported bytes capability kind is admitted by this change.

The layout adds an aligned 16-byte-per-handle table and an aligned
8-byte-per-item arena, with multiplication/addition/total-span checks. Context
public pointers now name the real table, item arena and private used counter,
including for the existing inline count/at/assoc-in-place lowering. The
context encoder checks arena spans and order and retains its 1024 initialized
bytes; mapped private state remains in the reserved header page. Startup
sets both counters to zero and installs the admitted capacities and length
limit at private offsets 1648..1680. Prelude emits the actual eight routines,
bindings and separate exhaustion messages. Image budget metadata records the
new limits rather than implying only pair/string budgets were selected.

Native defaults remain 4096 handles and 65536 item words. The profile proposal
exposes the existing native address-space maxima 4194304/134217728 and the
existing language per-vector maximum 16777216. These match canonical C1
constant literals 15/16/17 and the language vector bound; no C loader pin or
generator is required. All sixteen-slot/profile changes remain unactivated
until exact owning source/pins and native evidence are admitted together.

## Source receipt and remaining closure

Vector source: 34 functions, two public exports supported-slots/routine;
blob `00190c954e072efb12e954dd6e2e3a47a161fd86`, SHA-256
`4aa0b56e1927928637031e1beed03e6618305475bf3b2accaa3053f7b3a2cb18`.
Whole current source inventory reads 17 modules including owning ELF/artifact,
35 schemas, 571 import calls, 451 record uses and 603 type positions, with no
structural findings. All 97 private state words are unique/aligned inside the
header. These are source-data/API/arity/record/constant observations only.

Still required: the complete four bytes/string conversion/slice/concat
helpers; bytes capability type/lowering/provider/result contracts and genuine
raw-byte filesystem/hash/I/O; complete callers/resolver/materializer/authoring;
other required general runtime and ABI coverage; exact native artifacts and
positive/refusal/resource evidence; Definition CIDs, reviewed owning main/pins
and full Amu-produced self-rebuild. This component does not close JUN-241 or
JUN-202. No workflow/protection, live service or production route changed.
