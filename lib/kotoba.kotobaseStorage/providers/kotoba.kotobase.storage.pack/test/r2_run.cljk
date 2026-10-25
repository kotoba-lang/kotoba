(ns r2-run
  "The whole physical plane, on the deployment it was designed for.

  Everything else in this repository proves the plan against an object store
  written for the test. This runs it end to end: real CARv2 bytes, PUT into
  a real R2Bucket binding through `kotobase-storage-s3`'s `r2-client`, and a
  100-link cons chain walked back out one link at a time.

  Miniflare implements the R2 API, so the conversion this depends on — R2
  takes an offset and a length, the storage contract is half-open — is
  judged by something that can disagree. It is still not Cloudflare's
  production R2; what it establishes is that the adapter speaks the API and
  that one range read serves a chain across it."
  (:require ["miniflare" :refer [Miniflare]]
            [ipld.core :as ipld]
            [kotobase.storage.core :as storage]
            [kotobase.storage.object :as object]
            [kotobase.storage.object-s3 :as objs3]
            [kotobase.storage.pack :as pack]
            [kotobase.storage.pack-async :as apack]
            [kotobase.storage.s3 :as s3]))

(def ^:private failures (atom 0))

(defn- expect [ok? message]
  (if ok?
    (println (str "ok  - " message))
    (do (js/console.error (str "FAIL: " message)) (swap! failures inc))))

(defn- cons-chain [n]
  (loop [i (dec n) next-cid nil acc ()]
    (if (neg? i)
      (vec acc)
      (let [blk (ipld/node->block
                 (cond-> {"e" i} next-cid (assoc "rest" (ipld/link next-cid))))]
        (recur (dec i) (:cid blk) (conj acc blk))))))

(defn- walk-chain! [store head-cid seen]
  (-> (storage/-get-blocks store [head-cid])
      (.then (fn [got]
               (let [bytes (get got head-cid)]
                 (if-not bytes
                   (js/Promise.reject (ex-info "chain broke: block not returned"
                                               {:cid head-cid :at (count seen)}))
                   (let [node (ipld/decode bytes)
                         nxt (some-> (get node "rest") ipld/link-cid)
                         seen (conj seen (get node "e"))]
                     (if nxt (walk-chain! store nxt seen)
                         (js/Promise.resolve seen)))))))))

(defn- run-checks [bucket]
  (let [objects (objs3/open-objects {:client (s3/r2-client bucket)
                                     :prefix "kotobase"})
        catalog (pack/memory-catalog)
        store (apack/pack-block-store objects catalog)
        chain (cons-chain 100)]
    (expect (storage/packed? store) "the store declares :packed-blocks over R2")
    (-> (storage/-put-blocks! store chain)
        (.then (fn [_]
                 (apack/drop-cache! store)
                 (apack/reset-stats! store)
                 (walk-chain! store (:cid (first chain)) [])))
        (.then (fn [seen]
                 (let [s (apack/stats store)]
                   (expect (= (range 100) seen)
                           "100 links walked back out of R2")
                   (expect (= 1 (:requests s))
                           (str "one ranged GET against the binding served all "
                                "of them: " (pr-str s)))
                   (expect (< 0 (:bytes-fetched s))
                           "and it did fetch bytes rather than answering empty"))))
        ;; the projection claim, against the real store
        (.then (fn [_]
                 (let [pack-cid (:pack-cid (first (vals ((:snapshot catalog)))))]
                   (-> (apack/rebuild-catalog! objects pack-cid)
                       (.then (fn [recovered]
                                (expect (= 100 (count recovered))
                                        "and the catalog rebuilds from the R2 object alone")))))))
        ;; ── the drill, against the real binding ────────────────────────────
        ;;
        ;; The in-memory drill proves the store SAYS the right thing when the
        ;; object is gone. This proves the saying survives contact with a
        ;; provider: R2 answers a missing key with null, and the whole
        ;; difference between "no such object" and "a catalog that knew
        ;; nothing" is one counter that has to be incremented on this path
        ;; too. Measured before it was: {:requests 1, :blocks-served 0,
        ;; :evidence :nothing-served} -- indistinguishable from an empty
        ;; catalog, over a bucket that had lost the data.
        (.then (fn [_]
                 (let [pack-cid (:pack-cid (first (vals ((:snapshot catalog)))))]
                   (-> (js/Promise.resolve (object/-delete-object! objects pack-cid))
                       (.then (fn [_]
                                (apack/drop-cache! store)
                                (apack/reset-stats! store)
                                (storage/-get-blocks store [(:cid (first chain))])))
                       (.then (fn [got]
                                (let [s (apack/stats store)]
                                  (expect (= {} got)
                                          "with the pack deleted from R2, no block comes back")
                                  (expect (= 1 (:packs-missing s))
                                          (str "and the absent object is counted: " (pr-str s)))
                                  (expect (= :degraded (:evidence s))
                                          "so the read reads as degraded, not as an empty catalog"))))))))
        (.catch (fn [e]
                  (js/console.error (str "FAIL: " (.-message e) " "
                                         (pr-str (ex-data e))))
                  (swap! failures inc))))))

(defn -main [& _]
  (let [mf (Miniflare. #js {:modules true
                            :script "export default {};"
                            :r2Buckets #js {:BUCKET "kotobase-pack"}})]
    (-> (.getR2Bucket mf "BUCKET")
        (.then run-checks)
        (.catch (fn [e]
                  (js/console.error (str "FAIL: " (.-message e)))
                  (swap! failures inc)))
        (.then (fn [_]
                 (-> (.dispose mf)
                     (.then (fn [_]
                              (if (zero? @failures)
                                (println "packed blocks over R2: all green")
                                (println (str "packed blocks over R2: " @failures
                                              " FAILURE(S) above")))
                              (.exit js/process (if (zero? @failures) 0 1))))))))))

(-main)
