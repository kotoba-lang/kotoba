(ns kami.ongaku.sequencer.e2e.main-driver
  "E2E-only, main-thread bundle for kami-ongaku-sequencer's real-browser
   AudioWorkletProcessor SMF-round-trip-to-playback proof. Uses
   kotoba-lang/org-w3-webaudio's own src/w3/webaudio.cljs binding layer (not
   raw AudioContext calls) -- reusing its proven OfflineAudioContext +
   audioWorklet.addModule + AudioWorkletNode recipe rather than reinventing
   it (org-w3-webaudio commit e554d853d6403c35b1ffe1c4adb37d2a1d557451).

   Also requires kami.ongaku.sequencer.e2e.fixture directly (the SAME .cljc source the
   worklet bundle and the offline nbb reference both use) purely to learn
   :total-samples ahead of time -- OfflineAudioContext requires a fixed
   buffer length up front, and fixture/render-plan is what determines how
   long a buffer holds this pattern's 5 notes. This bundle does NOT
   duplicate the DSP: fixture.cljc has no audio.synth dependency at all, so
   this is only the tick->sample scheduling math, not a re-synthesis.

   Compiled the same way as worklet_dsp.cljs (:optimizations advanced +
   self-polyfill.js) for consistency -- see that namespace's docstring.

   IMPORTANT (found by kami-ongaku-sampler's own main_driver.cljs, reused
   here verbatim): reading a property off a value that crossed INTO this
   compilation unit from outside (a MessagePort message) must use
   bracket/string-keyed access (`aget`), NOT dot-interop (`.-foo`) --
   worklet_dsp.cljs and this namespace are compiled by TWO SEPARATE
   `cljs.main -c` invocations (two independent Closure compilations, each
   with its OWN property-renaming map), so an incoming MessageEvent.data's
   properties are not protected from Closure's internal renaming pass the
   way an ^:export-ed function's own returned object literal is."
  (:require [w3.webaudio :as w3a]
            [kami.ongaku.sequencer.e2e.fixture :as fixture]))

(defn ^:export run-e2e [params]
  (let [{:keys [workletUrl processorName]} (js->clj params :keywordize-keys true)
        flat (fixture/post-roundtrip-flat)
        {:keys [total-samples]} (fixture/render-plan (:events flat))
        sr fixture/sr
        ctx (w3a/new-offline-audio-context! 1 total-samples sr)]
    (-> (w3a/add-worklet-module! ctx workletUrl)
        (.then
          (fn [_]
            (let [node (w3a/create-worklet-node!
                         ctx processorName
                         #js {:numberOfInputs 0
                              :numberOfOutputs 1
                              :outputChannelCount #js [1]})
                  ;; See org-w3-webaudio's own main_driver.cljs / kami-ongaku-
                  ;; sampler's main_driver.cljs docstring: cross-thread
                  ;; postMessage delivery is not guaranteed to precede
                  ;; startRendering()'s resolution, so build a genuine
                  ;; plan-promise and Promise.all it with the render promise.
                  plan-promise
                  (js/Promise.
                    (fn [resolve _reject]
                      (w3a/on-message! (w3a/port node)
                        (fn [ev] (resolve (aget (.-data ev) "plan"))))))]
              (w3a/connect! node (w3a/destination ctx))
              (js/Promise.all #js [plan-promise (w3a/start-rendering! ctx)]))))
        (.then
          (fn [pair]
            (let [plan (aget pair 0)
                  audio-buffer (aget pair 1)
                  ch0 (.getChannelData audio-buffer 0)]
              #js {:pcm (js/Array.from ch0)
                   :length (.-length ch0)
                   :sampleRate (w3a/sample-rate ctx)
                   :plan plan
                   :totalSamples total-samples}))))))
