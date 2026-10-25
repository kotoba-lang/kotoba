(ns ctf.adapters.schema-conformance
  (:require [ctf.core :as core]))

(def required-result-keys
  #{:ctf/id :ctf/route :ctf/level :ctf/non-adjudicating})

(defn conform-result! [result]
  (let [missing (remove #(contains? result %) required-result-keys)
        problems (concat (map (fn [k] {:ctf.problem/code :schema/missing-key :key k}) missing)
                         (core/problems result))]
    (when-let [ps (seq problems)]
      (throw (ex-info "CTF result schema conformance failed" {:ctf/problems (vec ps)})))
    result))

(defn conform-screening! [screening]
  (doseq [result (:ctf/results screening)]
    (conform-result! result))
  screening)
