(ns collect-nyc
  "Credential-free NYC-owned property collector for nbb."
  (:require [cljs.reader :as reader]
            [kotoba.property.audit-runtime :as audit]
            [kotoba.property.coverage-runtime :as coverage]
            [kotoba.property.nyc-runtime :as nyc]
            ["crypto" :as crypto]
            ["fs" :as fs]
            ["path" :as path]))

(def default-store "var/kotoba-property/nyc-owned-properties.edn")

(defn- arg-value [args option default]
  (or (second (drop-while #(not= option %) args)) default))

(defn- read-state [store]
  (if (.existsSync fs store)
    (reader/read-string (.readFileSync fs store "utf8"))
    {:ownership-records {} :source-state {}}))

(defn- write-state! [store state]
  (.mkdirSync fs (.dirname path store) #js {:recursive true})
  (.writeFileSync fs store (pr-str state) "utf8"))

(defn- collect-state [state observed-at content-sha256 rows]
  (let [claims (keep #(nyc/normalize-record observed-at %) rows)
        current-records (into {} (map (juxt :ownership/id identity) claims))
        previous-records (into {}
                               (filter (fn [[_ claim]]
                                         (= nyc/source-id (:ownership/source claim))))
                               (:ownership-records state))
        retained (into {}
                       (remove (fn [[_ claim]]
                                 (= nyc/source-id (:ownership/source claim))))
                       (:ownership-records state))]
    (assoc state
           :ownership-records (into retained current-records)
           :source-state
           (assoc (:source-state state) nyc/source-id
                  (assoc (audit/source-audit nyc/source-id observed-at
                                             content-sha256
                                             previous-records current-records)
                         :source-audit/endpoint nyc/endpoint)))))

(defn -main []
  (let [args *command-line-args*
        limit (js/parseInt (arg-value args "--limit" "500") 10)
        store (arg-value args "--store" default-store)]
    (coverage/assert-collectable! nyc/source-id)
    (-> (js/fetch (str nyc/endpoint "?$limit=" limit))
        (.then (fn [response]
                 (if (.-ok response)
                   (.text response)
                   (js/Promise.reject (js/Error. (str "NYC Open Data HTTP " (.-status response)))))))
        (.then (fn [body]
                 (let [hash (-> (.createHash crypto "sha256")
                                (.update body "utf8")
                                (.digest "hex"))
                       prior (read-state store)
                       state (collect-state prior (.toISOString (js/Date.)) hash
                                            (js->clj (js/JSON.parse body) :keywordize-keys true))]
                   (write-state! store state)
                   (println (pr-str {:store store
                                     :ownership-records (count (:ownership-records state))
                                     :source nyc/source-id})))))
        (.catch (fn [error]
                  (binding [*out* *err*] (println (.-message error)))
                  (js/process.exit 1))))))

(-main)
