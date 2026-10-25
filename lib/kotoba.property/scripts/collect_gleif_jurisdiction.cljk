(ns collect-gleif-jurisdiction
  "Credential-free bounded GLEIF Level 1 jurisdiction collector for nbb."
  (:require [cljs.reader :as reader]
            [kotoba.property.audit-runtime :as audit]
            [kotoba.property.coverage-runtime :as coverage]
            [kotoba.property.gleif-runtime :as gleif]
            ["crypto" :as crypto]
            ["fs" :as fs]
            ["path" :as path]))

(def default-store "var/kotoba-property/gleif-level-2.edn")
(def endpoint "https://api.gleif.org/api/v1/lei-records")

(defn- arg-value [args option default]
  (or (second (drop-while #(not= option %) args)) default))

(defn- read-state [store]
  (if (.existsSync fs store)
    (reader/read-string (.readFileSync fs store "utf8"))
    {:lei-records {} :corporate-relations {} :source-state {}}))

(defn- write-state! [store state]
  (.mkdirSync fs (.dirname path store) #js {:recursive true})
  (.writeFileSync fs store (pr-str state) "utf8"))

(defn- fetch-page [jurisdiction page page-size]
  (let [url (str endpoint "?filter%5Bentity.jurisdiction%5D=" jurisdiction
                 "&page%5Bnumber%5D=" page "&page%5Bsize%5D=" page-size)]
    (-> (js/fetch url)
        (.then (fn [response]
                 (if (.-ok response)
                   (.text response)
                   (js/Promise.reject (js/Error. (str "GLEIF HTTP " (.-status response)))))))
        (.then (fn [body]
                 {:body body
                  :json (js->clj (js/JSON.parse body) :keywordize-keys true)})))))

(defn- fetch-pages [jurisdiction page page-size pages bodies records]
  (if (> page pages)
    (js/Promise.resolve {:bodies bodies :records records})
    (-> (fetch-page jurisdiction page page-size)
        (.then (fn [{:keys [body json]}]
                 (fetch-pages jurisdiction (inc page) page-size pages
                              (conj bodies body) (into records (:data json))))))))

(defn -main []
  (let [args *command-line-args*
        jurisdiction (arg-value args "--jurisdiction" "US")
        pages (js/parseInt (arg-value args "--pages" "1") 10)
        page-size (js/parseInt (arg-value args "--page-size" "100") 10)
        store (arg-value args "--store" default-store)
        source (str "gleif-level-1:" jurisdiction)]
    (coverage/assert-collectable! source)
    (-> (fetch-pages jurisdiction 1 page-size pages [] [])
        (.then (fn [{:keys [bodies records]}]
                 (let [observed-at (.toISOString (js/Date.))
                       current (into {}
                                     (map (fn [record]
                                            (let [entity (gleif/normalize-entity-with-source
                                                          source observed-at record)]
                                              [(:legal-entity/lei entity) entity])))
                                     records)
                       state (read-state store)
                       previous (into {}
                                      (filter (fn [[_ entity]]
                                                (= source (:legal-entity/source entity))))
                                      (:lei-records state))
                       retained (into {}
                                      (remove (fn [[_ entity]]
                                                (= source (:legal-entity/source entity))))
                                      (:lei-records state))
                       hash (-> (.createHash crypto "sha256")
                                (.update (apply str bodies) "utf8")
                                (.digest "hex"))
                       next-state (assoc state
                                         :lei-records (into retained current)
                                         :source-state (assoc (:source-state state) source
                                                              (assoc (audit/source-audit source observed-at hash
                                                                                         previous current)
                                                                     :source-audit/endpoint endpoint
                                                                     :source-audit/jurisdiction jurisdiction)))]
                   (write-state! store next-state)
                   (println (pr-str {:store store :source source
                                     :lei-records (count current)
                                     :pages pages})))))
        (.catch (fn [error]
                  (binding [*out* *err*] (println (.-message error)))
                  (js/process.exit 1))))))

(-main)
