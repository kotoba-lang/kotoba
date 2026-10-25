(ns whisper.main
  "Kotodama WASM entrypoint for the whisper clean-room STT/ASR actor (L5).

  Clean-room, API-compatible STT surface (OpenAI `audio/transcriptions` +
  `audio/translations` shape), data-driven over a Datomic-backed Kotoba schema.
  No proprietary code, model weights, or credentials — resource shapes only.

  Closes the one missing primitive in ADR-2606271930: `elevenlabs-compat` is
  TTS (speech out); `whisper-compat` is STT (speech in). Together they are the
  voice I/O of the `denwaban` actor, bound by the `koe-clj` session kernel.

  R0 scaffold: socket-free core. `transcribe` folds over the in-memory `*store*`;
  `stream-transcribe` is fixture-driven (partial Segments → final Transcription)
  so denwaban's barge-in can be tested without a socket. Live audio ingest is
  outward-gated (G7) and lands in a later R-cycle — `solve` raises at R0."
  (:require [kotoba.lang.text :as str]))

(def ns-prefix "whisper")
(def tier "L5")

;; --- schema-derived entity specs (single source the handlers fold over) ---
(def entity-specs
  [{:entity "Model"         :plural "models"         :id-prefix "whisper_mod"
    :fields [:modelId :name :languages :streaming :maxDurationSecs] :required [:name]
    :coerce {:streaming :bool :maxDurationSecs :int} :refs {}}
   {:entity "Transcription" :plural "transcriptions" :id-prefix "whisper_tr"
    :fields [:transcriptionId :modelId :language :text :durationSecs :final :confidence :createdAtUnix]
    :required [:modelId :text]
    :coerce {:durationSecs :float :final :bool :confidence :float :createdAtUnix :int}
    :refs {:modelId "Model"}}
   {:entity "Segment"       :plural "segments"       :id-prefix "whisper_seg"
    :fields [:segmentId :transcriptionId :startSecs :endSecs :text :final]
    :required [:transcriptionId :text]
    :coerce {:startSecs :float :endSecs :float :final :bool}
    :refs {:transcriptionId "Transcription"}}])

;; in-memory materialization used by the contract test + the WASM runtime
;; before a live engine binds. EAVT facts are emitted as `whisper.<Entity>/<field>`.
(def ^:dynamic *store* (atom {}))

(defn- spec-for [entity] (first (filter #(= entity (:entity %)) entity-specs)))

(defn emit-facts
  "Produce namespaced EAVT facts for an entity instance (no socket, no engine)."
  [entity id attrs]
  (let [{:keys [fields]} (spec-for entity)]
    (into [] (for [f fields :when (contains? attrs f)]
               [id (keyword (str ns-prefix "." entity) (name f)) (get attrs f)]))))

(defn transcribe
  "Non-streaming transcription contract: validate required fields against the
  Model spec and materialize a final Transcription into *store*. Pure — accepts
  an already-decoded request map (audio bytes are a host capability, not here)."
  [{:keys [modelId language text durationSecs] :as req}]
  (when (str/blank? (str modelId)) (throw (ex-info "modelId required" {:req req})))
  (let [id   (str "whisper_tr_" (hash [modelId text]))
        inst {:transcriptionId id :modelId modelId :language (or language "auto")
              :text (or text "") :durationSecs (or durationSecs 0.0)
              :final true :confidence 1.0}]
    (swap! *store* assoc-in [:Transcription id] inst)
    {:id id :facts (emit-facts "Transcription" id inst) :entity inst}))

(defn stream-transcribe
  "Streaming contract for barge-in: given a seq of partial chunk texts, return the
  ordered Segment stream (final=false) followed by the final Transcription
  (final=true). Fixture-driven at R0 — the host feeds chunks; no socket here."
  [{:keys [modelId language] :as _req} chunks]
  (let [segs (map-indexed
               (fn [i c] {:segmentId (str "whisper_seg_" i) :transcriptionId nil
                          :startSecs (double i) :endSecs (double (inc i))
                          :text c :final false})
               chunks)
        full (str/join " " chunks)
        {:keys [id entity]} (transcribe {:modelId modelId :language language :text full})]
    {:segments (mapv #(assoc % :transcriptionId id) segs)
     :final entity}))

(defn solve
  "R0 gate: no live audio ingest. Real socket/engine binding is outward-gated (G7)."
  [& _]
  (throw (ex-info "whisper-compat R0: live audio ingest is G7-gated; offline contract only"
                  {:status :r0 :gate "G7"})))
