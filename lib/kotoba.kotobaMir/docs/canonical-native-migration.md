# Canonical MIR migration: source candidate

This is a whole-public-source candidate, not a native-qualified release. The final
closure uses canonical `.kotoba` and an Amu selfhost-built and rebuilt compiler.
CLJK/CLJC/CLJS, NBB/KBB, Node, Clojure/Java/JVM/Graal and a C compiler, loader or
runtime are not final build, packaging or execution prerequisites. CDCI must
eventually run both its controller and gates as loaderless
`x86_64-linux-static` ELF artifacts.

## Owning source and dependency

The transcription reference is owning main
`2653e5f1413812248c84c33598a67c8ea1e1a3af`. Its complete 3,383-line
`src/kotoba/mir.cljk` and both existing suites remain byte-identical. The current
reference includes the fuel-charge and gas-charge offsets and the removal of
the obsolete hosted CI; that removal is not native qualification.

The supporting native modules explicitly depend on the canonical GMIR source
in [GMIR #42](https://github.com/kotoba-lang/kotoba-gmir/pull/42), inspected at
`b3fa31ec37151a8d8a2b460260a06605d64cd65e`. That dependency is draft/unmerged
and itself native-unqualified. No GMIR source is vendored here, no local overlay
is a lock update, and the existing hosted `deps.edn` is not a native resolver
recipe. Dependency integration, reviewed pins and Definition CIDs remain open.

[MIR #75](https://github.com/kotoba-lang/kotoba-mir/pull/75) contains useful
historical dual-runtime readings in CLJK. Those readings do not satisfy the
final canonical source contract or establish native execution. This source
candidate neither overwrites that draft nor uses its host runtime as an oracle.

## Present supporting source

| Module | Scope |
| --- | --- |
| `catalog.kotoba` | All 104 instruction keysets, both targets, all register banks, 37 runtime offsets, 8 capability offsets, versions, bounds, derived atomic/dequant operation sets, privileged registers and allocator pool |
| `outcome.kotoba` | Typed MIR refusals and lossless GMIR refusal adaptation: phase, problem, message and complete data |
| `registers.kotoba` | Physical register predicate and saved-register scan over every nested collection and map key, returning unique registers in preserved-bank order |
| `flat.kotoba` | Flat virtual/physical validation, exact fields and version exclusions, ordered profile/bound/ABI checks, labels and v2 GMIR projection |
| `validation.kotoba` | Full flat/module dispatcher source, function/entry/call/frame checks, symbolic reentry transport, backed values, parallel arguments and stack profiles |
| `table.kotoba` | Persistent AVL tables for exact nil/ordinal/keyword/symbol identities and nested ordinal sets; no typed-map/set 32-entry ceiling |
| `operands.kotoba` | The complete ordered source sequence, with phi/indexed/argument operands, exact named identity and filtered use counts |
| `selection.kotoba` | Target admission and full refusal ordering, every closed field, context offsets, v3 constant-divisor specialization/dead-definition removal and AArch64 zero/equality branch fusion |
| `schedule.kotoba` | RAW/WAR/WAW dependencies, original-index permutation checks, modeled completion times, critical-path scheduling and AArch64 adjacent fusion protection |
| `counted.kotoba` | Exact selected countdown structure, closed pure/nontrapping operation proof, isolated-function refusal of calls and validated-module direct pure-leaf admission |
| `allocator_data.kotoba` | Exact compiler key/set/sequence helpers over persistent AVL tables and paged nodes |
| `allocator_cfg.kotoba` | Basic blocks, successors/predecessors, dominators, fixed-point liveness, back-edge last uses, definition order, frame interference and slot coloring |
| `allocator_phi.kotoba` | Edge phi lowering, deterministic parallel copies with cycle slot, and complete transport coalescing |
| `allocator_linear.kotoba` | Primary linear scan, entry ABI placement, ordered free/reserve pools, call clobber/preserved values, definition-position stores, lazy reloads and exact direct reentry homes |
| `allocator_spill.kotoba` | The owning explicit all-vreg fallback operation families, typed refusal and frame bounds |
| `allocator.kotoba` | Whole allocation dispatch, original spill-required-only fallback, stack arguments, post-allocation scheduling and final flat/module validation |
| `../mir.kotoba` | All 29 original public names connected to the complete supporting source |

IR and refusal data use GMIR's nominal nodes, separate namespace/name text and
paged children. Large programs and strings are not flattened into bounded
documents. Catalog lists represent named lookup, membership or explicit ABI
order; their row positions are not new wire indices.

`kotoba.mir.flat/validate!` validates a **flat component**, including the flat
version 3 form used inside a module. `kotoba.mir.validation/validate!` dispatches
flat versions 1/2 and the complete version 3 module source. The canonical
`src/kotoba/mir.kotoba` root now delegates every original public name. Validation returns the original
input node on success and a typed full-data refusal on failure. Atom tags alone
do not establish nominal representation validity; a final recursive shape pass
runs after semantic checks. This pass adds `:non-canonical-value` for invalid
nominal values without replacing an earlier semantic refusal.

### Explicit API and bug-fix changes

* Public data maps/sets become typed named tables; queries return `Option`.
  Unknown lookup remains distinct from a real empty register sequence. Unknown
  target pool/privileged queries retain the reference's empty concatenation
  result; this does not admit that target to validation.
* Throwing APIs become `Result` values. Every native caller must propagate and
  consume these results. A GMIR error keeps its GMIR phase and projected input;
  it is not reduced to a MIR problem keyword.
* The owning v2 virtual adapter has a closed partial key `case` that omits
  modern fields such as `input`, `rodata-encoding`, and `function`. The new
  adapter renames every already-validated MIR field to GMIR, excludes only
  `context-offset`, and converts phi incoming keys. Modern instructions reach
  GMIR validation rather than a host unmatched-case exception. This is an
  explicit repair, not a claim of exception parity with the broken adapter.
* The reference's runtime/capability count domain and list/vector sequential
  equality are preserved. Unsupported scalar argument counts produce typed
  invalid-call refusals instead of a host count exception. String counts use
  UTF-16 units, including two units for an astral scalar. Physical ABI checks
  still require the exact ordered register sequence.
* The generic register scan preserves the reference's `keep` behavior: nil
  fields are skipped, and argument/parameter children are scanned there only
  for vectors. Existing admission holes are not an allocator permission or a
  reason to silently narrow accepted input during this transcription.
* A non-sequential scalar saved-register input produces a full-data
  `:non-sequential-instructions` refusal rather than a host sequence exception.
* Forward call signatures retain their original arity value in refusals. The
  physical comparison preserves wide integer and f64 ordering, including a
  fractional forward arity that is rejected only when its function is visited.
  A nonnumeric forward arity becomes a full-data `:call-arity-mismatch`, replacing
  an unstructured host comparison exception. Stack profile validation proves
  that a demanded index beyond the existing 0..63 range cannot be supplied;
  it does not allocate an unbounded range for an invalid forward signature.

The module checks retain the owning order: function shape, flat instructions,
physical entry arguments, frame policy, reentry, all-vregs backing and parallel
loads, direct-call linkage/arity, then physical stack stores. Symbolic reentry
executes only the closed move/store/load transport language over parameter
identities. It checks the exact ABI prefix, defined sources, restored slots,
unique parameter homes, recur argument agreement and termination at an end or
label. Home tables upsert architectural register locations and at most 4,095
existing frame slots; their size is not the prefix's instruction count. Pending
stack stores use paged nodes so a long invalid input is retained in refusal data.
Stack stores must cover each required index exactly once in the correct area;
each call/recur consumes the pending group, and leftovers are refused.

The owning validator's existing admission rules remain visible: x86-privileged
is not in its call-frame classifier, the backed-value set contains exactly 87
operations, and MIR function-address validation checks the name's type without
adding a new module membership check. No new gate is inferred from these rules.

These representation/API changes require native parser, caller, hash/resolver
and CID migration. Name coverage alone is not compatibility or parity proof.

### Selection and scheduling boundary

`selection/select-target` accepts the target as a nominal node, so an unsupported
target's entire value survives the typed refusal. Target rejection precedes
GMIR validation; GMIR errors keep their phase/message/data. Privileged target
refusals precede fused-dequant target refusals. Repeated privileged actions and
first-encounter order of distinct refused formats are retained across functions.
Both targets admit scalar dot-f32 and the existing rodata/function address
forms; AArch64 admits Q8_0 and refuses the rest of the current fused-dequant
family. New formats remain refused until explicitly admitted.

Every validated GMIR field is carried into MIR, with operation and phi incoming
keys renamed and runtime/capability context offsets added. Flat versions 1/2
retain direct translation. Version 3 retains the original single-pass constant
environment, captures a divisor's entire literal, removes that field's register
source, and removes only specialized definitions with no remaining vreg uses.
The exact integer zero predicate replaces host-number conversion. AArch64
zero/equal/branch fusion requires adjacency, three distinct identities and
unique whole-function uses, including phi edges. It preserves both equality
orientations and leaves other patterns intact.

The scheduler is **not called by target selection**. Its owning invocation is
after allocation, which is now connected through the allocator policy. It schedules only the original
14 pure integer operations; every other operation and protected multiply/add
or multiply/subtract pair is a barrier. The original last-def/readers algorithm
captures RAW, WAR and WAW before updating the current read/definition, so a
read-modify-write has no self-edge. Critical-path height then original index
select the next ready instruction. Multiply has modeled latency 3 on both
known targets; other operations have latency 1. Waiting advances the conceptual
cycle without inserting instructions. Exact original-index permutations keep
structurally duplicate instruction values distinct. Verification refuses a
dependency violation with the entire segment and proposed order.

Tables retain keyword versus symbol and separate namespace/name byte chunks,
including absent versus empty namespace and embedded slash ambiguity. AVL
updates preserve old roots; cached cardinality supplies ordered set access.
Tables and graph edges are not a bounded generic document or a 32-entry native
map/set. This is internal compiler data structure source, not another compiler
lineage. AVL invariants, sharing/copying, native record layouts, recursion/stack,
arena/fuel and large-input resource costs are all unqualified until execution.

### Counted reentry boundary

The isolated `counted-self-recur-plan` takes a selected virtual-MIR function,
as in the owning contract, and returns `Option` of the complete original plan.
The module API validates first, preserves any complete validation refusal,
then requires version 3 virtual MIR. It returns `Result` of a paged nominal map
whose keys are the original function symbols, without a 32-function map limit.
The returned plan retains `:counter-parameter`, `:runtime-domain
:nonnegative-i64` and `:charge :entry-plus-exact-self-recur-count`.

The proof preserves the exact 19-operation allow-list; constant quotient is
admitted separately only for an i64 divisor other than 0 or -1. General
quotient, memory, capability/runtime calls and unknown operations stay outside
the proof. It requires the complete indexed argument profile; one nonzero
branch, adjacent base return and body label; the matching label; and one
terminal self tail-call with exact arity. That tail argument must resolve to
`counter - one`, with the last definition of one having the exact integer
value 1. Reverse definition search preserves the reference's last-definition
behavior. Argument presence plus exact cardinality retains the reference's
sorted-index comparison without sorting a bounded container.

Only a validated closed module may authorize a direct call to a proven pure
leaf with exactly one return. A leaf cannot contain calls, tail calls or
branches, so recursive and non-leaf call chains cannot gain authority through
a transitive shortcut. The proof does not compute a runtime charge or admit
negative counters; backend per-edge fallback and actual fuel/resource behavior
still require execution. Canonical numeric/named representations and typed
outcomes need native reader, caller and CID integration just like the other
modules. This source port does not qualify arbitrary malformed host objects
outside the selected-function API precondition.

## Whole public scope remains required

All 29 original public names and their complete behavior remain acceptance
scope. The canonical root now represents all 29 names:

```
allocate-registers allocator-pool call-argument-registers capability-argument-registers
capability-context-offsets instruction-keysets kernel-atomic-ops
counted-self-recur-plan counted-self-recur-plans
kernel-dequant-dot-maximum kernel-dequant-dot-operations kernel-dot-f32-maximum
kernel-window-maxima kernel-window-operations leaf-registers physical-registers
preserved-registers privileged-argument-registers return-registers
runtime-argument-registers runtime-context-offsets saved-registers
select-target slice-item-limit slice-operations supported-versions targets validate! version
```

The source connects the primary linear scanner, growing scratch/reserve pools,
preserved call-crossing values, definition-position stores, label-local lazy
reloads, exact direct reentry homes, phi lowering and parallel copies,
coalescing, CFG/dominance/liveness, interference-colored frame slots, stack
arguments and post-allocation scheduling. Only the original `:spill-required`
refusal selects the all-vreg fallback; other complete refusals propagate.
The fallback preserves the reference's explicit operation cases and existing
unsupported-operation refusal. It is not substituted for the primary scanner.
AVL deletion preserves old roots and rebalances; key rank access retains
deterministic ordered-vreg traversal. Native source equivalence, record/type
admission, backend charging, resources and whole-component execution remain
unqualified. Name coverage is not a condition-equivalence or execution proof.
The adopted Amu compiler core/lineage, frontend, lowering, optimizer, backend
and complete full19 Embench workload must be preserved through integration.

## Evidence and open gates

Eight self-check component sources and an aggregate are present:

* `kotoba.mir-catalog-cases/main`: complete table counts/lookup/uniqueness,
  banks, derived operation families, offsets, pool truthiness/order, nested/map
  key register scanning, unknowns and full refusal adaptation.
* `kotoba.mir-flat-cases/main`: all 104 instruction rows, every required-field
  removal and an extra field per row; all 37 runtime, 55 privileged and 8
  capability ABI rows; list/vector/count rules; version and first-refusal
  ordering; labels/frames; repaired v2 projection and nominal representation.
* `kotoba.mir-module-cases/main`: both targets, full return/refusal data,
  function/entry/frame ordering, spill-restored and clobbered reentry homes,
  termination, backing and parallel loads, forward linkage/nonnumeric/fractional
  arities, outgoing/incoming stores, duplicates, per-call consumption and recur
  stack arguments. Separate large entries construct 16,385-instruction and
  16,385-move reentry prefixes without imposing a logical per-list limit.
* `kotoba.mir-table-cases/main`: all four AVL rotations, ordered lookup,
  persistence/update, present nil versus missing, nested sets and identity
  ambiguity. `large-main` inserts and checks all 16,700 ordinal keys.
* `kotoba.mir-selection-cases/main`: all 92 GMIR rows on both targets with an
  independent literal field mapping, exact target/GMIR refusal facts and order,
  divisor capture/dead versus shared definitions, flat-version behavior,
  scalar representations and zero fusion's adjacency/identity/global-use guards.
* `kotoba.mir-schedule-cases/main`: both targets, RAW/WAR/WAW, duplicate
  instruction identities, invalid/duplicate/out-of-range index orders, exact
  modeled completion vectors and sums, all barrier classes, adjacent add/sub
  fusion protection, immediate/phi/compare-exchange sources and 64-reader
  anti-dependency fan-in. `large-main` checks the complete 16,385-reader
  dependency set; this does not measure the full large scheduling runtime.
* `kotoba.mir-counted-cases/main`: full returned plan, integer text and divisor
  bounds, sorted argument identity, both counter positions, each structural
  condition, last-definition behavior, all 104 catalog operations, isolated
  call refusal, safe/trapping/cyclic module leaves on both targets, complete
  validation-error propagation, flat-module refusal and 41 returned plans.
  `large-main` analyzes a countdown with 16,385 additional pure instructions.
* `kotoba.mir-allocator-cases/main`: the public root on both targets, exact
  simple physical stream, deterministic repeat, parallel-copy cycles,
  40-value pressure with result checking in a closed integer-fixture
  interpreter, call-live preservation, counted direct reentry, seven-argument
  entry/calls, physical refusal data, CFG dominance/liveness/back-edge use,
  branch-disjoint slot coloring and complete phi transport coalescing.
  `large-main` applies both targets to 128-value pressure. The small fixture
  interpreter refuses unknown operations; it is not a whole-MIR runtime or
  an alternate compiler. AVL source cases also check deletion/rebalancing,
  persistence and rank key retrieval.
* `kotoba.mir-canonical-cases/main` calls all eight component entries;
  `large-main` calls both module large entries plus table/dependency/countdown
  large entries plus allocator pressure, and returns only an i64 status.

## Native selfhost execution (2026-10-23)

The whole canonical root, all 29 original public names, counted proof, full
allocator policies, selection, validation and scheduling are linked together
with seven canonical GMIR production units. The 33 source inputs and all three
source roots are checked with an exact KSL1 SHA-256 source manifest. The native
compiler checks, compiles and links that closure without `--unpinned`, reduced
roots, a C loader or a hosted semantic materializer.

The ordinary aggregate calls all eight components and exits zero. Individual
large entries also exit zero: 16,385-instruction module validation, 16,385-move
reentry, 16,385-entry AVL invariants, 16,385-reader dependency fan-in, 16,385
distinct counted-proof instructions and both-target 128-value allocator
pressure. The all-large aggregate is checked separately in the exact receipt.
These tests preserve the original guest allocator limits and all cases.

Resource fixes reclaim only scalar-result temporaries. Reference-returning
functions retain their allocations. Optional fallbacks are lazy, keyword/map
lookups reclaim their printed comparison data, and immutable empty graph
values are shared within one construction. Pending scheduler readers use
paged sequences; WAR consumption and final ordered graph construction produce
the same persistent AVL sets without retaining every intermediate path copy.
RAW/WAR/WAW, duplicate-source and read-before-write ordering remain covered.
Counted large fixtures share immutable literals and compare all 16,385
constructed instructions with the original construction before proving them.
The x86 fixture now checks the owning refusal for AArch64-only branch-nonzero;
positive counted modules use AArch64, and x86 direct reentry uses branch-zero.

The measured Amu seed successor has 18 modules. Its exact unity SHA-256 is
`3f43340887b2b5d1ec1a1c5541ef295f75b2bceaa0d2a24d69995112d2206523`.
G5 rebuilt G6 to byte-identical KSEED, SHA-256
`bb94ca3692b4bf1f62fbdb3447a916aec48145dc3da3ab814e57421bd162042c`.
The G5 ELF is `aca405b65c0313aee4b672a5c5c65839b6fe7e941aeaf957865c81da50b3843f`.
Its native growth packager is
`01d16edcfb23d2015c925a44796bdbcab16e87be48f77e4f007590794d064a0a`.
G5 freshly compiled all 19 complete Embench correctness workloads and all
exited zero with this runtime. No new performance score is claimed.

Native runtime checks cover 600,000 scalar releases, outer-value and scalar
preservation, depth 256, depth-257 refusal, unscoped budget refusal, persistent
vector forks/views and region rollback, exact-size growth fallback and actual
item-budget exhaustion. A reference cannot escape a scalar scope. Neither
grants nor cell/vector/item budgets were increased.

The initial E3 scope and E6015 missing-pin attempts are historical. Exact
source locking and an in-scope immutable input snapshot resolve those earlier
compile blockers. They are not current MIR prerequisites.

This is an internal AAPCS64 image framed for an existing AArch64 Linux guest.
It does not admit a public compiler target/profile/seal/CLI or the required
x86_64-linux-static CDCI controller. Full historical corpus/caller migration,
generic abort/recur cleanup, owning-main/resolver/Definition CID integration
and forbidden-process trace qualification remain open. The two original
owning suites and reference source remain byte-identical. New native cases
do not claim that those entire historical suites have been run.

Limited source-data inspections remain useful for table/refusal/field-set
preservation, but are not native execution or proof of full condition parity.

The integrated parent reader successor in Amu #1491 rebuilds G7/G8 byte-identically
and checks/compiles the same MIR input closure. Its MIR KSEED and both directly
re-executed aggregate ELFs are byte-identical to the G5 artifacts above; both
ordinary and whole-large aggregate executions again exit zero. Exact integrated
generation hashes are appended in the same correctness receipt.
