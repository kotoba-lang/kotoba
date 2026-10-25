# Native DOM component (JUN-93)

The JVM 17/21 setup-java/setup-clojure test/lint workflow has been deleted
under JUN-290. Do not restore JVM/nbb or a hosted/C-loader fallback.

The native facade and dom-core use typed `:document` values. Their nine
declared exports are checked as imported library functions, not external
container exports. Test `test/native/dom.kotoba` through the shared Browser
native gate using an Amu-produced compiler and exact source locks; Python may
stage/hash/observe, never replace the native verdict. Record ARM and x86
execution separately. See kotoba-lang/browser/scripts/check-shared-native.py.

The native golden covers document construction, root/children/attribute/style
changes, tree construction and operation consumption. The former full hosted
DOM/HTML/GPU test and lint matrix is no longer covered by CI. CSSOM, GPU output,
Browser surface and the kernel desktop remain separate qualification gates.

The native-shared workflow now executes the current owner fixture on both native
ARM and x86 Linux using an immutable Amu commit and pinned shared dependencies.
It hashes the actual compiler image, locks all discovered source bytes and
preserves Kotoba verdicts/refusals as artifacts. Its bounded result does not
restore the uncovered legacy full host suite or qualify the P4 desktop.
