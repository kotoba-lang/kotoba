(ns kotoba-code.transcript
  "Extract compact run transcripts from langchain/langgraph message state."
  (:require [kotoba.lang.text :as str]))

(defn- text [content]
  (cond
    (nil? content) ""
    (string? content) content
    (sequential? content) (apply str (map text content))
    :else (str content)))

(defn redact-text [s]
  (-> (text s)
      (str/replace #"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;\]\}\)]+"
                   "$1[REDACTED]")
      (str/replace #"(?i)\b((?:api[_-]?key|token|password|secret)\s*[:=]\s*)[^\s,;\]\}\)]+"
                   "$1[REDACTED]")
      (str/replace #"\bsk-or-[A-Za-z0-9._-]+" "sk-or-[REDACTED]")
      (str/replace #"\bsk-[A-Za-z0-9._-]+" "sk-[REDACTED]")))

(defn- sensitive-key? [k]
  (let [s (str/lower (name k))
        s* (str/replace s #"[_\s]+" "-")]
    (boolean
     (or (#{"authorization" "api-key" "apikey" "token" "password" "passwd" "secret"} s*)
         (str/includes? s* "api-key")
         (str/includes? s* "apikey")
         (str/includes? s* "token")
         (str/includes? s* "password")
         (str/includes? s* "secret")))))

(defn redact-data [x]
  (cond
    (map? x)
    (into (empty x)
          (map (fn [[k v]]
                 [k (if (sensitive-key? k)
                      "[REDACTED]"
                      (redact-data v))]))
          x)

    (vector? x)
    (mapv redact-data x)

    (sequential? x)
    (doall (map redact-data x))

    (string? x)
    (redact-text x)

    :else x))

(def ^:private max-input-string 240)
(def ^:private max-input-items 20)

(def summary-limits
  "Durable transcript summarization limits exposed for supervisors."
  {:max-input-string max-input-string
   :max-input-items max-input-items
   :max-result-tail-chars 240})

(defn- summarize-string [s]
  (let [s* (redact-text s)]
    (cond-> {:text (if (> (count s*) max-input-string)
                     (str (subs s* 0 max-input-string) "...")
                     s*)
             :chars (count s*)}
      (> (count s*) max-input-string) (assoc :truncated? true))))

(defn summarize-data [x]
  (let [x* (redact-data x)]
    (cond
      (map? x*)
      (into (empty x*)
            (map (fn [[k v]] [k (summarize-data v)]))
            x*)

      (vector? x*)
      (let [items (take max-input-items x*)]
        (cond-> (mapv summarize-data items)
          (> (count x*) max-input-items)
          (conj {:truncated-items (- (count x*) max-input-items)})))

      (sequential? x*)
      (let [xs (vec x*)
            items (take max-input-items xs)]
        (cond-> (mapv summarize-data items)
          (> (count xs) max-input-items)
          (conj {:truncated-items (- (count xs) max-input-items)})))

      (string? x*)
      (summarize-string x*)

      :else x*)))

(defn tail
  ([s] (tail s 240))
  ([s n]
   (let [s* (str/trim (redact-text s))]
     (if (> (count s*) n)
       (str "..." (subs s* (- (count s*) n)))
       s*))))

(defn- tool-error-result? [s]
  (str/starts-with? (str/trim (redact-text s)) "TOOL_ERROR:"))

(defn tool-events
  "Returns one event per observed tool call/result pair.

  Event shape:
    {:type :tool-call
     :payload {:id string :name string :input edn :result-tail string :error? bool}}"
  [final-state]
  (let [messages (:messages final-state)
        calls (atom {})]
    (->> messages
         (mapcat
          (fn [m]
            (cond
              (seq (:tool-calls m))
              (do
                (doseq [{:keys [id] :as call} (:tool-calls m)]
                  (swap! calls assoc id call))
                [])

              (= :tool (:role m))
              (let [id (:tool-call-id m)
                    {:keys [name input]} (get @calls id)
                    result-tail (tail (:content m))]
                [{:type :tool-call
                  :payload {:id id
                            :name name
                            :input (summarize-data input)
                            :result-tail result-tail
                            :error? (boolean (or (:error? m)
                                                 (tool-error-result? result-tail)))}}])

              :else [])))
         vec)))

(defn tool-count [final-state]
  (count (tool-events final-state)))

(defn lines
  "Human-facing compact transcript lines."
  [final-state]
  (mapv (fn [{:keys [payload]}]
          (let [{:keys [name result-tail error?]} payload]
            (str (if error? "ERR " "OK  ")
                 (or name "<unknown>")
                 (when (seq result-tail) (str " -> " result-tail)))))
        (tool-events final-state)))
