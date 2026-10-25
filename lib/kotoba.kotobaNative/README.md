# kotoba-native

Amu's native **綾** — checked KIR to x86_64/aarch64 machine code and ELF64.

This is not a being. [`amu`](https://github.com/kotoba-lang/amu) weaves
(編む); this repository is one pattern in that weave (the metal / ISA face).
It does not run artifacts and does not decide grants. Execution and runtime
linking are [`kototama`](https://github.com/kotoba-lang/kototama) (言霊).
Authority is [`grant`](https://github.com/kotoba-lang/grant); [`aiueos`](https://github.com/kotoba-lang/aiueos)
enforces it (root ADR-2608219500).
See root ADR-2608139980.

**Tier**: `T2`  **Role**: `backend` of amu

Split out of the overloaded core repos by ADR-2607266000 so that each
responsibility has exactly one owner and the dependency direction is
checkable from outside.

## Owns

- `kotoba.native.x86-64`
- `kotoba.native.aarch64`
- `kotoba.native.elf64` target layout, entry shims, and aiueos target-admission
  policy (which operations/ELF shapes the backend can emit). Kernel images copy
  the sealed artifact's finite fuel bound into the hidden context; the
  packager rejects disagreement between `:limits` and `:fuel-abi`.
- `kotoba.native.peephole`
- `kotoba.native.string-search`
- `kotoba.native.vector-region`

## Native is not an effect provider

The production direction is one-way:

```text
checked KIR -> kotoba-native machine semantics -> Amu artifacts/qualification
            -> kototama native host (tender-native) -> aiueos enforces grant's answer / QEMU evidence
```

This repository owns instruction selection, encoding, freestanding entry ABI,
and target-level fail-closed admission. It does not own UEFI memory policy,
page allocation, process isolation, syscalls, capability tables, or an effect
provider. Those are `kotoba-lang/aiueos` product responsibilities. Likewise,
emission parity here does not qualify Amu or aiueos maturity: qualification
requires the exact-pinned consumer chain, empty foreign-code receipts, and
positive plus negative machine execution. See ADR-0029.

### What that looks like from the guest side, measured 2026-09-08

Against amu `origin/main` `a169d7bf`, `--jvm-free`, each artifact **executed**
through `tools/kexe_loader.c` rather than merely built — because building is
not running, and `:ok true` means the first, not the second:

| guest form | `--target aarch64-macos` | answer |
|---|---|---|
| arithmetic, lambda, application, definition reference | compiles | correct value |
| `kgraph-assert!` / `kgraph-get` (the `rel` / `query` spellings) | compiles | reads back what was stored |
| a capability call (`cap-call` / `perform`) | compiles | **`KEXE_TRAP :SIGTRAP`** |
| `try` / `catch`, with or without the `handle` spelling | **refused** `:verify` | — |

The third row is this section's title, observed rather than asserted: the
guest compiles, and traps at the call because **there is no native effect
provider in the bare loader**. That is the documented boundary, not a defect
here. A native host that grants capabilities is `kototama` plus `aiueos`.
[Since root ADR-2608219500 (2026-08-21) `grant` decides the capabilities;
`kototama` and `aiueos` enforce that answer.]

The fourth row is a real gap in this backend and is named as one: the `:abort`
ability has no native lowering, so `native artifact contains an unsupported
effect`. The control is what makes it a backend gap rather than a surface
one — the refusal is identical with and without the `handle` spelling, so it
is the ability that is missing, not a source form. Recorded upstream as
`:native-gap` in kotoba-lang `lang/surface-status.edn`; guests targeting
native keep returning `[:result T E]` at boundaries.

## String search

`string-contains?` and `string-replace-all` are the one operator family whose
lowering lives in neither backend: both consume the SAME rewrite, from
`kotoba.native.string-search`, because the property under test is that one
program produces one value on both ISAs and two copies could drift while both
stayed green.

Since ABI v5 (2026-09-15, ADR 0082) `string-index-of` is a HOST operation at
context slot 216, like `string=?` at 112: one call per search, memmem on the
host's side, nothing allocated. The two rewrites lower onto it —
`string-contains?` as the 0/1 fold, `string-replace-all` through one driver
helper that `emit-program` appends only when a body reaches it, never
exported. Until v5 the search itself was a rewrite over the four string
callbacks — one substring handle and three or four host calls per haystack
byte, which is what made a packaged `grep` exhaust a 4 Mi-handle arena after
2 MB of a 3.3 MB file. See ADR 0002 for the rewrite era and ADR 0082 for the
slot.

## Optimization

Bounded native vector literals now pass through a conservative escape proof
before instruction selection. A literal of at most 32 items becomes scalar
locals only when every lexical use is `vector-count`, `vector-at`, or
`vector-get`; construction order and single evaluation are preserved. Passing
the value to a function, returning it, storing it, observing identity, or using
an unsupported operation keeps the existing checked host-vector ABI. The same
rewrite feeds x86-64 and AArch64, including lexical shadowing and dynamic-index
bounds behavior. This is scalar replacement for proven non-escaping literals,
not a general arena allocator; see ADR 0037.

`kotoba.codegen.layout` is the explicit MC/layout boundary. Its closed
reference EDN projection uses qualified keys and qualified label IDs:

```clojure
{:mir/op :mir/label
 :mir/id :kotoba.mir.label/if-end-1}

{:mir/op :mir/relative-branch
 :mir/encoding :x86-64/jz-rel32
 :mir/target :kotoba.mir.label/if-else-0}
```

Layout is two-pass: labels receive byte offsets first, then every relative
branch receives `target - (position + instruction-size)`. Duplicate labels,
unknown targets, unknown encodings, non-qualified IDs, extra token keys, and
encoder width drift all fail closed.

All audited x86-64 and AArch64 intra-function branch families now use this
boundary: ordinary conditionals, variant dispatch, kernel/string bounds,
capability and fuel gates, signed-division traps, and tail control flow.
Calls and tail-self relocation are resolved by the same final backend pass.
No optimizer therefore depends on a displacement baked before final layout.

The first rewrite materializes a constant right operand directly into the
scratch register (`rcx` / `x1`), dropping the spill-and-reload round trip that
protects the accumulator when the right operand needs it. Recognition is on
the KIR **form**, never on emitted bytes — matching byte patterns in an
undelimited instruction stream would rewrite immediates that happen to spell
an opcode.

The first variable-width rewrite reclaims the removed spill/reload bytes:
x86-64 constant RHS materialization is 10 bytes and AArch64 is 16 bytes, with
no architectural NOP padding. Final layout recomputes every affected branch.

MIR v3 additionally selects signed division by an SSA constant into a closed
constant-divisor operation. Both encoders derive the same exact reciprocal
multiplier and replace `IDIV` / `SDIV` with signed multiply-high plus the
required truncation-toward-zero corrections. Dynamic divisors and constant
zero or plus/minus one retain the guarded hardware path, so division traps do
not become optimizer assumptions.

`kotoba-gmir` now owns the closed target-independent GMIR contract and
`kotoba-mir` owns target selection plus explicit virtual/physical register
state and deterministic allocation, including liveness-minimal straight-line
call frames, parallel function-entry assignment for four live scalar
parameters, and one bounded lazy entry spill at five-live-parameter pressure.
`kotoba.native.machine-ir` consumes those
contracts and owns only the bounded KIR-to-GMIR producer, physical MC lowering,
and x86-64/AArch64 encoding. Register exhaustion is represented by bounded MIR
frame slots and encoded here as target stack-frame load/store instructions.
Final layout and the allocated MC v2/v3 schemas are consumed from
`kotoba-codegen`.
The scalar/control subset is selected by the production emitters and covers
integer/boolean literals, up to five parameters, lexical `let`, `+`, `-`, `*`,
`quot`, bitwise operations, signed comparisons, scalar predicates, ordered
word shifts, signed/unsigned 32-bit wrapping operations, f64 arithmetic,
ordered/unordered f64 comparisons, f64 bit-pattern conversions and unary
abs/neg/sqrt operations, bounded kernel u8/u32 loads and stores, bounded kernel
subregion derivation, the closed x86-64 privileged instruction family, ordered non-empty
`do`, and nested tail `if`, with deterministic spilling. `bit-not`, `bool-not`,
and the i32 family are target-neutral compositions over constants, arithmetic,
comparisons, and the three portable shift instructions. `do` keeps
every intermediate expression in source order, including unused operations
that may trap; only its final value is returned. When that final expression is
tail control, `do` delegates it to tail lowering after emitting every scalar
prefix, so both arms return directly without a synthetic merge. Other typed KIR
expression families outside the published native boundary fail closed before
target selection; production has no legacy-emitter fallback.
Native f64 values stay as their IEEE-754 bit patterns in the general-register
IR; selected instructions alone move them through the target FP bank, so GMIR
does not acquire target register classes.
Kernel memory instructions preserve their GMIR maximum through MIR and selected
MC. Both targets reject an oversized declared length, a null base, and an
out-of-range index before access; u32 uses the non-wrapping
`length - index >= 4` proof. Subregions similarly prove offset and size against
the remaining parent length before deriving the child pointer.

The x86-64-only control-register, TLB, interrupt, port-I/O, MSR, CPUID, and
boot-info operations lower through one closed GMIR action family. MIR owns the
target boundary and rejects that family on AArch64 before allocation. The x86
encoder preserves every non-destination allocator register and `rbx` around
fixed-register instructions; no operation can fall through to the legacy ISA
emitter.

Non-escaping flat records whose fields are only `:i64` or `:bool` use scalar
replacement before GMIR. Construction evaluates every field in declaration
order, bindings retain an ordered SSA bundle, projection selects one scalar,
and record-valued `if` emits one phi per field. Acyclic field transport reaches
the existing parallel-copy scheduler with no allocation or phi frame. Escaping
and nested records use declaration-order pair chains: each nested record is
itself one context-owned word handle, so recursive projection is a bounded
composition of the existing `pair-first`/`pair-second` operations.

Non-escaping sealed variants whose case payloads are only `:i64` or `:bool`
use the same extracted path without a stack aggregate. Construction creates an
internal tag-and-payload SSA bundle, variant-valued `if` joins it with two
phis, and `variant-match` becomes target-neutral tag comparison CFG while
binding the payload register only in the selected source branch. Payload
evaluation remains exactly once. A bounded function-boundary family is admitted
separately: qualified variants with 1--32 unique cases and `:i64`, `:bool`, or
admitted record payloads cross as one context-owned
`pair(zero-based-declaration-ordinal,payload-word)` handle. A record payload is
itself its recursive pair-chain handle. The public value keeps the canonical
KIR shape `[type case-keyword payload]`; unsupported payload schemas remain
outside the extracted path.

Function-boundary aggregates are described by the versioned portable contract
in `resources/aggregate-abi.edn`. The established record ABI remains a single
context-owned pair-chain handle with a 4,096-cell execution bound and a maximum
inline schema nesting depth of 32. Extracted
scalar calls are admitted by ABI v2: GMIR/MIR/MC v3 own a module of independent
functions, and a call-containing function backs every vreg with its own bounded
frame. Register-resident arguments move in parallel into the target ABI
registers; an excess backed entry value loads directly into its outgoing ABI
register. Every allocator register may be clobbered, and the return register is
captured before later use. x86-64 adds an eight-byte call-alignment pad;
AArch64 call functions save and restore FP/LR. The correctness-first all-vreg
policy remains the fail-closed path for remaining pressure without changing the
v3 call contract.

Word-field record pair chains, recursively nested record handles, and variants
carrying record handles are admitted by aggregate ABI v7. Local non-escaping
flat aggregates retain scalar replacement. Callable indirection is sealed to a
closed ordinal dispatcher and `apply` consumes at most four arguments from a
bounded pair chain; neither path accepts an arbitrary code address. External
linkage means a content-addressed closed module graph with no ambient or
unresolved symbol. Open-ended variadic parameters, arbitrary code pointers,
and dynamic unresolved linkage remain structurally rejected. This is not a
Rust-parity claim.

Value-position scalar `if` uses GMIR/MIR v2 phi values. Each branch reaches an
explicit predecessor exit. Single- and multi-phi joins lower through MIR's
deterministic parallel-copy scheduler: acyclic edges use zero phi frame bytes,
while cycles share one temporary slot. Final layout resolves all resulting
branches. Unselected branches do not execute, including trapping operations.

`kotoba-object` owns the target-neutral ELF64 record encoders. This repository
supplies the target-specific section layout, virtual addresses, relocation
requests, entry shims, and runtime/capability policy; it no longer carries a
second implementation of ELF headers, symbols, or RELA records.

`kotoba.native.macho/encode-text-object` is the single native integration path
from shared typed relocation requests to ARM64/x86-64 Mach-O section records;
it validates target and section ownership before `kotoba-object` packs bytes.

## Representations and identity

The EDN maps above are the developer/reference notation for the abstract
instruction data. They are not identity bytes and must never be hashed through
`pr-str`. JSON may project the same abstract model for tooling, but is likewise
not authoritative.

Content identity is computed from normalized abstract values encoded as
deterministic DAG-CBOR, with IPLD links for dependency CIDs. The implementation
lives at the current authority boundary: the `kotoba-lang` language contract
provides DefCID and `artifact` provides SourceCID, BuildCID, and ArtifactCID.
`osaho` (formerly `kotoba-kir`) owns the checked IR model but does not introduce a second DefCID
codec. This native repository consumes those contracts rather than defining
another codec.

## Does not own

- parse .kotoba source
- own language semantics
- require Rust in the core path

## Depends on

- `kotoba-lang/osaho` (formerly `kotoba-kir`)
- `kotoba-lang/kotoba-gmir`
- `kotoba-lang/kotoba-mir`
- `kotoba-lang/kotoba-codegen`
- `kotoba-lang/kotoba-object`
- `kotoba-lang/artifact`

## Test

```bash
kbb --backend sci --classpath "src:resources:test" run-tests.cljk   # the whole suite, counted
kbb -M:test                                                          # the same namespaces through the alias
```

No JVM anywhere in this path (ADR 0086, 2026-09-18). `run-tests.cljk` runs all
37 test namespaces, refuses a test file it does not list, and counts the
`known-red` deftests apart -- today the 18 x86-64 aiueos kernel-image tests
that read what only the JVM twin `elf64.clj.cljk` lays (ADR 0036). They run
and their failures print; a failure outside the list, or a listed test that
passes, fails the run. The six coordinates the tests reach are declared in
`nbb.edn` (same shas as `deps.edn`).
