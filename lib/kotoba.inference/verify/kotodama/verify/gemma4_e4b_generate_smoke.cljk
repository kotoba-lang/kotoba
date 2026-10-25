(ns kotodama.verify.gemma4-e4b-generate-smoke
  "Real Gemma4 GGUF -> end-to-end single-request text generation, on CPU/JVM.

  This is the generation boundary after `gemma4-e4b-num-smoke` (which proves
  2 composed transformer blocks match golden logits, but never tokenizes,
  samples, or runs the full model). This namespace:

    1. reads the *complete* tokenizer vocabulary (tokens/merges/scores/special
       ids) directly out of the real local Ollama `gemma4:e4b` GGUF and hands
       it to the portable `kotodama.inference.tokenizer` BPE implementation;
    2. runs every real transformer block (`gemma4.block_count`, introspected
       from the file's own metadata rather than assumed) instead of the 2
       blocks the existing verifier composes;
    3. samples greedily (`kotodama.inference.sample/greedy`) and feeds the
       token back in, via the portable `kotodama.inference.decode/generate`
       loop, with no KV-cache (`required-direct-lowering-ops`'s `:kv-cache`
       stays open; every step recomputes every position from scratch).

  ## Why this is a *new* block-composition function, not a reuse of
  `gemma4-e4b-num-smoke/compose-gemma-block`

  The real GGUF for this model (confirmed by introspecting its own metadata,
  not assumed) is architecturally richer than the already-verified 2-block
  path models: every `blk.N` carries `attn_q_norm` / `attn_k_norm` (QK-norm,
  applied per-head after Q/K projection) and `post_attention_norm` /
  `post_ffw_norm` (a Gemma2-style \"sandwich norm\" applied to the attention
  and MLP branch outputs *before* the residual add). `compose-gemma-block`
  does not apply any of these — empirically, chaining it past ~6 layers
  overflows the residual stream to +-Infinity (verified by hand: a 6-layer
  `real-gemma-runtime` forward returns exactly `[0.0 0.0 0.0 0.0]` logits,
  the signature of an RMSNorm divide-by-Infinity). QK-norm and the sandwich
  norm are exactly the mechanism Gemma2+ uses to keep 40+ layers numerically
  stable, so this file adds them. It does *not* attempt the model's
  AltUp / per-layer-embedding tensors (`inp_gate` / `proj` /
  `layer_output_scale` / `per_layer_token_embd` / `per_layer_model_proj`) or
  the 5th `post_norm` weight, or exploit `attention.shared_kv_layers` (an
  optimization hint, not a correctness requirement — every layer's own
  attn_k/attn_v tensors are physically present in the file and are read
  independently here). See the PR description for the honest accounting of
  what this omits.

  compose-gemma-block's already-golden-verified 2-block test is untouched by
  this file: everything below is new, additive, and JVM-only (this repo's
  established \"host-injected runtime\" boundary: `kotodama.inference.*`
  never opens a file; only `verify/` does)."
  (:require [kotodama.inference.gguf :as gguf]
            [kotodama.inference.ops :as ops]
            [kotodama.inference.tokenizer :as tokenizer]
            [kotodama.inference.sample :as sample]
            [kotodama.inference.decode :as decode]
            [kotodama.verify.gemma4-e4b-gguf :as verify-gguf])
  (:import (java.io RandomAccessFile)))

;; ---------------------------------------------------------------------------
;; low-level GGUF byte/metadata IO (JVM-only; mirrors gemma4-e4b-gguf.clj's
;; primitives but materializes the tokenizer arrays that file intentionally
;; skips)
;; ---------------------------------------------------------------------------

(defn- u8 [^RandomAccessFile f] (.readUnsignedByte f))

(defn- le-u32 [^RandomAccessFile f]
  (long (+ (u8 f) (bit-shift-left (u8 f) 8) (bit-shift-left (u8 f) 16) (bit-shift-left (u8 f) 24))))

(defn- le-f32 [^RandomAccessFile f]
  (Float/intBitsToFloat (unchecked-int (le-u32 f))))

(defn- le-u64 [^RandomAccessFile f]
  (let [lo (le-u32 f) hi (le-u32 f)] (+ lo (* hi 4294967296))))

(defn- read-string* [^RandomAccessFile f]
  (let [n (le-u64 f) b (byte-array n)]
    (.readFully f b)
    (String. b "UTF-8")))

(defn- skip! [^RandomAccessFile f n] (.seek f (+ (.getFilePointer f) n)))

(declare read-scalar skip-value!)

(defn- skip-array! [^RandomAccessFile f]
  (let [element-type (le-u32 f) n (le-u64 f)]
    (dotimes [_ n] (skip-value! f element-type))))

(defn- skip-value! [^RandomAccessFile f value-type]
  (case (int value-type)
    0 (skip! f 1) 1 (skip! f 1) 2 (skip! f 2) 3 (skip! f 2)
    4 (skip! f 4) 5 (skip! f 4) 6 (skip! f 4) 7 (skip! f 1)
    8 (skip! f (le-u64 f)) 9 (skip-array! f) 10 (skip! f 8) 11 (skip! f 8) 12 (skip! f 8)
    (throw (ex-info "unknown GGUF metadata value type" {:gguf/value-type value-type}))))

(defn- read-scalar [^RandomAccessFile f value-type]
  (case (int value-type)
    0 (u8 f) 1 (.readByte f) 2 (do (skip! f 2) :uint16) 3 (do (skip! f 2) :int16)
    4 (le-u32 f) 5 (unchecked-int (le-u32 f)) 6 (double (le-f32 f))
    7 (not (zero? (u8 f))) 8 (read-string* f) 10 (le-u64 f) 11 (le-u64 f)
    12 (do (skip! f 8) :float64)
    (throw (ex-info "unknown GGUF scalar value type" {:gguf/value-type value-type}))))

(def ^:private materialize-array-keys
  ;; scores/token_type are read by llama.cpp's SPM-unigram path; this BPE v1
  ;; only needs tokens+merges (see kotodama.inference.tokenizer docstring).
  #{"tokenizer.ggml.tokens" "tokenizer.ggml.merges"
    "gemma4.attention.sliding_window_pattern"})

(defn- read-array-values! [^RandomAccessFile f]
  (let [element-type (le-u32 f) n (le-u64 f)]
    (vec (repeatedly n #(read-scalar f element-type)))))

(defn- align-up [n alignment]
  (let [rem (mod n alignment)]
    (if (zero? rem) n (+ n (- alignment rem)))))

(defn read-gguf!
  "Read GGUF metadata (scalars fully, `materialize-array-keys` arrays fully,
  all other arrays skipped) plus a tensor index restricted to `wanted` names.
  Single sequential pass over the header; tensor payload bytes are untouched."
  [path wanted]
  (with-open [f (RandomAccessFile. path "r")]
    (let [magic (String. (byte-array [(byte (u8 f)) (byte (u8 f)) (byte (u8 f)) (byte (u8 f))]) "US-ASCII")
          _version (le-u32 f)
          tensor-count (le-u64 f)
          kv-count (le-u64 f)]
      (when-not (= "GGUF" magic) (throw (ex-info "not a GGUF file" {:path path :magic magic})))
      (let [metadata (atom {})]
        (dotimes [_ kv-count]
          (let [k (read-string* f) t (le-u32 f)]
            (if (= 9 (int t))
              (if (contains? materialize-array-keys k)
                (swap! metadata assoc k (read-array-values! f))
                (skip-array! f))
              (swap! metadata assoc k (read-scalar f t)))))
        (let [tensors (atom {})]
          (dotimes [_ tensor-count]
            (let [name (read-string* f)
                  n-dims (le-u32 f)
                  dims (vec (repeatedly n-dims #(le-u64 f)))
                  tensor-type (le-u32 f)
                  offset (le-u64 f)]
              (when (wanted name)
                (swap! tensors assoc name {:shape dims :type tensor-type :offset offset}))))
          (let [alignment (long (get @metadata "general.alignment" 32))
                tensor-data-start (align-up (.getFilePointer f) alignment)]
            {:gguf/metadata @metadata
             :gguf/tensors @tensors
             :gguf/tensor-data-start tensor-data-start}))))))

;; ---------------------------------------------------------------------------
;; row-batched dequantize + dot: decode every weight row exactly once per
;; generation step, dot it against every sequence position in one pass. This
;; is what keeps recompute-from-scratch (no KV-cache) tractable: per-step cost
;; is dominated by (num-rows * row-width) dequant work, independent of how
;; many positions are in the batch.
;; ---------------------------------------------------------------------------

(defn- row-byte-count [row-width tensor-type]
  (case (int tensor-type)
    12 (gguf/q4-k-row-byte-count row-width)
    14 (gguf/q6-k-row-byte-count row-width)
    (throw (ex-info "unsupported row tensor type (expected Q4_K or Q6_K)" {:type tensor-type}))))

;; `kotodama.inference.gguf`'s q4/q6 block decoders are the portable
;; correctness reference (persistent-vector output, `partition`/`mapcat`
;; internally). A generation step decodes hundreds of thousands of rows
;; (every projection row in every one of the real 42 blocks, plus the full
;; 262144-row vocab for greedy argmax every step), so the vector/seq
;; allocation cost is the dominant term in a step's wall-clock time. These
;; array-only reimplementations are byte-for-byte the same math (see the
;; `decode-row-matches-portable?` self-check called once at startup in
;; `-main`), just written straight into a preallocated `double[]` with no
;; boxing, no `nth`, no seq walk.

(defn- u8b ^long [^bytes bytes i] (bit-and 0xff (long (aget bytes i))))
(defn- i8b ^long [^bytes bytes i] (let [x (u8b bytes i)] (if (> x 127) (- x 256) x)))
(defn- le-u16b ^long [^bytes bytes i] (+ (u8b bytes i) (bit-shift-left (u8b bytes (inc i)) 8)))

(defn- q4-k-scale ^long [^bytes b scales-off j]
  (if (< j 4)
    (bit-and (u8b b (+ scales-off j)) 63)
    (bit-or (bit-and (u8b b (+ scales-off j 4)) 0x0f)
            (bit-shift-left (bit-shift-right (u8b b (+ scales-off (- j 4))) 6) 4))))

(defn- q4-k-min ^long [^bytes b scales-off j]
  (if (< j 4)
    (bit-and (u8b b (+ scales-off j 4)) 63)
    (bit-or (bit-shift-right (u8b b (+ scales-off j 4)) 4)
            (bit-shift-left (bit-shift-right (u8b b (+ scales-off j)) 6) 4))))

(defn- decode-q4-k-row! [^bytes row-bytes ^doubles out row-width]
  (let [block-count (quot row-width gguf/qk-k)]
    (dotimes [block block-count]
      (let [bo (* block gguf/q4-k-block-bytes)
            out-base (* block gguf/qk-k)
            scales-off (+ bo 4)
            d (gguf/fp16->double (le-u16b row-bytes bo))
            dmin (gguf/fp16->double (le-u16b row-bytes (+ bo 2)))]
        (loop [group 0 is 0]
          (when (< group 4)
            (let [d1 (* d (q4-k-scale row-bytes scales-off is))
                  d2 (* d (q4-k-scale row-bytes scales-off (inc is)))
                  min1 (* dmin (q4-k-min row-bytes scales-off is))
                  min2 (* dmin (q4-k-min row-bytes scales-off (inc is)))
                  base (+ out-base (* group 64))
                  q-base (+ bo 16 (* group 32))]
              (dotimes [l 32]
                (let [q (u8b row-bytes (+ q-base l))]
                  (aset out (+ base l) (double (- (* d1 (bit-and q 0x0f)) min1)))
                  (aset out (+ base l 32) (double (- (* d2 (bit-shift-right q 4)) min2)))))
              (recur (inc group) (+ is 2)))))))
    out))

(defn- decode-q6-k-row! [^bytes row-bytes ^doubles out row-width]
  (let [block-count (quot row-width gguf/qk-k)]
    (dotimes [block block-count]
      (let [bo (* block gguf/q6-k-block-bytes)
            out-base (* block gguf/qk-k)
            d (gguf/fp16->double (le-u16b row-bytes (+ bo 208)))]
        (dotimes [group 2]
          (let [base (+ out-base (* group 128))
                ql-base (+ bo (* group 64))
                qh-base (+ bo 128 (* group 32))
                scale-base (+ bo 192)]
            (dotimes [l 32]
              (let [is (quot l 16)
                    ql0 (u8b row-bytes (+ ql-base l))
                    ql32 (u8b row-bytes (+ ql-base 32 l))
                    qh (u8b row-bytes (+ qh-base l))
                    q1 (- (bit-or (bit-and ql0 0x0f) (bit-shift-left (bit-and (bit-shift-right qh 0) 0x03) 4)) 32)
                    q2 (- (bit-or (bit-and ql32 0x0f) (bit-shift-left (bit-and (bit-shift-right qh 2) 0x03) 4)) 32)
                    q3 (- (bit-or (bit-shift-right ql0 4) (bit-shift-left (bit-and (bit-shift-right qh 4) 0x03) 4)) 32)
                    q4 (- (bit-or (bit-shift-right ql32 4) (bit-shift-left (bit-and (bit-shift-right qh 6) 0x03) 4)) 32)]
                (aset out (+ base l) (double (* d (i8b row-bytes (+ scale-base is 0)) q1)))
                (aset out (+ base l 32) (double (* d (i8b row-bytes (+ scale-base is 2)) q2)))
                (aset out (+ base l 64) (double (* d (i8b row-bytes (+ scale-base is 4)) q3)))
                (aset out (+ base l 96) (double (* d (i8b row-bytes (+ scale-base is 6)) q4)))))))))
    out))

(defn- decode-row ^doubles [^bytes row-bytes tensor-type row-width]
  (let [out (double-array row-width)]
    (case (int tensor-type)
      12 (decode-q4-k-row! row-bytes out row-width)
      14 (decode-q6-k-row! row-bytes out row-width)
      (throw (ex-info "unsupported row tensor type (expected Q4_K or Q6_K)" {:type tensor-type})))))

(defn decode-row-matches-portable?
  "Self-check: array-fast decode == `kotodama.inference.gguf`'s portable
  vector decode, for one real row of `tensor`. Called once at generation
  startup; throws on any mismatch instead of silently trusting the fast path."
  [^RandomAccessFile f tensor-data-start tensor row-width row-index]
  (let [tensor-type (long (:type tensor))
        row-bytes-n (row-byte-count row-width tensor-type)
        row-offset (case (int tensor-type)
                     12 (gguf/q4-k-row-byte-offset row-index row-width)
                     14 (gguf/q6-k-row-byte-offset row-index row-width))
        row-buf (byte-array row-bytes-n)]
    (.seek f (+ (long tensor-data-start) (long (:offset tensor)) (long row-offset)))
    (.readFully f row-buf)
    (let [reference (case (int tensor-type)
                      12 (gguf/q4-k-blocks->values row-buf)
                      14 (gguf/q6-k-blocks->values row-buf))
          fast (vec (decode-row row-buf tensor-type row-width))]
      (= reference fast))))

(defn- project-all-rows
  "tensor: {:shape [row-width num-rows] :type :offset}. inputs: vector of
  Clojure vectors (or double-arrays), one per sequence position, each of
  length row-width. Returns a vector of double-arrays, one per position, each
  of length num-rows."
  [^RandomAccessFile f tensor-data-start tensor inputs]
  (let [[row-width num-rows] (:shape tensor)
        row-width (long row-width)
        num-rows (long num-rows)
        tensor-type (long (:type tensor))
        row-bytes-n (long (row-byte-count row-width tensor-type))
        n-pos (long (count inputs))
        ^objects in-arr (into-array (map double-array inputs))
        ^objects outputs (into-array (repeatedly n-pos #(double-array num-rows)))
        row-buf (byte-array row-bytes-n)]
    (.seek f (+ (long tensor-data-start) (long (:offset tensor))))
    (dotimes [r num-rows]
      (.readFully f row-buf)
      (let [row-d (decode-row row-buf tensor-type row-width)]
        (dotimes [p n-pos]
          (let [^doubles in (aget in-arr p)
                ^doubles out (aget outputs p)
                acc (double (loop [i (long 0) s (double 0.0)]
                              (if (< i row-width)
                                (recur (unchecked-inc i) (+ s (* (aget row-d i) (aget in i))))
                                s)))]
            (aset out r acc)))))
    (vec outputs)))

(defn- read-f32-vector [^RandomAccessFile f tensor-data-start tensor]
  (let [n (long (first (:shape tensor)))]
    (.seek f (+ (long tensor-data-start) (long (:offset tensor))))
    (vec (repeatedly n #(double (le-f32 f))))))

(defn- read-embedding-row [^RandomAccessFile f tensor-data-start tensor row-index hidden-size]
  (let [tensor-type (long (:type tensor))
        offset (case (int tensor-type)
                 12 (gguf/q4-k-row-byte-offset row-index hidden-size)
                 14 (gguf/q6-k-row-byte-offset row-index hidden-size)
                 (throw (ex-info "unsupported embedding tensor type" {:type tensor-type})))
        n-bytes (row-byte-count hidden-size tensor-type)
        row-buf (byte-array n-bytes)]
    (.seek f (+ (long tensor-data-start) (long (:offset tensor)) (long offset)))
    (.readFully f row-buf)
    (vec (decode-row row-buf tensor-type hidden-size)))) ; -> Clojure vector of doubles

;; ---------------------------------------------------------------------------
;; the numerically-stable full block: attn_norm -> Q/K/V -> QK-norm -> RoPE
;; (per-layer local/global dim+theta) -> causal attention -> attn_output ->
;; post_attention_norm -> residual -> ffn_norm -> gated MLP -> post_ffw_norm
;; -> residual. Operates on all sequence positions in the batch at once.
;; ---------------------------------------------------------------------------

(defn- tensor-name [layer-index suffix] (str "blk." layer-index "." suffix ".weight"))

(defn- global-layer? [layer-index swa-pattern]
  ;; swa-pattern[i] = true means sliding-window/local; false means global.
  (false? (nth swa-pattern layer-index)))

(defn stable-block-forward
  "hidden-vectors: vector of T Clojure double-vectors (each length
  hidden-size), one per sequence position. Returns the same shape."
  [^RandomAccessFile f tensor-data-start tensors expected swa-pattern layer-index hidden-vectors]
  (let [hidden-size (long (:gemma4/embedding-length expected))
        head-count (long (:gemma4/attention-head-count expected))
        kv-head-count (long (:gemma4/attention-head-count-kv expected))
        heads-per-kv (long (/ head-count kv-head-count))
        global? (global-layer? layer-index swa-pattern)
        rope-dim (if global? (:gemma4/rope-dimension-count expected) (:gemma4/rope-dimension-count-swa expected))
        theta (if global? (:gemma4/rope-freq-base expected) (:gemma4/rope-freq-base-swa expected))
        t* (fn [suffix] (get tensors (tensor-name layer-index suffix)))
        attn-norm-w (read-f32-vector f tensor-data-start (t* "attn_norm"))
        post-attn-norm-w (read-f32-vector f tensor-data-start (t* "post_attention_norm"))
        ffn-norm-w (read-f32-vector f tensor-data-start (t* "ffn_norm"))
        post-ffn-norm-w (read-f32-vector f tensor-data-start (t* "post_ffw_norm"))
        q-norm-w (read-f32-vector f tensor-data-start (t* "attn_q_norm"))
        k-norm-w (read-f32-vector f tensor-data-start (t* "attn_k_norm"))
        q-tensor (t* "attn_q") k-tensor (t* "attn_k") v-tensor (t* "attn_v")
        q-width (long (second (:shape q-tensor)))
        k-width (long (second (:shape k-tensor)))
        v-width (long (second (:shape v-tensor)))
        q-head-dim (/ q-width head-count)
        kv-head-dim (/ k-width kv-head-count)
        _ (when-not (= q-head-dim kv-head-dim (/ v-width kv-head-count))
            (throw (ex-info "Gemma4 Q/K/V derived head dims differ"
                            {:layer layer-index :q-head-dim q-head-dim :kv-head-dim kv-head-dim
                             :v-head-dim (/ v-width kv-head-count)})))
        normed (mapv #(ops/gemma-rmsnorm-values % attn-norm-w) hidden-vectors)
        q-all (project-all-rows f tensor-data-start q-tensor normed)
        k-all (project-all-rows f tensor-data-start k-tensor normed)
        v-all (project-all-rows f tensor-data-start v-tensor normed)
        slice-head (fn [^doubles arr h dim]
                     (let [start (int (* (long h) (long dim)))
                           end (int (* (long (inc h)) (long dim)))]
                       (vec (java.util.Arrays/copyOfRange arr start end))))
        ;; per-position, per-head: QK-norm then RoPE. Position is 1-based
        ;; (matches this repo's existing verified convention); RoPE's score is
        ;; provably invariant to a constant offset applied to every position.
        q-heads (mapv (fn [pos ^doubles q-arr]
                        (mapv (fn [h]
                                (-> (slice-head q-arr h q-head-dim)
                                    (ops/gemma-rmsnorm-values q-norm-w)
                                    (ops/rope-interleaved-values (inc pos) rope-dim theta)))
                              (range head-count)))
                      (range) q-all)
        k-heads (mapv (fn [pos ^doubles k-arr]
                        (mapv (fn [h]
                                (-> (slice-head k-arr h kv-head-dim)
                                    (ops/gemma-rmsnorm-values k-norm-w)
                                    (ops/rope-interleaved-values (inc pos) rope-dim theta)))
                              (range kv-head-count)))
                      (range) k-all)
        v-heads (mapv (fn [^doubles v-arr]
                        (mapv (fn [h] (slice-head v-arr h kv-head-dim)) (range kv-head-count)))
                      v-all)
        t-count (count hidden-vectors)
        attn-concat (mapv
                     (fn [pos]
                       (vec (mapcat
                             (fn [h]
                               (let [kv-h (quot h heads-per-kv)
                                     q-head (nth (nth q-heads pos) h)
                                     k-heads-upto (mapv #(nth (nth k-heads %) kv-h) (range (inc pos)))
                                     v-heads-upto (mapv #(nth (nth v-heads %) kv-h) (range (inc pos)))]
                                 (:values (ops/causal-attention-values q-head k-heads-upto v-heads-upto))))
                             (range head-count))))
                     (range t-count))
        attn-out (project-all-rows f tensor-data-start (t* "attn_output") attn-concat)
        post-attn (mapv #(ops/gemma-rmsnorm-values (vec %) post-attn-norm-w) attn-out)
        residual1 (mapv ops/add-values hidden-vectors post-attn)
        ffn-normed (mapv #(ops/gemma-rmsnorm-values % ffn-norm-w) residual1)
        gate-all (project-all-rows f tensor-data-start (t* "ffn_gate") ffn-normed)
        up-all (project-all-rows f tensor-data-start (t* "ffn_up") ffn-normed)
        activation (mapv (fn [^doubles g ^doubles u] (ops/gated-mlp-activation-values (vec g) (vec u))) gate-all up-all)
        down-all (project-all-rows f tensor-data-start (t* "ffn_down") activation)
        post-ffn (mapv #(ops/gemma-rmsnorm-values (vec %) post-ffn-norm-w) down-all)
        residual2 (mapv ops/add-values residual1 post-ffn)]
    residual2))

;; ---------------------------------------------------------------------------
;; wanted-tensor set, tokenizer materialization, full-model forward, and the
;; JVM `generate` entry point wired through the portable decode/tokenizer/
;; sample namespaces.
;; ---------------------------------------------------------------------------

(defn- layer-tensor-names [layer-index]
  (mapv #(tensor-name layer-index %)
        ["attn_norm" "attn_q" "attn_k" "attn_v" "attn_q_norm" "attn_k_norm"
         "attn_output" "post_attention_norm" "ffn_norm" "ffn_gate" "ffn_up"
         "ffn_down" "post_ffw_norm"]))

(defn tokenizer-vocab-data
  "Pull tokenizer.cljc's `build` input straight out of raw GGUF metadata."
  [metadata]
  {:tokens (get metadata "tokenizer.ggml.tokens")
   :merges (get metadata "tokenizer.ggml.merges")
   :bos-token-id (long (get metadata "tokenizer.ggml.bos_token_id"))
   :eos-token-id (long (get metadata "tokenizer.ggml.eos_token_id"))
   :add-bos-token? (boolean (get metadata "tokenizer.ggml.add_bos_token" true))
   :unknown-token-id (long (get metadata "tokenizer.ggml.unknown_token_id" 3))})

(defn model-expected
  "Model-shape facts read from the file's own metadata (never assumed)."
  [metadata]
  {:gemma4/block-count (long (get metadata "gemma4.block_count"))
   :gemma4/embedding-length (long (get metadata "gemma4.embedding_length"))
   :gemma4/feed-forward-length (long (get metadata "gemma4.feed_forward_length"))
   :gemma4/attention-head-count (long (get metadata "gemma4.attention.head_count"))
   :gemma4/attention-head-count-kv (long (get metadata "gemma4.attention.head_count_kv"))
   :gemma4/rope-dimension-count (long (get metadata "gemma4.rope.dimension_count"))
   :gemma4/rope-dimension-count-swa (long (get metadata "gemma4.rope.dimension_count_swa"))
   :gemma4/rope-freq-base (double (get metadata "gemma4.rope.freq_base"))
   :gemma4/rope-freq-base-swa (double (get metadata "gemma4.rope.freq_base_swa"))
   :gemma4/final-logit-softcapping (double (get metadata "gemma4.final_logit_softcapping" 30.0))})

(defn- softcap [x cap]
  (* cap (Math/tanh (/ (double x) (double cap)))))

(defn full-forward-logits
  "Run every real transformer block over `token-ids` (recompute from scratch)
  and return the dense full-vocab logit vector for the *last* position."
  [^RandomAccessFile f tensor-data-start tensors expected swa-pattern token-ids]
  (let [hidden-size (:gemma4/embedding-length expected)
        block-count (:gemma4/block-count expected)
        embd-tensor (get tensors "token_embd.weight")
        output-norm-w (read-f32-vector f tensor-data-start (get tensors "output_norm.weight"))
        hidden0 (mapv #(read-embedding-row f tensor-data-start embd-tensor % hidden-size) token-ids)
        final-hidden (reduce
                      (fn [hidden layer-index]
                        (stable-block-forward f tensor-data-start tensors expected swa-pattern layer-index hidden))
                      hidden0
                      (range block-count))
        last-hidden (ops/gemma-rmsnorm-values (peek final-hidden) output-norm-w)
        [logits] (project-all-rows f tensor-data-start embd-tensor [last-hidden])
        cap (:gemma4/final-logit-softcapping expected)]
    (mapv #(softcap % cap) logits)))

(def default-model "gemma4:e4b")
(def default-prompt "The capital of France is")

(defn- wanted-tensor-names [block-count]
  (into #{"token_embd.weight" "output_norm.weight"}
        (mapcat layer-tensor-names)
        (range block-count)))

(defn generate
  "opts:
    :kotodama/model-path  resolved GGUF path (or supply :kotodama/model + a
                          local Ollama tag and it is resolved via `ollama show`)
    :kotodama/model
    :kotodama/prompt
    :kotodama/max-tokens
    :kotodama/on-token    optional (fn [token-id token-text elapsed-nanos])
  Returns the `kotodama.inference.decode/generate` result map plus timing."
  [{:keys [kotodama/model-path kotodama/model kotodama/prompt kotodama/max-tokens kotodama/on-token]
    :or {model default-model prompt default-prompt max-tokens 16}}]
  (let [path (or model-path (verify-gguf/gguf-path model))
        ;; block-count is not known yet, so pass a permissive `wanted` that
        ;; covers up to 128 layers -- cheap (name-string compare only), and
        ;; correct regardless of this model's real depth.
        {:gguf/keys [metadata tensors tensor-data-start]} (read-gguf! path (wanted-tensor-names 128))
        expected (model-expected metadata)
        swa-pattern (get metadata "gemma4.attention.sliding_window_pattern")
        tok (tokenizer/build (tokenizer-vocab-data metadata))
        ;; tokenizer.ggml.eot_token_id is not present in every GGUF conversion
        ;; (this real gemma4:e4b file omits it) -- `into #{}` tolerates the
        ;; resulting duplicate with eos-token-id where `#{a b}` would throw.
        eos-ids (into #{(:kotodama.tokenizer/eos-token-id tok)}
                      (some-> (get metadata "tokenizer.ggml.eot_token_id") long vector))]
    (with-open [f (RandomAccessFile. path "r")]
      (let [hidden-size (:gemma4/embedding-length expected)
            q0-tensor (get tensors "blk.0.attn_q.weight")
            embd-tensor (get tensors "token_embd.weight")]
        (when-not (and (decode-row-matches-portable? f tensor-data-start q0-tensor hidden-size 0)
                       (decode-row-matches-portable? f tensor-data-start embd-tensor hidden-size
                                                      (:kotodama.tokenizer/bos-token-id tok)))
          (throw (ex-info "fast array row decode diverged from the portable kotodama.inference.gguf decode"
                          {:tensor ["blk.0.attn_q.weight" "token_embd.weight"]}))))
      (let [forward-fn (fn [token-ids]
                          (full-forward-logits f tensor-data-start tensors expected swa-pattern token-ids))
            result (decode/generate {:kotodama/tokenizer tok
                                      :kotodama/forward-fn forward-fn
                                      :kotodama/prompt prompt
                                      :kotodama/max-tokens max-tokens
                                      :kotodama/eos-token-ids eos-ids
                                      :kotodama/on-token on-token})]
        (assoc result
               :kotodama/model model
               :kotodama/path path
               :gemma4/block-count (:gemma4/block-count expected))))))

(defn -main [& _]
  (let [model (or (System/getenv "KOTODAMA_VERIFY_MODEL") default-model)
        model-path (System/getenv "KOTODAMA_VERIFY_GGUF_PATH")
        prompt (or (System/getenv "KOTODAMA_VERIFY_PROMPT") default-prompt)
        max-tokens (Long/parseLong (or (System/getenv "KOTODAMA_VERIFY_MAX_TOKENS") "16"))
        t0 (System/nanoTime)
        result (generate {:kotodama/model model
                          :kotodama/model-path model-path
                          :kotodama/prompt prompt
                          :kotodama/max-tokens max-tokens
                          :kotodama/on-token (fn [token-id token-text elapsed-nanos]
                                               (println (format "  [+%.1fs] token %d %s"
                                                                 (/ elapsed-nanos 1.0e9)
                                                                 token-id
                                                                 (pr-str token-text)))
                                               (flush))})
        total-sec (/ (- (System/nanoTime) t0) 1.0e9)]
    (println "prompt:" (pr-str prompt))
    (println "generated:" (pr-str (:kotodama/text result)))
    (println "stop-reason:" (:kotodama/stop-reason result))
    (println "block-count:" (:gemma4/block-count result))
    (println "generated-token-count:" (count (:kotodama/generated-token-ids result)))
    (println "total-seconds:" total-sec)
    (println "tokens-per-second:" (/ (count (:kotodama/generated-token-ids result)) total-sec))
    (prn {:kotodama/gemma4-e4b-generate-smoke :ok
          :kotodama/prompt prompt
          :kotodama/generated-text (:kotodama/text result)
          :kotodama/stop-reason (:kotodama/stop-reason result)
          :gemma4/block-count (:gemma4/block-count result)
          :kotodama/total-seconds total-sec})))
