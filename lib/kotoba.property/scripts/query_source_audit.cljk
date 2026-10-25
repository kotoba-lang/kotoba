(ns query-source-audit
  "Run a Datalog audit query over an nbb collector state file."
  (:require [cljs.reader :as reader]
            [kotoba.property.query-runtime :as runtime]
            ["fs" :as fs]))

(def query
  "[:find ?source ?hash ?retrieved ?count ?added ?removed
     :where
     [?audit \"source-audit/id\" ?source]
     [?audit \"source-audit/content-sha256\" ?hash]
     [?audit \"source-audit/retrieved-at\" ?retrieved]
     [?audit \"source-audit/record-count\" ?count]
     [?audit \"source-audit/added-count\" ?added]
     [?audit \"source-audit/removed-count\" ?removed]]")

(defn -main []
  (let [store (or (second (drop-while #(not= "--store" %) *command-line-args*))
                  "var/kotoba-property/nyc-owned-properties.edn")
        state (reader/read-string (.readFileSync fs store "utf8"))
        db (runtime/db (vals (:source-state state)))]
    (doseq [row (runtime/q db query)]
      (println (pr-str (zipmap [:source/id :source/content-sha256 :source/retrieved-at
                                :source/record-count :source/added-count :source/removed-count]
                               row))))))

(-main)
