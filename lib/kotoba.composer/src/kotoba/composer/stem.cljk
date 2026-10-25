(ns kotoba.composer.stem
  "Per-stem audio record, child of a track — mirrors
  `ai.gftd.ongakuka.stem`'s record schema exactly (ADR-2607031510).

  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM.")

(def kinds
  "Valid stem kinds, matching the lexicon's kind enum."
  #{:vocal :chorus :drums :bass :guitar :keys :synth :strings :fx :other
    :instrumental :fullmix})

(defn stem
  "Construct a stem record. `track-uri`/`kind`/`blob-key`/`mime-type` are
  required (matching the lexicon's own `required` list). Returns nil when a
  required field is missing/malformed."
  [{:keys [track-uri kind blob-key mime-type duration-sec loudness-lufs
           actor-did created-at]}]
  (when (and (string? track-uri) (seq track-uri)
             (contains? kinds kind)
             (string? blob-key) (seq blob-key)
             (string? mime-type) (seq mime-type))
    {:composer.stem/track-uri     track-uri
     :composer.stem/kind          kind
     :composer.stem/blob-key      blob-key
     :composer.stem/mime-type     mime-type
     :composer.stem/duration-sec  duration-sec
     :composer.stem/loudness-lufs loudness-lufs
     :composer.stem/actor-did     actor-did
     :composer.stem/created-at    created-at}))

(defn stem-valid?
  "True when m is a well-formed stem record (as produced by stem)."
  [m]
  (boolean
   (and (map? m)
        (stem {:track-uri     (:composer.stem/track-uri m)
               :kind          (:composer.stem/kind m)
               :blob-key      (:composer.stem/blob-key m)
               :mime-type     (:composer.stem/mime-type m)
               :duration-sec  (:composer.stem/duration-sec m)
               :loudness-lufs (:composer.stem/loudness-lufs m)
               :actor-did     (:composer.stem/actor-did m)
               :created-at    (:composer.stem/created-at m)}))))

(defn validate-stem
  "Return a validation result for a candidate stem map."
  [m]
  (cond
    (not (map? m))         {:composer/valid? false :composer/error :not-a-map}
    (not (stem-valid? m))  {:composer/valid? false :composer/error :malformed-stem}
    :else                  {:composer/valid? true :composer/stem m}))

(defn stems-of-kind
  "Return the stems of the given kind from a coll of stem records."
  [stems kind]
  (filterv #(= kind (:composer.stem/kind %)) stems))
