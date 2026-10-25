(ns bim.plugin
  "Capability-scoped extension API for BIM commands, validators, exporters,
  and lifecycle hooks. Manifests stay serializable; runtime handlers are kept
  in the host registry."
  (:require [kotoba.lang.coll :as coll]))

(def api-version 1)
(def known-capabilities
  #{:model/read :model/write :selection/read :view/read :filesystem/export
    :network/cloud-itonami})

(defn manifest
  [{:keys [id name version api-version-required capabilities contributions]}]
  (let [required (set capabilities) unknown (coll/set-difference required known-capabilities)]
    (when (or (not (string? id)) (empty? id) (seq unknown)
              (> (or api-version-required 1) api-version))
      (throw (ex-info "invalid BIM plugin manifest"
                      {:id id :unknown-capabilities unknown
                       :api-version-required api-version-required})))
    {:plugin/id id :plugin/name name :plugin/version version
     :plugin/api-version (or api-version-required 1)
     :plugin/capabilities required
     :plugin/contributions
     {:commands (vec (:commands contributions))
      :validators (vec (:validators contributions))
      :exporters (vec (:exporters contributions))
      :hooks (vec (:hooks contributions))}}))

(defn host
  ([] (host known-capabilities))
  ([allowed-capabilities]
   {:plugin-host/api-version api-version
    :plugin-host/allowed-capabilities (set allowed-capabilities)
    :plugin-host/plugins {} :plugin-host/handlers {}}))

(defn install
  "Install a manifest and its handler map after capability and contribution checks."
  [host plugin-manifest handlers]
  (let [id (:plugin/id plugin-manifest)
        required (:plugin/capabilities plugin-manifest)
        denied (coll/set-difference required (:plugin-host/allowed-capabilities host))
        contribution-ids
        (into #{}
              (map :id)
              (mapcat val (:plugin/contributions plugin-manifest)))
        handler-ids (set (keys handlers))]
    (when (contains? (:plugin-host/plugins host) id)
      (throw (ex-info "BIM plugin is already installed" {:plugin-id id})))
    (when (seq denied)
      (throw (ex-info "BIM plugin capabilities are denied"
                      {:plugin-id id :denied denied})))
    (when-not (= contribution-ids handler-ids)
      (throw (ex-info "BIM plugin handlers do not match contributions"
                      {:plugin-id id :missing (coll/set-difference contribution-ids handler-ids)
                       :undeclared (coll/set-difference handler-ids contribution-ids)})))
    (-> host
        (assoc-in [:plugin-host/plugins id] plugin-manifest)
        (assoc-in [:plugin-host/handlers id] handlers))))

(defn uninstall [host plugin-id]
  (-> host (update :plugin-host/plugins dissoc plugin-id)
      (update :plugin-host/handlers dissoc plugin-id)))

(defn- contribution [host plugin-id kind contribution-id]
  (let [plugin (get-in host [:plugin-host/plugins plugin-id])
        declaration (first (filter #(= contribution-id (:id %))
                                   (get-in plugin [:plugin/contributions kind])))
        handler (get-in host [:plugin-host/handlers plugin-id contribution-id])]
    (when-not (and plugin declaration handler)
      (throw (ex-info "BIM plugin contribution not found"
                      {:plugin-id plugin-id :kind kind :contribution-id contribution-id})))
    [plugin declaration handler]))

(defn- scoped-context [plugin context]
  (let [capabilities (:plugin/capabilities plugin)]
    (cond-> {:plugin/context-version api-version
             :project-id (:project-id context)}
      (contains? capabilities :model/read) (assoc :model (:model context))
      (contains? capabilities :selection/read) (assoc :selection (:selection context))
      (contains? capabilities :view/read) (assoc :view (:view context))
      (contains? capabilities :model/write) (assoc :transaction-base (:transaction-base context))
      (contains? capabilities :filesystem/export) (assoc :export-options (:export-options context))
      (contains? capabilities :network/cloud-itonami) (assoc :cloud (:cloud context)))))

(defn invoke-command [host plugin-id command-id context arguments]
  (let [[plugin declaration handler] (contribution host plugin-id :commands command-id)
        result (handler (scoped-context plugin context) arguments)]
    (when (and (:writes-model? declaration)
               (not (contains? (:plugin/capabilities plugin) :model/write)))
      (throw (ex-info "BIM plugin command lacks model write capability"
                      {:plugin-id plugin-id :command-id command-id})))
    (when (and (:writes-model? declaration)
               (not (vector? (:transaction/operations result))))
      (throw (ex-info "model-writing plugin command must return a transaction"
                      {:plugin-id plugin-id :command-id command-id})))
    result))

(defn run-validators
  "Run every validator deterministically and attach plugin provenance."
  [host context]
  (vec
   (mapcat
    (fn [[plugin-id plugin]]
      (mapcat (fn [{validator-id :id}]
                (let [handler (get-in host [:plugin-host/handlers plugin-id validator-id])]
                  (map #(assoc % :plugin/id plugin-id :validator/id validator-id)
                       (or (handler (scoped-context plugin context)) []))))
              (get-in plugin [:plugin/contributions :validators])))
    (sort-by key (:plugin-host/plugins host)))))

(defn invoke-exporter [host plugin-id exporter-id context options]
  (let [[plugin _ handler] (contribution host plugin-id :exporters exporter-id)]
    (when-not (contains? (:plugin/capabilities plugin) :filesystem/export)
      (throw (ex-info "BIM plugin exporter lacks export capability"
                      {:plugin-id plugin-id :exporter-id exporter-id})))
    (let [result (handler (scoped-context plugin context) options)]
      (when-not (and (string? (:filename result)) (string? (:media-type result))
                     (some? (:content result)))
        (throw (ex-info "BIM plugin exporter returned an invalid artifact"
                        {:plugin-id plugin-id :exporter-id exporter-id})))
      result)))

(defn dispatch-hook [host event context]
  (reduce
   (fn [results [plugin-id plugin]]
     (reduce (fn [accumulator {:keys [id event-kind]}]
               (if (= event event-kind)
                 (conj accumulator
                       {:plugin/id plugin-id :hook/id id
                        :result ((get-in host [:plugin-host/handlers plugin-id id])
                                 (scoped-context plugin context))})
                 accumulator))
             results (get-in plugin [:plugin/contributions :hooks])))
   [] (sort-by key (:plugin-host/plugins host))))
