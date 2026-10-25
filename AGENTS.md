# Native-only CDCI and shared text (JUN-93 / JUN-290)

Follow the workspace architecture and native-only CI contract. The canonical
text owner is `lib/kotoba.text`; the old kotoba-lang/text repository is archived.
Keep immutable import snapshots and update explicit local-changes provenance
for maintained sources. Do not change independent profile/credential stores.

The old CI workflow has been deleted: it started JVM/Clojure/SCI/nbb/Node for
launcher, library, security, qualification, provenance and lint checks. Its
other job compiled `adopted-loader-20261012.c` with clang and used that C loader
for old native selfbuild/runtime/library fixtures. Neither is an accepted
native fallback. Their source fixtures remain, but those checks are uncovered
until a real Amu-produced loaderless route is qualified. Do not silently
reclassify historical C-supervisor receipts as current native passes.

The replacement shared component gate uses the Amu native root/public compiler,
exact source locks and `kotoba-lang/browser/scripts/check-shared-native.py`.
Its bounded text/DOM/text-edit goldens do not qualify this repository's whole
CLI, full library catalog, security or Q9 behavior. Record ARM and x86 native
execution separately, and keep broader closure checks blocked.

Native text keeps host names and contracts for the typed string profile:
Unicode whitespace excludes U+00A0/U+2007/U+202F; ascii-lower preserves non-ASCII;
includes? accepts an empty needle. The ASCII bounded-text whitespace/index
helpers have different contracts and cannot replace full text APIs silently.
CSSOM capture regex, index-of/join and full Unicode case APIs remain separate
qualification requirements. Preserve every declaration in selected graphs.
