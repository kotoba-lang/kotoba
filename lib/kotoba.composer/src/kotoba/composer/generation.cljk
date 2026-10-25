(ns kotoba.composer.generation
  "One generation/regeneration event record for a track or stem — mirrors
  `ai.gftd.ongakuka.generation`'s record schema exactly (ADR-2607031510).
  Audit + metering source of truth: any composing actor emits one of these
  per pipeline stage it runs, giving a consistent audit shape across every
  consumer instead of each actor inventing its own.

  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM.")

(def stages
  "Valid generation stages, matching the lexicon's stage enum and
  `kotoba.composer.pipeline`'s state machine."
  #{:lyric :compose :vocal :arrange :mix :review :regenerate})

(def statuses
  "Valid generation outcome statuses."
  #{:ok :rejected :failed})

(defn generation
  "Construct a generation/audit record. `target-uri`/`stage`/`model-id`/
  `status` are required (matching the lexicon's own `required` list).
  Returns nil when a required field is missing/malformed."
  [{:keys [target-uri stage actor-did model-id params prompt-tokens
           completion-tokens audio-sec inference-ms credits-consumer
           credits-operator node status reject-reason created-at]}]
  (when (and (string? target-uri) (seq target-uri)
             (contains? stages stage)
             (string? model-id) (seq model-id)
             (contains? statuses status))
    {:composer.generation/target-uri        target-uri
     :composer.generation/stage             stage
     :composer.generation/actor-did         actor-did
     :composer.generation/model-id          model-id
     :composer.generation/params            params
     :composer.generation/prompt-tokens     prompt-tokens
     :composer.generation/completion-tokens completion-tokens
     :composer.generation/audio-sec         audio-sec
     :composer.generation/inference-ms      inference-ms
     :composer.generation/credits-consumer  credits-consumer
     :composer.generation/credits-operator  credits-operator
     :composer.generation/node              node
     :composer.generation/status            status
     :composer.generation/reject-reason     reject-reason
     :composer.generation/created-at        created-at}))

(defn generation-valid?
  "True when m is a well-formed generation record (as produced by
  generation)."
  [m]
  (boolean
   (and (map? m)
        (generation {:target-uri        (:composer.generation/target-uri m)
                     :stage             (:composer.generation/stage m)
                     :actor-did         (:composer.generation/actor-did m)
                     :model-id          (:composer.generation/model-id m)
                     :params            (:composer.generation/params m)
                     :prompt-tokens     (:composer.generation/prompt-tokens m)
                     :completion-tokens (:composer.generation/completion-tokens m)
                     :audio-sec         (:composer.generation/audio-sec m)
                     :inference-ms      (:composer.generation/inference-ms m)
                     :credits-consumer  (:composer.generation/credits-consumer m)
                     :credits-operator  (:composer.generation/credits-operator m)
                     :node              (:composer.generation/node m)
                     :status            (:composer.generation/status m)
                     :reject-reason     (:composer.generation/reject-reason m)
                     :created-at        (:composer.generation/created-at m)}))))

(defn validate-generation
  "Return a validation result for a candidate generation map."
  [m]
  (cond
    (not (map? m))                {:composer/valid? false :composer/error :not-a-map}
    (not (generation-valid? m))   {:composer/valid? false :composer/error :malformed-generation}
    :else                         {:composer/valid? true :composer/generation m}))

(defn for-target
  "Return the generation events targeting target-uri, from a coll of
  generation records."
  [generations target-uri]
  (filterv #(= target-uri (:composer.generation/target-uri %)) generations))

(defn ok?
  "True when a generation event's status is :ok."
  [generation]
  (= :ok (:composer.generation/status generation)))
