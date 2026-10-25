(ns browseruse.guardrail
  (:require [kotoba.lang.text :as str]))

(def defaults
  {:allowed-domains [] :sensitive-data {} :max-action-retries 0
   :action-timeout-ms 120000 :output-validator nil})

(defn policy [opts] (merge defaults (or opts {})))

(defn redact
  "Replace configured secret values in nested data and strings."
  [value sensitive-data]
  (let [secrets (remove str/blank? (map str (vals sensitive-data)))
        scrub #(reduce (fn [s secret] (str/replace s secret "[REDACTED]")) (str %) secrets)]
    (cond (map? value) (into {} (map (fn [[k v]] [k (redact v sensitive-data)])) value)
          (vector? value) (mapv #(redact % sensitive-data) value)
          (sequential? value) (map #(redact % sensitive-data) value)
          (string? value) (scrub value)
          :else value)))

(defn url-domain [url]
  #?(:clj (try (.getHost (java.net.URI. (str url))) (catch Exception _ nil))
     :cljs (try (.-hostname (js/URL. (str url))) (catch :default _ nil))))

(defn allowed-url? [allowed-domains url]
  (or (empty? allowed-domains)
      (let [host (some-> (url-domain url) str/lower)]
        (boolean (some (fn [domain]
                         (let [domain (str/lower (str domain))]
                           (or (= host domain) (str/ends-with? host (str "." domain)))))
                       allowed-domains)))))

(defn assert-action! [{:keys [allowed-domains]} {:keys [name input]}]
  (when (and (= "navigate" name) (not (allowed-url? allowed-domains (:url input))))
    (throw (ex-info "browser-use: navigation domain denied"
                    {:type :guardrail/domain-denied :url (:url input)})))
  true)

(defn assert-url! [{:keys [allowed-domains]} url]
  (when-not (allowed-url? allowed-domains url)
    (throw (ex-info "browser-use: resulting domain denied"
                    {:type :guardrail/domain-denied :url url})))
  true)

(defn execute
  "Execute with bounded retries, elapsed timeout classification and validation."
  [{:keys [max-action-retries action-timeout-ms output-validator] :as p} action f]
  (assert-action! p action)
  (loop [attempt 1]
    (let [started #?(:clj (System/nanoTime) :cljs (.now js/Date))
          outcome (try {:value (f)}
                       (catch #?(:clj Exception :cljs :default) e {:error e}))
          elapsed #?(:clj (/ (- (System/nanoTime) started) 1000000.0)
                     :cljs (- (.now js/Date) started))
          error (or (:error outcome)
                    (when (> elapsed action-timeout-ms)
                      (ex-info "browser-use: action timeout" {:type :guardrail/timeout}))
                    (when (and output-validator
                               (not (output-validator (:value outcome))))
                      (ex-info "browser-use: output validation failed"
                               {:type :guardrail/invalid-output})))]
      (if (and error (<= attempt max-action-retries))
        (recur (inc attempt))
        (if error (throw error) {:value (:value outcome) :attempts attempt :elapsed-ms elapsed})))))
