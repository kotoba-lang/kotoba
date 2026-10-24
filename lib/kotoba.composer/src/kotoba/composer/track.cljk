(ns kotoba.composer.track
  "Generated music track record — mirrors `ai.gftd.ongakuka.track`'s record
  schema exactly (ADR-2607031510). See `kotoba.composer` for the ns-level
  scope note (this models ongakuka's OUTER track record, not its internal
  composer stage).

  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM.")

(def statuses
  "Valid track pipeline statuses, matching the lexicon's status enum and
  `kotoba.composer.pipeline`'s state machine."
  #{:queued :lyric :compose :vocal :mix :review :published :rejected :failed})

(def min-bpm 30)
(def max-bpm 300)
(def min-duration-sec 5)
(def max-duration-sec 600)

(defn track
  "Construct a track record. `title`/`lyrics`/`style`/`status` are required
  (matching the lexicon's own `required` list). Returns nil when a required
  field is missing/malformed or `bpm`/`duration-sec` fall outside the
  lexicon's stated bounds."
  [{:keys [title lyrics style style-ref-uri language bpm duration-sec status
           blob-key mime-type project-id model-id seed created-at]}]
  (when (and (string? title) (seq title) (<= (count title) 200)
             (string? lyrics) (seq lyrics)
             (string? style) (seq style)
             (contains? statuses status)
             (or (nil? bpm) (and (integer? bpm) (<= min-bpm bpm max-bpm)))
             (or (nil? duration-sec)
                 (and (integer? duration-sec)
                      (<= min-duration-sec duration-sec max-duration-sec))))
    {:composer.track/title         title
     :composer.track/lyrics        lyrics
     :composer.track/style         style
     :composer.track/style-ref-uri style-ref-uri
     :composer.track/language      language
     :composer.track/bpm           bpm
     :composer.track/duration-sec  duration-sec
     :composer.track/status        status
     :composer.track/blob-key      blob-key
     :composer.track/mime-type     mime-type
     :composer.track/project-id    project-id
     :composer.track/model-id      model-id
     :composer.track/seed          seed
     :composer.track/created-at    created-at}))

(defn track-valid?
  "True when m is a well-formed track record (as produced by track)."
  [m]
  (boolean
   (and (map? m)
        (track {:title         (:composer.track/title m)
                :lyrics        (:composer.track/lyrics m)
                :style         (:composer.track/style m)
                :style-ref-uri (:composer.track/style-ref-uri m)
                :language      (:composer.track/language m)
                :bpm           (:composer.track/bpm m)
                :duration-sec  (:composer.track/duration-sec m)
                :status        (:composer.track/status m)
                :blob-key      (:composer.track/blob-key m)
                :mime-type     (:composer.track/mime-type m)
                :project-id    (:composer.track/project-id m)
                :model-id      (:composer.track/model-id m)
                :seed          (:composer.track/seed m)
                :created-at    (:composer.track/created-at m)}))))

(defn validate-track
  "Return a validation result for a candidate track map."
  [m]
  (cond
    (not (map? m))          {:composer/valid? false :composer/error :not-a-map}
    (not (track-valid? m))  {:composer/valid? false :composer/error :malformed-track}
    :else                   {:composer/valid? true :composer/track m}))

(def terminal-statuses
  "Statuses from which the pipeline reducer makes no further transition."
  #{:published :rejected :failed})

(defn terminal?
  "True when track's status is terminal (published/rejected/failed)."
  [track]
  (contains? terminal-statuses (:composer.track/status track)))
