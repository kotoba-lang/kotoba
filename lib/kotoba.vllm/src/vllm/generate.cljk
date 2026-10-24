(ns vllm.generate
  "Autoregressive token generation over vllm.llama/step!."
  (:require [vllm.llama :as llama])
  (:import [java.util Random]))

(defn- adjusted-logits [^floats logits history repetition-penalty]
  (let [values (double-array (map double logits))]
    (when (and repetition-penalty (not= 1.0 repetition-penalty))
      (doseq [token (distinct history)]
        (when (< -1 token (alength values))
          (let [value (aget values token)]
            (aset-double values token
                         (if (neg? value) (* value repetition-penalty)
                             (/ value repetition-penalty)))))))
    values))

(defn sample-token
  "Sample one token with temperature, top-k and nucleus top-p filtering."
  [logits history ^Random random
   {:keys [temperature top-k top-p repetition-penalty]
    :or {temperature 0.8 top-k 40 top-p 0.95 repetition-penalty 1.0}}]
  (let [values (adjusted-logits logits history repetition-penalty)
        count* (alength values)]
    (if (or (zero? temperature) (<= temperature 1.0e-8))
      (reduce (fn [best i] (if (> (aget values i) (aget values best)) i best))
              0 (range 1 count*))
      (let [ranked (sort-by (fn [i] (- (aget values i))) (range count*))
            ranked (take (min count* (max 1 (long top-k))) ranked)
            maximum (apply max (map #(aget values %) ranked))
            weighted (mapv (fn [id] [id (Math/exp (/ (- (aget values id) maximum)
                                                       temperature))]) ranked)
            total (reduce + (map second weighted))
            normalized (mapv (fn [[id weight]] [id (/ weight total)]) weighted)
            nucleus (loop [remaining normalized cumulative 0.0 kept []]
                      (let [[entry & more] remaining
                            kept (conj kept entry) cumulative (+ cumulative (second entry))]
                        (if (or (>= cumulative top-p) (empty? more)) kept
                            (recur more cumulative kept))))
            nucleus-total (reduce + (map second nucleus))
            target (* (.nextDouble random) nucleus-total)]
        (loop [remaining nucleus cumulative 0.0]
          (let [[[id probability] & more] remaining
                cumulative (+ cumulative probability)]
            (if (or (>= cumulative target) (empty? more)) id
                (recur more cumulative))))))))

(defn generate-tokens
  "Prefill prompt IDs and generate tokens. Options include `:max-tokens`,
  `:seed`, `:eos-token-ids`, sampling options, and optional `:on-token`.
  `:step-fn` is an injectable `(fn [model state token] result)` test/runtime seam."
  [model state prompt-ids
   {:keys [max-tokens seed eos-token-ids on-token step-fn] :as options
    :or {max-tokens 128 seed 0 eos-token-ids #{} step-fn llama/step!}}]
  (when-not (seq prompt-ids)
    (throw (ex-info "generation requires at least one prompt token" {})))
  (let [random (Random. (long seed))
        history (transient [])]
    (doseq [token (butlast prompt-ids)]
      (step-fn model state token)
      (conj! history token))
    (loop [input (last prompt-ids) generated [] history (persistent! (conj! history input))]
      (if (>= (count generated) max-tokens)
        {:tokens generated :finish-reason :length :state state}
        (let [{:keys [logits]} (step-fn model state input)
              token (sample-token logits history random options)
              generated (conj generated token)]
          (when on-token (on-token token))
          (if (contains? (set eos-token-ids) token)
            {:tokens generated :finish-reason :stop :state state}
            (recur token generated (conj history token))))))))

(defn batch-generate-tokens
  "Continuously batch a cohort of requests with different prompt lengths and
  generation limits. Each request is `{:state :prompt-ids :options}`. Finished
  sequences leave the active batch while the remaining sequences continue."
  [model requests & [{:keys [step-batch-fn] :or {step-batch-fn llama/step-batch!}}]]
  (when-not (seq requests)
    (throw (ex-info "batch generation requires at least one request" {})))
  (let [entries
        (mapv (fn [{:keys [state prompt-ids options prefilled? on-prefilled]}]
                (when-not (seq prompt-ids)
                  (throw (ex-info "generation requires at least one prompt token" {})))
                {:state state :pending (if prefilled? [] (vec (butlast prompt-ids)))
                 :input (last prompt-ids) :on-prefilled on-prefilled
                 :history (vec prompt-ids) :generated [] :done? false
                 :finish-reason nil :options options
                 :random (Random. (long (get options :seed 0)))}) requests)
        entries
        (loop [entries entries]
          (let [active (keep-indexed #(when (seq (:pending %2)) %1) entries)]
            (if (empty? active) entries
              (let [states (mapv #(get-in entries [% :state]) active)
                    tokens (mapv #(first (get-in entries [% :pending])) active)]
                (step-batch-fn model states tokens)
                (recur (reduce (fn [result index]
                                 (update-in result [index :pending] #(vec (rest %))))
                               entries active))))))]
    (doseq [{:keys [state on-prefilled]} entries :when on-prefilled]
      (on-prefilled state))
    (loop [entries entries]
      (let [active (keep-indexed
                    (fn [index entry]
                      (when (and (not (:done? entry))
                                 (< (count (:generated entry))
                                    (long (get-in entry [:options :max-tokens] 128))))
                        index)) entries)]
        (if (empty? active)
          (mapv (fn [{:keys [state generated finish-reason]}]
                  {:tokens generated :finish-reason (or finish-reason :length)
                   :state state}) entries)
          (let [results (step-batch-fn model
                                       (mapv #(get-in entries [% :state]) active)
                                       (mapv #(get-in entries [% :input]) active))
                entries
                (reduce
                 (fn [current [index result]]
                   (let [entry (nth current index) options (:options entry)
                         token (sample-token (:logits result) (:history entry)
                                             (:random entry) options)
                         generated (conj (:generated entry) token)
                         stopped? (contains? (set (get options :eos-token-ids #{})) token)
                         reached? (>= (count generated) (long (get options :max-tokens 128)))
                         on-token (:on-token options)]
                     (when on-token (on-token token))
                     (assoc current index
                            (assoc entry :input token :generated generated
                                   :history (conj (:history entry) token)
                                   :done? (or stopped? reached?)
                                   :finish-reason (cond stopped? :stop reached? :length)))))
                 entries (map vector active results))]
            (recur entries)))))))
