(ns torch.deno-quantized-llama-benchmark
  "Whole-graph packed Llama Metal integration and completion-time benchmark."
  (:require [num.array :as arr]
            [num.deno-gpu :as dg]
            [num.dtype :as dtype]
            [num.quantized :as q]
            [torch.core :as core]
            [torch.model :as model]
            [torch.num-backend :as nb]))

(def embed 256)
(def hidden 256)
(def vocab 256)
(def token-ids (vec (take 16 (cycle [2 7 11 3 19 5]))))
(def packed-scales [1 1 1 1, 0 0 0 0, 1 1 1 1])

(defn half-bytes [value]
  (let [bits (bit-and 0xffff (dtype/f32->f16-bits value))]
    [(bit-and bits 0xff) (bit-and (bit-shift-right bits 8) 0xff)]))

(defn block [row]
  (let [d (+ 0.0002 (* 0.000001 (mod row 31)))]
    (vec (concat (half-bytes d) (half-bytes 0.0)
                 packed-scales (repeat 128 0x11)))))

(defn packed-bytes [rows]
  (vec (mapcat block (range rows))))

(defn packed-matrix [backend out]
  (q/matrix backend (packed-bytes out) [out embed] :q4-k))

(defn fixture [backend]
  (let [embedding (q/table backend (packed-bytes vocab) [vocab embed] :q4-k)
        block-weight
        (fn [] {:attn-norm (arr/from-vec backend (repeat embed 1.0) [embed])
                :qw (packed-matrix backend embed)
                :kw (packed-matrix backend 128)
                :vw (packed-matrix backend 128)
                :ow (packed-matrix backend embed)
                :ffn-norm (arr/from-vec backend (repeat embed 1.0) [embed])
                :gate (packed-matrix backend hidden)
                :up (packed-matrix backend hidden)
                :down (packed-matrix backend embed)})]
    {:model (model/sequential
             (model/embedding vocab embed)
             (model/llama-block embed 4 hidden {:kv-heads 2})
             (model/llama-block embed 4 hidden {:kv-heads 2})
             (model/rmsnorm embed) (model/lm-head embed vocab))
     :weights [{:w embedding} (block-weight) (block-weight)
               {:w (arr/from-vec backend (repeat embed 1.0) [embed])}
               {:w (q/as-matrix embedding)}]}))

(defn now [] (.now js/performance))

(defn full-forward [{:keys [model weights]} backend]
  (core/run (nb/num-backend backend weights) model
            (arr/from-vec backend token-ids [(count token-ids)])))

(defn cached-forward [{:keys [model weights]} backend]
  (let [initial (nb/init-llama-caches backend model 32)
        decoded (reduce (fn [{:keys [caches logits]} token]
                          (let [step (nb/llama-lm-step
                                      model weights
                                      (arr/from-vec backend [token] [1]) caches)]
                            {:caches (:caches step)
                             :logits (conj logits (:logits step))}))
                        {:caches initial :logits []} token-ids)]
    decoded))

(defn close? [left right]
  (and (= (count left) (count right))
       (every? #(< (js/Math.abs %) 3.0e-3) (map - left right))))

(defn -main [& _]
  (-> (dg/request-device)
      (.then
       (fn [request]
         (let [backend (dg/backend request)
               fixture* (fixture backend)
               cold-start (now)]
           (println "Packed whole-Llama benchmark on" (dg/adapter-description request))
           (-> (arr/->vec (full-forward fixture* backend))
               (.then
                (fn [_]
                  (let [cold-ms (- (now) cold-start) warm-start (now)]
                    (-> (arr/->vec (full-forward fixture* backend))
                        (.then
                         (fn [full-values]
                           (let [prefill-ms (- (now) warm-start)
                                 decode-start (now)
                                 decoded (cached-forward fixture* backend)]
                             (-> (js/Promise.all
                                  (into-array (map arr/->vec (:logits decoded))))
                                 (.then
                                  (fn [rows]
                                    (let [decode-ms (- (now) decode-start)
                                          cached-values (vec (mapcat vec (array-seq rows)))
                                          packed-weight-bytes 479232
                                          dense-weight-bytes 3407872
                                          ok? (close? full-values cached-values)]
                                      (println "tokens:" (count token-ids)
                                               "blocks: 2 embed:" embed "GQA: 4/2")
                                      (println "packed weight bytes:" packed-weight-bytes)
                                      (println "dense equivalent bytes:" dense-weight-bytes)
                                      (println "weight memory ratio:"
                                               (.toFixed (/ dense-weight-bytes
                                                            packed-weight-bytes) 2) "x")
                                      (println "full cold ms:" (.toFixed cold-ms 3))
                                      (println "full warm prefill ms:" (.toFixed prefill-ms 3))
                                      (println "cached decode ms/token:"
                                               (.toFixed (/ decode-ms (count token-ids)) 3))
                                      (println "full/cached parity:"
                                               (if ok? "passed" "failed"))
                                      (nb/release-llama-caches! (:caches decoded))
                                      (nb/release-weights! (:weights fixture*))
                                      (when-not ok?
                                        (throw (js/Error. "packed full/cached Llama mismatch"))))))))))))))))))
      (.catch (fn [error]
                (println "ERROR:" (or (.-stack error) (str error)))
                (js/Deno.exit 1)))))

(set! *main-cli-fn* -main)
