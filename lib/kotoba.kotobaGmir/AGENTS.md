# GMIR source and qualification contract

Use canonical `.kotoba` and Amu selfhost / Kotoba native for source, tooling,
CDCI gates and the controller. CLJK/CLJC, JVM/Java/Clojure, NBB/Node, KBB and
C loader/runtime pins are not final dependencies or acceptance conditions.

Migrate all public exports and their transitive implementation. Preserve
complete instruction keysets, versions, arities, value/label identities,
rodata encodings, kernel bounds, phi/module validation and refusal facts.
An empty host-region projection or a table-only slice is not whole GMIR.

Keep target-independent contract ownership here. Instruction selection and
encoding belong to their native owner. Adding a kind does not establish
compiler lowering, provider availability, raw-byte results or authority.
Byte payloads must not silently pass through UTF-8 text or host crypto.

Preserve existing source/corpus and unrelated WIP as migration provenance.
Do not add or run tests unless the user asks to test or verify implementation.
Native source, compilation, execution, corpus parity, artifact admission and
downstream immutable pins are separate evidence. Missing native gates stay
open; do not register a success placeholder or restore an obsolete host gate.

## Retired CI and current evidence

The Java 21/Clojure workflow (`.github/workflows/test.yml`) was removed in
PR #41. It is not retained disabled and must not return as a fallback. No
public native CDCI gate/controller is registered yet. Internal native Amu
selfhost receipts cover all four canonical component entries, the ordinary
and large aggregates, all instruction rows/arities/capability kinds, long
rodata and paged collection cases. Historical host-suite assertion parity,
caller/reader integration, public target/profile/seal, authority/resource
qualification and downstream main/lock/CID remain separate open checks.
