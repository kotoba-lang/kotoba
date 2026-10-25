(ns network-bench
  "Live, repeatable evidence for Ayatori's public discovery/retrieval seam.

  This deliberately uses public cid.contact and providers it returns. It also
  injects bounded failures ahead of Kotobase's real provider. The benchmark
  uses the original raw CID from the publisher corpus: IPNI indexes the
  multihash, so inventing a DAG-CBOR CID with the same digest is not evidence
  that the advertised raw block is unavailable.
  Output is JSON so a dated evidence file can record the exact observation."
  (:require [ayatori.discovery :as discovery]
            [ayatori.remote :as remote]))

(def successful-cid
  ;; The original raw CID corresponding to the first entry in Kotobase's
  ;; advertisement. cid.contact discovers Kotobase's provider and the
  ;; advertised kotobase.net gateway serves the bytes.
  "bafkreia2cc444k5yrw57uhszfrvbri7wee3ljbpb5wfcorykk72kgxhjaq")

(def codec-alias-cid
  ;; Same SHA-256 multihash as one advertised raw block, but a DAG-CBOR codec.
  ;; Discovery is expected to find the multihash; retrieval must still fail
  ;; closed because this distinct CID is not the object the provider stored.
  "bafyreia2cc444k5yrw57uhszfrvbri7wee3ljbpb5wfcorykk72kgxhjaq")

(defn- now [] (.now js/performance))

(defn- json-http [{:keys [url headers]}]
  (-> (js/fetch url #js {:method "GET" :headers (clj->js headers)})
      (.then (fn [response]
               (-> (.text response)
                   (.then (fn [body]
                            {:status (.-status response)
                             :body (when (seq body)
                                     (js->clj (js/JSON.parse body)
                                              :keywordize-keys true))})))))))

(defn- block-http [{:keys [url headers]}]
  (-> (js/fetch url #js {:method "GET" :headers (clj->js headers)
                         :redirect "follow"})
      (.then (fn [response]
               (if (= 200 (.-status response))
                 (-> (.arrayBuffer response)
                     (.then (fn [body]
                              {:status 200 :body (js/Uint8Array. body)})))
                 {:status (.-status response)})))))

(def real-fetch (remote/gateway-fetcher-async block-http))

(defn- discover [cid]
  (discovery/find-providers-async
   json-http cid {:routers ["https://cid.contact/routing/v1"] :quorum 1}))

(defn- fake-provider [peer]
  {:plane :discovery :peer peer :cid successful-cid :addrs []
   :mutates-cid? false})

(defn- with-first-provider [discover-fn provider]
  (fn [cid]
    (-> (discover-fn cid)
        (.then (fn [result]
                 (update result :providers #(vec (cons (assoc provider :cid cid) %))))))))

(defn- delay-reject [ms message]
  (js/Promise. (fn [_ reject]
                 (js/setTimeout #(reject (js/Error. message)) ms))))

(defn- sample [cid discover-fn fetch-fn]
  (let [started (now)
        stats (atom {})
        getter (remote/provider-block-getter-async
                {:discover-fn discover-fn :fetch-fn fetch-fn :stats stats})]
    (-> (getter cid)
        (.then (fn [bytes]
                 {:ok true :ms (- (now) started)
                  :bytes (.-byteLength bytes) :stats @stats}))
        (.catch (fn [e]
                  {:ok false :ms (- (now) started)
                   :type (some-> e ex-data :type name)
                   :message (or (.-message e) (str e))
                   :stats @stats})))))

(defn- run-n [n f]
  (reduce (fn [promise _]
            (.then promise
                   (fn [acc]
                     (-> (f) (.then #(conj acc %))))))
          (js/Promise.resolve [])
          (range n)))

(defn- percentile [xs p]
  (when (seq xs)
    (let [sorted (vec (sort xs))
          idx (max 0 (dec (js/Math.ceil (* p (count sorted)))))]
      (nth sorted idx))))

(defn- summary [samples]
  (let [ok (filter :ok samples)
        ms (map :ms ok)]
    {:samples (count samples)
     :successes (count ok)
     :failures (- (count samples) (count ok))
     :p50-ms (percentile ms 0.50)
     :p95-ms (percentile ms 0.95)
     :min-ms (when (seq ms) (apply min ms))
     :max-ms (when (seq ms) (apply max ms))
     :observations samples}))

(defn- main []
  (let [normal-n (js/parseInt (or (aget js/process.env "AYATORI_NORMAL_SAMPLES") "20") 10)
        failure-n (js/parseInt (or (aget js/process.env "AYATORI_FAILURE_SAMPLES") "10") 10)
        alias-n (js/parseInt (or (aget js/process.env "AYATORI_ALIAS_SAMPLES") "5") 10)
        timeout-provider (fake-provider "injected-timeout")
        corrupt-provider (fake-provider "injected-corrupt")
        corrupt-bytes (.encode (js/TextEncoder.) "not the requested block")
        normal-p (run-n normal-n #(sample successful-cid discover real-fetch))
        timeout-p
        (.then normal-p
               (fn [normal]
                 (-> (run-n failure-n
                            #(sample successful-cid
                                     (with-first-provider discover timeout-provider)
                                     (fn [provider cid]
                                       (if (= "injected-timeout" (:peer provider))
                                         (delay-reject 50 "injected timeout")
                                         (real-fetch provider cid)))))
                     (.then (fn [timeout-fallback]
                              [normal timeout-fallback])))))
        corrupt-p
        (.then timeout-p
               (fn [[normal timeout-fallback]]
                 (-> (run-n failure-n
                            #(sample successful-cid
                                     (with-first-provider discover corrupt-provider)
                                     (fn [provider cid]
                                       (if (= "injected-corrupt" (:peer provider))
                                         (js/Promise.resolve corrupt-bytes)
                                         (real-fetch provider cid)))))
                     (.then (fn [corrupt-fallback]
                              [normal timeout-fallback corrupt-fallback])))))
        result-p
        (.then corrupt-p
               (fn [[normal timeout-fallback corrupt-fallback]]
                 (-> (run-n alias-n
                            #(sample codec-alias-cid discover real-fetch))
                     (.then
                      (fn [codec-alias]
                        {:schema "ayatori.network-benchmark/v1"
                         :measured-at (.toISOString (js/Date.))
                         :runtime (.-version js/process)
                         :public-indexer "https://cid.contact/routing/v1"
                         :successful-cid successful-cid
                         :codec-alias-cid codec-alias-cid
                         :normal (summary normal)
                         :timeout-first-provider (summary timeout-fallback)
                         :corrupt-first-provider (summary corrupt-fallback)
                         :codec-alias-negative (summary codec-alias)})))))]
    (-> result-p
        (.then #(println (js/JSON.stringify (clj->js %) nil 2)))
        (.catch (fn [e]
                  (println (js/JSON.stringify
                            #js {:fatal (or (.-message e) (str e))}))
                  (set! (.-exitCode js/process) 1))))))

(main)
