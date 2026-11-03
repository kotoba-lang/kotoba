(ns cae.host
  "Kotoba AOT Wasm guest and kototama tender descriptors; no JVM runtime."
  (:require [cae.protocol :as protocol]))

(defn component-job
  [{:keys [source artifact export arguments package-lock policy requested-imports
           grants limits rank-environment]}]
  {:source source
   :artifact (str artifact)
   :export (str (or export "main"))
   :arguments (vec arguments)
   :package-lock package-lock
   :policy policy
   :requested-imports (vec requested-imports)
   :host-caps {:grants (set grants) :limits (or limits {})}
   :rank-environment rank-environment
   :runtime :kotoba-wasm
   :tender :kototama
   :protocol :kotoba-wasm-job-v1})

(defn validate-component-job [job]
  (when-not (or (seq (:source job)) (seq (:artifact job)))
    (throw (ex-info "Kotoba job requires source or artifact" {:job job})))
  (when (and (:source job) (not (:package-lock job)))
    (throw (ex-info "kotoba wasm emit requires package-lock" {:job job})))
  (assoc job :validated? true))

(defn emit-argv [job]
  (let [{:keys [source artifact package-lock policy]} (validate-component-job job)]
    (cond-> ["kotoba" "wasm" "emit" source "--package-lock" package-lock "-o" artifact]
      policy (into ["--policy" policy]))))

(defn tender-request [job]
  (let [job (validate-component-job job)]
    {:guest/wasm (:artifact job)
     :guest/export (:export job)
     :guest/arguments (:arguments job)
     :abi/namespace "actor:host"
     :abi/version 0
     :abi/imports (:requested-imports job)
     :host-caps (:host-caps job)
     :runtime :kototama
     :protocol :kototama-tender-request-v1}))

(defn run-job [job]
  {:status :kototama-pending
   :emit (when (:source job) (emit-argv job))
   :tender (tender-request job)
   :protocol :kotoba-kototama-host-v1})

(defn mpi-component-job [{:keys [source artifact export arguments package-lock policy ranks rank]}]
  (component-job {:source source :artifact artifact :export export :arguments arguments
                  :package-lock package-lock :policy policy
                  :requested-imports [:log-read :log-write :clock-monotonic]
                  :grants [:log-read :log-write :clock-monotonic]
                  :limits {:max-log-read-bytes 1048576 :max-log-write-bytes 1048576
                           :max-memory-pages 256}
                  :rank-environment (protocol/rank-environment
                                     (protocol/job-spec {:executable artifact :arguments [] :ranks ranks})
                                     rank)}))
