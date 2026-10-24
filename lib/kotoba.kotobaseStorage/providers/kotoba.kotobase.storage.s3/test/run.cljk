(ns run
  "Conformance, plus the part conformance cannot reach.

  The suite can only judge the store it is handed. It cannot know whether
  the real endpoint behind that store honours `If-Match` -- the one thing
  deciding whether this adapter's read-then-conditional-write is
  linearizable or lossy. So this file does two jobs: run the contract
  against an enforcing mock, and pin the decisions this adapter makes
  BEFORE any request is sent -- which profile it declares, and when it
  refuses to open at all."
  (:require [kotobase.storage.async-contract :as contract]
            [kotobase.storage.core :as storage]
            [kotobase.storage.s3 :as s3]))

(def ^:private failures
  "Counted explicitly, with the process exiting on this rather than on
  `process.exitCode`, which the runner may reset before the promise chain
  settles. Verified by breaking a check on purpose: with the implicit form
  a failing run still exited 0, so CI would have been green forever."
  (atom 0))

(defn- expect [ok? message]
  (if ok?
    (println (str "ok  - " message))
    (do (js/console.error (str "FAIL: " message)) (swap! failures inc))))

(defn- object-store
  "A mock S3 that evaluates preconditions the way a conforming endpoint
   does: at write time, against the stored ETag."
  [{:keys [enforce?] :or {enforce? true}}]
  (let [objects (atom {})
        version (atom 0)]
    {:get-object
     (fn [{:keys [key]}] (js/Promise.resolve (get @objects key)))
     :put-object!
     (fn [{:keys [key body if-match if-none-match]}]
       (js/Promise.resolve
        (let [current (get @objects key)
              won? (if-not enforce?
                     true
                     (cond
                       if-match (= if-match (:etag current))
                       if-none-match (nil? current)
                       :else true))]
          (when won?
            (let [etag (str "v" (swap! version inc))]
              (swap! objects assoc key {:body body :etag etag})))
          (when won? (get @objects key)))))}))

(defn- native-client [opts] (assoc (object-store opts) :conditional-put :native))

;; ── what this adapter decides before it ever sends a request ────────────────

(defn- pin-profiles []
  (expect (= :linearizable-ref
             (storage/ref-profile
              (s3/open {:client (native-client {}) :prefix "t"})))
          "an R2-style native client is linearizable")
  (expect (= :single-writer-ref
             (storage/ref-profile
              (s3/open {:client (object-store {}) :prefix "t"})))
          "an UNMARKED client is single-writer, not linearizable by default")
  (expect (= :single-writer-ref
             (storage/ref-profile
              (s3/open {:client (assoc (object-store {})
                                       :conditional-put :unverified)
                        :prefix "t"})))
          "and an explicitly unverified endpoint stays single-writer")
  (expect (= :linearizable-ref
             (storage/ref-profile
              (s3/open {:client (assoc (object-store {})
                                       :conditional-put :verified)
                        :prefix "t"})))
          "a probed endpoint may be promoted to linearizable")
  (expect (= :unverified (s3/conditional-put (s3/signed-client {:endpoint "x"})))
          "a signed HTTP client does not claim more than it can know"))

(defn- pin-refusal []
  (expect (try (s3/open {:client (object-store {}) :prefix "t"
                         :require-linearizable? true})
               false
               (catch :default e
                 (= :kotobase.storage/unverified-conditional-put
                    (:type (ex-data e)))))
          "opening a linearizable-required backend on an unverified endpoint is refused")
  (expect (some? (s3/open {:client (native-client {}) :prefix "t"
                           :require-linearizable? true}))
          "and permitted on a native one"))

;; ── the probe, against endpoints that do and do not enforce ─────────────────

(defn- pin-probe []
  (-> (s3/probe-conditional-put! {:client (native-client {}) :prefix "t"})
      (.then (fn [{:keys [enforced?]}]
               (expect (true? enforced?) "the probe passes an enforcing endpoint")))
      (.then (fn [_]
               (s3/probe-conditional-put!
                {:client (object-store {:enforce? false}) :prefix "t"})))
      (.then (fn [{:keys [enforced? checks]}]
               (expect (false? enforced?)
                       "the probe catches an endpoint that ignores preconditions")
               (expect (= {:if-none-match-rejected? false
                           :if-match-rejected? false
                           :etag-returned? true}
                          checks)
                       "and says which precondition was ignored, not just that one was")))))

(defn -main [& _]
  (pin-profiles)
  (pin-refusal)
  (-> (pin-probe)
      (.then (fn [_]
               (contract/verify (s3/open {:client (native-client {})
                                          :prefix "test"}))))
      (.then (fn [result]
               (println (str "S3 contract: " (pr-str result)))
               (expect (= :verified (:concurrency result))
                       "the contract actually raced this backend")))
      (.catch (fn [error]
                (js/console.error (str "FAIL: contract -- " (.-message error)))
                (when-let [data (ex-data error)] (js/console.error (pr-str data)))
                (swap! failures inc)))
      (.then (fn [_]
               (if (zero? @failures)
                 (println "kotobase-storage-s3: all green")
                 (println (str "kotobase-storage-s3: " @failures " FAILURE(S) above")))
               (.exit js/process (if (zero? @failures) 0 1))))))

(-main)
