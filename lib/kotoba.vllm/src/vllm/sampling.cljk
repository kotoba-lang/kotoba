(ns vllm.sampling
  "Sampling parameters as data. Holds the canonical default set, the
  `:vllm/*` → OpenAI/vLLM wire-field mapping, and pure range checks. vLLM
  extends the OpenAI sampling surface (top_k, min_p, repetition_penalty,
  best_of, and the `guided_*` structured-output knobs); those live here too so
  the request model stays a plain map."
  (:require [kotoba.lang.text :as str]))

(def defaults
  "A conservative default sampling map."
  {:vllm/temperature 0.7
   :vllm/top-p       1.0
   :vllm/max-tokens  512})

;; namespaced sampling key -> OpenAI/vLLM JSON field name.
(def field->wire
  {:vllm/temperature        "temperature"
   :vllm/top-p              "top_p"
   :vllm/top-k              "top_k"               ; vLLM extension
   :vllm/min-p              "min_p"               ; vLLM extension
   :vllm/max-tokens         "max_tokens"
   :vllm/n                  "n"
   :vllm/best-of            "best_of"             ; vLLM extension
   :vllm/presence-penalty   "presence_penalty"
   :vllm/frequency-penalty  "frequency_penalty"
   :vllm/repetition-penalty "repetition_penalty"  ; vLLM extension
   :vllm/stop               "stop"
   :vllm/seed               "seed"
   :vllm/logprobs           "logprobs"
   :vllm/guided-json        "guided_json"         ; vLLM structured output
   :vllm/guided-regex       "guided_regex"        ; vLLM structured output
   :vllm/guided-choice      "guided_choice"})     ; vLLM structured output

;; (key, lower-incl, upper-incl) bounds. nil bound = unbounded on that side.
(def ^:private bounds
  {:vllm/temperature        [0.0 2.0]
   :vllm/top-p              [0.0 1.0]
   :vllm/min-p              [0.0 1.0]
   :vllm/top-k              [-1 nil]              ; -1 = disabled in vLLM
   :vllm/max-tokens         [1 nil]
   :vllm/n                  [1 nil]
   :vllm/best-of            [1 nil]
   :vllm/presence-penalty   [-2.0 2.0]
   :vllm/frequency-penalty  [-2.0 2.0]
   :vllm/repetition-penalty [0.0 nil]})

(defn- out-of-range? [k v]
  (when-let [[lo hi] (get bounds k)]
    (and (number? v)
         (or (and lo (< v lo)) (and hi (> v hi))))))

(defn problems
  "Range/consistency problems in a sampling map, as a vector of problem maps
  `{:vllm/severity :vllm/code :vllm/field :vllm/msg}`. Pure."
  [sampling]
  (vec
   (concat
    (for [[k v] sampling :when (out-of-range? k v)]
      {:vllm/severity :error :vllm/code :sampling/range :vllm/field k
       :vllm/msg (str k " = " v " is out of range " (get bounds k))})
    (when-let [bo (:vllm/best-of sampling)]
      (let [n (:vllm/n sampling 1)]
        (when (< bo n)
          [{:vllm/severity :error :vllm/code :sampling/best-of :vllm/field :vllm/best-of
            :vllm/msg (str "best_of " bo " must be ≥ n " n)}])))
    (for [k (keys sampling) :when (not (contains? field->wire k))]
      {:vllm/severity :warn :vllm/code :sampling/unknown :vllm/field k
       :vllm/msg (str "unknown sampling key (dropped on the wire): " k)}))))

(defn to-wire
  "Render a sampling map to string-keyed OpenAI/vLLM fields. Unknown keys are
  dropped (they are reported by `problems`/`vllm.validate`). `:vllm/stop` may be
  a string or a vector. Pure."
  [sampling]
  (reduce-kv
   (fn [m k v]
     (if-let [wire (field->wire k)] (assoc m wire v) m))
   {}
   sampling))

(defn summary-str
  "A short `temp=0.7 top_p=1.0 max=512`-style line for logs."
  [sampling]
  (->> [[:vllm/temperature "temp"] [:vllm/top-p "top_p"] [:vllm/top-k "top_k"]
        [:vllm/max-tokens "max"]]
       (keep (fn [[k label]] (when-some [v (get sampling k)] (str label "=" v))))
       (str/join " ")))
