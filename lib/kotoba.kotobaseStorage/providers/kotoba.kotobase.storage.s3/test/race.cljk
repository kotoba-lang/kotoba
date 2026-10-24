(ns race
  "Two writers, one ref. Exactly one may be told it won.

  `-compare-and-set-ref!` reads the ref, compares, then does a conditional PUT.
  Sequentially the read-and-compare answers correctly whether or not the
  provider enforces the precondition, which is why the shared contract passes
  for a backend that ignores preconditions entirely. The precondition is the
  only thing standing between two writers that both read the SAME current
  value — so this property cannot be observed by a sequential suite, and the
  contract is sequential.

  No threads are needed: both CAS calls are started before either completes, so
  both observe the same ref, which is exactly the interleaving that matters."
  (:require [kotobase.storage.core :as storage]
            [kotobase.storage.s3 :as s3]))

(defn- client [honour-match?]
  (let [objects (atom {})
        version (atom 0)]
    {:get-object (fn [{:keys [key]}] (js/Promise.resolve (get @objects key)))
     :put-object!
     (fn [{:keys [key body if-match if-none-match]}]
       (let [current (get @objects key)
             won? (cond
                    if-match (if honour-match? (= if-match (:etag current)) true)
                    if-none-match (nil? current)
                    :else true)]
         (if-not won?
           (js/Promise.resolve nil)
           (let [etag (str "v" (swap! version inc))]
             (swap! objects assoc key {:body body :etag etag})
             (js/Promise.resolve {:etag etag})))))}))

(defn- race-case [label honour-match? expect-winners]
  (let [backend (s3/open {:client (client honour-match?) :prefix (str "race/" label)})]
    (-> (storage/-compare-and-set-ref! backend "main" nil "cid-genesis")
        (.then (fn [_]
                 ;; both start before either finishes, so both read "cid-genesis"
                 (js/Promise.all
                  #js [(storage/-compare-and-set-ref! backend "main" "cid-genesis" "cid-a")
                       (storage/-compare-and-set-ref! backend "main" "cid-genesis" "cid-b")])))
        (.then (fn [rs]
                 (let [winners (count (filter :published? (js->clj rs :keywordize-keys true)))
                       ok? (= winners expect-winners)]
                   (println (str (if ok? "PASS " "FAIL ") label
                                 "  winners=" winners
                                 " expected=" expect-winners
                                 (when (> winners 1)
                                   "  — both writers were told they won; the head can diverge")))
                   ok?))))))

(defn ^:export main [& _]
  (println "two writers, one ref")
  (println)
  (-> (js/Promise.all
       #js [(race-case "provider-honours-if-match" true 1)
            (race-case "provider-ignores-if-match" false 1)])
      (.then (fn [rs]
               (let [bad (count (remove true? (js->clj rs)))]
                 (println)
                 (if (zero? bad)
                   (println "CAS holds under interleaving in both cases")
                   (do (println (str bad " case(s) failed — a provider that ignores If-Match"
                                     " gives this adapter no compare-and-set at all"))
                       (set! (.-exitCode js/process) 1))))))))
