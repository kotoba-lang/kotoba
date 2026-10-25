(ns run
  "Qualification for the provider-neutral, block-only IPFS adapter."
  (:require [kotobase.storage.async-contract :as contract]
            [kotobase.storage.core :as storage]
            [kotobase.storage.ipfs :as ipfs]))

(def ^:private failures (atom 0))

(defn- expect [ok? message]
  (if ok?
    (println (str "ok  - " message))
    (do (js/console.error (str "FAIL: " message)) (swap! failures inc))))

(defn- block-client []
  (let [blocks (atom {})]
    {:put-block! (fn [cid bytes]
                   (swap! blocks assoc cid bytes)
                   (js/Promise.resolve cid))
     :get-block (fn [cid] (js/Promise.resolve (get @blocks cid)))}))

(defrecord LinearRefs [heads]
  storage/IRefStore
  (-read-ref [_ name]
    (js/Promise.resolve (get @heads name)))
  (-compare-and-set-ref! [_ name expected next]
    (let [answer (atom nil)]
      (swap! heads
             (fn [state]
               (let [{current :cid version :version} (get state name)
                     version (or version 0)]
                 (if (= expected current)
                   (let [next-record {:cid next :version (inc version)}]
                     (reset! answer
                             {:published? true :current next
                              :version (:version next-record)})
                     (assoc state name next-record))
                   (do
                     (reset! answer
                             {:published? false :current current
                              :version version})
                     state)))))
      (js/Promise.resolve @answer)))

  storage/IBackendCapabilities
  (-capabilities [_]
    #{:conditional-ref :linearizable-ref}))

(defn- adapter [] (ipfs/open {:client (block-client)}))

(defn- qualify-shape []
  (let [blocks (adapter)]
    (storage/validate-block-store! blocks)
    (expect (storage/block-store? blocks)
            "the adapter implements immutable block storage")
    (expect (not (storage/ref-store? blocks))
            "the adapter does not pretend block transport is mutable agreement")
    (expect (not (contains? (storage/-capabilities blocks) :conditional-ref))
            "the adapter declares no ref capability")))

(defn- qualify-client-validation []
  (try
    (ipfs/open {:client {:get-block (fn [_] (js/Promise.resolve nil))}})
    (expect false "an incomplete client is rejected")
    (catch :default error
      (expect (= :put-block! (:missing (ex-data error)))
              "an incomplete client identifies the missing operation"))))

(defn -main [& _]
  (qualify-shape)
  (qualify-client-validation)
  (let [backend (storage/compose
                 {:blocks (adapter)
                  :refs (->LinearRefs (atom {}))})]
    (-> (contract/verify backend)
        (.then
         (fn [result]
           (println (str "composed backend contract: " (pr-str result)))
           (expect (= :verified (:concurrency result))
                   "concurrency is supplied and verified by the ref plane")))
        (.catch
         (fn [error]
           (js/console.error (str "FAIL: contract -- " (.-message error)))
           (when-let [data (ex-data error)] (js/console.error (pr-str data)))
           (swap! failures inc)))
        (.then
         (fn [_]
           (if (zero? @failures)
             (println "kotobase-storage-ipfs: all green")
             (println (str "kotobase-storage-ipfs: " @failures
                           " FAILURE(S) above")))
           (.exit js/process (if (zero? @failures) 0 1)))))))

(-main)
