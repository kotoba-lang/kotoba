(ns aiueos.verify-value-handle-plan
  (:require [clojure.edn :as edn]
            [kotoba.compiler.core :as compiler]
            [kotoba.kir :as kir]))

(defn- fail! [message data]
  (throw (ex-info message (assoc data :phase :aiueos-value-handle-plan))))

(defn -main [& [source-path vectors-path]]
  (when-not (and source-path vectors-path)
    (fail! "usage: <value-handle-plan.kotoba> <value-handle-plan-v1.edn>" {}))
  (let [vectors (edn/read-string (slurp vectors-path))
        result (compiler/compile-source (slurp source-path)
                                        :x86_64-aiueos-kernel-v1)
        object (:object result)
        program (:kir result)]
    (when-not (= "kotoba_aiueos_value_handle_plan" (:export object))
      (fail! "planner object export is not exact" {:export (:export object)}))
    (when-not (empty? (:imports object))
      (fail! "planner object acquired a host import" {:imports (:imports object)}))
    (doseq [{:keys [name args expected]} (:vectors vectors)]
      (let [actual (kir/execute program 'aiueos-value-handle-plan args)]
        (when-not (= expected actual)
          (fail! "planner semantic vector failed"
                 {:vector name :args args :expected expected :actual actual}))))
    (println (pr-str {:format :aiueos.value-handle-plan/verification-v1
                      :vectors (count (:vectors vectors))
                      :export (:export object)
                      :imports (:imports object)
                      :status :passed}))))
