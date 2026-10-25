(ns ooyake.murakumo-test
  (:require [clojure.test :refer [deftest is]]
            [ooyake.cofog :as cofog]
            [ooyake.coverage :as coverage]
            [ooyake.murakumo :as ooyake]
            [ooyake.procedure-graph :as procedure-graph]))

(def full-attestations
  (into {}
        (map (fn [gate] [gate (str "attested-" (name gate))]))
        (distinct (mapcat :required-gates (vals ooyake/cell-specs)))))

(deftest maps-ooyake-atlas-cells
  (is (= #{"unit-registry"
           "reconcile"
           "address-ingest"
           "procedure-link"
           "procedure-graph"
           "atlas-serve"
           "freshness"
           "world-model"
           "cofog-classify"
           "coverage-plan"}
         (set (map :legacy-cell (vals ooyake/cell-specs))))))

(deftest r0-gates-block-effects
  (let [plan (ooyake/cell-plan :cofog_classify
                               {:unit {:gov.unit/id "gov.jpn.mod"
                                       :gov.unit/name-en "Ministry of Defense"}})]
    (is (= :blocked (:status plan)))
    (is (= [:council-charter-attestation
            :no-platform-held-key-baseline
            :no-probing-baseline
            :murakumo-only-inference-baseline
            :did-primary-baseline
            :append-only-gate-baseline
            :kotoba-only-substrate-baseline]
           (:missing-gates plan)))
    (is (empty? (:effects plan)))))

(deftest cofog-taxonomy-normalizes-government-function-codes
  (is (= "02" (cofog/normalize-code "2")))
  (is (= "03.1" (cofog/normalize-code "3.1")))
  (is (cofog/valid-code? "09"))
  (is (= "Education" (:cofog/name (cofog/cofog-entry "09")))))

(deftest ministry-unit-carries-cofog-at-ministry-level
  (let [unit (cofog/ministry-unit {:jurisdiction "jpn"
                                   :ministry-kind :education
                                   :slug "mext"
                                   :name-en "Ministry of Education, Culture, Sports, Science and Technology"
                                   :official-url "https://www.mext.go.jp/"
                                   :wikidata "Q1137665"
                                   :sourcing :authoritative
                                   :provenance "https://www.mext.go.jp/"
                                   :last-verified "2026-07-01"
                                   :verification-status :maintainer-verified})]
    (is (= :ministry (:gov.unit/level unit)))
    (is (= :education (:gov.unit/ministry-kind unit)))
    (is (= ["09"] (:gov.unit/cofog unit)))))

(deftest explicit-cofog-wins-over-inference
  (let [classification (cofog/classify-unit {:gov.unit/id "gov.example.custom"
                                             :gov.unit/level :ministry
                                             :gov.unit/name-en "Ministry of Health and Welfare"
                                             :gov.unit/cofog ["10"]})]
    (is (= ["10"] (:gov.unit/cofog classification)))
    (is (= :explicit (:cofog/source classification)))))

(deftest cofog-classify-cell-emits-support-metadata-classification
  (let [plan (ooyake/cell-plan :cofog_classify
                               {:attestations full-attestations
                                :request-id "req-001"
                                :computed-at "2026-07-01T00:00:00Z"
                                :unit {:gov.unit/id "gov.usa.defense"
                                       :gov.unit/level :ministry
                                       :gov.unit/name-en "Department of Defense"}})
        effect (first (:effects plan))]
    (is (= :ready (:status plan)))
    (is (= "com.etzhayyim.ooyake.cofog_classification" (:collection effect)))
    (is (= ["02"] (get-in effect [:record :cofog.classification/codes])))
    (is (= false (get-in effect [:record :officialChannel])))
    (is (= "support-metadata-classification"
           (get-in effect [:record :constitutionalStatus])))))

(deftest procedure-graph-prioritizes-langgraph-and-pregel-over-bpmn
  (let [record (procedure-graph/procedure-record
                {:gov.procedure/id "gov.jpn.shinjuku.residence-certificate"
                 :gov.procedure/owner-unit "gov.jpn.tokyo.shinjuku"
                 :gov.procedure/channel :counter
                 :gov.procedure/required-docs ["identity-card"]
                 :gov.procedure/legal-basis ["resident-basic-register-act"]
                 :gov.procedure/toritsugi-ref "toritsugi.gov.jpn.shinjuku.residence-certificate"
                 :gov.procedure/bpmn "bpmn.gov.jpn.shinjuku.residence-certificate"})]
    (is (= :langgraph-pregel (:procedure.graph/primary record)))
    (is (= "bpmn.gov.jpn.shinjuku.residence-certificate"
           (:procedure.graph/bpmn-ref record)))
    (is (= :visual-interop-only (:procedure.graph/legacy-bpmn-role record)))
    (is (= :state-graph (get-in record [:procedure.graph/langgraph :langgraph/type])))
    (is (= :bulk-synchronous-parallel
           (get-in record [:procedure.graph/pregel :pregel/model])))
    (is (= [:member-consent :operator-handoff]
           (get-in record [:procedure.graph/langgraph :langgraph/interrupt-before])))))

(deftest procedure-graph-cell-emits-member-support-plan
  (let [plan (ooyake/cell-plan :procedure_graph
                               {:attestations full-attestations
                                :request-id "req-002"
                                :computed-at "2026-07-01T00:00:00Z"
                                :procedure {:gov.procedure/id "gov.usa.passport-renewal"
                                            :gov.procedure/owner-unit "gov.usa.state"
                                            :gov.procedure/channel :online
                                            :gov.procedure/toritsugi-ref "toritsugi.gov.usa.passport-renewal"
                                            :gov.procedure/bpmn "bpmn.gov.usa.passport-renewal"}})
        effect (first (:effects plan))]
    (is (= :ready (:status plan)))
    (is (= "com.etzhayyim.ooyake.procedure_graph" (:collection effect)))
    (is (= :langgraph-pregel
           (get-in effect [:record :procedure.graph/primary])))
    (is (= false (get-in effect [:record :officialChannel])))
    (is (= false (get-in effect [:record :procedure.graph/official-channel])))
    (is (= :member-procedure-support
           (get-in effect [:record :procedure.graph/agent-role])))
    (is (= true
           (get-in effect [:record :procedure.graph/requires-explicit-member-consent])))
    (is (= "member-support-planning"
           (get-in effect [:record :constitutionalStatus])))))

(deftest coverage-classifier-counts-multi-portfolio-bodies
  (let [unit {:gov.unit/id "gov.aaa.trade"
              :gov.unit/level :ministry
              :gov.unit/jurisdiction "aaa"
              :gov.unit/name-en "Ministry of Trade, Industry and Competition"
              :gov.unit/cofog ["04.1" "04.7"]}]
    (is (every? (coverage/unit-categories unit)
                [:trade :industry :competition]))))

(deftest coverage-plan-emits-member-support-gaps
  (let [units [{:gov.unit/id "gov.aaa"
                :gov.unit/level :country
                :gov.unit/jurisdiction "aaa"}
               {:gov.unit/id "gov.aaa.finance"
                :gov.unit/level :ministry
                :gov.unit/jurisdiction "aaa"
                :gov.unit/name-en "Ministry of Finance"}]
        plan (ooyake/cell-plan :coverage_plan
                               {:attestations full-attestations
                                :request-id "req-003"
                                :computed-at "2026-07-01T00:00:00Z"
                                :units units})
        effects (:effects plan)]
    (is (= :ready (:status plan)))
    (is (seq effects))
    (is (every? #(= "com.etzhayyim.ooyake.coverage_gap" (:collection %)) effects))
    (is (some #(= :water (get-in % [:record :coverage.gap/category])) effects))))

(deftest all-cell-plans-ready-when-attested
  (let [plans (ooyake/all-cell-plans {:attestations full-attestations
                                      :request-id "req-001"
                                      :computed-at "2026-07-01T00:00:00Z"
                                      :unit {:gov.unit/id "gov.jpn.mof"
                                             :gov.unit/level :ministry
                                             :gov.unit/name-en "Ministry of Finance"
                                             :gov.unit/cofog ["01.1"]}
                                      :units [{:gov.unit/id "gov.jpn"
                                               :gov.unit/level :country
                                               :gov.unit/jurisdiction "jpn"}
                                              {:gov.unit/id "gov.jpn.mof"
                                               :gov.unit/level :ministry
                                               :gov.unit/jurisdiction "jpn"
                                               :gov.unit/name-en "Ministry of Finance"}]
                                      :procedure {:gov.procedure/id "gov.jpn.tax-return"
                                                  :gov.procedure/owner-unit "gov.jpn.nta"
                                                  :gov.procedure/channel :online}})]
    (is (= (set (keys ooyake/cell-specs)) (set (keys plans))))
    (is (every? #(= :ready (:status %)) (vals plans)))
    (is (< (count ooyake/cell-specs) (count (mapcat :effects (vals plans)))))))
