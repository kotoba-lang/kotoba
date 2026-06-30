(ns kotodama.verify.gemma4-e4b-num-smoke
  "Real Gemma GGUF block -> CLJC GGUF decoder -> num-clj tensor smoke.

  This is still not full Gemma generation. It proves the next boundary after
  artifact inspection: quantized bytes from the real local model can become
  num-clj NDArrays, flow through RMSNorm, feed Q/K/V projections and RoPE,
  reach a single-token GQA attention boundary, evaluate a partial gated MLP
  path, and evaluate a tied-embedding output-logit probe with deterministic
  values. KOTODAMA_VERIFY_FULL_MLP=1 enables the heavier full first-block MLP
  projection contract used by the local-model maturity gate.
  KOTODAMA_VERIFY_FULL_VOCAB=1 streams the complete tied token embedding head
  and fixes greedy/top-k logits without materializing the 262144-wide vector."
  (:require [kotodama.inference.gemma :as gemma]
            [kotodama.inference.core :as inference-core]
            [kotodama.inference.ports :as inference-ports]
            [kotodama.inference.runtime :as inference-runtime]
            [kotodama.inference.gguf :as gguf]
            [kotodama.inference.ops :as ops]
            [kotodama.verify.gemma4-e4b-gguf :as verify-gguf]
            [num.array :as arr]
            [num.core :as num]
            [num.cpu :as cpu]
            [torch.core :as torch]
            [torch.model :as model]
            [torch.ports :as ports])
  (:import (java.io RandomAccessFile)))

(defn- approx= [a b]
  (< (Math/abs (- (double a) (double b))) 1.0e-6))

(defn- round6 [x]
  (/ (Math/round (* 1000000.0 x)) 1000000.0))

(defn- read-tensor-range [path tensor-data-start tensor offset n]
  (with-open [f (RandomAccessFile. path "r")]
    (.seek f (+ tensor-data-start (:offset tensor) offset))
    (let [bytes (byte-array n)]
      (.readFully f bytes)
      (vec bytes))))

(defn- read-tensor-range* [^RandomAccessFile f tensor-data-start tensor offset n]
  (.seek f (+ tensor-data-start (:offset tensor) offset))
  (let [bytes (byte-array n)]
    (.readFully f bytes)
    (vec bytes)))

(defn- read-tensor-range-bytes* [^RandomAccessFile f tensor-data-start tensor offset n]
  (.seek f (+ tensor-data-start (:offset tensor) offset))
  (let [bytes (byte-array n)]
    (.readFully f bytes)
    bytes))

(defn- u8-byte [^bytes bytes offset]
  (bit-and 0xff (aget bytes offset)))

(defn- i8-byte [^bytes bytes offset]
  (let [x (u8-byte bytes offset)]
    (if (> x 127) (- x 256) x)))

(defn- le-u16-bytes [^bytes bytes offset]
  (+ (u8-byte bytes offset)
     (bit-shift-left (u8-byte bytes (inc offset)) 8)))

(defn- q4-k-scale-min* [^ints scales j]
  (if (< j 4)
    {:scale (bit-and (aget scales j) 63)
     :min (bit-and (aget scales (+ j 4)) 63)}
    {:scale (bit-or (bit-and (aget scales (+ j 4)) 0x0f)
                    (bit-shift-left (bit-shift-right (aget scales (- j 4)) 6) 4))
     :min (bit-or (bit-shift-right (aget scales (+ j 4)) 4)
                  (bit-shift-left (bit-shift-right (aget scales j) 6) 4))}))

(defn- q4-k-block-dot [^bytes bytes block-offset input input-offset]
  (let [d (gguf/fp16->double (le-u16-bytes bytes block-offset))
        dmin (gguf/fp16->double (le-u16-bytes bytes (+ block-offset 2)))
        scales (int-array 12)]
    (dotimes [i 12]
      (aset scales i (u8-byte bytes (+ block-offset 4 i))))
    (loop [group 0
           is 0
           acc 0.0]
      (if (< group 4)
        (let [{s1 :scale m1 :min} (q4-k-scale-min* scales is)
              {s2 :scale m2 :min} (q4-k-scale-min* scales (inc is))
              d1 (* d s1)
              d2 (* d s2)
              min1 (* dmin m1)
              min2 (* dmin m2)
              base (* group 64)
              q-base (+ block-offset 16 (* group 32))
              acc* (loop [l 0
                          acc acc]
                     (if (< l 32)
                       (let [q (u8-byte bytes (+ q-base l))
                             v1 (- (* d1 (bit-and q 0x0f)) min1)
                             v2 (- (* d2 (bit-shift-right q 4)) min2)]
                         (recur (inc l)
                                (+ acc
                                   (* v1 (double (nth input (+ input-offset base l))))
                                   (* v2 (double (nth input (+ input-offset base l 32)))))))
                       acc))]
          (recur (inc group) (+ is 2) acc*))
        acc))))

(defn- q6-k-block-dot [^bytes bytes block-offset input input-offset]
  (let [d (gguf/fp16->double (le-u16-bytes bytes (+ block-offset 208)))]
    (loop [group 0
           acc 0.0]
      (if (< group 2)
        (let [base (* group 128)
              ql-base (+ block-offset (* group 64))
              qh-base (+ block-offset 128 (* group 32))
              acc* (loop [l 0
                          acc acc]
                     (if (< l 32)
                       (let [is (quot l 16)
                             ql0 (u8-byte bytes (+ ql-base l))
                             ql32 (u8-byte bytes (+ ql-base 32 l))
                             qh (u8-byte bytes (+ qh-base l))
                             q1 (- (bit-or (bit-and ql0 0x0f)
                                           (bit-shift-left (bit-and (bit-shift-right qh 0) 0x03) 4))
                                   32)
                             q2 (- (bit-or (bit-and ql32 0x0f)
                                           (bit-shift-left (bit-and (bit-shift-right qh 2) 0x03) 4))
                                   32)
                             q3 (- (bit-or (bit-shift-right ql0 4)
                                           (bit-shift-left (bit-and (bit-shift-right qh 4) 0x03) 4))
                                   32)
                             q4 (- (bit-or (bit-shift-right ql32 4)
                                           (bit-shift-left (bit-and (bit-shift-right qh 6) 0x03) 4))
                                   32)
                             s1 (i8-byte bytes (+ block-offset 192 is 0))
                             s2 (i8-byte bytes (+ block-offset 192 is 2))
                             s3 (i8-byte bytes (+ block-offset 192 is 4))
                             s4 (i8-byte bytes (+ block-offset 192 is 6))
                             v1 (* d s1 q1)
                             v2 (* d s2 q2)
                             v3 (* d s3 q3)
                             v4 (* d s4 q4)]
                         (recur (inc l)
                                (+ acc
                                   (* v1 (double (nth input (+ input-offset base l))))
                                   (* v2 (double (nth input (+ input-offset base l 32))))
                                   (* v3 (double (nth input (+ input-offset base l 64))))
                                   (* v4 (double (nth input (+ input-offset base l 96)))))))
                       acc))]
          (recur (inc group) acc*))
        acc))))

(defn- q6-k-block-dot-array [^bytes bytes block-offset ^doubles input input-offset]
  (let [d (gguf/fp16->double (le-u16-bytes bytes (+ block-offset 208)))]
    (loop [group 0
           acc 0.0]
      (if (< group 2)
        (let [base (* group 128)
              ql-base (+ block-offset (* group 64))
              qh-base (+ block-offset 128 (* group 32))
              acc* (loop [l 0
                          acc acc]
                     (if (< l 32)
                       (let [is (quot l 16)
                             ql0 (u8-byte bytes (+ ql-base l))
                             ql32 (u8-byte bytes (+ ql-base 32 l))
                             qh (u8-byte bytes (+ qh-base l))
                             q1 (- (bit-or (bit-and ql0 0x0f)
                                           (bit-shift-left (bit-and (bit-shift-right qh 0) 0x03) 4))
                                   32)
                             q2 (- (bit-or (bit-and ql32 0x0f)
                                           (bit-shift-left (bit-and (bit-shift-right qh 2) 0x03) 4))
                                   32)
                             q3 (- (bit-or (bit-shift-right ql0 4)
                                           (bit-shift-left (bit-and (bit-shift-right qh 4) 0x03) 4))
                                   32)
                             q4 (- (bit-or (bit-shift-right ql32 4)
                                           (bit-shift-left (bit-and (bit-shift-right qh 6) 0x03) 4))
                                   32)
                             s1 (i8-byte bytes (+ block-offset 192 is 0))
                             s2 (i8-byte bytes (+ block-offset 192 is 2))
                             s3 (i8-byte bytes (+ block-offset 192 is 4))
                             s4 (i8-byte bytes (+ block-offset 192 is 6))
                             v1 (* d s1 q1)
                             v2 (* d s2 q2)
                             v3 (* d s3 q3)
                             v4 (* d s4 q4)]
                         (recur (inc l)
                                (+ acc
                                   (* v1 (aget input (+ input-offset base l)))
                                   (* v2 (aget input (+ input-offset base l 32)))
                                   (* v3 (aget input (+ input-offset base l 64)))
                                   (* v4 (aget input (+ input-offset base l 96))))))
                       acc))]
          (recur (inc group) acc*))
        acc))))

(defn- le-u32 [^RandomAccessFile f]
  (long (+ (.readUnsignedByte f)
           (bit-shift-left (.readUnsignedByte f) 8)
           (bit-shift-left (.readUnsignedByte f) 16)
           (bit-shift-left (.readUnsignedByte f) 24))))

(defn- le-f32 [^RandomAccessFile f]
  (Float/intBitsToFloat (unchecked-int (le-u32 f))))

(defn- read-f32-values [path tensor-data-start tensor n]
  (with-open [f (RandomAccessFile. path "r")]
    (.seek f (+ tensor-data-start (:offset tensor)))
    (vec (repeatedly n #(double (le-f32 f))))))

(defn- require-summary! [tensor-name actual expected]
  (doseq [[k v] expected]
    (when-not (= v (get actual k))
      (throw (ex-info "Gemma num tensor summary mismatch"
                      {:tensor tensor-name
                       :key k
                       :expected v
                       :actual (get actual k)})))))

(defn- row-selection-summary [row-indices]
  (let [rows (vec row-indices)]
    (if (<= (count rows) 16)
      {:rows rows}
      {:row-range [(first rows) (last rows)]
       :row-count (count rows)})))

(defn- q4-num-summary [backend path tensor-data-start tensor]
  (let [values (gguf/q4-k-block->values
                (read-tensor-range path tensor-data-start tensor 0 gguf/q4-k-block-bytes))
        block (gguf/values->num backend values [16 16])]
    {:block 0
     :shape (:shape block)
     :value-count (arr/nelems (:shape block))
     :sample (mapv round6 (take 16 (arr/->vec block)))
     :sum (round6 (num/sum block))
     :min (round6 (num/amin block))
     :max (round6 (num/amax block))}))

(defn- q6-num-summary [backend path tensor-data-start tensor]
  (let [values (gguf/q6-k-block->values
                (read-tensor-range path tensor-data-start tensor 0 gguf/q6-k-block-bytes))
        block (gguf/values->num backend values [16 16])]
    {:block 0
     :shape (:shape block)
     :value-count (arr/nelems (:shape block))
     :sample (mapv round6 (take 16 (arr/->vec block)))
     :sum (round6 (num/sum block))
     :min (round6 (num/amin block))
     :max (round6 (num/amax block))}))

(defn- token-embedding-summary [backend path tensor-data-start tensor token-id hidden-size]
  (let [offset (gguf/q6-k-row-byte-offset token-id hidden-size)
        n-bytes (gguf/q6-k-row-byte-count hidden-size)
        values (gguf/q6-k-blocks->values
                (read-tensor-range path tensor-data-start tensor offset n-bytes))
        embedding (gguf/values->num backend values [hidden-size])]
    {:token-id token-id
     :shape (:shape embedding)
     :value-count (arr/nelems (:shape embedding))
     :sample (mapv round6 (take 16 (arr/->vec embedding)))
     :sum (round6 (num/sum embedding))
     :min (round6 (num/amin embedding))
     :max (round6 (num/amax embedding))}))

(defn- token-embedding-values [path tensor-data-start tensor token-id hidden-size]
  (let [offset (gguf/q6-k-row-byte-offset token-id hidden-size)
        n-bytes (gguf/q6-k-row-byte-count hidden-size)]
    (gguf/q6-k-blocks->values
     (read-tensor-range path tensor-data-start tensor offset n-bytes))))

(defn- rmsnorm-summary [backend values weights]
  (let [normed (ops/gemma-rmsnorm-values values weights)
        tensor (ops/values->num backend normed [(count normed)])]
    {:shape (:shape tensor)
     :value-count (arr/nelems (:shape tensor))
     :sample (mapv round6 (take 16 (arr/->vec tensor)))
     :sum (round6 (num/sum tensor))
     :min (round6 (num/amin tensor))
     :max (round6 (num/amax tensor))}))

(defn- q4-row-values [path tensor-data-start tensor row-index row-width]
  (let [offset (gguf/q4-k-row-byte-offset row-index row-width)
        n-bytes (gguf/q4-k-row-byte-count row-width)]
    (gguf/q4-k-blocks->values
     (read-tensor-range path tensor-data-start tensor offset n-bytes))))

(defn- q4-row-values* [^RandomAccessFile f tensor-data-start tensor row-index row-width]
  (let [offset (gguf/q4-k-row-byte-offset row-index row-width)
        n-bytes (gguf/q4-k-row-byte-count row-width)]
    (gguf/q4-k-blocks->values
     (read-tensor-range* f tensor-data-start tensor offset n-bytes))))

(defn- q4-row-dot* [^RandomAccessFile f tensor-data-start tensor row-index row-width input]
  (let [offset (gguf/q4-k-row-byte-offset row-index row-width)
        n-bytes (gguf/q4-k-row-byte-count row-width)
        row-bytes (read-tensor-range-bytes* f tensor-data-start tensor offset n-bytes)
        block-count (/ row-width gguf/qk-k)]
    (loop [block 0
           acc 0.0]
      (if (< block block-count)
        (recur (inc block)
               (+ acc
                  (q4-k-block-dot row-bytes
                                  (* block gguf/q4-k-block-bytes)
                                  input
                                  (* block gguf/qk-k))))
        acc))))

(defn- q4-projection-summary [backend path tensor-data-start tensor input-values row-indices row-width]
  (let [input (ops/values->num backend input-values [row-width])
        values (mapv (fn [row-index]
                       (let [row-values (q4-row-values path tensor-data-start tensor row-index row-width)
                             row (ops/values->num backend row-values [row-width])]
                         (num/dot row input)))
                     row-indices)
        projected (ops/values->num backend values [(count values)])]
    (merge
     (row-selection-summary row-indices)
     {:shape (:shape projected)
      :value-count (arr/nelems (:shape projected))
      :sample (mapv round6 (take 16 (arr/->vec projected)))
      :sum (round6 (num/sum projected))
      :min (round6 (num/amin projected))
      :max (round6 (num/amax projected))
      :values values})))

(defn- q4-projection-summary-direct [backend path tensor-data-start tensor input-values row-indices row-width]
  (let [input (vec input-values)]
    (with-open [f (RandomAccessFile. path "r")]
      (let [values (mapv (fn [row-index]
                           (q4-row-dot* f tensor-data-start tensor row-index row-width input))
                         row-indices)
            projected (ops/values->num backend values [(count values)])]
        (merge
         (row-selection-summary row-indices)
         {:shape (:shape projected)
          :value-count (arr/nelems (:shape projected))
          :sample (mapv round6 (take 16 (arr/->vec projected)))
          :sum (round6 (num/sum projected))
          :min (round6 (num/amin projected))
          :max (round6 (num/amax projected))
          :values values})))))

(defn- q6-row-values [path tensor-data-start tensor row-index row-width]
  (let [offset (gguf/q6-k-row-byte-offset row-index row-width)
        n-bytes (gguf/q6-k-row-byte-count row-width)]
    (gguf/q6-k-blocks->values
     (read-tensor-range path tensor-data-start tensor offset n-bytes))))

(defn- q6-row-values* [^RandomAccessFile f tensor-data-start tensor row-index row-width]
  (let [offset (gguf/q6-k-row-byte-offset row-index row-width)
        n-bytes (gguf/q6-k-row-byte-count row-width)]
    (gguf/q6-k-blocks->values
     (read-tensor-range* f tensor-data-start tensor offset n-bytes))))

(defn- q6-row-dot* [^RandomAccessFile f tensor-data-start tensor row-index row-width input]
  (let [offset (gguf/q6-k-row-byte-offset row-index row-width)
        n-bytes (gguf/q6-k-row-byte-count row-width)
        row-bytes (read-tensor-range-bytes* f tensor-data-start tensor offset n-bytes)
        block-count (/ row-width gguf/qk-k)]
    (loop [block 0
           acc 0.0]
      (if (< block block-count)
        (recur (inc block)
               (+ acc
                  (q6-k-block-dot row-bytes
                                  (* block gguf/q6-k-block-bytes)
                                  input
                                  (* block gguf/qk-k))))
        acc))))

(defn- q6-row-dot-array* [^RandomAccessFile f tensor-data-start tensor row-index row-width ^doubles input]
  (let [offset (gguf/q6-k-row-byte-offset row-index row-width)
        n-bytes (gguf/q6-k-row-byte-count row-width)
        row-bytes (read-tensor-range-bytes* f tensor-data-start tensor offset n-bytes)
        block-count (/ row-width gguf/qk-k)]
    (loop [block 0
           acc 0.0]
      (if (< block block-count)
        (recur (inc block)
               (+ acc
                  (q6-k-block-dot-array row-bytes
                                        (* block gguf/q6-k-block-bytes)
                                        input
                                        (* block gguf/qk-k))))
        acc))))

(defn- q6-row-dot-array-bytes [^bytes row-bytes row-width ^doubles input]
  (let [block-count (/ row-width gguf/qk-k)]
    (loop [block 0
           acc 0.0]
      (if (< block block-count)
        (recur (inc block)
               (+ acc
                  (q6-k-block-dot-array row-bytes
                                        (* block gguf/q6-k-block-bytes)
                                        input
                                        (* block gguf/qk-k))))
        acc))))

(defn- q6-projection-summary [backend path tensor-data-start tensor input-values row-indices row-width]
  (let [input (ops/values->num backend input-values [row-width])
        values (mapv (fn [row-index]
                       (let [row-values (q6-row-values path tensor-data-start tensor row-index row-width)
                             row (ops/values->num backend row-values [row-width])]
                         (num/dot row input)))
                     row-indices)
        projected (ops/values->num backend values [(count values)])]
    (merge
     (row-selection-summary row-indices)
     {:shape (:shape projected)
      :value-count (arr/nelems (:shape projected))
      :sample (mapv round6 (take 16 (arr/->vec projected)))
      :sum (round6 (num/sum projected))
      :min (round6 (num/amin projected))
      :max (round6 (num/amax projected))
      :values values})))

(defn- q6-projection-summary-direct [backend path tensor-data-start tensor input-values row-indices row-width]
  (let [input (vec input-values)]
    (with-open [f (RandomAccessFile. path "r")]
      (let [values (mapv (fn [row-index]
                           (q6-row-dot* f tensor-data-start tensor row-index row-width input))
                         row-indices)
            projected (ops/values->num backend values [(count values)])]
        (merge
         (row-selection-summary row-indices)
         {:shape (:shape projected)
          :value-count (arr/nelems (:shape projected))
          :sample (mapv round6 (take 16 (arr/->vec projected)))
          :sum (round6 (num/sum projected))
          :min (round6 (num/amin projected))
          :max (round6 (num/amax projected))
          :values values})))))

(defn- q6-logits-summary [backend path tensor-data-start tensor input-values token-ids hidden-size]
  (let [input (ops/values->num backend input-values [hidden-size])
        values (mapv (fn [token-id]
                       (let [row-values (q6-row-values path tensor-data-start tensor token-id hidden-size)
                             row (ops/values->num backend row-values [hidden-size])]
                         (num/dot row input)))
                     token-ids)
        logits (ops/values->num backend values [(count values)])
        greedy-index (first (apply max-key second (map-indexed vector values)))]
    {:token-ids (vec token-ids)
     :shape (:shape logits)
     :value-count (arr/nelems (:shape logits))
     :sample (mapv round6 (arr/->vec logits))
     :sum (round6 (num/sum logits))
     :min (round6 (num/amin logits))
     :max (round6 (num/amax logits))
     :greedy-token-id (nth (vec token-ids) greedy-index)
     :greedy-logit (round6 (nth values greedy-index))
     :values values}))

(defn- q6-full-vocab-logits-summary [path tensor-data-start tensor input-values hidden-size vocab-size k]
  (let [input (double-array (map double input-values))
        sample-count 16
        row-bytes (byte-array (gguf/q6-k-row-byte-count hidden-size))
        top-token-ids (long-array k -1)
        top-logits (double-array k Double/NEGATIVE_INFINITY)]
    (with-open [f (RandomAccessFile. path "r")]
      (.seek f (+ tensor-data-start (:offset tensor)))
      (loop [token-id 0
             sample []
             sum 0.0
             min-logit Double/POSITIVE_INFINITY
             min-token-id nil
             max-logit Double/NEGATIVE_INFINITY
             max-token-id nil]
        (if (< token-id vocab-size)
          (do
            (.readFully f row-bytes)
            (let [logit (q6-row-dot-array-bytes row-bytes hidden-size input)
                sample* (if (< token-id sample-count)
                          (conj sample (round6 logit))
                          sample)
                min-top-index (loop [i 1
                                      min-index 0
                                      min-value (aget top-logits 0)]
                                 (if (< i k)
                                   (let [value (aget top-logits i)]
                                     (if (< value min-value)
                                       (recur (inc i) i value)
                                       (recur (inc i) min-index min-value)))
                                   min-index))
                _ (when (> logit (aget top-logits min-top-index))
                    (aset top-token-ids min-top-index token-id)
                    (aset top-logits min-top-index logit))
                sum* (+ sum logit)
                [min-logit* min-token-id*] (if (< logit min-logit)
                                             [logit token-id]
                                             [min-logit min-token-id])
                [max-logit* max-token-id*] (if (> logit max-logit)
                                             [logit token-id]
                                             [max-logit max-token-id])]
              (recur (inc token-id)
                     sample*
                     sum*
                     min-logit*
                     min-token-id*
                     max-logit*
                     max-token-id*)))
          {:token-id-range [0 (dec vocab-size)]
           :value-count vocab-size
           :sample sample
           :sum (round6 sum)
           :min (round6 min-logit)
           :min-token-id min-token-id
           :max (round6 max-logit)
           :max-token-id max-token-id
           :greedy-token-id max-token-id
           :greedy-logit (round6 max-logit)
           :top-k (mapv (fn [i]
                          {:token-id (aget top-token-ids i)
                           :logit (round6 (aget top-logits i))})
                        (sort-by (fn [i] (- (aget top-logits i))) (range k)))})))))

(defn- rope-summary [backend projection position rope-dim theta]
  (let [values (ops/rope-interleaved-values (:values projection) position rope-dim theta)
        tensor (ops/values->num backend values [(count values)])]
    {:position position
     :rope-dim rope-dim
     :theta theta
     :shape (:shape tensor)
     :value-count (arr/nelems (:shape tensor))
     :sample (mapv round6 (arr/->vec tensor))
     :sum (round6 (num/sum tensor))
     :min (round6 (num/amin tensor))
     :max (round6 (num/amax tensor))}))

(defn- summarize-values [backend values extra]
  (let [tensor (ops/values->num backend values [(count values)])]
    (merge extra
           {:shape (:shape tensor)
            :value-count (arr/nelems (:shape tensor))
            :sample (mapv round6 (take 16 (arr/->vec tensor)))
            :sum (round6 (num/sum tensor))
            :min (round6 (num/amin tensor))
            :max (round6 (num/amax tensor))})))

(defn- attention-summary [backend q-head k-head v-head extra]
  (let [{:keys [score weights values]} (ops/single-token-attention-values q-head k-head v-head)]
    (assoc (summarize-values backend values extra)
           :score (round6 score)
           :weights (mapv round6 weights))))

(defn- rope-heads-values [values head-dim position rope-dim theta]
  (->> values
       (partition head-dim)
       (mapcat #(ops/rope-interleaved-values (vec %) position rope-dim theta))
       vec))

(defn- all-head-single-token-attention [q-values k-values v-values q-head-count kv-head-count head-dim]
  (let [q-per-kv (/ q-head-count kv-head-count)
        scores (transient [])
        kv-heads (transient [])
        out-values (transient [])]
    (doseq [q-head-index (range q-head-count)
            :let [kv-head-index (quot q-head-index q-per-kv)
                  q-head (subvec q-values (* q-head-index head-dim) (* (inc q-head-index) head-dim))
                  k-head (subvec k-values (* kv-head-index head-dim) (* (inc kv-head-index) head-dim))
                  v-head (subvec v-values (* kv-head-index head-dim) (* (inc kv-head-index) head-dim))
                  {score :score attention-values :values} (ops/single-token-attention-values q-head k-head v-head)]]
      (conj! scores score)
      (conj! kv-heads kv-head-index)
      (doseq [value attention-values]
        (conj! out-values value)))
    {:scores (persistent! scores)
     :kv-heads (persistent! kv-heads)
     :values (persistent! out-values)}))

(defn- slice-head [values head-index head-dim]
  (subvec values (* head-index head-dim) (* (inc head-index) head-dim)))

(defn- all-head-causal-attention [q-values k-values-by-token v-values-by-token q-head-count kv-head-count head-dim]
  (let [q-per-kv (/ q-head-count kv-head-count)
        scores (transient [])
        weights (transient [])
        kv-heads (transient [])
        out-values (transient [])]
    (doseq [q-head-index (range q-head-count)
            :let [kv-head-index (quot q-head-index q-per-kv)
                  q-head (slice-head q-values q-head-index head-dim)
                  k-heads (mapv #(slice-head % kv-head-index head-dim) k-values-by-token)
                  v-heads (mapv #(slice-head % kv-head-index head-dim) v-values-by-token)
                  {head-scores :scores head-weights :weights attention-values :values}
                  (ops/causal-attention-values q-head k-heads v-heads)]]
      (conj! scores head-scores)
      (conj! weights head-weights)
      (conj! kv-heads kv-head-index)
      (doseq [value attention-values]
        (conj! out-values value)))
    {:scores (persistent! scores)
     :weights (persistent! weights)
     :kv-heads (persistent! kv-heads)
     :values (persistent! out-values)}))

(defn- all-head-attention-summary [backend attention extra]
  (assoc (summarize-values backend (:values attention) extra)
         :score-sample (mapv round6 (:scores attention))
         :score-sum (round6 (reduce + (:scores attention)))
         :score-min (round6 (reduce min (:scores attention)))
         :score-max (round6 (reduce max (:scores attention)))
         :weights [1.0]
         :kv-heads (:kv-heads attention)))

(defn- all-head-causal-attention-summary [backend attention extra]
  (assoc (summarize-values backend (:values attention) extra)
         :score-sample (mapv #(mapv round6 %) (:scores attention))
         :weight-sample (mapv #(mapv round6 %) (:weights attention))
         :score-sum (round6 (reduce + (mapcat identity (:scores attention))))
         :score-min (round6 (reduce min (mapcat identity (:scores attention))))
         :score-max (round6 (reduce max (mapcat identity (:scores attention))))
         :kv-heads (:kv-heads attention)))

(defn- single-head-attention-vector [values total-width offset]
  (let [out (vec (repeat total-width 0.0))
        value-count (count values)]
    (when (> (+ offset value-count) total-width)
      (throw (ex-info "Attention head slice exceeds output width"
                      {:offset offset
                       :value-count value-count
                       :total-width total-width})))
    (into (subvec out 0 offset)
          (concat values (subvec out (+ offset value-count))))))

(defn- prefix-vector [values total-width]
  (let [value-count (count values)]
    (when (> value-count total-width)
      (throw (ex-info "Prefix exceeds vector width"
                      {:value-count value-count
                       :total-width total-width})))
    (into (vec values) (repeat (- total-width value-count) 0.0))))

(defn- parse-env-long [name default-value]
  (if-let [value (System/getenv name)]
    (Long/parseLong value)
    default-value))

(defn- layer-tensor-name [layer-index suffix]
  (str "blk." layer-index "." suffix ".weight"))

(defn- block-key-layer-index [block-key]
  (Long/parseLong (subs (namespace block-key) 4)))

(defn- layer-tensor-names [layer-index]
  (mapv #(layer-tensor-name layer-index %)
        ["attn_norm"
         "attn_q"
         "attn_k"
         "attn_v"
         "attn_output"
         "ffn_norm"
         "ffn_gate"
         "ffn_up"
         "ffn_down"]))

(defn- compose-gemma-block
  "Compose one single-token Gemma block from decoded GGUF rows.

  This is intentionally host-value oriented for verifier determinism. It proves
  the layer contract before the same stages are moved behind a reusable
  torch-clj -> num-clj runner."
  [backend path tensor-data-start tensors expected layer-index input-values position]
  (let [hidden-size (:gemma4/embedding-length expected)
        ffn-size (:gemma4/feed-forward-length expected)
        q-name (layer-tensor-name layer-index "attn_q")
        k-name (layer-tensor-name layer-index "attn_k")
        v-name (layer-tensor-name layer-index "attn_v")
        out-name (layer-tensor-name layer-index "attn_output")
        attn-norm-name (layer-tensor-name layer-index "attn_norm")
        ffn-norm-name (layer-tensor-name layer-index "ffn_norm")
        gate-name (layer-tensor-name layer-index "ffn_gate")
        up-name (layer-tensor-name layer-index "ffn_up")
        down-name (layer-tensor-name layer-index "ffn_down")
        attn-norm-weights (read-f32-values path tensor-data-start (get tensors attn-norm-name) hidden-size)
        ffn-norm-weights (read-f32-values path tensor-data-start (get tensors ffn-norm-name) hidden-size)
        output-norm-weights (read-f32-values path tensor-data-start (get tensors "output_norm.weight") hidden-size)
        attn-norm-values (ops/gemma-rmsnorm-values input-values attn-norm-weights)
        q-width (second (:shape (get tensors q-name)))
        k-width (second (:shape (get tensors k-name)))
        v-width (second (:shape (get tensors v-name)))
        q-head-dim (/ q-width (:gemma4/attention-head-count expected))
        kv-head-dim (/ k-width (:gemma4/attention-head-count-kv expected))
        _ (when-not (= kv-head-dim (/ v-width (:gemma4/attention-head-count-kv expected)))
            (throw (ex-info "Gemma K/V derived head dimensions differ"
                            {:layer layer-index
                             :k-head-dim kv-head-dim
                             :v-head-dim (/ v-width (:gemma4/attention-head-count-kv expected))})))
        _ (when-not (= q-head-dim kv-head-dim)
            (throw (ex-info "Gemma Q/K/V derived head dimensions differ"
                            {:layer layer-index
                             :q-head-dim q-head-dim
                             :kv-head-dim kv-head-dim})))
        q-all (q4-projection-summary-direct backend path tensor-data-start (get tensors q-name)
                                            attn-norm-values (range q-width) hidden-size)
        k-all (q4-projection-summary-direct backend path tensor-data-start (get tensors k-name)
                                            attn-norm-values (range k-width) hidden-size)
        v-all (q6-projection-summary-direct backend path tensor-data-start (get tensors v-name)
                                            attn-norm-values (range v-width) hidden-size)
        q-rope-values (rope-heads-values (:values q-all)
                                         q-head-dim
                                         position
                                         (:gemma4/rope-dimension-count expected)
                                         (:gemma4/rope-freq-base expected))
        k-rope-values (rope-heads-values (:values k-all)
                                         kv-head-dim
                                         position
                                         (:gemma4/rope-dimension-count expected)
                                         (:gemma4/rope-freq-base expected))
        attention (all-head-single-token-attention q-rope-values
                                                   k-rope-values
                                                   (:values v-all)
                                                   (:gemma4/attention-head-count expected)
                                                   (:gemma4/attention-head-count-kv expected)
                                                   q-head-dim)
        attention-summary (all-head-attention-summary backend
                                                      attention
                                                      {:layer layer-index
                                                       :position position
                                                       :q-head-range [0 (dec (:gemma4/attention-head-count expected))]
                                                       :kv-head-range [0 (dec (:gemma4/attention-head-count-kv expected))]
                                                       :head-dim q-head-dim})
        attention-output (q4-projection-summary-direct backend path tensor-data-start (get tensors out-name)
                                                       (:values attention)
                                                       (range hidden-size)
                                                       q-width)
        attention-residual-values (ops/add-values input-values (:values attention-output))
        attention-residual (summarize-values backend attention-residual-values
                                             {:token-id (:tokenizer/bos-token-id expected)
                                              :layer layer-index
                                              :stage :attention-residual})
        ffn-norm-values (ops/gemma-rmsnorm-values attention-residual-values ffn-norm-weights)
        ffn-norm (summarize-values backend ffn-norm-values
                                   {:token-id (:tokenizer/bos-token-id expected)
                                    :layer layer-index
                                    :stage :ffn-norm})
        gate (q4-projection-summary-direct backend path tensor-data-start (get tensors gate-name)
                                           ffn-norm-values
                                           (range ffn-size)
                                           hidden-size)
        up (q4-projection-summary-direct backend path tensor-data-start (get tensors up-name)
                                         ffn-norm-values
                                         (range ffn-size)
                                         hidden-size)
        activation-values (ops/gated-mlp-activation-values (:values gate) (:values up))
        activation (summarize-values backend activation-values
                                     {:token-id (:tokenizer/bos-token-id expected)
                                      :layer layer-index
                                      :stage :ffn-activation
                                      :row-range [0 (dec ffn-size)]
                                      :row-count ffn-size})
        down (q6-projection-summary-direct backend path tensor-data-start (get tensors down-name)
                                           activation-values
                                           (range hidden-size)
                                           ffn-size)
        output-values (ops/add-values attention-residual-values (:values down))
        output (summarize-values backend output-values
                                 {:token-id (:tokenizer/bos-token-id expected)
                                  :layer layer-index
                                  :stage :block-output})
        output-norm-values (ops/gemma-rmsnorm-values output-values output-norm-weights)
        output-norm (summarize-values backend output-norm-values
                                      {:token-id (:tokenizer/bos-token-id expected)
                                       :layer layer-index
                                       :stage :output-norm-after-block})
        logits (q6-logits-summary backend path tensor-data-start (get tensors "token_embd.weight")
                                  output-norm-values
                                  [1 2 3 4]
                                  hidden-size)]
    {:values output-values
     :summary {:attention attention-summary
               :attention-output (dissoc attention-output :values)
               :attention-residual attention-residual
               :ffn-norm ffn-norm
               :ffn-gate (dissoc gate :values)
               :ffn-up (dissoc up :values)
               :ffn-activation activation
               :ffn-down (dissoc down :values)
	               :block-output output
	               :output-norm output-norm
	               :logits (dissoc logits :values)}}))

(defn- gemma-block-subgraph [expected block-count]
  (let [layers (:torch/layers (gemma/gemma4-e4b-graph expected))]
    (apply model/sequential (subvec layers 1 (inc block-count)))))

(defn- real-gemma-block-backend [backend path tensor-data-start tensors expected]
  (reify ports/IBackend
    (forward [_ graph input-values]
      (loop [values (vec input-values)
             blocks {}
             layers (:torch/layers graph)]
        (if-not (seq layers)
          {:values values
           :blocks blocks}
          (let [layer (first layers)
                ltype (model/layer-type layer)
                args (model/layer-args layer)]
            (case ltype
              :gemma4-block
              (let [layer-index (:layer-index args)
                    {output-values :values summary :summary}
                    (compose-gemma-block backend
                                         path
                                         tensor-data-start
                                         tensors
                                         expected
                                         layer-index
                                         values
                                         1)
                    block-key (keyword (str "blk." layer-index)
                                       (str "block" layer-index "_full"))]
                (recur output-values
                       (assoc blocks block-key summary)
                       (rest layers)))

              (throw (ex-info "unsupported real Gemma torch block layer"
                              {:torch/layer-type ltype
                               :torch/layer layer})))))))))

(defn- tensor-index-for-layers [path expected full-layer-count]
  (let [wanted (into (conj (set (keys (:gguf/required-tensors expected)))
                           "blk.0.attn_norm.weight"
                           "blk.0.ffn_norm.weight"
                           "blk.0.ffn_gate.weight"
                           "blk.0.ffn_up.weight"
                           "blk.0.ffn_down.weight")
                     (mapcat layer-tensor-names (range 1 full-layer-count)))]
    (verify-gguf/read-gguf-tensor-index path wanted)))

(defn- torch-block-num-summary [full-layer-count torch-real-block-run]
  (let [last-block-key (keyword (str "blk." (dec full-layer-count))
                                (str "block" (dec full-layer-count) "_full"))]
    {:block-count (count (:blocks torch-real-block-run))
     :block-keys (vec (keys (:blocks torch-real-block-run)))
     :last-block-key last-block-key
     :last-block-logits (get-in torch-real-block-run
                                [:blocks last-block-key :logits])}))

(defn real-gemma-runtime
  "Verification-only IModelRuntime for real local Gemma GGUF forward.

  This intentionally lives in verify code until the real host runtime API is
  ready. It proves `core/forward` can cross the IModelRuntime port and execute
  indexed `:gemma4-block` layers through `torch/run` on the real GGUF artifact."
  ([] (real-gemma-runtime {}))
  ([{:keys [model path full-layer-count]
     :or {model verify-gguf/default-model
          full-layer-count 2}}]
   (let [expected gemma/gemma4-e4b-expected
         path* (or path (verify-gguf/ollama-gguf-path model))
         backend (cpu/cpu-backend)
         sessions (atom {})]
     (inference-ports/fn-runtime
      {:probe (fn []
                {:kotodama/backends [:native]
                 :kotodama/compute-backends [:num/cpu]
                 :kotodama/model-family :gemma4
                 :kotodama/forward [:real-gguf :torch-run :gemma4-block]})
       :load (fn [runtime-spec]
               (let [tensor-index (tensor-index-for-layers path* expected full-layer-count)
                     session {:kotodama/session-id (str "gemma4-real-" (count @sessions))
                              :kotodama/model model
                              :kotodama/runtime (:kotodama/runtime runtime-spec)
                              :kotodama/spec runtime-spec
                              :kotodama/artifact-path path*
                              :kotodama/full-layer-count full-layer-count
                              :kotodama/backend :native
                              :kotodama/compute-backend :num/cpu
                              :kotodama/forward-cache (atom {})
                              :gguf/tensor-index tensor-index}]
                 (swap! sessions assoc (:kotodama/session-id session) session)
                 session))
       :generate (fn [_ _ _]
                   (throw (ex-info "real Gemma verify runtime implements forward only"
                                   {:kotodama/model model})))
       :forward (fn [session token-ids options]
                  (let [layer-count (long (:kotodama/full-layer-count options
                                                                       (:kotodama/full-layer-count session)))
                        token-id (first token-ids)
                        tensor-index (:gguf/tensor-index session)
                        tensors (:gguf/tensors tensor-index)
                        cache-key {:token-ids (vec token-ids)
                                   :layer-count layer-count}
                        cache (:kotodama/forward-cache session)
                        cached (get @cache cache-key)
                        torch-run (or cached
                                      (let [token-values (token-embedding-values path*
                                                                                 (:gguf/tensor-data-start tensor-index)
                                                                                 (get tensors "token_embd.weight")
                                                                                 token-id
                                                                                 (:gemma4/embedding-length expected))
                                            run (torch/run (real-gemma-block-backend backend
                                                                                    path*
                                                                                    (:gguf/tensor-data-start tensor-index)
                                                                                    tensors
                                                                                    expected)
                                                           (gemma-block-subgraph expected layer-count)
                                                           token-values)]
                                        (swap! cache assoc cache-key run)
                                        run))
                        torch-summary (torch-block-num-summary layer-count torch-run)]
                    {:kotodama/session-id (:kotodama/session-id session)
                     :kotodama/input-ids (vec token-ids)
                     :kotodama/forward :real-gguf-torch-run
                     :kotodama/cache-hit? (boolean cached)
                     :gguf/torch-block-num torch-summary
                     :gguf/torch-run (when (:kotodama/include-blocks? options) torch-run)
                     :kotodama/logits (get-in torch-summary [:last-block-logits :sample])}))
       :dispose (fn [session]
                  (swap! sessions dissoc (:kotodama/session-id session))
                  {:kotodama/disposed? true
                   :kotodama/session-id (:kotodama/session-id session)})}))))

(defn -main [& _]
  (let [model (or (System/getenv "KOTODAMA_VERIFY_MODEL") verify-gguf/default-model)
        path (or (System/getenv "KOTODAMA_VERIFY_GGUF_PATH")
                 (verify-gguf/ollama-gguf-path model))
        expected gemma/gemma4-e4b-expected
        full-mlp? (= "1" (System/getenv "KOTODAMA_VERIFY_FULL_MLP"))
        full-vocab? (= "1" (System/getenv "KOTODAMA_VERIFY_FULL_VOCAB"))
        full-layer-count (parse-env-long "KOTODAMA_VERIFY_FULL_LAYERS" (if full-mlp? 1 0))
        wanted (into (conj (set (keys (:gguf/required-tensors expected)))
                           "blk.0.attn_norm.weight"
                           "blk.0.ffn_norm.weight"
                           "blk.0.ffn_gate.weight"
                           "blk.0.ffn_up.weight"
                           "blk.0.ffn_down.weight")
                     (mapcat layer-tensor-names (range 1 full-layer-count)))
        tensor-index (verify-gguf/read-gguf-tensor-index path wanted)
        tensors (:gguf/tensors tensor-index)
        backend (cpu/cpu-backend)
        q4-actual (into {}
                        (for [[name expected-sample] (:gguf/q4-k-samples expected)
                              :let [actual (q4-num-summary backend path
                                                           (:gguf/tensor-data-start tensor-index)
                                                           (get tensors name))]]
                          (do
                            (require-summary! name
                                              (dissoc actual :shape)
                                              expected-sample)
                            [name actual])))
        q6-actual (into {}
                        (for [[name expected-sample] (:gguf/q6-k-samples expected)
                              :let [actual (q6-num-summary backend path
                                                           (:gguf/tensor-data-start tensor-index)
                                                           (get tensors name))]]
                          (do
                            (require-summary! name
                                              (dissoc actual :shape)
                                              expected-sample)
                            [name actual])))
        token-embedding (token-embedding-summary backend path
                                                 (:gguf/tensor-data-start tensor-index)
                                                 (get tensors "token_embd.weight")
                                                 (:tokenizer/bos-token-id expected)
                                                 (:gemma4/embedding-length expected))
        token-values (token-embedding-values path
                                             (:gguf/tensor-data-start tensor-index)
                                             (get tensors "token_embd.weight")
                                             (:tokenizer/bos-token-id expected)
                                             (:gemma4/embedding-length expected))
        second-token-id (:tokenizer/eos-token-id expected)
        second-token-values (token-embedding-values path
                                                    (:gguf/tensor-data-start tensor-index)
                                                    (get tensors "token_embd.weight")
                                                    second-token-id
                                                    (:gemma4/embedding-length expected))
        attn-norm-weights (read-f32-values path
                                           (:gguf/tensor-data-start tensor-index)
                                           (get tensors "blk.0.attn_norm.weight")
                                           (:gemma4/embedding-length expected))
        ffn-norm-weights (read-f32-values path
                                          (:gguf/tensor-data-start tensor-index)
                                          (get tensors "blk.0.ffn_norm.weight")
                                          (:gemma4/embedding-length expected))
        output-norm-weights (read-f32-values path
                                             (:gguf/tensor-data-start tensor-index)
                                             (get tensors "output_norm.weight")
                                             (:gemma4/embedding-length expected))
        rmsnorm-values (ops/gemma-rmsnorm-values token-values attn-norm-weights)
        second-rmsnorm-values (ops/gemma-rmsnorm-values second-token-values attn-norm-weights)
        ffn-norm-values (ops/gemma-rmsnorm-values token-values ffn-norm-weights)
        output-norm-values (ops/gemma-rmsnorm-values token-values output-norm-weights)
        rmsnorm (rmsnorm-summary backend token-values attn-norm-weights)
        ffn-rmsnorm (rmsnorm-summary backend token-values ffn-norm-weights)
        output-rmsnorm (rmsnorm-summary backend token-values output-norm-weights)
        attn-q (q4-projection-summary backend path
                                      (:gguf/tensor-data-start tensor-index)
                                      (get tensors "blk.0.attn_q.weight")
                                      rmsnorm-values
                                      [0 1 2 3]
                                      (:gemma4/embedding-length expected))
        attn-k (q4-projection-summary backend path
                                      (:gguf/tensor-data-start tensor-index)
                                      (get tensors "blk.0.attn_k.weight")
                                      rmsnorm-values
                                      [0 1 2 3]
                                      (:gemma4/embedding-length expected))
        attn-v (q6-projection-summary backend path
                                      (:gguf/tensor-data-start tensor-index)
                                      (get tensors "blk.0.attn_v.weight")
                                      rmsnorm-values
                                      [0 1 2 3]
                                      (:gemma4/embedding-length expected))
        projections {:blk.0/attn_q attn-q
                     :blk.0/attn_k attn-k
                     :blk.0/attn_v attn-v}
        rope {:blk.0/attn_q (rope-summary backend attn-q 1
                                           (:gemma4/rope-dimension-count expected)
                                           (:gemma4/rope-freq-base expected))
              :blk.0/attn_k (rope-summary backend attn-k 1
                                           (:gemma4/rope-dimension-count expected)
                                           (:gemma4/rope-freq-base expected))}
        q-head-dim (/ (second (get-in expected [:gguf/required-tensors "blk.0.attn_q.weight" :shape]))
                      (:gemma4/attention-head-count expected))
        kv-head-dim (/ (second (get-in expected [:gguf/required-tensors "blk.0.attn_k.weight" :shape]))
                       (:gemma4/attention-head-count-kv expected))
        _ (when-not (= q-head-dim kv-head-dim)
            (throw (ex-info "Gemma Q/K/V derived head dimensions differ"
                            {:q-head-dim q-head-dim
                             :kv-head-dim kv-head-dim})))
        q-head (q4-projection-summary backend path
                                      (:gguf/tensor-data-start tensor-index)
                                      (get tensors "blk.0.attn_q.weight")
                                      rmsnorm-values
                                      (range q-head-dim)
                                      (:gemma4/embedding-length expected))
        k-head (q4-projection-summary backend path
                                      (:gguf/tensor-data-start tensor-index)
                                      (get tensors "blk.0.attn_k.weight")
                                      rmsnorm-values
                                      (range kv-head-dim)
                                      (:gemma4/embedding-length expected))
        v-head (q6-projection-summary backend path
                                      (:gguf/tensor-data-start tensor-index)
                                      (get tensors "blk.0.attn_v.weight")
                                      rmsnorm-values
                                      (range kv-head-dim)
                                      (:gemma4/embedding-length expected))
        q-head-rope-values (ops/rope-interleaved-values (:values q-head) 1
                                                        (:gemma4/rope-dimension-count expected)
                                                        (:gemma4/rope-freq-base expected))
        k-head-rope-values (ops/rope-interleaved-values (:values k-head) 1
                                                        (:gemma4/rope-dimension-count expected)
                                                        (:gemma4/rope-freq-base expected))
        head-materialized {:blk.0/attn_q (summarize-values backend q-head-rope-values
                                                           {:head 0
                                                            :position 1
                                                            :rows [0 (dec q-head-dim)]
                                                            :rope? true})
                           :blk.0/attn_k (summarize-values backend k-head-rope-values
                                                           {:head 0
                                                            :kv-head 0
                                                            :position 1
                                                            :rows [0 (dec kv-head-dim)]
                                                            :rope? true})
                           :blk.0/attn_v (summarize-values backend (:values v-head)
                                                           {:kv-head 0
                                                            :rows [0 (dec kv-head-dim)]
                                                            :rope? false})}
        attention {:blk.0/head0-token0 (attention-summary backend
                                                          q-head-rope-values
                                                          k-head-rope-values
                                                          (:values v-head)
                                                          {:q-head 0
                                                           :kv-head 0
                                                           :position 1
                                                           :head-dim q-head-dim})}
        attention-width (second (get-in expected [:gguf/required-tensors "blk.0.attn_q.weight" :shape]))
        attention-vector (single-head-attention-vector (:values v-head) attention-width 0)
        q-all (q4-projection-summary-direct backend path
                                            (:gguf/tensor-data-start tensor-index)
                                            (get tensors "blk.0.attn_q.weight")
                                            rmsnorm-values
                                            (range attention-width)
                                            (:gemma4/embedding-length expected))
        k-all (q4-projection-summary-direct backend path
                                            (:gguf/tensor-data-start tensor-index)
                                            (get tensors "blk.0.attn_k.weight")
                                            rmsnorm-values
                                            (range (second (get-in expected [:gguf/required-tensors "blk.0.attn_k.weight" :shape])))
                                            (:gemma4/embedding-length expected))
        v-all (q6-projection-summary-direct backend path
                                            (:gguf/tensor-data-start tensor-index)
                                            (get tensors "blk.0.attn_v.weight")
                                            rmsnorm-values
                                            (range (second (get-in expected [:gguf/required-tensors "blk.0.attn_v.weight" :shape])))
                                            (:gemma4/embedding-length expected))
        q-all-rope-values (rope-heads-values (:values q-all)
                                             q-head-dim
                                             1
                                             (:gemma4/rope-dimension-count expected)
                                             (:gemma4/rope-freq-base expected))
        k-all-rope-values (rope-heads-values (:values k-all)
                                             kv-head-dim
                                             1
                                             (:gemma4/rope-dimension-count expected)
                                             (:gemma4/rope-freq-base expected))
        all-head-attention (all-head-single-token-attention q-all-rope-values
                                                            k-all-rope-values
                                                            (:values v-all)
                                                            (:gemma4/attention-head-count expected)
                                                            (:gemma4/attention-head-count-kv expected)
                                                            q-head-dim)
        all-head-attention-summary (all-head-attention-summary backend
                                                               all-head-attention
                                                               {:q-head-range [0 (dec (:gemma4/attention-head-count expected))]
                                                                :kv-head-range [0 (dec (:gemma4/attention-head-count-kv expected))]
                                                                :position 1
                                                                :head-dim q-head-dim})
        q-all-token1 (q4-projection-summary-direct backend path
                                                   (:gguf/tensor-data-start tensor-index)
                                                   (get tensors "blk.0.attn_q.weight")
                                                   second-rmsnorm-values
                                                   (range attention-width)
                                                   (:gemma4/embedding-length expected))
        k-all-token1 (q4-projection-summary-direct backend path
                                                   (:gguf/tensor-data-start tensor-index)
                                                   (get tensors "blk.0.attn_k.weight")
                                                   second-rmsnorm-values
                                                   (range (second (get-in expected [:gguf/required-tensors "blk.0.attn_k.weight" :shape])))
                                                   (:gemma4/embedding-length expected))
        v-all-token1 (q6-projection-summary-direct backend path
                                                   (:gguf/tensor-data-start tensor-index)
                                                   (get tensors "blk.0.attn_v.weight")
                                                   second-rmsnorm-values
                                                   (range (second (get-in expected [:gguf/required-tensors "blk.0.attn_v.weight" :shape])))
                                                   (:gemma4/embedding-length expected))
        q-all-token1-rope-values (rope-heads-values (:values q-all-token1)
                                                    q-head-dim
                                                    2
                                                    (:gemma4/rope-dimension-count expected)
                                                    (:gemma4/rope-freq-base expected))
        k-all-token1-rope-values (rope-heads-values (:values k-all-token1)
                                                    kv-head-dim
                                                    2
                                                    (:gemma4/rope-dimension-count expected)
                                                    (:gemma4/rope-freq-base expected))
        two-token-attention (all-head-causal-attention q-all-token1-rope-values
                                                       [k-all-rope-values k-all-token1-rope-values]
                                                       [(:values v-all) (:values v-all-token1)]
                                                       (:gemma4/attention-head-count expected)
                                                       (:gemma4/attention-head-count-kv expected)
                                                       q-head-dim)
        two-token-attention-summary (all-head-causal-attention-summary backend
                                                                       two-token-attention
                                                                       {:token-ids [(:tokenizer/bos-token-id expected) second-token-id]
                                                                        :query-token-index 1
                                                                        :position 2
                                                                        :visible-token-count 2
                                                                        :q-head-range [0 (dec (:gemma4/attention-head-count expected))]
                                                                        :kv-head-range [0 (dec (:gemma4/attention-head-count-kv expected))]
                                                                        :head-dim q-head-dim})
        attention-output (q4-projection-summary backend path
                                                (:gguf/tensor-data-start tensor-index)
                                                (get tensors "blk.0.attn_output.weight")
                                                attention-vector
                                                [0 1 2 3]
                                                attention-width)
        attention-output-full (q4-projection-summary backend path
                                                     (:gguf/tensor-data-start tensor-index)
                                                     (get tensors "blk.0.attn_output.weight")
                                                     attention-vector
                                                     (range (:gemma4/embedding-length expected))
                                                     attention-width)
        attention-output-all-heads (q4-projection-summary-direct backend path
                                                                 (:gguf/tensor-data-start tensor-index)
                                                                 (get tensors "blk.0.attn_output.weight")
                                                                 (:values all-head-attention)
                                                                 (range (:gemma4/embedding-length expected))
                                                                 attention-width)
        block-attn-residual-values (when full-mlp?
                                     (ops/add-values token-values (:values attention-output-all-heads)))
        block-attn-residual (when full-mlp?
                              (summarize-values backend block-attn-residual-values
                                                {:token-id (:tokenizer/bos-token-id expected)
                                                 :layer 0
                                                 :stage :attention-residual}))
        block-ffn-norm-values (when full-mlp?
                                (ops/gemma-rmsnorm-values block-attn-residual-values ffn-norm-weights))
        block-ffn-norm (when full-mlp?
                         (summarize-values backend block-ffn-norm-values
                                           {:token-id (:tokenizer/bos-token-id expected)
                                            :layer 0
                                            :stage :ffn-norm}))
        ffn-gate (q4-projection-summary backend path
                                        (:gguf/tensor-data-start tensor-index)
                                        (get tensors "blk.0.ffn_gate.weight")
                                        ffn-norm-values
                                        [0 1 2 3]
                                        (:gemma4/embedding-length expected))
        ffn-up (q4-projection-summary backend path
                                      (:gguf/tensor-data-start tensor-index)
                                      (get tensors "blk.0.ffn_up.weight")
                                      ffn-norm-values
                                      [0 1 2 3]
                                      (:gemma4/embedding-length expected))
        ffn-activation-values (ops/gated-mlp-activation-values (:values ffn-gate)
                                                               (:values ffn-up))
        ffn-activation (summarize-values backend ffn-activation-values
                                         {:rows [0 1 2 3]})
        ffn-down-input (prefix-vector ffn-activation-values
                                      (:gemma4/feed-forward-length expected))
        ffn-down (q6-projection-summary backend path
                                        (:gguf/tensor-data-start tensor-index)
                                        (get tensors "blk.0.ffn_down.weight")
                                        ffn-down-input
                                        [0 1 2 3]
                                        (:gemma4/feed-forward-length expected))
        ffn-gate-full (when full-mlp?
                        (q4-projection-summary-direct backend path
                                                      (:gguf/tensor-data-start tensor-index)
                                                      (get tensors "blk.0.ffn_gate.weight")
                                                      ffn-norm-values
                                                      (range (:gemma4/feed-forward-length expected))
                                                      (:gemma4/embedding-length expected)))
        ffn-up-full (when full-mlp?
                      (q4-projection-summary-direct backend path
                                                    (:gguf/tensor-data-start tensor-index)
                                                    (get tensors "blk.0.ffn_up.weight")
                                                    ffn-norm-values
                                                    (range (:gemma4/feed-forward-length expected))
                                                    (:gemma4/embedding-length expected)))
        ffn-activation-full-values (when full-mlp?
                                     (ops/gated-mlp-activation-values (:values ffn-gate-full)
                                                                      (:values ffn-up-full)))
        ffn-activation-full (when full-mlp?
                              (summarize-values backend ffn-activation-full-values
                                                {:row-range [0 (dec (:gemma4/feed-forward-length expected))]
                                                 :row-count (:gemma4/feed-forward-length expected)}))
        ffn-down-full (when full-mlp?
                        (q6-projection-summary-direct backend path
                                                     (:gguf/tensor-data-start tensor-index)
                                                     (get tensors "blk.0.ffn_down.weight")
                                                     ffn-activation-full-values
                                                     (range (:gemma4/embedding-length expected))
                                                     (:gemma4/feed-forward-length expected)))
        block-ffn-gate-full (when full-mlp?
                              (q4-projection-summary-direct backend path
                                                            (:gguf/tensor-data-start tensor-index)
                                                            (get tensors "blk.0.ffn_gate.weight")
                                                            block-ffn-norm-values
                                                            (range (:gemma4/feed-forward-length expected))
                                                            (:gemma4/embedding-length expected)))
        block-ffn-up-full (when full-mlp?
                            (q4-projection-summary-direct backend path
                                                          (:gguf/tensor-data-start tensor-index)
                                                          (get tensors "blk.0.ffn_up.weight")
                                                          block-ffn-norm-values
                                                          (range (:gemma4/feed-forward-length expected))
                                                          (:gemma4/embedding-length expected)))
        block-ffn-activation-full-values (when full-mlp?
                                           (ops/gated-mlp-activation-values (:values block-ffn-gate-full)
                                                                            (:values block-ffn-up-full)))
        block-ffn-activation-full (when full-mlp?
                                    (summarize-values backend block-ffn-activation-full-values
                                                      {:token-id (:tokenizer/bos-token-id expected)
                                                       :layer 0
                                                       :stage :ffn-activation
                                                       :row-range [0 (dec (:gemma4/feed-forward-length expected))]
                                                       :row-count (:gemma4/feed-forward-length expected)}))
        block-ffn-down-full (when full-mlp?
                              (q6-projection-summary-direct backend path
                                                            (:gguf/tensor-data-start tensor-index)
                                                            (get tensors "blk.0.ffn_down.weight")
                                                            block-ffn-activation-full-values
                                                            (range (:gemma4/embedding-length expected))
                                                            (:gemma4/feed-forward-length expected)))
        block-output-values (when full-mlp?
                              (ops/add-values block-attn-residual-values (:values block-ffn-down-full)))
        block-output (when full-mlp?
                       (summarize-values backend block-output-values
                                         {:token-id (:tokenizer/bos-token-id expected)
                                          :layer 0
                                          :stage :block-output}))
        block-output-norm-values (when full-mlp?
                                   (ops/gemma-rmsnorm-values block-output-values output-norm-weights))
        block-output-norm (when full-mlp?
                            (summarize-values backend block-output-norm-values
                                              {:token-id (:tokenizer/bos-token-id expected)
                                               :layer 0
                                               :stage :output-norm-after-block}))
        block-output-logits (when full-mlp?
                              (q6-logits-summary backend path
                                                 (:gguf/tensor-data-start tensor-index)
                                                 (get tensors "token_embd.weight")
                                                 block-output-norm-values
                                                 [1 2 3 4]
                                                 (:gemma4/embedding-length expected)))
        core-forward-result (when (and full-mlp? (> full-layer-count 1))
                              (let [runtime (real-gemma-runtime {:model model
                                                                 :path path
                                                                 :full-layer-count full-layer-count})
                                    session (inference-core/load-model
                                             runtime
                                     (inference-runtime/transformer
                                      model
                                      {:kotodama/backend :native
                                       :kotodama/compute-backend :num/cpu
                                       :kotodama/model-graph (gemma/gemma4-e4b-graph expected)}))
                                    forward-opts {:kotodama/full-layer-count full-layer-count
                                                  :kotodama/include-blocks? true}
                                    first-result (inference-core/forward runtime
                                                                         session
                                                                         [(:tokenizer/bos-token-id expected)]
                                                                         forward-opts)
                                    second-result (inference-core/forward runtime
                                                                          session
                                                                          [(:tokenizer/bos-token-id expected)]
                                                                          forward-opts)]
                                (when (:kotodama/cache-hit? first-result)
                                  (throw (ex-info "Gemma core/forward first call unexpectedly hit cache"
                                                  {:forward first-result})))
                                (when-not (:kotodama/cache-hit? second-result)
                                  (throw (ex-info "Gemma core/forward second call did not hit cache"
                                                  {:forward second-result})))
                                second-result))
        torch-real-block-run (:gguf/torch-run core-forward-result)
        multi-layer-blocks (when (and full-mlp? (> full-layer-count 1))
                             (into {}
                                   (filter (fn [[block-key _]]
                                             (pos? (block-key-layer-index block-key))))
                                   (:blocks torch-real-block-run)))
        output-logits (q6-logits-summary backend path
                                         (:gguf/tensor-data-start tensor-index)
                                         (get tensors "token_embd.weight")
                                         output-norm-values
                                         [1 2 3 4]
                                         (:gemma4/embedding-length expected))
        output-logits-full (when full-vocab?
                             (q6-full-vocab-logits-summary path
                                                           (:gguf/tensor-data-start tensor-index)
                                                           (get tensors "token_embd.weight")
                                                           output-norm-values
                                                           (:gemma4/embedding-length expected)
                                                           (second (get-in expected [:gguf/required-tensors
                                                                                    "token_embd.weight"
                                                                                    :shape]))
                                                           16))]
    (doseq [[name summary] (merge q4-actual q6-actual)]
      (when-not (and (= [16 16] (:shape summary))
                     (= 256 (:value-count summary))
                     (approx= (:sum summary) (:sum (get-in expected [:gguf/q4-k-samples name]
                                                           (get-in expected [:gguf/q6-k-samples name])))))
        (throw (ex-info "Gemma num tensor shape/count failed"
                        {:tensor name :summary summary}))))
    (when-let [expected-token (get-in expected [:gguf/token-embedding-samples
                                                (:tokenizer/bos-token-id expected)])]
      (require-summary! "token_embd.weight:BOS"
                        (dissoc token-embedding :shape)
                        expected-token))
    (when-not (and (= [(:gemma4/embedding-length expected)] (:shape token-embedding))
                   (= (:gemma4/embedding-length expected) (:value-count token-embedding)))
      (throw (ex-info "Gemma token embedding shape/count failed"
                      {:summary token-embedding})))
    (when-let [expected-rms (get-in expected [:gguf/rmsnorm-samples :blk.0/attn_norm])]
      (require-summary! "blk.0.attn_norm(BOS)"
                        (dissoc rmsnorm :shape)
                        expected-rms))
    (when-not (and (= [(:gemma4/embedding-length expected)] (:shape rmsnorm))
                   (= (:gemma4/embedding-length expected) (:value-count rmsnorm)))
      (throw (ex-info "Gemma RMSNorm shape/count failed"
                      {:summary rmsnorm})))
    (doseq [[projection-key summary] projections]
      (when-let [expected-projection (get-in expected [:gguf/projection-samples projection-key])]
        (require-summary! (str (name projection-key) "(BOS)")
                          (dissoc summary :shape :values)
                          expected-projection))
      (when-not (and (= [4] (:shape summary))
                     (= 4 (:value-count summary)))
        (throw (ex-info "Gemma projection shape/count failed"
                        {:projection projection-key
                         :summary summary}))))
    (doseq [[rope-key summary] rope]
      (when-let [expected-rope (get-in expected [:gguf/rope-samples rope-key])]
        (require-summary! (str (name rope-key) "(rope)")
                          (dissoc summary :shape)
                          expected-rope))
      (when-not (and (= [4] (:shape summary))
                     (= 4 (:value-count summary)))
        (throw (ex-info "Gemma RoPE shape/count failed"
                        {:rope rope-key
                         :summary summary}))))
    (doseq [[head-key summary] head-materialized]
      (when-let [expected-head (get-in expected [:gguf/head-samples head-key])]
        (require-summary! (str (name head-key) "(head)")
                          (dissoc summary :shape)
                          expected-head))
      (when-not (and (= [q-head-dim] (:shape summary))
                     (= q-head-dim (:value-count summary)))
        (throw (ex-info "Gemma head materialization shape/count failed"
                        {:head head-key
                         :summary summary}))))
    (doseq [[attention-key summary] attention]
      (when-let [expected-attention (get-in expected [:gguf/attention-samples attention-key])]
        (require-summary! (str (name attention-key) "(attention)")
                          (dissoc summary :shape)
                          expected-attention))
      (when-not (and (= [q-head-dim] (:shape summary))
                     (= q-head-dim (:value-count summary)))
        (throw (ex-info "Gemma single-token attention shape/count failed"
                        {:attention attention-key
                         :summary summary}))))
    (when-let [expected-all-heads (get-in expected [:gguf/attention-samples :blk.0/all-heads-token0])]
      (require-summary! "blk.0.all-heads-token0(attention)"
                        (dissoc all-head-attention-summary :shape)
                        expected-all-heads))
    (when-not (and (= [attention-width] (:shape all-head-attention-summary))
                   (= attention-width (:value-count all-head-attention-summary)))
      (throw (ex-info "Gemma all-head single-token attention shape/count failed"
                      {:summary all-head-attention-summary})))
    (when-let [expected-two-token (get-in expected [:gguf/attention-samples :blk.0/all-heads-token1-causal])]
      (require-summary! "blk.0.all-heads-token1-causal(attention)"
                        (dissoc two-token-attention-summary :shape)
                        expected-two-token))
    (when-not (and (= [attention-width] (:shape two-token-attention-summary))
                   (= attention-width (:value-count two-token-attention-summary)))
      (throw (ex-info "Gemma two-token all-head attention shape/count failed"
                      {:summary two-token-attention-summary})))
    (when-let [expected-output (get-in expected [:gguf/attention-output-samples :blk.0/attn_output])]
      (require-summary! "blk.0.attn_output(single-token)"
                        (dissoc attention-output :shape :values)
                        expected-output))
    (when-not (and (= [4] (:shape attention-output))
                   (= 4 (:value-count attention-output)))
      (throw (ex-info "Gemma attention output projection shape/count failed"
                      {:summary attention-output})))
    (when-let [expected-output-full (get-in expected [:gguf/attention-output-samples :blk.0/attn_output_full])]
      (require-summary! "blk.0.attn_output(single-token-full-width)"
                        (dissoc attention-output-full :shape :values)
                        expected-output-full))
    (when-not (and (= [(:gemma4/embedding-length expected)] (:shape attention-output-full))
                   (= (:gemma4/embedding-length expected) (:value-count attention-output-full)))
      (throw (ex-info "Gemma full attention output projection shape/count failed"
                      {:summary (dissoc attention-output-full :values)})))
    (when-let [expected-output-all-heads (get-in expected [:gguf/attention-output-samples :blk.0/attn_output_all_heads])]
      (require-summary! "blk.0.attn_output(all-heads-full-width)"
                        (dissoc attention-output-all-heads :shape :values)
                        expected-output-all-heads))
    (when-not (and (= [(:gemma4/embedding-length expected)] (:shape attention-output-all-heads))
                   (= (:gemma4/embedding-length expected) (:value-count attention-output-all-heads)))
      (throw (ex-info "Gemma all-head attention output projection shape/count failed"
                      {:summary (dissoc attention-output-all-heads :values)})))
    (when-let [expected-ffn-rms (get-in expected [:gguf/rmsnorm-samples :blk.0/ffn_norm])]
      (require-summary! "blk.0.ffn_norm(BOS)"
                        (dissoc ffn-rmsnorm :shape)
                        expected-ffn-rms))
    (when-not (and (= [(:gemma4/embedding-length expected)] (:shape ffn-rmsnorm))
                   (= (:gemma4/embedding-length expected) (:value-count ffn-rmsnorm)))
      (throw (ex-info "Gemma FFN RMSNorm shape/count failed"
                      {:summary ffn-rmsnorm})))
    (when-let [expected-gate (get-in expected [:gguf/mlp-samples :blk.0/ffn_gate])]
      (require-summary! "blk.0.ffn_gate(BOS)"
                        (dissoc ffn-gate :shape :values)
                        expected-gate))
    (when-let [expected-up (get-in expected [:gguf/mlp-samples :blk.0/ffn_up])]
      (require-summary! "blk.0.ffn_up(BOS)"
                        (dissoc ffn-up :shape :values)
                        expected-up))
    (when-let [expected-activation (get-in expected [:gguf/mlp-samples :blk.0/ffn_activation])]
      (require-summary! "blk.0.ffn_activation(BOS)"
                        (dissoc ffn-activation :shape)
                        expected-activation))
    (when-let [expected-down (get-in expected [:gguf/mlp-samples :blk.0/ffn_down])]
      (require-summary! "blk.0.ffn_down(partial)"
                        (dissoc ffn-down :shape :values)
                        expected-down))
    (when-let [expected-gate-full (and full-mlp?
                                       (get-in expected [:gguf/mlp-samples :blk.0/ffn_gate_full]))]
      (require-summary! "blk.0.ffn_gate(full)"
                        (dissoc ffn-gate-full :shape :values)
                        expected-gate-full))
    (when-let [expected-up-full (and full-mlp?
                                     (get-in expected [:gguf/mlp-samples :blk.0/ffn_up_full]))]
      (require-summary! "blk.0.ffn_up(full)"
                        (dissoc ffn-up-full :shape :values)
                        expected-up-full))
    (when-let [expected-activation-full (and full-mlp?
                                             (get-in expected [:gguf/mlp-samples :blk.0/ffn_activation_full]))]
      (require-summary! "blk.0.ffn_activation(full)"
                        (dissoc ffn-activation-full :shape)
                        expected-activation-full))
    (when-let [expected-down-full (and full-mlp?
                                       (get-in expected [:gguf/mlp-samples :blk.0/ffn_down_full]))]
      (require-summary! "blk.0.ffn_down(full)"
                        (dissoc ffn-down-full :shape :values)
                        expected-down-full))
    (doseq [[mlp-key summary] {:blk.0/ffn_gate ffn-gate
                               :blk.0/ffn_up ffn-up
                               :blk.0/ffn_activation ffn-activation
                               :blk.0/ffn_down ffn-down}]
      (when-not (and (= [4] (:shape summary))
                     (= 4 (:value-count summary)))
        (throw (ex-info "Gemma MLP partial shape/count failed"
                        {:mlp mlp-key
                         :summary summary}))))
    (when full-mlp?
      (doseq [[mlp-key summary expected-size] [[:blk.0/ffn_gate_full ffn-gate-full (:gemma4/feed-forward-length expected)]
                                               [:blk.0/ffn_up_full ffn-up-full (:gemma4/feed-forward-length expected)]
                                               [:blk.0/ffn_activation_full ffn-activation-full (:gemma4/feed-forward-length expected)]
                                               [:blk.0/ffn_down_full ffn-down-full (:gemma4/embedding-length expected)]]]
        (when-not (and (= [expected-size] (:shape summary))
                       (= expected-size (:value-count summary)))
          (throw (ex-info "Gemma MLP full shape/count failed"
                          {:mlp mlp-key
                           :summary (dissoc summary :values)})))))
    (when-let [expected-block (and full-mlp?
                                   (get-in expected [:gguf/block-samples :blk.0/block0_full]))]
      (let [actual-block (if (> full-layer-count 1)
                           (get-in torch-real-block-run [:blocks :blk.0/block0_full])
                           {:attention-residual block-attn-residual
                            :ffn-norm block-ffn-norm
                            :ffn-gate block-ffn-gate-full
                            :ffn-up block-ffn-up-full
                            :ffn-activation block-ffn-activation-full
                            :ffn-down block-ffn-down-full
                            :block-output block-output
                            :output-norm block-output-norm
                            :logits block-output-logits})]
        (doseq [[stage-key summary] actual-block]
          (when-let [expected-stage (get expected-block stage-key)]
            (require-summary! (str "blk.0.block0_full/" (name stage-key))
                              (dissoc summary :shape :values)
                              expected-stage)))))
    (when full-mlp?
      (let [actual-block (if (> full-layer-count 1)
                           (get-in torch-real-block-run [:blocks :blk.0/block0_full])
                           {:attention-residual block-attn-residual
                            :ffn-norm block-ffn-norm
                            :ffn-gate block-ffn-gate-full
                            :ffn-up block-ffn-up-full
                            :ffn-activation block-ffn-activation-full
                            :ffn-down block-ffn-down-full
                            :block-output block-output
                            :output-norm block-output-norm
                            :logits block-output-logits})]
        (doseq [[stage-key summary expected-size] [[:attention-residual (:attention-residual actual-block) (:gemma4/embedding-length expected)]
                                                   [:ffn-norm (:ffn-norm actual-block) (:gemma4/embedding-length expected)]
                                                   [:ffn-gate (:ffn-gate actual-block) (:gemma4/feed-forward-length expected)]
                                                   [:ffn-up (:ffn-up actual-block) (:gemma4/feed-forward-length expected)]
                                                   [:ffn-activation (:ffn-activation actual-block) (:gemma4/feed-forward-length expected)]
                                                   [:ffn-down (:ffn-down actual-block) (:gemma4/embedding-length expected)]
                                                   [:block-output (:block-output actual-block) (:gemma4/embedding-length expected)]
                                                   [:output-norm (:output-norm actual-block) (:gemma4/embedding-length expected)]]]
          (when-not (and (= [expected-size] (:shape summary))
                         (= expected-size (:value-count summary)))
            (throw (ex-info "Gemma full block composition shape/count failed"
                            {:stage stage-key
                             :summary (dissoc summary :values)}))))
        (when-not (and (= [4] (:shape (:logits actual-block)))
                       (= 4 (:value-count (:logits actual-block))))
          (throw (ex-info "Gemma full block output logits shape/count failed"
                          {:summary (:logits actual-block)})))))
    (when-let [expected-blocks (and full-mlp?
                                    (> full-layer-count 1)
                                    (:gguf/multi-layer-block-samples expected))]
      (doseq [[block-key expected-block] expected-blocks
              :let [actual-block (get multi-layer-blocks block-key)]]
        (when-not actual-block
          (throw (ex-info "Gemma multi-layer block summary missing"
                          {:block block-key
                           :available (keys multi-layer-blocks)})))
        (doseq [[stage-key expected-stage] expected-block
                :let [summary (get actual-block stage-key)]]
          (require-summary! (str (namespace block-key) "." (name block-key) "/" (name stage-key))
                            (dissoc summary :shape :values)
                            expected-stage))))
    (when (and full-mlp? (> full-layer-count 1))
      (doseq [[block-key block] multi-layer-blocks]
        (doseq [[stage-key summary expected-size] [[:attention (:attention block) (first (:shape (:attention block)))]
                                                   [:attention-output (:attention-output block) (:gemma4/embedding-length expected)]
                                                   [:attention-residual (:attention-residual block) (:gemma4/embedding-length expected)]
                                                   [:ffn-norm (:ffn-norm block) (:gemma4/embedding-length expected)]
                                                   [:ffn-gate (:ffn-gate block) (:gemma4/feed-forward-length expected)]
                                                   [:ffn-up (:ffn-up block) (:gemma4/feed-forward-length expected)]
                                                   [:ffn-activation (:ffn-activation block) (:gemma4/feed-forward-length expected)]
                                                   [:ffn-down (:ffn-down block) (:gemma4/embedding-length expected)]
                                                   [:block-output (:block-output block) (:gemma4/embedding-length expected)]
                                                   [:output-norm (:output-norm block) (:gemma4/embedding-length expected)]]]
          (when-not (and (= [expected-size] (:shape summary))
                         (= expected-size (:value-count summary)))
            (throw (ex-info "Gemma multi-layer full block shape/count failed"
                            {:block block-key
                             :stage stage-key
                             :summary summary}))))
        (when-not (and (= [4] (:shape (:logits block)))
                       (= 4 (:value-count (:logits block))))
          (throw (ex-info "Gemma multi-layer full block logits shape/count failed"
                          {:block block-key
                           :summary (:logits block)})))))
    (when (and full-mlp? (> full-layer-count 1))
      (let [contracts (merge (:gguf/block-samples expected)
                             (:gguf/multi-layer-block-samples expected))
            torch-blocks (:blocks torch-real-block-run)]
        (when-not (= full-layer-count (count torch-blocks))
          (throw (ex-info "Gemma torch real block runner block count failed"
                          {:expected full-layer-count
                           :actual (count torch-blocks)
                           :blocks (keys torch-blocks)})))
        (doseq [[block-key expected-block] contracts
                :when (contains? torch-blocks block-key)
                [stage-key expected-stage] expected-block
                :let [summary (get-in torch-blocks [block-key stage-key])]]
          (when-not summary
            (throw (ex-info "Gemma torch real block runner stage missing"
                            {:block block-key
                             :stage stage-key
                             :available (keys (get torch-blocks block-key))})))
          (require-summary! (str "torch-run/" (namespace block-key) "." (name block-key) "/" (name stage-key))
                            (dissoc summary :shape :values)
                            expected-stage))))
    (when (and full-mlp? (> full-layer-count 1))
      (let [expected-logits (get-in expected [:gguf/multi-layer-block-samples
                                              :blk.1/block1_full
                                              :logits])
            actual-logits (get-in core-forward-result [:gguf/torch-block-num
                                                       :last-block-logits])]
        (require-summary! "core-forward/real-gguf-torch-run/last-block-logits"
                          (dissoc actual-logits :shape :values)
                          expected-logits)
        (when-not (= (:sample expected-logits) (:kotodama/logits core-forward-result))
          (throw (ex-info "Gemma core/forward logits sample mismatch"
                          {:expected (:sample expected-logits)
                           :actual (:kotodama/logits core-forward-result)
                           :forward core-forward-result})))))
    (when-let [expected-output-rms (get-in expected [:gguf/rmsnorm-samples :output/norm])]
      (require-summary! "output_norm(BOS)"
                        (dissoc output-rmsnorm :shape)
                        expected-output-rms))
    (when-not (and (= [(:gemma4/embedding-length expected)] (:shape output-rmsnorm))
                   (= (:gemma4/embedding-length expected) (:value-count output-rmsnorm)))
      (throw (ex-info "Gemma output RMSNorm shape/count failed"
                      {:summary output-rmsnorm})))
    (when-let [expected-logits (get-in expected [:gguf/output-logit-samples :token_embd/candidates])]
      (require-summary! "token_embd(output-logits)"
                        (dissoc output-logits :shape :values)
                        expected-logits))
    (when-not (and (= [4] (:shape output-logits))
                   (= 4 (:value-count output-logits)))
      (throw (ex-info "Gemma output logits shape/count failed"
                      {:summary output-logits})))
    (when-let [expected-full-logits (and full-vocab?
                                         (get-in expected [:gguf/output-logit-samples :token_embd/full-vocab]))]
      (require-summary! "token_embd(full-vocab-logits)"
                        output-logits-full
                        expected-full-logits))
    (when (and full-vocab? (nil? output-logits-full))
      (throw (ex-info "Gemma full-vocab logits missing" {})))
    (prn {:kotodama/gemma4-e4b-num-smoke :ok
          :kotodama/model model
          :kotodama/backend :num/cpu
          :gguf/q4-k-num q4-actual
          :gguf/q6-k-num q6-actual
          :gguf/token-embedding-num token-embedding
          :gguf/rmsnorm-num {:blk.0/attn_norm rmsnorm}
          :gguf/ffn-rmsnorm-num {:blk.0/ffn_norm ffn-rmsnorm}
          :gguf/output-rmsnorm-num {:output/norm output-rmsnorm}
          :gguf/projection-num (update-vals projections #(dissoc % :values))
          :gguf/rope-num rope
          :gguf/head-num head-materialized
          :gguf/attention-num attention
          :gguf/attention-output-num {:blk.0/attn_output (dissoc attention-output :values)
                                      :blk.0/attn_output_full (dissoc attention-output-full :values)
                                      :blk.0/attn_output_all_heads (dissoc attention-output-all-heads :values)}
          :gguf/all-head-attention-num {:blk.0/all-heads-token0 all-head-attention-summary}
          :gguf/multi-token-attention-num {:blk.0/all-heads-token1-causal two-token-attention-summary}
          :gguf/mlp-num (cond-> {:blk.0/ffn_gate (dissoc ffn-gate :values)
                                 :blk.0/ffn_up (dissoc ffn-up :values)
                                 :blk.0/ffn_activation ffn-activation
                                 :blk.0/ffn_down (dissoc ffn-down :values)}
                          full-mlp?
                          (assoc :blk.0/ffn_gate_full (dissoc ffn-gate-full :values)
                                 :blk.0/ffn_up_full (dissoc ffn-up-full :values)
                                 :blk.0/ffn_activation_full ffn-activation-full
                                 :blk.0/ffn_down_full (dissoc ffn-down-full :values)))
          :gguf/block-num (when full-mlp?
                            {:blk.0/block0_full {:attention-residual block-attn-residual
                                                 :ffn-norm block-ffn-norm
                                                 :ffn-gate (dissoc block-ffn-gate-full :values)
                                                 :ffn-up (dissoc block-ffn-up-full :values)
                                                 :ffn-activation block-ffn-activation-full
                                                 :ffn-down (dissoc block-ffn-down-full :values)
                                                 :block-output block-output
                                                 :output-norm block-output-norm
                                                 :logits (dissoc block-output-logits :values)}})
          :gguf/multi-layer-block-num multi-layer-blocks
          :gguf/torch-block-num (when torch-real-block-run
                                  (let [last-block-key (keyword (str "blk." (dec full-layer-count))
                                                                (str "block" (dec full-layer-count) "_full"))]
                                    {:block-count (count (:blocks torch-real-block-run))
                                     :block-keys (vec (keys (:blocks torch-real-block-run)))
                                     :last-block-key last-block-key
                                     :last-block-logits (get-in torch-real-block-run
                                                                [:blocks last-block-key :logits])}))
          :gguf/core-forward-num (when core-forward-result
                                   (select-keys core-forward-result
                                                [:kotodama/forward
                                                 :kotodama/input-ids
                                                 :kotodama/cache-hit?
                                                 :kotodama/logits
                                                 :gguf/torch-block-num]))
          :gguf/output-logits-num (cond-> {:token_embd/candidates (dissoc output-logits :values)}
                                    full-vocab?
                                    (assoc :token_embd/full-vocab output-logits-full))})))
