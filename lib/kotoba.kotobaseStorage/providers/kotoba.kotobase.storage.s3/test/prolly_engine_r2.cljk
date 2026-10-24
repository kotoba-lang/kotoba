(ns prolly-engine-r2
  "Cold write/read qualification for the new IEngine path over a real
  Miniflare R2Bucket binding."
  (:require ["miniflare" :refer [Miniflare]]
            [kotobase.engine.contract :as engine]
            [kotobase.engine.prolly.provider :as provider]
            [kotobase.storage.s3 :as s3]))

(def ^:private failures (atom 0))

(defn- expect [ok? message]
  (if ok?
    (println (str "ok  - " message))
    (do (js/console.error (str "FAIL: " message))
        (swap! failures inc))))

(def crypto
  {:blind-fn #(js/Promise.resolve (str "blind:" %))
   :encrypt-fn #(js/Promise.resolve %)
   :decrypt-fn #(js/Promise.resolve %)
   :digest-fn #(str "digest:" (hash %))})

(defn- backend [bucket]
  (s3/open {:client (s3/r2-client bucket)
            :prefix "kotobase-prolly-engine"
            :require-linearizable? true}))

(defn- run [bucket]
  (let [storage (backend bucket)
        first-writer (provider/engine-from-backend storage crypto)
        initial (engine/empty-state first-writer "r2/db")
        seed {:database-id "r2/db" :request-id "seed"
              :tx-data
              (into [[:db/add "alice" :person/name "Alice"]]
                    (map (fn [n]
                           [:db/add (str "entity-" n) :metric/value n]))
                    (range 4000))}]
    (-> (provider/transact-and-publish!
         first-writer storage "main" initial seed)
        (.then
         (fn [published]
           (expect (= :published (:publish-status published))
                   "seed blocks land in R2 before CAS")
           (let [cold-writer (provider/engine-from-backend storage crypto)]
             (-> (provider/restore-head cold-writer storage "main")
                 (.then
                  (fn [restored]
                    (expect (nil? (:db restored))
                            "cold writer restores only the manifest")
                    (provider/transact-and-publish!
                     cold-writer storage "main" restored
                     {:database-id "r2/db" :request-id "cold-mixed"
                      :tx-data
                      [[:db/retract "alice" :person/name "Alice"]
                       [:db/add "bob" :person/name "Bob"]]})))
                 (.then
                  (fn [result]
                    (expect (= :published (:publish-status result))
                            "cold mixed mutation wins R2 CAS")
                    (expect (< (provider/request-count cold-writer) 20)
                            (str "cold writer block GETs="
                                 (provider/request-count cold-writer)))))))))
        (.then
         (fn [_]
           (let [reader (provider/engine-from-backend storage crypto)]
             (-> (provider/restore-head reader storage "main")
                 (.then
                  (fn [restored]
                    (js/Promise.all
                     #js [(engine/scan
                           reader (engine/open-snapshot reader restored)
                           ["alice" :person/name nil])
                          (engine/scan
                           reader (engine/open-snapshot reader restored)
                           ["bob" :person/name nil])])))
                 (.then
                  (fn [rows]
                    (expect (empty? (aget rows 0))
                            "retraction survives a second R2 reopen")
                    (expect (= ["Bob"] (mapv :v (aget rows 1)))
                            "assertion survives a second R2 reopen"))))))))))

(defn -main [& _]
  (let [mf (Miniflare.
            #js {:modules true
                 :script "export default {};"
                 :r2Buckets #js {:BUCKET "kotobase-prolly-engine"}})]
    (-> (.getR2Bucket mf "BUCKET")
        (.then run)
        (.catch (fn [error]
                  (js/console.error error)
                  (swap! failures inc)))
        (.then (fn [_]
                 (-> (.dispose mf)
                     (.then
                      (fn [_]
                        (println
                         (if (zero? @failures)
                           "new Prolly engine on R2: all green"
                           (str "new Prolly engine on R2: " @failures
                                " FAILURE(S)")))
                        (.exit js/process
                               (if (zero? @failures) 0 1))))))))))
