# Kotoba native migration

Use the Kotoba Labs Linear workspace. This migration is tracked by AWAI-24,
AWAI-43, AWAI-48 and JUN-290. Workspace architecture and authority rules apply.

## CDCI

Use Amu selfhost and canonical Kotoba only. Do not restore CLJK/CLJC, NBB,
KBB, Clojure, JVM/Java, GraalVM, Node or a C compiler/loader as a CI prerequisite
or fallback. Python scripts may stage/hash bytes and observe native processes;
they must not implement language resolution, compilation or verdicts.

The 2026-10-24 replacement removes the JVM/Node launcher job and the macOS C
loader toolchain. Original definitions/scripts are byte-preserved as inert
text under `docs/retired/native-ci-20261024/` with their hashes. Do not execute
these archives. The static documentation Pages workflow remains separate.

Current native CI checks the pinned loaderless Amu root, combined selfhost,
all12 CLI request parsing with all declared flags/aliases and refusals, and
the Amu/Kotoba native controller on an actual x86 Linux runner. The controller
qualifies its declared complete24 Kotoba corpus, not this product's whole CLI.
All native guests run without a hosted language executable in their PATH.

The public launcher still contains retired host routes. Do not run them.
All12 command execution, package/signature admission, general FS fault/race
parity, public target parity and the old library/runtime-value oracle corpus
remain open until ported and qualified. A green request-parser or controller
job must not mark these acceptance criteria Done. Legacy JVM/JS lint, Q9,
runtime-values, SDK packaging, library and package admission jobs no longer
run in CI; preserve their fixtures while porting their checks to native code.

## JUN-93 shared native text

The canonical text owner is lib/kotoba.text; kotoba-lang/text is archived.
Maintain the immutable imports and explicit local-changes source/addition
hashes. Extend the existing loaderless native CI; retain its CLI request and
controller gates. Shared component goldens do not qualify the whole library
catalog, public CLI execution or the P4 desktop.

Native text keeps Unicode whitespace excluding U+00A0/U+2007/U+202F, ASCII
lower preserving non-ASCII, and an empty needle matching every string.
Do not alias the differently named ASCII whitespace/UTF-8 byte-index kernels
to full text APIs. Native index-of retains UTF-16/option semantics and both arities; join takes
typed string lists and preserves empty fields. CSSOM capture regex and full
Unicode case remain distinct qualification requirements. Preserve all graph declarations.
