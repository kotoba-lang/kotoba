(ns engine-r2
  "Does the Datalog surface actually run on R2?

  Everything verified so far about R2 is the storage contract: blocks,
  refs, and a CAS that survives contention. That is a necessary condition
  and not the question anyone actually has. The question for moving
  cloud-itonami's datom plane off D1 is whether `transact` / `q` / `pull`
  work over an R2-backed store -- the D1 backend answers queries out of a
  SQL projection, and nothing in the storage contract says the engine can
  serve them from blocks alone.

  So this transacts, reads back, queries, pulls and re-opens against a
  real R2Bucket binding. Re-opening matters most: it is the difference
  between 'the engine kept state in memory' and 'the data is in the
  bucket'."
  (:require ["miniflare" :refer [Miniflare]]
            [kotobase.datomic :as d]
            [kotobase.engine :as engine]
            [kotobase.storage.s3 :as s3]))

(def ^:private failures (atom 0))

(defn- expect [ok? message]
  (if ok?
    (println (str "ok  - " message))
    (do (js/console.error (str "FAIL: " message)) (swap! failures inc))))

(defn- backend [bucket]
  (s3/open {:client (s3/r2-client bucket)
            :prefix "kotobase"
            ;; The whole point of moving here. If this throws, the
            ;; migration is off before any query runs.
            :require-linearizable? true}))

(defn- open-db
  "The engine wants four explicit security controls and refuses without
   them. Pass-through here: this probe is about whether the Datalog
   surface reaches R2, not about sealing, and saying so openly beats a
   helper that hides that nothing is being encrypted.

   They must return PROMISES. kotobase-peer's crypto seam is synchronous
   on the JVM but Promise-returning on cljs, so plain `identity` throws
   `.then is not a function` from inside `put-tx-block!` -- a failure that
   names the peer's internals and not the caller's mistake. The D1 worker
   has the same three lines for the same reason."
  [bucket]
  (engine/open {:storage (backend bucket)
                :ref-name "probe"
                :encrypt-fn #(js/Promise.resolve %)
                :decrypt-fn #(js/Promise.resolve %)
                :blind-fn #(js/Promise.resolve (pr-str %))
                :visible? (constantly true)}))

(defn- run [bucket]
  (let [conn (open-db bucket)]
    (-> (d/transact conn [{:db/id "kawaraban"
                           :site/name "kawaraban"
                           :site/storage "r2"}
                          {:db/id "itonami"
                           :site/name "itonami"
                           :site/storage "r2"}])
        (.then (fn [report]
                 (expect (some? report) "transact returned a report")
                 (d/q '[:find ?n :where [?e :site/name ?n]] (d/db conn))))
        (.then (fn [rows]
                 (expect (= #{["kawaraban"] ["itonami"]}
                            (set (map vec rows)))
                         (str "q over blocks in R2 returned both entities: "
                              (pr-str rows)))))
        (.then (fn [_]
                 ;; A fresh connection over the same bucket. If the engine
                 ;; had been answering from memory this is where it stops.
                 (let [reopened (open-db bucket)]
                   (d/q '[:find ?s :where [?e :site/name "itonami"] [?e :site/storage ?s]]
                        (d/db reopened)))))
        (.then (fn [rows]
                 (expect (= [["r2"]] (map vec rows))
                         (str "a REOPENED connection reads it back -- the data is "
                              "in the bucket, not in the process: " (pr-str rows))))))))

(defn -main [& _]
  (let [mf (Miniflare. #js {:modules true
                            :script "export default {};"
                            :r2Buckets #js {:BUCKET "kotobase-engine-probe"}})]
    (-> (.getR2Bucket mf "BUCKET")
        (.then run)
        (.catch (fn [error]
                  (js/console.error (str "FAIL: " (.-message error)))
                  (when-let [data (ex-data error)] (js/console.error (pr-str data)))
                  (swap! failures inc)))
        (.then (fn [_]
                 (-> (.dispose mf)
                     (.then (fn [_]
                              (if (zero? @failures)
                                (println "engine on R2: all green")
                                (println (str "engine on R2: " @failures
                                              " FAILURE(S) above")))
                              (.exit js/process (if (zero? @failures) 0 1))))))))))
