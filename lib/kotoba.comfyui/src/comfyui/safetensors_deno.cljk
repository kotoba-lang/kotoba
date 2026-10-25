(ns comfyui.safetensors-deno
  "Validated Deno safetensors reader for direct WebGPU checkpoint execution."
  (:require [num.array :as arr]
            [num.dtype :as dtype]))

(def ^:private dtype-width
  {"BOOL" 1 "U8" 1 "I8" 1 "U16" 2 "I16" 2 "U32" 4 "I32" 4
   "U64" 8 "I64" 8 "F16" 2 "BF16" 2 "F32" 4 "F64" 8})

(defn- nelems [shape] (reduce * 1 shape))

(defn- read-exact-at [file offset length]
  (.seekSync file offset js/Deno.SeekMode.Start)
  (let [output (js/Uint8Array. length)]
    (loop [read 0]
      (if (= read length)
        output
        (let [n (.readSync file (.subarray output read))]
          (when (or (nil? n) (zero? n))
            (throw (ex-info "unexpected EOF in safetensors" {:offset offset
                                                               :length length
                                                               :read read})))
          (recur (+ read n)))))))

(defn open-file [path]
  (let [file (js/Deno.openSync path #js {:read true})]
    (try
      (let [size (.-size (.statSync file))
            prefix (read-exact-at file 0 8)
            view (js/DataView. (.-buffer prefix) (.-byteOffset prefix) 8)
            header-length (js/Number (.getBigUint64 view 0 true))
            data-start (+ 8 header-length)]
        (when (or (> header-length (* 128 1024 1024)) (> data-start size))
          (throw (ex-info "invalid safetensors header" {:path path :header-length header-length})))
        (let [header-bytes (read-exact-at file 8 header-length)
          header-text (.decode (js/TextDecoder.) header-bytes)
          header (js->clj (js/JSON.parse header-text))
          tensors (dissoc header "__metadata__")
              payload (- size data-start)]
          (doseq [[name entry] tensors]
            (let [shape (get entry "shape") dtype-name (get entry "dtype")
                  [start end] (get entry "data_offsets")
                  expected (* (or (dtype-width dtype-name) 0) (nelems shape))]
              (when-not (and (dtype-width dtype-name) (= expected (- end start))
                             (<= 0 start end payload))
                (throw (ex-info "invalid safetensors tensor" {:name name :entry entry})))))
          {:path path :file file :closed? (atom false)
           :file-size size :data-start data-start :tensors tensors
           :stats (atom {:header-bytes (+ 8 header-length)
                         :window-reads 0 :window-bytes 0 :peak-window-bytes 0
                         :direct-uploads 0 :direct-bytes 0 :direct-dtypes {}
                         :decoded-uploads 0 :decoded-elements 0})}))
      (catch :default error
        (.close file)
        (throw error)))))

(defn tensor-names [checkpoint] (vec (sort (keys (:tensors checkpoint)))))

(defn reader-stats [checkpoint] @(:stats checkpoint))

(defn close-file! [checkpoint]
  (when (compare-and-set! (:closed? checkpoint) false true)
    (.close (:file checkpoint)))
  nil)

(defn- tensor-window [checkpoint entry]
  (when @(:closed? checkpoint)
    (throw (ex-info "safetensors file is closed" {:path (:path checkpoint)})))
  (let [[start end] (get entry "data_offsets")
        length (- end start)]
    (swap! (:stats checkpoint)
           #(-> % (update :window-reads inc)
                (update :window-bytes + length)
                (update :peak-window-bytes max length)))
    (read-exact-at (:file checkpoint) (+ (:data-start checkpoint) start) length)))

(defn- bf16->f32 [bits]
  (let [buffer (js/ArrayBuffer. 4)
        view (js/DataView. buffer)]
    (.setUint32 view 0 (bit-shift-left bits 16) true)
    (.getFloat32 view 0 true)))

(defn- decode-values [checkpoint entry]
  (let [bytes (tensor-window checkpoint entry)
        offset 0
        dtype-name (get entry "dtype")
        n (nelems (get entry "shape"))
        view (js/DataView. (.-buffer bytes) (+ (.-byteOffset bytes) offset) (.-byteLength bytes))]
    (mapv (fn [index]
            (case dtype-name
              "F32" (.getFloat32 view (* index 4) true)
              "F64" (.getFloat64 view (* index 8) true)
              "F16" (dtype/f16-bits->f32 (.getUint16 view (* index 2) true))
              "BF16" (bf16->f32 (.getUint16 view (* index 2) true))
              "BOOL" (if (zero? (.getUint8 view index)) 0.0 1.0)
              "U8" (.getUint8 view index)
              "I8" (.getInt8 view index)
              "U16" (.getUint16 view (* index 2) true)
              "I16" (.getInt16 view (* index 2) true)
              "U32" (.getUint32 view (* index 4) true)
              "I32" (.getInt32 view (* index 4) true)
              "U64" (js/Number (.getBigUint64 view (* index 8) true))
              "I64" (js/Number (.getBigInt64 view (* index 8) true))))
          (range n))))

(defn read-tensor
  ([checkpoint backend tensor-name]
   (read-tensor checkpoint backend tensor-name {}))
  ([checkpoint backend tensor-name {:keys [preserve-f16?]}]
  (when @(:closed? checkpoint)
    (throw (ex-info "safetensors file is closed" {:path (:path checkpoint)})))
  (let [entry (get-in checkpoint [:tensors tensor-name])]
    (when-not entry
      (throw (ex-info "tensor absent from safetensors" {:tensor tensor-name
                                                         :path (:path checkpoint)})))
    (let [shape (get entry "shape")
          dtype-name (get entry "dtype")
          upload (case dtype-name
                   "F32" (when-let [f (resolve 'num.deno-gpu/upload-byte-view)]
                           #(f backend % shape :f32))
                   "F16" (if preserve-f16?
                           (when-let [f (resolve 'num.deno-gpu/upload-byte-view)]
                             #(f backend % shape :f16))
                           (when-let [f (resolve 'num.deno-gpu/upload-f16-as-f32-byte-view)]
                             #(f backend % shape)))
                   "BF16" (when-let [f (resolve 'num.deno-gpu/upload-bf16-as-f32-byte-view)]
                            #(f backend % shape))
                   nil)]
      (if upload
        (let [[start end] (get entry "data_offsets")
              window (tensor-window checkpoint entry)]
          (swap! (:stats checkpoint)
                 #(-> % (update :direct-uploads inc)
                      (update :direct-bytes + (- end start))
                      (update-in [:direct-dtypes dtype-name] (fnil inc 0))))
          (upload window))
        (do
          (swap! (:stats checkpoint)
                 #(-> % (update :decoded-uploads inc)
                      (update :decoded-elements + (nelems shape))))
          (arr/from-vec backend (decode-values checkpoint entry) shape
                        (if (and preserve-f16? (= "F16" dtype-name)) :f16 :f32))))))))

(defn component
  ([checkpoint] (component checkpoint {}))
  ([checkpoint {:keys [preserve-f16?] :as options}]
   (cond-> {:comfyui/read-tensor (fn [backend name]
                                  (read-tensor checkpoint backend name options))}
     preserve-f16? (assoc :comfyui/dtype :f16))))
