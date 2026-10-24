# kotoba-gmir

Kotoba generic machine IR: the target-independent virtual-register contract
between checked KIR lowering and target instruction selection.

**Tier**: `T0`  **Role**: `contract`

## Owns

- the closed GMIR v1 abstract data model and versioned GMIR v2/v3 extensions;
- virtual-register and label identity rules;
- structural validation for arguments, constants, integer arithmetic,
  signed/unsigned shifts, f64 bit-pattern arithmetic, comparisons, branches,
  returns, and v2 block-entry
  phi values with explicit predecessor jumps;
- v3 function ownership, module-local scalar direct calls, entry/callee and
  arity validation, plus the closed semantic x86 privileged-action family;
- deterministic EDN-shaped in-memory/reference data.

## Does not own

- source parsing or semantic analysis;
- KIR-to-GMIR lowering policy;
- target instruction selection, target admission, or physical registers;
- instruction encoding, machine bytes, or object formats.

GMIR is an abstract data contract. EDN is its reference notation; printed EDN
and JSON are not identity encodings.

## Current migration and CDCI contract

Canonical source and tooling use `.kotoba`, Amu selfhost and Kotoba native,
including the CDCI controller. CLJK/CLJC, JVM/Java/Clojure, NBB/Node and KBB
are historical port inputs, not required runtime, bootstrap or release gates.

The former Java 21 / Clojure test workflow is retired. No native replacement
gate is registered by this change. Existing source and the full corpus remain
unchanged; native compilation/execution, refusal coverage and component
admission are still open. The compatibility projection in kotoba-lang has an
empty `i64-value?` body and does not establish a complete canonical validator.

The native capability-kind contract currently ends at discriminator 7. Byte
request/result kinds and their complete lowering/provider/FS2 closure remain
open. Removing a hosted job does not activate those shapes or grant authority.

See [the retirement record](docs/hosted-ci-retirement.md).
