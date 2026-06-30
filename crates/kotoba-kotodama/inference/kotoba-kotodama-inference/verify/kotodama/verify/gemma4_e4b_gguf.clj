(ns kotodama.verify.gemma4-e4b-gguf
  "Direct artifact verification for the local gemma4:e4b GGUF model.

  This reads the GGUF blob itself, not Ollama's generate API. It is the first
  direct-loader gate: model identity and architecture metadata must be available
  to kotodama before tensor loading/decoding can move from a host adapter to
  torch-clj + num-clj."
  (:require [clojure.string :as str]
            [kotodama.inference.gguf :as gguf]
            [kotodama.inference.gemma :as gemma])
  (:import (java.io RandomAccessFile)
           (java.lang ProcessBuilder)))

(def default-model "gemma4:e4b")

(defn- u8 [^RandomAccessFile f]
  (.readUnsignedByte f))

(defn- le-u32 [^RandomAccessFile f]
  (long (+ (u8 f)
           (bit-shift-left (u8 f) 8)
           (bit-shift-left (u8 f) 16)
           (bit-shift-left (u8 f) 24))))

(defn- le-f32 [^RandomAccessFile f]
  (Float/intBitsToFloat (unchecked-int (le-u32 f))))

(defn- le-u64 [^RandomAccessFile f]
  (let [lo (le-u32 f)
        hi (le-u32 f)]
    (+ lo (* hi 4294967296))))

(defn- read-string* [^RandomAccessFile f]
  (let [n (le-u64 f)
        b (byte-array n)]
    (.readFully f b)
    (String. b "UTF-8")))

(defn- skip! [^RandomAccessFile f n]
  (.seek f (+ (.getFilePointer f) n)))

(declare read-value)
(declare skip-value!)

(defn- skip-string! [^RandomAccessFile f]
  (skip! f (le-u64 f)))

(defn- read-array [^RandomAccessFile f]
  (let [element-type (le-u32 f)
        n (le-u64 f)]
    (dotimes [_ n]
      (skip-value! f element-type))
    {:gguf/array-type element-type
     :gguf/array-count n}))

(defn- skip-array! [^RandomAccessFile f]
  (let [element-type (le-u32 f)
        n (le-u64 f)]
    (dotimes [_ n]
      (skip-value! f element-type))))

(defn- skip-value! [^RandomAccessFile f value-type]
  (case value-type
    0 (skip! f 1)
    1 (skip! f 1)
    2 (skip! f 2)
    3 (skip! f 2)
    4 (skip! f 4)
    5 (skip! f 4)
    6 (skip! f 4)
    7 (skip! f 1)
    8 (skip-string! f)
    9 (skip-array! f)
    10 (skip! f 8)
    11 (skip! f 8)
    12 (skip! f 8)
    (throw (ex-info "unknown GGUF metadata value type"
                    {:gguf/value-type value-type}))))

(defn- read-value [^RandomAccessFile f value-type]
  (case value-type
    0 (u8 f)
    1 (.readByte f)
    2 (do (skip! f 2) :uint16)
    3 (do (skip! f 2) :int16)
    4 (le-u32 f)
    5 (le-u32 f)
    6 (double (le-f32 f))
    7 (not (zero? (u8 f)))
    8 (read-string* f)
    9 (read-array f)
    10 (le-u64 f)
    11 (le-u64 f)
    12 (do (skip! f 8) :float64)
    (throw (ex-info "unknown GGUF metadata value type"
                    {:gguf/value-type value-type}))))

(def interesting-keys
  #{"general.architecture"
    "general.alignment"
    "general.file_type"
    "general.parameter_count"
    "general.quantization_version"
    "gemma4.block_count"
    "gemma4.context_length"
    "gemma4.embedding_length"
    "gemma4.feed_forward_length"
    "gemma4.attention.head_count"
    "gemma4.attention.head_count_kv"
    "gemma4.attention.key_length"
    "gemma4.attention.value_length"
    "gemma4.attention.sliding_window"
    "gemma4.rope.dimension_count"
    "gemma4.rope.dimension_count_swa"
    "gemma4.rope.freq_base"
    "gemma4.rope.freq_base_swa"
    "tokenizer.ggml.bos_token_id"
    "tokenizer.ggml.eos_token_id"})

(defn- align-up [n alignment]
  (let [rem (mod n alignment)]
    (if (zero? rem) n (+ n (- alignment rem)))))

(defn read-gguf-metadata [path]
  (with-open [f (RandomAccessFile. path "r")]
    (let [magic (String. (byte-array [(byte (u8 f))
                                      (byte (u8 f))
                                      (byte (u8 f))
                                      (byte (u8 f))])
                         "US-ASCII")
          version (le-u32 f)
          tensor-count (le-u64 f)
          kv-count (le-u64 f)]
      (when-not (= "GGUF" magic)
        (throw (ex-info "not a GGUF file" {:path path :magic magic})))
      (loop [i 0
             metadata {}]
        (if (= i kv-count)
          {:gguf/version version
           :gguf/tensor-count tensor-count
           :gguf/metadata-count kv-count
           :gguf/metadata metadata}
          (let [k (read-string* f)
                t (le-u32 f)]
            (if (= "tokenizer.ggml.merges" k)
              {:gguf/version version
               :gguf/tensor-count tensor-count
               :gguf/metadata-count kv-count
               :gguf/metadata (assoc metadata "tokenizer.ggml.merges" :present)}
              (let [v (read-value f t)]
                (recur (inc i)
                       (cond-> metadata
                         (contains? interesting-keys k) (assoc k v)))))))))))

(defn read-gguf-tensor-index [path wanted]
  (with-open [f (RandomAccessFile. path "r")]
    (let [magic (String. (byte-array [(byte (u8 f))
                                      (byte (u8 f))
                                      (byte (u8 f))
                                      (byte (u8 f))])
                         "US-ASCII")
          version (le-u32 f)
          tensor-count (le-u64 f)
          kv-count (le-u64 f)
          metadata (atom {})]
      (when-not (= "GGUF" magic)
        (throw (ex-info "not a GGUF file" {:path path :magic magic})))
      (dotimes [_ kv-count]
        (let [k (read-string* f)
              t (le-u32 f)]
          (if (contains? interesting-keys k)
            (swap! metadata assoc k (read-value f t))
            (skip-value! f t))))
      (let [selected (atom {})
            type-counts (atom {})
            tensor-infos (atom [])]
        (dotimes [i tensor-count]
          (let [name (read-string* f)
                n-dims (le-u32 f)
                dims (vec (repeatedly n-dims #(le-u64 f)))
                tensor-type (le-u32 f)
                offset (le-u64 f)]
            (swap! type-counts update tensor-type (fnil inc 0))
            (swap! tensor-infos conj {:name name
                                      :index i
                                      :shape dims
                                      :type tensor-type
                                      :offset offset})
            (when (contains? wanted name)
              (swap! selected assoc name {:index i
                                          :shape dims
                                          :type tensor-type
                                          :offset offset}))))
        (let [alignment (long (get @metadata "general.alignment" 32))
              tensor-data-start (align-up (.getFilePointer f) alignment)
              file-len (.length f)
              sorted-infos (sort-by :offset @tensor-infos)
              selected-with-spans
              (into {}
                    (for [[name tensor] @selected
                          :let [next-tensor (first (filter #(> (:offset %) (:offset tensor))
                                                           sorted-infos))
                                span (if next-tensor
                                       (- (:offset next-tensor) (:offset tensor))
                                       (- file-len tensor-data-start (:offset tensor)))]]
                      [name (assoc tensor :span-bytes span)]))]
          {:gguf/version version
           :gguf/tensor-count tensor-count
           :gguf/metadata-count kv-count
           :gguf/alignment alignment
           :gguf/tensor-data-start tensor-data-start
           :gguf/tensor-type-counts (into (sorted-map) @type-counts)
           :gguf/tensors selected-with-spans})))))

(defn- process-lines [cmd]
  (let [process (-> (ProcessBuilder. ^java.util.List cmd)
                    (.redirectErrorStream true)
                    (.start))
        out (slurp (.getInputStream process))
        exit (.waitFor process)]
    (when-not (zero? exit)
      (throw (ex-info "command failed" {:command cmd :exit exit :output out})))
    (str/split-lines out)))

(defn ollama-gguf-path [model]
  (let [lines (process-lines ["ollama" "show" model "--modelfile"])
        from-line (first (filter #(str/starts-with? % "FROM ") lines))]
    (when-not from-line
      (throw (ex-info "could not resolve Ollama GGUF blob path"
                      {:model model :lines lines})))
    (subs from-line 5)))

(defn- require= [actual expected key]
  (when-not (= expected actual)
    (throw (ex-info "GGUF metadata mismatch"
                    {:key key :expected expected :actual actual}))))

(defn- require-tensors! [actual expected]
  (doseq [[name spec] expected
          :let [tensor (get actual name)]]
    (when-not tensor
      (throw (ex-info "required GGUF tensor missing"
                      {:tensor name
                       :available (sort (keys actual))})))
    (require= (:shape tensor) (:shape spec) [:tensor name :shape])
    (require= (:type tensor) (:type spec) [:tensor name :type])
    (when (neg? (:offset tensor))
      (throw (ex-info "GGUF tensor has negative offset"
                      {:tensor name :offset (:offset tensor)})))))

(defn- bytes->hex [bytes]
  (apply str (map #(format "%02x" (bit-and 0xff %)) bytes)))

(defn- read-tensor-bytes [path tensor-data-start tensor n]
  (with-open [f (RandomAccessFile. path "r")]
    (.seek f (+ tensor-data-start (:offset tensor)))
    (let [bytes (byte-array n)]
      (.readFully f bytes)
      (vec bytes))))

(defn- read-tensor-range [path tensor-data-start tensor offset n]
  (with-open [f (RandomAccessFile. path "r")]
    (.seek f (+ tensor-data-start (:offset tensor) offset))
    (let [bytes (byte-array n)]
      (.readFully f bytes)
      (vec bytes))))

(defn- read-f32-sample [path tensor-data-start tensor n]
  (with-open [f (RandomAccessFile. path "r")]
    (.seek f (+ tensor-data-start (:offset tensor)))
    (vec (repeatedly n #(double (le-f32 f))))))

(defn- round6 [x]
  (/ (Math/round (* 1000000.0 x)) 1000000.0))

(defn- q6-k-sample [path tensor-data-start tensor]
  (let [values (gguf/q6-k-block->values
                (read-tensor-range path tensor-data-start tensor 0 gguf/q6-k-block-bytes))]
    {:block 0
     :value-count (count values)
     :sample (mapv round6 (take 16 values))
     :sum (round6 (reduce + values))
     :min (round6 (reduce min values))
     :max (round6 (reduce max values))}))

(defn- q4-k-sample [path tensor-data-start tensor]
  (let [values (gguf/q4-k-block->values
                (read-tensor-range path tensor-data-start tensor 0 gguf/q4-k-block-bytes))]
    {:block 0
     :value-count (count values)
     :sample (mapv round6 (take 16 values))
     :sum (round6 (reduce + values))
     :min (round6 (reduce min values))
     :max (round6 (reduce max values))}))

(defn- payload-samples [path tensor-index]
  (let [tensor-data-start (:gguf/tensor-data-start tensor-index)]
    {:gguf/payload-prefix-hex
     (into {}
           (for [[name tensor] (:gguf/tensors tensor-index)]
             [name (bytes->hex (read-tensor-bytes path tensor-data-start tensor 32))]))
     :gguf/f32-samples
     (into {}
           (for [[name tensor] (:gguf/tensors tensor-index)
                 :when (= 0 (:type tensor))]
             [name (read-f32-sample path tensor-data-start tensor 8)]))
     :gguf/q4-k-samples
     (into {}
           (for [[name tensor] (:gguf/tensors tensor-index)
                 :when (= 12 (:type tensor))]
             [name (q4-k-sample path tensor-data-start tensor)]))
     :gguf/q6-k-samples
     (into {}
           (for [[name tensor] (:gguf/tensors tensor-index)
                 :when (= 14 (:type tensor))]
             [name (q6-k-sample path tensor-data-start tensor)]))}))

(defn- require-payload! [samples expected]
  (require= (:gguf/payload-prefix-hex samples)
            (:gguf/payload-prefix-hex expected)
            :gguf/payload-prefix-hex)
  (require= (:gguf/f32-samples samples)
            (:gguf/f32-samples expected)
            :gguf/f32-samples)
  (when (:gguf/q4-k-samples expected)
    (require= (:gguf/q4-k-samples samples)
              (:gguf/q4-k-samples expected)
              :gguf/q4-k-samples))
  (require= (:gguf/q6-k-samples samples)
            (:gguf/q6-k-samples expected)
            :gguf/q6-k-samples))

(defn- require-spans! [actual expected]
  (let [spans (into {} (map (fn [[name tensor]] [name (:span-bytes tensor)]) actual))]
    (require= spans expected :gguf/tensor-spans)))

(defn -main [& _]
  (let [model (or (System/getenv "KOTODAMA_VERIFY_MODEL") default-model)
        path (or (System/getenv "KOTODAMA_VERIFY_GGUF_PATH")
                 (ollama-gguf-path model))
        parsed (read-gguf-metadata path)
        m (:gguf/metadata parsed)
        expected gemma/gemma4-e4b-expected
        tensor-index (read-gguf-tensor-index path (set (keys (:gguf/required-tensors expected))))
        samples (payload-samples path tensor-index)]
    (require= (:gguf/tensor-count parsed) (:gguf/tensor-count expected) :gguf/tensor-count)
    (require= (get m "general.architecture") (:gguf/architecture expected) :gguf/architecture)
    (require= (get m "general.file_type") (:gguf/file-type expected) :gguf/file-type)
    (require= (get m "general.quantization_version") (:gguf/quantization-version expected) :gguf/quantization-version)
    (require= (get m "gemma4.block_count") (:gemma4/block-count expected) :gemma4/block-count)
    (require= (get m "gemma4.context_length") (:gemma4/context-length expected) :gemma4/context-length)
    (require= (get m "gemma4.embedding_length") (:gemma4/embedding-length expected) :gemma4/embedding-length)
    (require= (get m "gemma4.feed_forward_length") (:gemma4/feed-forward-length expected) :gemma4/feed-forward-length)
    (require= (get m "gemma4.attention.head_count") (:gemma4/attention-head-count expected) :gemma4/attention-head-count)
    (require= (get m "gemma4.attention.head_count_kv") (:gemma4/attention-head-count-kv expected) :gemma4/attention-head-count-kv)
    (require= (get m "gemma4.attention.key_length") (:gemma4/attention-key-length expected) :gemma4/attention-key-length)
    (require= (get m "gemma4.attention.value_length") (:gemma4/attention-value-length expected) :gemma4/attention-value-length)
    (require= (get m "gemma4.attention.sliding_window") (:gemma4/attention-sliding-window expected) :gemma4/attention-sliding-window)
    (require= (get m "gemma4.rope.dimension_count") (:gemma4/rope-dimension-count expected) :gemma4/rope-dimension-count)
    (require= (get m "gemma4.rope.dimension_count_swa") (:gemma4/rope-dimension-count-swa expected) :gemma4/rope-dimension-count-swa)
    (require= (get m "gemma4.rope.freq_base") (:gemma4/rope-freq-base expected) :gemma4/rope-freq-base)
    (require= (get m "gemma4.rope.freq_base_swa") (:gemma4/rope-freq-base-swa expected) :gemma4/rope-freq-base-swa)
    (require= (get m "tokenizer.ggml.bos_token_id") (:tokenizer/bos-token-id expected) :tokenizer/bos-token-id)
    (require= (get m "tokenizer.ggml.eos_token_id") (:tokenizer/eos-token-id expected) :tokenizer/eos-token-id)
    (when-not (= :present (get m "tokenizer.ggml.merges"))
      (throw (ex-info "GGUF tokenizer merge table marker is missing"
                      {:metadata-keys (sort (keys m))})))
    (require= (:gguf/tensor-type-counts tensor-index)
              (:gguf/tensor-type-counts expected)
              :gguf/tensor-type-counts)
    (require-tensors! (:gguf/tensors tensor-index)
                      (:gguf/required-tensors expected))
    (require-spans! (:gguf/tensors tensor-index)
                    (:gguf/expected-tensor-spans expected))
    (require-payload! samples expected)
    (prn {:kotodama/gemma4-e4b-gguf :ok
          :kotodama/model model
          :kotodama/path path
          :gguf/version (:gguf/version parsed)
          :gguf/tensor-count (:gguf/tensor-count parsed)
          :gguf/metadata-count (:gguf/metadata-count parsed)
          :gguf/architecture (get m "general.architecture")
          :gguf/file-type (get m "general.file_type")
          :gguf/parameter-count (get m "general.parameter_count")
          :gguf/tensor-type-counts (:gguf/tensor-type-counts tensor-index)
          :gguf/tensor-data-start (:gguf/tensor-data-start tensor-index)
          :gguf/required-tensors (:gguf/tensors tensor-index)
          :gguf/payload-prefix-hex (:gguf/payload-prefix-hex samples)
          :gguf/f32-samples (:gguf/f32-samples samples)
          :gguf/q4-k-samples (:gguf/q4-k-samples samples)
          :gguf/q6-k-samples (:gguf/q6-k-samples samples)
          :gemma4/block-count (get m "gemma4.block_count")
          :gemma4/context-length (get m "gemma4.context_length")
          :gemma4/embedding-length (get m "gemma4.embedding_length")
          :gemma4/feed-forward-length (get m "gemma4.feed_forward_length")
          :tokenizer/bos-token-id (get m "tokenizer.ggml.bos_token_id")
          :tokenizer/eos-token-id (get m "tokenizer.ggml.eos_token_id")
          :tokenizer/merges :present})))
