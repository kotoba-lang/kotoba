// AudioWorkletGlobalScope has no `self` (WorkletGlobalScope, unlike
// WorkerGlobalScope, does not define it), but Closure's goog.global
// detection (`goog.global = this || self`, in the Closure Library base
// bundled by cljs.main) unconditionally references bare `self` whenever
// anything in the build needs goog.global -- which this bundle's
// `^:export render-pattern` (-> goog.exportSymbol) does. Referencing an
// undeclared bare identifier throws ReferenceError; `typeof self` is the
// safe form of the same check. This is the standard technique non-browser
// JS runtimes use to run browser-oriented code (e.g. Node has historically
// polyfilled `global.self = global` for the same reason) -- not a hack
// specific to this repo. Identical fix, and identical root cause, as
// kotoba-lang/org-w3-webaudio's own test/e2e/page/self-polyfill.js (see
// that repo's README + scripts/build-e2e-bundles.sh for the full
// root-cause writeup); reused here verbatim rather than rediscovered. This
// file MUST stay textually BEFORE the compiled bundle in the same worklet
// module file (see scripts/build-e2e-bundles.sh).
if (typeof self === "undefined") { globalThis.self = globalThis; }
