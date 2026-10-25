(ns verify-coverage-gate
  (:require [kotoba.property.coverage-runtime :as coverage]))

(doseq [source ["nyc-owned-properties" "gleif-level-2" "gleif-level-1:US"
                "gleif-golden-copy" "gleif-api-by-lei"]]
  (let [entry (coverage/assert-collectable! source)]
    (println (pr-str {:source source
                      :authority (:authority/id entry)
                      :status (:status entry)}))))
