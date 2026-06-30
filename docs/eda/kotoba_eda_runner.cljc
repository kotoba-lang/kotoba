(ns kotoba.eda.runner
  "Pure EDN job-plan builder for host/murakumo EDA runners.

  The browser and CLJC layer only build plans. A host runner may execute the
  whitelisted commands after resolving CIDs into a workspace and checking
  policy/license gates."
  (:require [clojure.string :as str]))

(defn adapters [registry] (:adapters registry))

(defn adapter-by-id [registry id]
  (first (filter #(= id (:eda.runner/id %)) (adapters registry))))

(defn adapter-supports?
  [adapter format-id]
  (some #{format-id} (:eda.runner/formats adapter)))

(defn artifact-format
  [artifact]
  (or (:eda.artifact/format artifact)
      (:format artifact)))

(defn matching-adapters
  [registry artifacts]
  (let [formats (set (map artifact-format artifacts))]
    (filter (fn [adapter]
              (some #(some #{%} formats) (:eda.runner/formats adapter)))
            (adapters registry))))

(defn adapter-inputs
  [adapter artifacts]
  (filter #(adapter-supports? adapter (artifact-format %)) artifacts))

(defn command-plan
  [adapter inputs]
  {:eda.command/argv (:eda.runner/command adapter)
   :eda.command/input-cids (mapv #(or (:eda.artifact/cid %) (:cid %)) inputs)
   :eda.command/input-paths (mapv #(or (:eda.artifact/path %) (:name %) (:path %)) inputs)
   :eda.command/policy (:eda.runner/policy adapter)
   :eda.command/outputs (:eda.runner/outputs adapter)})

(defn build-job-plan
  ([runner-registry artifacts] (build-job-plan runner-registry artifacts {}))
  ([runner-registry artifacts opts]
   (let [selected (or (:adapters opts)
                      (map :eda.runner/id (matching-adapters runner-registry artifacts)))]
     {:eda.job/schema 1
      :eda.job/kind :eda.runner/job-plan
      :eda.job/id (str "eda-job-" (Math/abs (hash [selected artifacts])))
      :eda.job/mode :dry-run-until-host-approved
      :eda.job/adapters
      (mapv (fn [id]
              (let [adapter (adapter-by-id runner-registry id)
                    inputs (vec (adapter-inputs adapter artifacts))]
                {:eda.job.adapter/id id
                 :eda.job.adapter/name (:eda.runner/name adapter)
                 :eda.job.adapter/software (:eda.runner/software adapter)
                 :eda.job.adapter/operation (:eda.runner/operation adapter)
                 :eda.job.adapter/status (if (seq inputs) :ready :missing-inputs)
                 :eda.job.adapter/inputs (mapv #(select-keys % [:eda.artifact/path :eda.artifact/cid :eda.artifact/format
                                                                :name :cid :format])
                                               inputs)
                 :eda.job.adapter/command (command-plan adapter inputs)}))
            selected)})))

(defn runnable-adapters
  [job-plan]
  (filter #(= :ready (:eda.job.adapter/status %)) (:eda.job/adapters job-plan)))

(defn report-datoms
  [job-plan]
  (mapv (fn [adapter]
          {:eda.run/tool (:eda.job.adapter/software adapter)
           :eda.run/operation (:eda.job.adapter/operation adapter)
           :eda.run/status (:eda.job.adapter/status adapter)
           :eda.run/adapter (:eda.job.adapter/id adapter)
           :eda.run/input-cids (get-in adapter [:eda.job.adapter/command :eda.command/input-cids])})
        (:eda.job/adapters job-plan)))
