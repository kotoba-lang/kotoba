(ns advanced-r2
  "The same checks, compiled the way production is.

  This exists because every suite in this repo ran unoptimised -- nbb, or
  shadow-cljs at `:optimizations :none` -- and the bug it guards against
  only appears under `:advanced`, which is what a Workers build ships.

  What happened: `(.-etag object)` on the R2 binding was renamed by the
  Closure compiler, because externs inference could not type the bucket
  (it arrives as an untyped function parameter). `:etag` came back nil,
  every ref got a nil version, and `-compare-and-set-ref!` then sent a PUT
  carrying no precondition at all. Against PRODUCTION R2 that reported
  `etag-returned? false` and `4 of 4 concurrent writers all published`,
  while the identical source at `:optimizations :simple` reported
  `enforced? true` and passed the race.

  So the property this pins is narrow and specific: the ETag survives
  advanced compilation. If it stops surviving, `-compare-and-set-ref!` now
  refuses rather than writing unconditionally -- but a refusal is an
  outage, and this catches it before a deploy does."
  (:require ["miniflare" :refer [Miniflare]]
            [kotobase.storage.async-contract :as contract]
            [kotobase.storage.s3 :as s3]))

(def ^:private failures (atom 0))

(defn- expect [ok? message]
  (if ok?
    (println (str "ok  - " message))
    (do (js/console.error (str "FAIL: " message)) (swap! failures inc))))

(defn- run [bucket]
  (let [client (s3/r2-client bucket)]
    (-> (s3/probe-conditional-put! {:client client :prefix "adv"})
        (.then
         (fn [{:keys [enforced? checks] :as probe}]
           (expect (get checks :etag-returned?)
                   (str "the ETag survives advanced compilation -- "
                        "this is the whole test: " (pr-str probe)))
           (expect (true? enforced?)
                   "and both preconditions are enforced through the compiled client")))
        (.then
         (fn [_]
           (contract/verify (s3/open {:client client :prefix "adv"
                                      :require-linearizable? true}))))
        (.then
         (fn [result]
           (println (str "advanced contract: " (pr-str result)))
           (expect (= :verified (:concurrency result))
                   "the race passes in the shipping configuration"))))))

(defn -main [& _]
  (let [mf (Miniflare. #js {:modules true
                            :script "export default {};"
                            :r2Buckets #js {:BUCKET "kotobase-advanced"}})]
    (-> (.getR2Bucket mf "BUCKET")
        (.then run)
        (.catch (fn [error]
                  (js/console.error (str "FAIL: " (.-message error)))
                  (swap! failures inc)))
        (.then (fn [_]
                 (-> (.dispose mf)
                     (.then (fn [_]
                              (if (zero? @failures)
                                (println "kotobase-storage-s3 (advanced): all green")
                                (println (str "kotobase-storage-s3 (advanced): "
                                              @failures " FAILURE(S) above")))
                              (.exit js/process (if (zero? @failures) 0 1))))))))))
