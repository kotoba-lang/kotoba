# Retired JVM host CI (2026-10-22)

The active JDK 17/21 Clojure test/lint workflow is retired. Its complete bytes
are preserved as non-executable `ci.yml.txt`, with a SHA-256 in `manifest.json`.
No GitHub Actions workflow is supplied by this evidence directory.

The old `clojure -M:test` path was recorded as discovering zero `.cljk` tests.
KBB/SCI also had a typed-binding baseline failure. Neither path is an accepted
native qualification route. The manifest preserves the original test sources
and legacy dependency configuration unchanged; this is not a port of them.

The target is the complete CSSOM component, both existing suites, all public
APIs and the full transitive dependency closure in canonical Kotoba, built
and executed through an independently qualified Amu selfhost toolchain.
The final closure must not require CLJK/CLJC/CLJS, NBB/KBB, Node, Clojure/JVM,
Java/Graal, or a C compiler/loader/runtime. A compatibility wrapper, a scanner
oracle, source inspection, or zero discovered tests cannot satisfy that gate.

Native qualification remains OPEN: no qualifying independent Amu-built,
loaderless compiler entry was available for this cleanup. No replacement
workflow, passing check, self-rebuild claim, or native test result is implied.
A future native gate must execute all suites with nonzero discovery, zero
skips and zero failures, including positive, refusal/authority, resource and
cleanup behavior, and preserve existing CSSOM/layout semantics.

This retirement changes no source API, test corpus, dependency pin, branch
protection, required context, live service, or production route.
