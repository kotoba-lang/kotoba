# Native shared Browser integration (JUN-93)

Follow the workspace Kotoba app/client-runtime contract. App origins distribute
static artifacts; this repository must not create an application-origin proxy
or its own descriptor/consent broker.

The JVM setup-java/setup-clojure test/lint workflow has been deleted under
JUN-290. Do not restore it, nbb, a hosted compiler or a C loader as a fallback.
The replacement gate is `scripts/check-shared-native.py`, with an Amu-produced
native compiler and immutable source locks. It executes the canonical text,
DOM and all13 text-edit reducer exports through checked-in Kotoba goldens.
Native x86 qualification additionally requires the locked typed-project route.
Native ARM and native x86 outcomes must be recorded separately.

This does not cover the former full hosted Browser tests/lint, shared CSSOM,
surface/input, a kernel desktop, accessibility, reference hardware, dapps or
state restoration. Keep those qualification gaps open. Do not delete source
declarations to make a graph compile. Preserve other owners' source ports.

The native-shared workflow now executes the current owner fixture on both native
ARM and x86 Linux using an immutable Amu commit and pinned shared dependencies.
It hashes the actual compiler image, locks all discovered source bytes and
preserves Kotoba verdicts/refusals as artifacts. Its bounded result does not
restore the uncovered legacy full host suite or qualify the P4 desktop.
