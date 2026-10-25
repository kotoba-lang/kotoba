(ns teeth
  "Does the storage contract actually detect a provider that ignores
  preconditions?

  The suite is only worth running against a real endpoint if it FAILS for a
  backend that accepts conditional PUTs unconditionally. If it passes, then a
  green run against any provider proves nothing, and the S3 adapter would be
  promoted to primary on the strength of a test that cannot fail.

  So this runs the same contract three times:

    conforming      honours If-None-Match / If-Match   -> must PASS
    ignores-all     accepts every conditional PUT      -> must FAIL
    ignores-if-match  honours creation, ignores CAS    -> must FAIL

  The third case is the realistic one. Several S3-compatible providers added
  `If-None-Match: *` for creation without adding `If-Match` for updates, so a
  backend can look correct for blocks while silently having no
  compare-and-set for refs — which is the property the single-writer head
  model depends on."
  (:require [kotobase.storage.async-contract :as contract]
            [kotobase.storage.s3 :as s3]))

(defn- client
  "In-memory S3, with the precondition behaviour selectable.

  HONOUR-CREATE? -- enforce If-None-Match:* (reject overwrite)
  HONOUR-MATCH?  -- enforce If-Match (reject a stale etag)"
  [honour-create? honour-match?]
  (let [objects (atom {})
        version (atom 0)]
    {:get-object (fn [{:keys [key]}] (js/Promise.resolve (get @objects key)))
     :put-object!
     (fn [{:keys [key body if-match if-none-match]}]
       (let [current (get @objects key)
             won? (cond
                    if-match (if honour-match?
                               (= if-match (:etag current))
                               true)
                    if-none-match (if honour-create?
                                    (nil? current)
                                    true)
                    :else true)]
         (if-not won?
           (js/Promise.resolve nil)
           (let [etag (str "v" (swap! version inc))
                 result {:body body :etag etag}]
             (swap! objects assoc key result)
             (js/Promise.resolve result)))))}))

(defn- run-case [label honour-create? honour-match? expect-pass?]
  (-> (contract/verify (s3/open {:client (client honour-create? honour-match?)
                                 :prefix (str "teeth/" label)}))
      (.then (fn [_] [true nil]))
      (.catch (fn [e] [false (or (.-message e) (str e))]))
      (.then (fn [[passed? reason]]
               (let [ok? (= passed? expect-pass?)]
                 (println (str (if ok? "PASS " "FAIL ")
                               label
                               "  contract " (if passed? "passed" "failed")
                               ", expected " (if expect-pass? "pass" "fail")
                               (when reason (str "  — " reason)))))
               (= passed? expect-pass?)))))

(defn ^:export main [& _]
  (println "does the storage contract have teeth?")
  (println)
  (-> (js/Promise.all
       #js [(run-case "conforming" true true true)
            (run-case "ignores-all-preconditions" false false false)
            (run-case "ignores-if-match-only" true false false)])
      (.then (fn [rs]
               (let [rs (js->clj rs)
                     bad (count (remove true? rs))]
                 (println)
                 (if (zero? bad)
                   (println "the contract distinguishes conforming providers from non-conforming ones")
                   (do (println (str bad " case(s) behaved unexpectedly — the contract cannot be"
                                     " trusted to qualify a provider"))
                       (set! (.-exitCode js/process) 1))))))))
