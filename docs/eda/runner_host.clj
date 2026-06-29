(ns runner-host
  "Minimal host-side skeleton for executing kotoba EDA runner EDN plans.

  Usage:
    clojure runner_host.clj plan.edn

  This script is intentionally conservative: default mode prints whitelisted
  commands and emits dry-run datoms. Set EDA_RUNNER_EXEC=1 only inside a prepared
  sandbox/workspace with required tools installed."
  (:require [clojure.edn :as edn]
            [clojure.java.process :as p]))

(def allowed
  #{"verilator" "yosys" "sta" "openroad" "klayout" "netgen" "ngspice"})

(defn runnable? [adapter]
  (= :ready (:eda.job.adapter/status adapter)))

(defn argv [adapter]
  (get-in adapter [:eda.job.adapter/command :eda.command/argv]))

(defn dry-run-datom [adapter]
  {:eda.run/adapter (:eda.job.adapter/id adapter)
   :eda.run/tool (:eda.job.adapter/software adapter)
   :eda.run/operation (:eda.job.adapter/operation adapter)
   :eda.run/status :dry-run
   :eda.run/input-cids (get-in adapter [:eda.job.adapter/command :eda.command/input-cids])
   :eda.run/argv (argv adapter)})

(defn execute! [adapter]
  (let [cmd (argv adapter)
        exe (first cmd)]
    (when-not (allowed exe)
      (throw (ex-info "Executable is not whitelisted" {:exe exe :adapter (:eda.job.adapter/id adapter)})))
    (if (= "1" (System/getenv "EDA_RUNNER_EXEC"))
      (let [res (apply p/exec cmd)]
        {:eda.run/adapter (:eda.job.adapter/id adapter)
         :eda.run/tool (:eda.job.adapter/software adapter)
         :eda.run/status (if (zero? (:exit res)) :passed :failed)
         :eda.run/exit (:exit res)
         :eda.run/stdout (:out res)
         :eda.run/stderr (:err res)})
      (dry-run-datom adapter))))

(defn -main [& [path]]
  (when-not path
    (throw (ex-info "Missing plan.edn path" {})))
  (let [plan (edn/read-string (slurp path))
        results (mapv execute! (filter runnable? (:eda.job/adapters plan)))]
    (prn {:eda.runner/results results})))

(apply -main *command-line-args*)
