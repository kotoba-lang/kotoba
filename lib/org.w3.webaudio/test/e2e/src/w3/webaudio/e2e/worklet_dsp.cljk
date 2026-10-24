(ns w3.webaudio.e2e.worklet-dsp
  "E2E-only, worklet-side bundle for org-w3-webaudio's real-browser
   AudioWorkletProcessor proof (see README, 'Real-browser AudioWorklet DSP
   E2E'). Requires kotoba-lang/audio's own audio.synth namespace directly --
   the .cljc DSP source of truth -- so this is not a worklet-only
   reimplementation of the DSP: it's the actual audio.cljc code running
   inside AudioWorkletGlobalScope.

   Exposes one render-note entrypoint via ^:export (-> goog.exportSymbol),
   callable from the hand-written AudioWorkletProcessor tail
   (test/e2e/page/worklet-processor-tail.js) at its munged path
   w3.webaudio.e2e.worklet_dsp.render_note.

   NOTE: a plain `(set! (.-x js/goog.global) f)` (bypassing ^:export) is NOT
   a safe substitute -- tried first, and Closure's :advanced whole-program
   DCE silently removed the entire assignment (and the function body behind
   it) in a sibling bundle in this same E2E (w3.webaudio.e2e.main-driver)
   despite the identical-looking pattern working here. `^:export` /
   `goog.exportSymbol` is the one mechanism Closure's optimizer passes
   explicitly special-case as always-keep; don't reinvent it."
  (:require [audio.synth :as synth]))

(defn ^:export render-note
  "-> Float32Array. Renders `dur-samples` samples of a `freq` Hz sine wave
   at `sample-rate` sr through an ADSR envelope -- exactly audio.synth's own
   sine-wave + adsr + apply-envelope composition (this *is* that code
   running inside the worklet, not a port of it)."
  [freq sr dur-samples gate-off attack decay sustain release]
  (let [osc (synth/sine-wave freq sr dur-samples)
        env (synth/adsr {:attack attack :decay decay :sustain sustain
                          :release release :gate-off gate-off :sample-rate sr}
                         dur-samples)
        buf (synth/apply-envelope osc env)]
    (js/Float32Array.from (clj->js buf))))
