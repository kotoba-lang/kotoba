(ns kami.ongaku.notation.e2e.main-driver
  "E2E-only, main-thread bundle for kami-ongaku-notation's real-browser
   AudioWorkletProcessor phrase proof. Uses kotoba-lang/org-w3-webaudio's
   own src/w3/webaudio.cljs binding layer (not raw AudioContext calls) --
   reusing its proven OfflineAudioContext + audioWorklet.addModule +
   AudioWorkletNode recipe rather than reinventing it -- to render the
   WHOLE phrase in ONE OfflineAudioContext (length = total-samples across
   all 4 notes), not one context per note.

   Compiled the same way as worklet_dsp.cljs (:optimizations advanced +
   self-polyfill.js) for consistency -- see that namespace's docstring."
  (:require [w3.webaudio :as w3a]))

(defn ^:export run-e2e [params]
  (let [{:keys [notes totalSamples sr attack decay sustain release
                workletUrl processorName]}
        (js->clj params :keywordize-keys true)
        ctx (w3a/new-offline-audio-context! 1 totalSamples sr)]
    (-> (w3a/add-worklet-module! ctx workletUrl)
        (.then
          (fn [_]
            (let [node (w3a/create-worklet-node!
                         ctx processorName
                         #js {:numberOfInputs 0
                              :numberOfOutputs 1
                              :outputChannelCount #js [1]
                              :processorOptions
                              #js {:notes (clj->js notes)
                                   :totalSamples totalSamples
                                   :sr sr :attack attack :decay decay
                                   :sustain sustain :release release}})]
              (w3a/connect! node (w3a/destination ctx))
              (w3a/start-rendering! ctx))))
        (.then
          (fn [audio-buffer]
            (let [ch0 (.getChannelData audio-buffer 0)]
              #js {:pcm (js/Array.from ch0)
                   :length (.-length ch0)
                   :sampleRate (w3a/sample-rate ctx)}))))))
