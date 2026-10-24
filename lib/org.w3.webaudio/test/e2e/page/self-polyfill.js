// AudioWorkletGlobalScope has no `self` (WorkletGlobalScope, unlike
// WorkerGlobalScope, does not define it), but Closure's goog.global
// detection (`goog.global = this || self`, in the Closure Library base
// bundled by cljs.main) unconditionally references bare `self` whenever
// anything in the build needs goog.global -- which this bundle's own
// `(set! (.-kamiRenderNote js/goog.global) ...)` export does. Referencing
// an undeclared bare identifier throws ReferenceError; `typeof self` is the
// safe form of the same check. This is the standard technique non-browser
// JS runtimes use to run browser-oriented code (e.g. Node has historically
// polyfilled `global.self = global` for the same reason) -- not a hack
// specific to this repo. See scripts/build-e2e-bundles.sh for the full
// root-cause writeup and why this must be textually BEFORE the compiled
// bundle in the same worklet module file.
if (typeof self === "undefined") { globalThis.self = globalThis; }
