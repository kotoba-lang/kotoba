# Kototama and Amu: multilanguage architecture and roadmap

Status: **working proposal**, JUN-792. The shared VM contract remains under
construction; this document records the intended architecture and dependent
work, not an approved specification, supported language, release commitment,
or a claim that any milestone is complete. Resolve the open contract issues
in `multilanguage-vm-contract-proposal.md` before choosing a first frontend.
The existing normative `spec/kototama-vm-v1.edn` remains authoritative.

## Intended shape

```text
 source + version + options
        |
        v
 language frontend -----> diagnostics / explicit refusal
        |
        v
 canonical Kototama program bytes + translation evidence
        |
        v
 independent admission: encoding, profile, whole program, resource bounds
        |
        +----------------------+-----------------------+
        |                      |                       |
        v                      v                       v
 reference evaluator     Amu native AOT           future engines
        |                      |                       |
        +-------- comparable transition observations -+
                               |
                               v
            host: admission, limits, authority, effects, receipts
```

Kototama is the engine-independent contract for an admitted program and its
observable transition. Amu provides native compilation and tools around it;
a compiled native artifact is engine- and target-specific. A compiler can be
used by another component, but its output is not trusted merely because it
was produced by Amu. Program admission, artifact admission and permission to
perform an effect are separate decisions. Hosts do not silently grant authority
on the basis of a frontend or compiler annotation.

Translation identity should bind source bytes and dependencies, language and
frontend versions, options, declared subset, output program CID and diagnostic
status. Program identity is the CID of canonical DAG-CBOR bytes. Artifact
identity should separately bind the program CID, VM/profile revision, compiler
and runtime versions, target/ABI, build options and artifact digest. A host
must validate those bindings and its own policy before execution; a receipt
validator checks framing and consistency, not producer identity or authority.
The exact schemas, trust roots, revocation and distribution mechanisms are
unsettled design work, not existing guarantees.

## Contract and execution boundaries

The initial candidate is the existing bounded pure-i64 route. It has no guest
imports, effects or heap and does not represent the full VM. Its AOT result
protocol and receipt/v2 are different from the full VM transition and receipt.
The admitted program's identity, source semantics, canonical evaluation order,
fuel, trap class and permitted effects must remain observable across engines.
Resource accounting is a VM rule, not a measurement of machine instructions.
Compilation and admission need their own explicit limits as well as execution.

The current historical CLJK evaluator is a local reference, not the native
implementation. Its tested division-by-zero path loses spent fuel and typed
failure information; the current Amu receipt/v2 path reports a typed fault and
spent fuel. Do not call them equivalent or alter the normative contract merely
to mask the difference. Define the intended trap and charge behavior, then
implement and compare independent native paths. The historical decoder also
accepts unknown fields that the normative specification rejects. The bounded
Amu frontend check rejects its tested cases; it is not a general VM decoder.

A future effectful profile needs explicit guest import and effect types, host
capability scope and lifetime, per-operation authorization, denial behavior,
resource exhaustion, rollback and treatment of already externalized effects.
Define which observations are deterministic and which are supplied by a host;
replay and signed receipts require their own identity and trust protocols.
A sandbox or native process boundary alone does not supply these properties.

## Language and toolchain boundary

A language frontend is a versioned translator with a documented supported
subset, not a promise that every program or library in that language works.
It must refuse unsupported or ambiguous constructs and establish source-to-VM
behavior against independent examples, including refusal and undefined or
implementation-defined behavior. Compatibility with existing binaries,
platform ABIs, native libraries or a language ecosystem is a further claim.

* C and C++ need explicit object representation, pointer provenance, memory,
  layout, calls, undefined behavior and foreign-library rules. C++ additionally
  needs a scoped choice for exceptions, templates, RTTI and runtime support.
* Rust needs a defined target and ABI, memory and allocator behavior, panic and
  unwinding policy, unsafe/FFI boundaries and a supported core/library subset.
* Java needs class loading, bytecode semantics, exceptions, memory management,
  threading and an explicit runtime/library scope; Java source support does
  not follow from compiling a few integer expressions.
* JavaScript needs dynamic values, coercion, objects, exceptions, closures and
  host APIs; TypeScript also needs a versioned type-erasure/diagnostics policy.
  Browser and Node APIs are separate host contracts, not automatic VM features.
* LLVM IR or WebAssembly can be considered as an input route with a pinned
  version and an explicit semantic mapping. Neither is automatically
  equivalent to a language frontend, a complete runtime, or Kototama admission.
  Source behavior, undefined behavior, memory, calls and effects still need
  evidence. No LLVM or Wasm dependency is selected by this proposal.

Kotoba, CLJK and Mith paths likewise require individually scoped statements
about their actual frontends and runtime support. CI and production build
paths remain native/selfhost; the allowed one-time local reference oracle is
not a CI gate, implementation fallback or native conformance proof.

## Roadmap and exit criteria

1. **Shared contract and executable evidence.** Pin the profile, permitted
   program forms and values, whole-program refusal rules, evaluation and trap
   semantics, fuel schedule, limit behavior and host observations. Build a
   native reference path independent of the AOT backend and run retained
   positive, boundary and negative vectors through both. Resolve the observed
   trap/fuel discrepancy and unknown-field admission gap. Exit only when a
   named profile and its test corpus are reviewable and both engines have
   recorded matching observations and explicit exclusions.
2. **End-to-end native execution.** Bind source/program/artifact identity and
   target, verify artifact and runtime ABI at a host boundary, enforce admitted
   budgets and no-authority default, and observe actual process results. Test
   corruption, mismatched identity/context, failure, resource exhaustion and
   refusal without guest effects. Qualify each engine/ISA separately; the present
   test-only FS2 bridge and receipt validator are evidence, not this host.
3. **First external frontend.** Choose one language and a small useful subset
   only after steps 1–2 define the destination. Specify versions, semantics,
   diagnostics and unsupported constructs. Run defined source examples
   against an independent source-language oracle and both VM engines, retain
   inputs/outputs and negative cases, and demonstrate native compilation on
   the chosen target. Add capabilities or memory only when required by a
   separately reviewed profile; do not claim whole-language compatibility.
4. **Broaden the VM deliberately.** Add memory, data types, calls, linking,
   exceptions or effects as separately versioned contracts driven by actual
   frontend needs. Each adds limits, failure semantics, independent engine
   evidence and adversarial refusal tests before a compatibility claim.
5. **Additional languages and distribution.** Add frontends and runtimes one
   at a time with published subset matrices, ABI/library boundaries and
   reproducible conformance evidence. Qualify release and update procedures
   separately from source merge; track compatibility and deprecation by
   profile version rather than declaring a single global compatibility bit.

The first language, interpreter architecture, artifact manifest schema,
profile versioning/migration, compatibility commitments and release targets
remain decisions. Time estimates and a shipping date require a reviewed scope,
owner and measured implementation capacity; none are inferred here.
