(ns ooyake.procedure-graph
  "Member-support langgraph/Pregel projection for government procedures.

  BPMN remains a legacy/visual interchange reference; the executable planning
  shape is EDN data for langgraph-style state graphs and Pregel supersteps."
  (:require [kotoba.lang.text :as str]))

(def default-graph-version
  "gov-procedure-graph-v1")

(defn- keyword-or-default
  [x default]
  (cond
    (keyword? x) x
    (string? x) (keyword x)
    :else default))

(defn- proc-id
  [procedure]
  (or (:gov.procedure/id procedure)
      (:id procedure)
      "procedure.unknown"))

(defn- owner-unit
  [procedure]
  (or (:gov.procedure/owner-unit procedure)
      (:owner-unit procedure)
      "gov.unknown"))

(defn- toritsugi-ref
  [procedure]
  (or (:gov.procedure/toritsugi-ref procedure)
      (:toritsugi-ref procedure)))

(defn- bpmn-ref
  [procedure]
  (or (:gov.procedure/bpmn procedure)
      (:gov.bpmn/id procedure)
      (:bpmn-ref procedure)))

(defn- required-docs
  [procedure]
  (vec (or (:gov.procedure/required-docs procedure)
           (:required-docs procedure)
           [])))

(defn- legal-basis
  [procedure]
  (vec (or (:gov.procedure/legal-basis procedure)
           (:legal-basis procedure)
           [])))

(defn- channel
  [procedure]
  (keyword-or-default (or (:gov.procedure/channel procedure)
                          (:channel procedure))
                      :unknown))

(defn graph-id
  [procedure]
  (str "langgraph.ooyake." (proc-id procedure)))

(defn pregel-id
  [procedure]
  (str "pregel.ooyake." (proc-id procedure)))

(defn procedure->state-graph
  "Build an EDN langgraph-style state graph for a procedure.

  The graph can resolve, verify, collect, draft, and hand off administrative
  work for an etzhayyim member. Any external submission/payment/signature or
  government-record mutation must pass explicit member consent and legal/licensed
  boundary checks outside this projection."
  [procedure]
  (let [pid (proc-id procedure)]
    {:langgraph/id (graph-id procedure)
     :langgraph/version default-graph-version
     :langgraph/type :state-graph
     :langgraph/entry :resolve-owner
     :langgraph/checkpoint-graph "gov-atlas-v1"
     :langgraph/channels {:procedure/id pid
                          :procedure/owner-unit (owner-unit procedure)
                          :procedure/channel (channel procedure)
                          :procedure/toritsugi-ref (toritsugi-ref procedure)
                          :procedure/required-docs (required-docs procedure)
                          :procedure/legal-basis (legal-basis procedure)}
     :langgraph/nodes [{:id :resolve-owner
                        :reads [:gov.procedure/owner-unit :gov.unit/id]
                        :writes [:procedure/owner-resolved?]}
                       {:id :verify-freshness
                        :reads [:gov.procedure/last-verified :gov.unit/verification-status]
                        :writes [:procedure/fresh? :procedure/stale-reason]}
                       {:id :collect-docs
                        :reads [:gov.procedure/required-docs :gov.form/chigiri-ref]
                        :writes [:procedure/document-checklist]}
                       {:id :draft
                        :reads [:procedure/document-checklist :gov.procedure/legal-basis]
                        :writes [:procedure/draft-plan]}
                       {:id :member-consent
                        :reads [:procedure/draft-plan :member/authorization]
                        :writes [:procedure/member-consent-required?
                                 :procedure/member-consent-status]}
                       {:id :operator-handoff
                        :reads [:procedure/draft-plan
                                :procedure/member-consent-status
                                :gov.procedure/toritsugi-ref]
                        :writes [:procedure/support-handoff
                                 :procedure/toritsugi-handoff]}]
     :langgraph/edges [{:from :resolve-owner :to :verify-freshness}
                       {:from :verify-freshness :to :collect-docs
                        :when :fresh}
                       {:from :verify-freshness :to :operator-handoff
                        :when :stale}
                       {:from :collect-docs :to :draft}
                       {:from :draft :to :member-consent}
                       {:from :member-consent :to :operator-handoff
                        :when :member-authorized}]
     :langgraph/interrupt-before [:member-consent :operator-handoff]
     :langgraph/non-goals [:claim-government-identity
                           :official-government-channel
                           :unsupervised-submission
                           :unconsented-government-record-mutation
                           :claim-official-channel]}))

(defn procedure->pregel-plan
  "Build the Pregel/BSP execution plan that drives the same procedure graph."
  [procedure]
  {:pregel/id (pregel-id procedure)
   :pregel/version default-graph-version
   :pregel/model :bulk-synchronous-parallel
   :pregel/source-graph (graph-id procedure)
   :pregel/vertices [{:id :resolve-owner
                      :compute :read-owner-unit}
                     {:id :verify-freshness
                      :compute :freshness-gate}
                     {:id :collect-docs
                      :compute :required-document-fold}
                     {:id :draft
                      :compute :draft-member-support-guide}
                     {:id :member-consent
                      :compute :confirm-member-authorization}
                     {:id :operator-handoff
                      :compute :emit-member-support-handoff}]
   :pregel/supersteps [{:step 0 :active [:resolve-owner]}
                       {:step 1 :active [:verify-freshness]}
                       {:step 2 :active [:collect-docs]}
                       {:step 3 :active [:draft]}
                      {:step 4 :active [:member-consent]}
                      {:step 5 :active [:operator-handoff]}]
   :pregel/halting-condition :operator-handoff-emitted
   :pregel/non-goals [:claim-government-identity
                      :official-government-channel
                      :unsupervised-submission
                      :unconsented-government-record-mutation
                      :claim-official-channel]})

(defn procedure-record
  [procedure]
  (let [pid (proc-id procedure)
        legacy-bpmn (bpmn-ref procedure)]
    (cond-> {:procedure.graph/procedure-id pid
             :procedure.graph/owner-unit (owner-unit procedure)
             :procedure.graph/primary :langgraph-pregel
             :procedure.graph/langgraph (procedure->state-graph procedure)
             :procedure.graph/pregel (procedure->pregel-plan procedure)
             :procedure.graph/source :generated-from-procedure-edn
             :procedure.graph/official-channel false
             :procedure.graph/agent-role :member-procedure-support
             :procedure.graph/member-authorized-support true
             :procedure.graph/requires-explicit-member-consent true
             :procedure.graph/external-effect-policy :consent-and-audit-required
             :procedure.graph/legacy-bpmn-role :visual-interop-only}
      (some? (toritsugi-ref procedure))
      (assoc :procedure.graph/toritsugi-ref (toritsugi-ref procedure))

      (some? legacy-bpmn)
      (assoc :procedure.graph/bpmn-ref legacy-bpmn))))

(defn rkey
  [procedure]
  (-> (proc-id procedure)
      (str/replace #"[^A-Za-z0-9._~-]" "-")
      (#(if (str/blank? %) "procedure-unknown" %))))
