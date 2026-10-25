(ns kotoba.lang.kami-nv-compat.kami-drive.coc
  "Chain-of-Causation (CoC) reasoning schema — JVM port of src/kami-drive/coc.ts.
  Clean-room schema mirroring NVIDIA Alpamayo's CoC reasoning traces + the
  PhysicalAI-Autonomous-Vehicles `ood_reasoning` label record (clip uuid /
  event-cluster / human-refined narrative / keyframe indices), so existing
  CoC-labelled data ports by field-name mapping and the KAMI planner can emit
  the same trace structure. A CoC trace is an ordered list of causal steps
  (observation → inference → action, grounded to a keyframe) — making planner
  decisions auditable. No Alpamayo data/weights/text copied; from-spec schema.
  AV scope per wadachi / kami-autodrive. Wave 8 of ADR-2607020130."
  (:require [kotoba.lang.text :as str]))

(def event-clusters
  #{"nominal" "vru_interaction" "vehicle_cut_in" "intersection"
    "yield" "lane_change" "stop" "obstacle" "merge"})

(defn- lower-first [s]
  (if (str/blank? s) s (str (str/lower (subs s 0 1)) (subs s 1))))

(defn render-narrative
  "Render a default narrative from `steps` (deterministic; a verbalizer can
  replace this). Empty -> nominal-conditions sentence."
  [steps]
  (if (empty? steps)
    "Proceeding under nominal conditions."
    (str/join " "
      (for [s steps]
        (str "Because " (lower-first (:observation s)) ", "
             (lower-first (:inference s)) "; therefore "
             (lower-first (:action s)) ".")))))

(defprotocol ICausationBuilder
  (set-cluster! [this cluster])
  (add-step!    [this observation inference action] [this observation inference action keyframe-index])
  (build        [this]))

(defn causation-builder
  "Fluent builder for assembling a CoC trace step-by-step."
  ([]
   (causation-builder "nominal"))
  ([cluster]
   (let [state (atom {:cluster cluster :steps []})]
     (reify ICausationBuilder
       (set-cluster! [this c]
         (swap! state assoc :cluster c)
         this)
       (add-step! [this observation inference action]
         (add-step! this observation inference action 0))
       (add-step! [this observation inference action keyframe-index]
         (swap! state (fn [{:keys [steps]}]
                        {:cluster (:cluster @state)        ; cluster may have changed
                         :steps (conj steps {:index    (count steps)
                                             :observation observation
                                             :inference  inference
                                             :action     action
                                             :keyframe-index keyframe-index})}))
         this)
       (build [_]
         (let [{:keys [cluster steps]} @state]
           {:event-cluster cluster
            :steps         steps
            :narrative     (render-narrative steps)}))))))

;; ── dataset record (mirrors ood_reasoning.parquet) ────────────────────────

(defn parse-reasoning-record
  "Parse + validate a loosely-typed (string-keyed) map into a ReasoningRecord.
  Accepts snake_case or camelCase keys (dataset uses snake_case). Throws on a
  missing/invalid required field."
  [obj]
  (let [uuid (or (get obj "clipUuid") (get obj "clip_uuid") (get obj "uuid"))]
    (when-not (and (string? uuid) (pos? (count uuid)))
      (throw (ex-info "ReasoningRecord: clipUuid (string) is required" {:obj obj})))
    (let [cluster-raw (str (or (get obj "eventCluster") (get obj "event_cluster") "nominal"))]
      (when-not (contains? event-clusters cluster-raw)
        (throw (ex-info (str "ReasoningRecord: unknown eventCluster '" cluster-raw "'")
                        {:event-cluster cluster-raw})))
      (let [narrative (str (or (get obj "narrative") (get obj "chain_of_causation") ""))
            kf-raw    (or (get obj "keyframeIndices") (get obj "keyframe_indices") [])]
        (when-not (sequential? kf-raw)
          (throw (ex-info "ReasoningRecord: keyframeIndices must be an array" {:keyframe-indices kf-raw})))
        {:clip-uuid      uuid
         :event-cluster  cluster-raw
         :narrative      narrative
         :keyframe-indices (mapv #(long %) kf-raw)}))))

(defn record-from-trace
  "Build a dataset record from a clip id + a planner-emitted CoC trace."
  [clip-uuid coc]
  {:clip-uuid      clip-uuid
   :event-cluster  (:event-cluster coc)
   :narrative      (:narrative coc)
   :keyframe-indices (mapv :keyframe-index (:steps coc))
   :steps          (:steps coc)})

;; ── kotoba Datom bridge ───────────────────────────────────────────────────

(defn record->datoms
  "Project a reasoning record to append-only `:coc/*` datoms so a trace is
  queryable on the kotoba Datom log."
  [rec]
  (let [e (str "coc:" (:clip-uuid rec))
        base [{:e e :a ":coc/clip"          :v (:clip-uuid rec)}
              {:e e :a ":coc/event-cluster" :v (:event-cluster rec)}
              {:e e :a ":coc/narrative"     :v (:narrative rec)}]
        keyframes (for [k (:keyframe-indices rec)] {:e e :a ":coc/keyframe" :v k})
        step-datoms (mapcat (fn [s]
                              (let [se (str e ":step:" (:index s))]
                                [{:e se :a ":coc.step/of"          :v e}
                                 {:e se :a ":coc.step/observation" :v (:observation s)}
                                 {:e se :a ":coc.step/inference"   :v (:inference s)}
                                 {:e se :a ":coc.step/action"      :v (:action s)}
                                 {:e se :a ":coc.step/keyframe"    :v (:keyframe-index s)}]))
                            (:steps rec))]
    (vec (concat base keyframes step-datoms))))
