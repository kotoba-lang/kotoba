(ns kotodama.inference.ops
  "Portable transformer ops used by the direct Gemma verifier path."
  (:require [num.array :as arr]))

(defn gemma-rmsnorm-values
  "Gemma RMSNorm over host values.

  Gemma stores the RMSNorm scale as an offset weight, so the multiplier is
  `(1 + weight)` after RMS normalization."
  ([xs weights] (gemma-rmsnorm-values xs weights 1.0e-6))
  ([xs weights eps]
   (when-not (= (count xs) (count weights))
     (throw (ex-info "RMSNorm input and weight lengths differ"
                     {:input-count (count xs)
                      :weight-count (count weights)})))
   (let [n (count xs)
         mean-square (/ (reduce + (map #(* (double %) (double %)) xs)) n)
         inv-rms (/ 1.0 #?(:clj (Math/sqrt (+ mean-square eps))
                           :cljs (js/Math.sqrt (+ mean-square eps))))]
     (mapv (fn [x w]
             (* (double x) inv-rms (+ 1.0 (double w))))
           xs
           weights))))

(defn values->num
  "Upload op output values to a num-clj backend as an NDArray."
  [backend values shape]
  (arr/from-vec backend values shape))

(defn rope-interleaved-values
  "Apply interleaved rotary position embedding to a value prefix.

  Values are interpreted as `[x0 y0 x1 y1 ...]`. This helper is intentionally
  prefix-friendly so verifiers can prove the Q/K lowering boundary before full
  head materialization lands."
  [values position rope-dim theta]
  (when-not (zero? (mod (count values) 2))
    (throw (ex-info "RoPE input count must be even"
                    {:value-count (count values)})))
  (when-not (pos? rope-dim)
    (throw (ex-info "RoPE dimension must be positive"
                    {:rope-dim rope-dim})))
  (when-not (pos? theta)
    (throw (ex-info "RoPE theta must be positive"
                    {:theta theta})))
  (let [pos (double position)
        dim (double rope-dim)]
    (vec
     (mapcat
      (fn [pair-index [x y]]
        (let [angle (/ pos #?(:clj (Math/pow theta (/ (* 2.0 pair-index) dim))
                              :cljs (js/Math.pow theta (/ (* 2.0 pair-index) dim))))
              c #?(:clj (Math/cos angle) :cljs (js/Math.cos angle))
              s #?(:clj (Math/sin angle) :cljs (js/Math.sin angle))
              xd (double x)
              yd (double y)]
          [(- (* xd c) (* yd s))
           (+ (* xd s) (* yd c))]))
      (range)
      (partition 2 values)))))

(defn dot-values [xs ys]
  (when-not (= (count xs) (count ys))
    (throw (ex-info "Dot inputs must have the same length"
                    {:x-count (count xs)
                     :y-count (count ys)})))
  (reduce + (map #(* (double %1) (double %2)) xs ys)))

(defn add-values
  "Elementwise residual add over host values."
  [xs ys]
  (when-not (= (count xs) (count ys))
    (throw (ex-info "Add inputs must have the same length"
                    {:x-count (count xs)
                     :y-count (count ys)})))
  (mapv #(+ (double %1) (double %2)) xs ys))

(defn silu-value [x]
  (let [xd (double x)]
    (/ xd (+ 1.0 #?(:clj (Math/exp (- xd))
                    :cljs (js/Math.exp (- xd)))))))

(defn gated-mlp-activation-values
  "Gemma gated MLP activation for matching gate/up projection prefixes."
  [gate-values up-values]
  (when-not (= (count gate-values) (count up-values))
    (throw (ex-info "Gate and up projection counts differ"
                    {:gate-count (count gate-values)
                     :up-count (count up-values)})))
  (mapv #(* (silu-value %1) (double %2)) gate-values up-values))

(defn single-token-attention-values
  "Single-token causal attention over one Q head and one matching KV head.

  With a single visible key, softmax has one entry with weight 1.0. The score
  is still returned because it proves the scaled QK boundary before multi-token
  GQA lands."
  [q-head k-head v-head]
  (when-not (= (count q-head) (count k-head))
    (throw (ex-info "Q and K head dimensions differ"
                    {:q-count (count q-head)
                     :k-count (count k-head)})))
  (let [head-dim (count q-head)
        score (/ (dot-values q-head k-head)
                 #?(:clj (Math/sqrt head-dim)
                    :cljs (js/Math.sqrt head-dim)))]
    {:score score
     :weights [1.0]
     :values (vec v-head)}))

(defn softmax-values [xs]
  (let [values (mapv double xs)
        max-value (reduce max values)
        exps (mapv #?(:clj #(Math/exp (- % max-value))
                      :cljs #(js/Math.exp (- % max-value)))
                   values)
        total (reduce + exps)]
    (mapv #(/ % total) exps)))

(defn causal-attention-values
  "Causal attention for one Q head over visible K/V heads."
  [q-head k-heads v-heads]
  (when-not (= (count k-heads) (count v-heads))
    (throw (ex-info "K/V token counts differ"
                    {:k-count (count k-heads)
                     :v-count (count v-heads)})))
  (doseq [k-head k-heads]
    (when-not (= (count q-head) (count k-head))
      (throw (ex-info "Q and K head dimensions differ"
                      {:q-count (count q-head)
                       :k-count (count k-head)}))))
  (let [head-dim (count q-head)
        scores (mapv #(/ (dot-values q-head %)
                         #?(:clj (Math/sqrt head-dim)
                            :cljs (js/Math.sqrt head-dim)))
                     k-heads)
        weights (softmax-values scores)
        values (mapv (fn [i]
                       (reduce +
                               (map #(* (double %1)
                                        (double (nth %2 i)))
                                    weights
                                    v-heads)))
                     (range head-dim))]
    {:scores scores
     :weights weights
     :values values}))
