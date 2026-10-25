(ns query-coverage
  "Inspect the authority coverage matrix; unlisted jurisdictions are unknown."
  (:require [cljs.reader :as reader]
            ["fs" :as fs]))

(def path "resources/property/open_data/coverage.edn")

(defn -main []
  (let [coverage (reader/read-string (.readFileSync fs path "utf8"))
        status (second (drop-while #(not= "--status" %) *command-line-args*))
        entries (if status
                  (filter #(= (keyword status) (:status %)) (:coverage/entries coverage))
                  (:coverage/entries coverage))]
    (doseq [entry entries]
      (println (pr-str (select-keys entry [:authority/id :jurisdiction :dataset :status
                                           :property-owner-data? :natural-person-ubo-data?]))))))

(-main)
