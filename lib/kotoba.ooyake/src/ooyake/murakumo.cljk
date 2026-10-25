(ns ooyake.murakumo
  "Pure cljc actor boundary generated from manifest migration scaffold."
  (:require [kotoba.lang.text :as str]
            [ooyake.cofog :as cofog]
            [ooyake.coverage :as coverage]
            [ooyake.procedure-graph :as procedure-graph]))

(def actor-did
  "did:web:ooyake.etzhayyim.com")

(def common-gates
  [:council-charter-attestation
   :no-platform-held-key-baseline
   :no-probing-baseline
   :murakumo-only-inference-baseline
   :did-primary-baseline
   :append-only-gate-baseline
   :kotoba-only-substrate-baseline])

(defn collection
  [name]
  (str "com.etzhayyim.ooyake." name))

(def cell-specs {
  :unit_registry {:legacy-cell "unit-registry"
     :phase :event
     :murakumo-node "reuben"
     :collections [(collection "unit_registry")]
     :required-gates common-gates
     :trigger "manifest cell unit_registry"
     :ceiling "Manifest-driven migration scaffold; explicit execution stays in runtime methods"}
  :reconcile {:legacy-cell "reconcile"
     :phase :event
     :murakumo-node "reuben"
     :collections [(collection "reconcile")]
     :required-gates common-gates
     :trigger "manifest cell reconcile"
     :ceiling "Manifest-driven migration scaffold; explicit execution stays in runtime methods"}
  :address_ingest {:legacy-cell "address-ingest"
     :phase :event
     :murakumo-node "reuben"
     :collections [(collection "address_ingest")]
     :required-gates common-gates
     :trigger "manifest cell address_ingest"
     :ceiling "Manifest-driven migration scaffold; explicit execution stays in runtime methods"}
  :procedure_link {:legacy-cell "procedure-link"
     :phase :event
     :murakumo-node "reuben"
     :collections [(collection "procedure_link")]
     :required-gates common-gates
     :trigger "manifest cell procedure_link"
     :ceiling "Manifest-driven migration scaffold; explicit execution stays in runtime methods"}
  :procedure_graph {:legacy-cell "procedure-graph"
     :phase :event
     :murakumo-node "gad"
     :collections [(collection "procedure_graph")]
     :required-gates common-gates
     :trigger "project :gov.procedure/* into primary langgraph/Pregel EDN plans"
     :ceiling "Member-support planning; BPMN remains visual/legacy interop, never an execution authority. External effects require explicit member consent and audit."}
  :atlas_serve {:legacy-cell "atlas-serve"
     :phase :event
     :murakumo-node "reuben"
     :collections [(collection "atlas_serve")]
     :required-gates common-gates
     :trigger "manifest cell atlas_serve"
     :ceiling "Manifest-driven migration scaffold; explicit execution stays in runtime methods"}
  :freshness {:legacy-cell "freshness"
     :phase :event
     :murakumo-node "reuben"
     :collections [(collection "freshness")]
     :required-gates common-gates
     :trigger "manifest cell freshness"
     :ceiling "Manifest-driven migration scaffold; explicit execution stays in runtime methods"}
  :world_model {:legacy-cell "world-model"
     :phase :event
     :murakumo-node "reuben"
     :collections [(collection "world_model")]
     :required-gates common-gates
     :trigger "manifest cell world_model"
     :ceiling "Manifest-driven migration scaffold; explicit execution stays in runtime methods"}
  :cofog_classify {:legacy-cell "cofog-classify"
     :phase :event
     :murakumo-node "reuben"
     :collections [(collection "cofog_classification")]
     :required-gates common-gates
     :trigger "classify ministry-level :gov.unit rows by COFOG"
     :ceiling "Read-side classification only; never an official budget claim"}
  :coverage_plan {:legacy-cell "coverage-plan"
     :phase :event
     :murakumo-node "reuben"
     :collections [(collection "coverage_gap")]
     :required-gates common-gates
     :trigger "derive per-country functional coverage gaps from existing :gov.unit rows"
     :ceiling "Read-side planning only; never fabricates government bodies or marks representative rows as complete"}
})

(defn safe-rkey
  [s]
  (let [clean (-> (str s)
                  (str/replace #"^did:web:" "")
                  (str/replace #"[^A-Za-z0-9._~-]" "-"))]
    (if (str/blank? clean) "unknown" clean)))

(defn gate-value
  [attestations gate]
  (or (get attestations gate)
      (get attestations (name gate))
      (when (set? attestations) (attestations gate))
      (when (set? attestations) (attestations (name gate)))))

(defn missing-gates
  [spec attestations]
  (->> (:required-gates spec)
       (remove #(boolean (gate-value attestations %)))
       vec))

(defn put-record-effect
  [collection rkey record]
  {:op :mst/put-record
   :actor actor-did
   :collection collection
   :rkey rkey
   :record record})

(defn records-for
  [spec {:keys [records record computed-at request-id]
         :as input}]
  (let [input-records (cond
                        (map? records) records
                        (some? record) {0 record}
                        :else {})
        base {:actorDid actor-did
              :computedAt computed-at
              :legacyCell (:legacy-cell spec)
              :phase (:phase spec)
              :requestId request-id
              :actorBoundary "cljc-migration-scaffold"
              :scaffold true
              :constitutionalStatus "attested-plan"}]
    (map-indexed
     (fn [idx coll]
       (let [record* (merge {:$type coll}
                            base
                            (or (get input-records coll)
                                (get input-records idx)
                                {}))
             rkey (safe-rkey (or (:rkey record*)
                                 (get record* "rkey")
                                 (:tid record*)
                                 request-id
                                 (str (:legacy-cell spec) "-" idx)))]
         {:collection coll
          :record record*
          :rkey rkey}))
     (:collections spec))))

(defn- cofog-records
  [{:keys [units unit computed-at request-id]}]
  (let [units* (cond
                 (sequential? units) units
                 (some? unit) [unit]
                 :else [])]
    (mapv
     (fn [unit*]
       (let [record (merge {:actorDid actor-did
                            :computedAt computed-at
                            :legacyCell "cofog-classify"
                            :phase :event
                            :requestId request-id
                            :actorBoundary "cljc-cofog-classifier"
                            :constitutionalStatus "support-metadata-classification"
                            :officialChannel false}
                           (cofog/classification-record unit*))]
         {:collection (collection "cofog_classification")
          :record record
          :rkey (safe-rkey (or (:gov.unit/id unit*) request-id "cofog-classification"))}))
     units*)))

(defn- procedure-graph-records
  [{:keys [procedures procedure computed-at request-id]}]
  (let [procedures* (cond
                      (sequential? procedures) procedures
                      (some? procedure) [procedure]
                      :else [])]
    (mapv
     (fn [procedure*]
       (let [record (merge {:actorDid actor-did
                            :computedAt computed-at
                            :legacyCell "procedure-graph"
                            :phase :event
                            :requestId request-id
                            :actorBoundary "cljc-procedure-graph"
                            :constitutionalStatus "member-support-planning"
                            :officialChannel false}
                           (procedure-graph/procedure-record procedure*))]
         {:collection (collection "procedure_graph")
          :record record
          :rkey (safe-rkey (or (procedure-graph/rkey procedure*) request-id "procedure-graph"))}))
     procedures*)))

(defn- coverage-gap-records
  [{:keys [units computed-at request-id]}]
  (mapv
   (fn [gap]
     (let [record (merge {:actorDid actor-did
                          :computedAt computed-at
                          :legacyCell "coverage-plan"
                          :phase :event
                          :requestId request-id
                          :actorBoundary "cljc-coverage-planner"
                          :constitutionalStatus "member-support-gap-plan"
                          :officialChannel false}
                         gap)]
       {:collection (collection "coverage_gap")
        :record record
        :rkey (safe-rkey (str (:coverage.gap/jurisdiction gap)
                             "."
                             (name (:coverage.gap/category gap))))}))
   (coverage/gap-records (or units []))))

(defn cell-plan
  [cell-key {:keys [attestations] :as input}]
  (let [spec (get cell-specs cell-key)]
    (when-not spec
      (throw (ex-info "unknown cell" {:cell cell-key})))
    (let [missing (missing-gates spec attestations)]
      (merge
       {:cell cell-key
        :legacy-cell (:legacy-cell spec)
        :actor actor-did
        :phase (:phase spec)
        :murakumo-node (:murakumo-node spec)
        :trigger (:trigger spec)
        :ceiling (:ceiling spec)
        :required-gates (:required-gates spec)
        :missing-gates missing}
       (if (seq missing)
         {:status :blocked
          :effects []}
         (let [planned-records (case cell-key
                                 :cofog_classify (cofog-records input)
                                 :procedure_graph (procedure-graph-records input)
                                 :coverage_plan (coverage-gap-records input)
                                 (records-for spec input))]
           {:status :ready
            :records (vec planned-records)
            :effects (mapv (fn [{:keys [collection record rkey]}]
                             (put-record-effect collection rkey record))
                           planned-records)}))))))

(defn all-cell-plans
  [input]
  (into {}
        (map (fn [cell-key] [cell-key (cell-plan cell-key input)]))
        (keys cell-specs)))
