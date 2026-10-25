# Retire the Clojure/JVM object-library workflow

Tracking: [AWAI-48](https://linear.app/kotobalabs/issue/AWAI-48), Kotoba Labs.
Codex thread: 01a15eb9-ef0b-73f3-a095-1a1af90d3a21.

The owner requires canonical Kotoba and Amu selfhost, with only the Amu
selfhost and Kotoba native CDCI gates and a loaderless x86_64-linux-static
controller. CLJK/CLJC/CLJS, NBB/KBB, Clojure, JVM/Java/GraalVM, Node and C
compiler/loader/runtime prerequisites are retired from that final closure.

## Removed registration

Delete `.github/workflows/test.yml`, the one `clojure` job triggered by pull
requests and pushes to main. It installs the Clojure CLI, checks out a pinned
JVM compatibility loader from kotoba-lang/kotoba, runs the hosted CLJK suite,
and uses Python to check that the hosted runner executed a nonempty suite.
Those mechanisms do not qualify Kotoba / Amu selfhost. The registration is
removed without replacing it with an unconditional success or empty suite.

The complete workflow is preserved by the immutable pre-retirement commit
`9510241bf8892a2d700877ad5fa784f410dcbd51`, path and Git blob in
[the retirement record](native-cdci-retirement.edn). Source, tests, dependency
manifests, corpus and recorded observations are unchanged by this cleanup.
The full corpus remains material to port and qualify. Historical hosted
evidence keeps its original provenance; it is not native execution evidence.

A fresh pre-change branch/rules read showed main unprotected, with no
required checks and no applied branch rules. This cleanup does not change
any protection setting, live service, production route or dependency pin.

## Open acceptance

The complete owning ELF64, PE32+ and Mach-O encoders, all public exports,
validation/refusal/bound/resource behavior and transitive source closure
must be integrated from canonical Kotoba and built with an Amu-produced
compiler. Keep container construction separate from compiler lowering,
target ABI, entry/layout/linker policy and filesystem publication. The Linux
static consumer requires ELF64; that does not remove the sibling formats.

Actual native positive/refusal/resource/corpus evidence, Definition CIDs,
reviewed owning main/source/lock and consuming compiler pins, whole package
integration and Amu self-rebuild remain open. The existing canonical object
port draft is source work, not a qualified implementation or gate. Current
CLJK/JVM/NBB sources and dependencies remain migration inventory to port and
retire; this workflow deletion does not complete that migration.

No implementation, encoder, compiler/generator/loader, native runtime or
tests were run for this cleanup; no tests were added. The native controller
and two gates are unqualified. Do not substitute the retired JVM/KBB job as
a final comparison requirement or require its compatibility loader as a pin.
