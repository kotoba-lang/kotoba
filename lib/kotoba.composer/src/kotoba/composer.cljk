(ns kotoba.composer
  "AI music composition requests — pure data contracts (ADR-2607031510).

  A kotoba-lang capability library. No network, no I/O, no model call.
  Models the compose-request record any caller sends to
  `ai.gftd.ongakuka.compose` (a cross-project XRPC surface) 1:1 with that
  lexicon's input schema, so a caller constructs a valid request without
  re-deriving the shape from the raw lexicon JSON each time.

  `ongakuka.compose`'s own internal pipeline is `lyricist→composer→
  vocalist‖arranger→mixer→critic` — this namespace is NOT that internal
  'composer' stage. It models the OUTER request contract any external actor
  (yukkuri or otherwise) uses to talk to ongakuka as a whole. See
  `kotoba.composer.pipeline` for the status-transition reducer over the
  resulting track, and `kotoba.composer.track`/`.stem`/`.style`/
  `.generation` for the response-side records.

  The actual XRPC call to ongakuka (network I/O, auth, retries) stays with
  the app-level actor that owns the deployment — same separation of
  concerns `kotoba.webrtc.session` uses (host injects every concrete
  capability; this library only models the records).

  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM.")

(def min-duration-sec 5)
(def max-duration-sec 600)
(def default-duration-sec 90)

(defn compose-request
  "Construct a compose-request record, mirroring `ai.gftd.ongakuka.compose`'s
  input schema exactly. `lyrics` and `style` are required (matching the
  lexicon's own `required` list); `duration-sec` defaults to 90 when absent,
  matching the lexicon's own default. `stems?` requests additional vocal/
  inst/drum/bass stem outputs alongside the mixed master. Returns nil when a
  required field is missing or malformed — never a partially-valid record."
  [{:keys [title lyrics style style-ref-uri language bpm duration-sec
           model-id seed stems?]}]
  (when (and (string? lyrics) (seq lyrics)
             (string? style) (seq style)
             (or (nil? title) (and (string? title) (<= (count title) 200)))
             (or (nil? duration-sec)
                 (and (integer? duration-sec)
                      (<= min-duration-sec duration-sec max-duration-sec))))
    {:composer/title         title
     :composer/lyrics        lyrics
     :composer/style         style
     :composer/style-ref-uri style-ref-uri
     :composer/language      language
     :composer/bpm           bpm
     :composer/duration-sec  (or duration-sec default-duration-sec)
     :composer/model-id      model-id
     :composer/seed          seed
     :composer/stems?        (boolean stems?)}))

(defn compose-request-valid?
  "True when m is a well-formed compose-request record (as produced by
  compose-request)."
  [m]
  (boolean
   (and (map? m)
        (compose-request {:title         (:composer/title m)
                          :lyrics        (:composer/lyrics m)
                          :style         (:composer/style m)
                          :style-ref-uri (:composer/style-ref-uri m)
                          :language      (:composer/language m)
                          :bpm           (:composer/bpm m)
                          :duration-sec  (:composer/duration-sec m)
                          :model-id      (:composer/model-id m)
                          :seed          (:composer/seed m)
                          :stems?        (:composer/stems? m)}))))

(defn validate-compose-request
  "Return a validation result for a candidate compose-request map."
  [m]
  (cond
    (not (map? m))                       {:composer/valid? false :composer/error :not-a-map}
    (not (compose-request-valid? m))      {:composer/valid? false :composer/error :malformed-request}
    :else                                 {:composer/valid? true :composer/request m}))
