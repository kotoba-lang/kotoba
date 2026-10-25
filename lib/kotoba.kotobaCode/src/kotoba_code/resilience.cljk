(ns kotoba-code.resilience
  "Resilience wrappers for the model seam. A single transient API error
  (rate limit, 5xx, network blip) should not kill a whole agent run — the
  batch on 2026-06-14 lost segment 26 to exactly that. `retrying-model`
  wraps any ChatModel so -generate retries with linear backoff."
  (:require [langchain.model :as model])
  (:import [java.io IOException]
           [java.net ConnectException SocketTimeoutException]))

(def ^:private retryable-statuses #{408 409 425 429})

(defn retryable-error?
  "True when an exception is likely transient at the model/API boundary."
  [^Throwable e]
  (let [status (:status (ex-data e))]
    (or (instance? IOException e)
        (instance? ConnectException e)
        (instance? SocketTimeoutException e)
        (contains? retryable-statuses status)
        (and (integer? status) (<= 500 status 599)))))

(defn retrying-model
  "Wrap a ChatModel so -generate retries on exception (transient API errors).
   opts:
     :attempts   total tries before giving up (default 4)
     :backoff-ms base backoff; attempt n sleeps (* backoff-ms n) (default 1500)
     :retryable? (fn [^Throwable e] -> boolean), default retryable-error?
     :on-retry   (fn [attempt ^Throwable e]) side-effect hook (e.g. logging)"
  ([m] (retrying-model m {}))
  ([m {:keys [attempts backoff-ms retryable? on-retry]
       :or {attempts 4 backoff-ms 1500 retryable? retryable-error?}}]
   (reify model/ChatModel
     (-generate [_ messages opts]
       (loop [n 1]
         (let [r (try {:ok (model/-generate m messages opts)}
                      (catch Throwable e {:err e}))]
           (if (contains? r :ok)
             (:ok r)
             (if (and (< n attempts) (retryable? (:err r)))
               (do (when on-retry (on-retry n (:err r)))
                   (when (pos? backoff-ms) (Thread/sleep (* (long backoff-ms) n)))
                   (recur (inc n)))
               (let [e ^Throwable (:err r)
                     data (merge (or (ex-data e) {})
                                 {:retry/attempts-used n
                                  :retry/attempts-limit attempts
                                  :retry/retryable? (boolean (retryable? e))})]
                 (throw (ex-info (or (.getMessage e) "Model call failed")
                                 data
                                 e)))))))))))
