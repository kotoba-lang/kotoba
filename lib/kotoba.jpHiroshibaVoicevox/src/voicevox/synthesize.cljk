(ns voicevox.synthesize
  "High-level text -> WAV bytes, combining `voicevox.client`'s HTTP calls
  with the speedScale/pitchScale override logic
  `ai-gftd-project-yukkuri`'s `yukkuri.voicevox/synthesize-plan` described
  as a plan only. This is the real execution of that plan."
  (:require [kotoba.lang.text :as str]
            [voicevox.client :as client]))

#?(:clj
(defn synthesize!
  "{:text :style-id :speed :pitch} -> WAV bytes (byte[]). speed/pitch
  default to 1.0/0.0 (VOICEVOX's own neutral defaults); only applied as
  AudioQuery overrides when non-default, mirroring the Python
  `if speed != 1.0` / `if pitch != 0.0` guards this was ported from.
  Throws ex-info (via voicevox.client) on any transport/API failure; throws
  plain ex-info on blank text (mirrors the original's `raise ValueError`)."
  ([opts] (synthesize! opts {}))
  ([{:keys [text style-id speed pitch] :or {speed 1.0 pitch 0.0}} http-opts]
   (when (str/blank? text)
     (throw (ex-info "voicevox synthesize: empty text" {:stage :validate})))
   (let [query (client/audio-query! style-id text http-opts)
         query (cond-> query
                 (not= speed 1.0) (assoc :speedScale speed)
                 (not= pitch 0.0) (assoc :pitchScale pitch))]
     (client/synthesis! style-id query http-opts)))))
