(ns num.deno-q8-worker
  "Persistent JSON-lines Q8_0 GEMV worker backed by WebGPU/Metal."
  (:require [num.wgsl :as wgsl]))

(def usage (.-GPUBufferUsage js/globalThis))
(def map-mode (.-GPUMapMode js/globalThis))
(def readline (js/require "node:readline"))
(def registry (atom {}))
(def kv-registry (atom {}))
(def metrics (atom {:gemv 0 :gemv-many 0 :submissions 0}))

(defn- gpu-buffer [device typed-array flags]
  (let [buffer (.createBuffer device #js {:size (max 4 (.-byteLength typed-array))
                                           :usage flags :mappedAtCreation true})
        constructor (.-constructor typed-array)
        mapped (new constructor (.getMappedRange buffer))]
    (.set mapped typed-array) (.unmap buffer) buffer))

(defn- half [bits]
  (let [sign (if (zero? (bit-and bits 0x8000)) 1 -1)
        exponent (bit-and (unsigned-bit-shift-right bits 10) 31)
        fraction (bit-and bits 1023)]
    (cond (zero? exponent) (* sign (Math/pow 2 -14) (/ fraction 1024))
          (= exponent 31) (if (zero? fraction) (* sign js/Infinity) js/NaN)
          :else (* sign (Math/pow 2 (- exponent 15)) (+ 1 (/ fraction 1024))))))

(defn- decode-base64 [text]
  (js/Uint8Array.from (js/Buffer.from text "base64")))

(defn- reply [value] (.write (.-stdout js/process) (str (js/JSON.stringify (clj->js value)) "\n")))

(defn- upload! [device pipeline bytes-per-block command]
  (let [id (aget command "id") rows (aget command "rows") cols (aget command "cols")
        blocks (/ cols 32) source (decode-base64 (aget command "data"))
        qbytes (js/Uint8Array. (* rows blocks bytes-per-block))
        scales (js/Float32Array. (* rows blocks))]
    (dotimes [block (* rows blocks)]
      (let [src (* block (+ bytes-per-block 2)) bits (bit-or (aget source src)
                                          (bit-shift-left (aget source (inc src)) 8))]
        (aset scales block (half bits))
        (.set qbytes (.subarray source (+ src 2) (+ src 2 bytes-per-block))
              (* block bytes-per-block))))
    (let [storage (bit-or (.-STORAGE usage) (.-COPY_DST usage))
          qbuf (gpu-buffer device (js/Uint32Array. (.-buffer qbytes)) storage)
          sbuf (gpu-buffer device scales storage)
          params (gpu-buffer device (js/Uint32Array. #js [rows cols blocks 0])
                             (bit-or (.-UNIFORM usage) (.-COPY_DST usage)))]
      (swap! registry assoc id #js {:q qbuf :scales sbuf :params params
                                    :rows rows :cols cols :pipeline pipeline})
      (reply {:ok true :id id :gpu-bytes (+ (.-size qbuf) (.-size sbuf))}))))

(defn- upload-raw! [device pipeline block-size block-elements command]
  (let [id (aget command "id") rows (aget command "rows") cols (aget command "cols")
        blocks (/ cols block-elements) source (decode-base64 (aget command "data"))
        padded (js/Uint8Array. (* 4 (Math/ceil (/ (.-byteLength source) 4))))
        _ (.set padded source)
        storage (bit-or (.-STORAGE usage) (.-COPY_DST usage) (.-COPY_SRC usage))
        qbuf (gpu-buffer device (js/Uint32Array. (.-buffer padded)) storage)
        sbuf (gpu-buffer device (js/Float32Array. #js [0]) storage)
        params (gpu-buffer device (js/Uint32Array. #js [rows cols blocks 0])
                           (bit-or (.-UNIFORM usage) (.-COPY_DST usage)))]
    (when-not (= (.-byteLength source) (* rows blocks block-size))
      (throw (js/Error. "quantized matrix byte length mismatch")))
    (swap! registry assoc id #js {:q qbuf :scales sbuf :params params
                                  :rows rows :cols cols :pipeline pipeline})
    (reply {:ok true :id id :gpu-bytes (+ (.-size qbuf) (.-size sbuf))})))

(defn- gemv! [device command]
  (let [id (aget command "id") entry (get @registry id)]
    (when-not entry (throw (js/Error. (str "unknown Q8 handle: " id))))
    (let [rows (.-rows entry) cols (.-cols entry)
          values (js/Float32Array. (aget command "x"))
          _ (when-not (= cols (.-length values))
              (throw (js/Error. "GEMV input length mismatch")))
          storage (bit-or (.-STORAGE usage) (.-COPY_DST usage))
          xbuf (gpu-buffer device values storage)
          ybuf (.createBuffer device #js {:size (* rows 4)
                                           :usage (bit-or (.-STORAGE usage) (.-COPY_SRC usage))})
          read (.createBuffer device #js {:size (* rows 4)
                                           :usage (bit-or (.-COPY_DST usage) (.-MAP_READ usage))})
          bind (.createBindGroup device
                                 #js {:layout (.getBindGroupLayout (.-pipeline entry) 0)
                                      :entries #js [#js {:binding 0 :resource #js {:buffer (.-q entry)}}
                                                    #js {:binding 1 :resource #js {:buffer (.-scales entry)}}
                                                    #js {:binding 2 :resource #js {:buffer xbuf}}
                                                    #js {:binding 3 :resource #js {:buffer ybuf}}
                                                    #js {:binding 4 :resource #js {:buffer (.-params entry)}}]})
          encoder (.createCommandEncoder device) pass (.beginComputePass encoder)]
      (.setPipeline pass (.-pipeline entry)) (.setBindGroup pass 0 bind)
      (.dispatchWorkgroups pass (Math/ceil (/ rows 64))) (.end pass)
      (.copyBufferToBuffer encoder ybuf 0 read 0 (* rows 4))
      (swap! metrics #(-> % (update :gemv inc) (update :submissions inc)))
      (.submit (.-queue device) #js [(.finish encoder)])
      (-> (.mapAsync read (.-READ map-mode))
          (.then (fn []
                   (let [output (vec (js/Float32Array. (.getMappedRange read)))]
                     (reply {:ok true :id id :y output})
                     (.destroy xbuf) (.destroy ybuf) (.destroy read))))))))

(defn- encode-gemv! [device encoder request]
  (let [id (aget request "id") entry (get @registry id)]
    (when-not entry (throw (js/Error. (str "unknown Q8 handle: " id))))
    (let [rows (.-rows entry) cols (.-cols entry)
          values (js/Float32Array. (aget request "x"))
          _ (when-not (= cols (.-length values))
              (throw (js/Error. "GEMV input length mismatch")))
          storage (bit-or (.-STORAGE usage) (.-COPY_DST usage))
          xbuf (gpu-buffer device values storage)
          ybuf (.createBuffer device #js {:size (* rows 4)
                                           :usage (bit-or (.-STORAGE usage) (.-COPY_SRC usage))})
          read (.createBuffer device #js {:size (* rows 4)
                                           :usage (bit-or (.-COPY_DST usage) (.-MAP_READ usage))})
          bind (.createBindGroup device
                                 #js {:layout (.getBindGroupLayout (.-pipeline entry) 0)
                                      :entries #js [#js {:binding 0 :resource #js {:buffer (.-q entry)}}
                                                    #js {:binding 1 :resource #js {:buffer (.-scales entry)}}
                                                    #js {:binding 2 :resource #js {:buffer xbuf}}
                                                    #js {:binding 3 :resource #js {:buffer ybuf}}
                                                    #js {:binding 4 :resource #js {:buffer (.-params entry)}}]})
          pass (.beginComputePass encoder)]
      (.setPipeline pass (.-pipeline entry)) (.setBindGroup pass 0 bind)
      (.dispatchWorkgroups pass (Math/ceil (/ rows 64))) (.end pass)
      (.copyBufferToBuffer encoder ybuf 0 read 0 (* rows 4))
      #js {:id id :x xbuf :y ybuf :read read})))

(defn- gemv-many! [device command]
  (let [encoder (.createCommandEncoder device)
        jobs (mapv #(encode-gemv! device encoder %)
                   (array-seq (aget command "requests")))]
    (swap! metrics #(-> % (update :gemv-many inc) (update :submissions inc)))
    (.submit (.-queue device) #js [(.finish encoder)])
    (-> (js/Promise.all
         (clj->js
          (map (fn [job]
                 (-> (.mapAsync (.-read job) (.-READ map-mode))
                     (.then (fn []
                              (let [result {:id (.-id job)
                                            :y (vec (js/Float32Array.
                                                     (.getMappedRange (.-read job))))}]
                                (.destroy (.-x job)) (.destroy (.-y job))
                                (.destroy (.-read job)) result)))))
               jobs)))
        (.then (fn [results]
                 (reply {:ok true :results (js->clj results :keywordize-keys true)}))))))

(defn- create-kv! [device command]
  (let [id (aget command "id") layers (aget command "layers")
        context (aget command "context") kv-heads (aget command "kvHeads")
        head-dim (aget command "headDim") page-tokens (min context 16)
        bytes (* layers page-tokens kv-heads head-dim 4)
        storage (bit-or (.-STORAGE usage) (.-COPY_DST usage) (.-COPY_SRC usage))
        keys (.createBuffer device #js {:size bytes :usage storage})
        values (.createBuffer device #js {:size bytes :usage storage})]
    (swap! kv-registry assoc id #js {:keys keys :values values :bytes bytes :layers layers
                                     :context context :capacity page-tokens
                                     :kvHeads kv-heads :headDim head-dim})
    (reply {:ok true :id id :gpu-bytes (* bytes 2)})))

(defn- clone-kv! [device command]
  (let [source-id (aget command "source") id (aget command "id")
        source (get @kv-registry source-id)]
    (when-not source (throw (js/Error. (str "unknown KV handle: " source-id))))
    (let [storage (bit-or (.-STORAGE usage) (.-COPY_DST usage) (.-COPY_SRC usage))
          keys (.createBuffer device #js {:size (.-bytes source) :usage storage})
          values (.createBuffer device #js {:size (.-bytes source) :usage storage})
          encoder (.createCommandEncoder device)]
      (.copyBufferToBuffer encoder (.-keys source) 0 keys 0 (.-bytes source))
      (.copyBufferToBuffer encoder (.-values source) 0 values 0 (.-bytes source))
      (.submit (.-queue device) #js [(.finish encoder)])
      (swap! kv-registry assoc id #js {:keys keys :values values :bytes (.-bytes source)
                                       :layers (.-layers source) :context (.-context source)
                                       :capacity (.-capacity source)
                                       :kvHeads (.-kvHeads source) :headDim (.-headDim source)})
      (reply {:ok true :id id :gpu-bytes (* 2 (.-bytes source))}))))

(defn- grow-kv! [device id entry position]
  (if (< position (.-capacity entry)) entry
    (let [capacity (min (.-context entry)
                        (max (inc position) (* 2 (.-capacity entry))))
          bytes (* (.-layers entry) capacity (.-kvHeads entry) (.-headDim entry) 4)
          storage (bit-or (.-STORAGE usage) (.-COPY_DST usage) (.-COPY_SRC usage))
          keys (.createBuffer device #js {:size bytes :usage storage})
          values (.createBuffer device #js {:size bytes :usage storage})
          encoder (.createCommandEncoder device)]
      ;; Layer strides change with capacity, so copy each layer independently.
      (dotimes [layer (.-layers entry)]
        (let [old-layer-bytes (* (.-capacity entry) (.-kvHeads entry)
                                 (.-headDim entry) 4)
              new-layer-bytes (* capacity (.-kvHeads entry) (.-headDim entry) 4)]
          (.copyBufferToBuffer encoder (.-keys entry) (* layer old-layer-bytes)
                               keys (* layer new-layer-bytes) old-layer-bytes)
          (.copyBufferToBuffer encoder (.-values entry) (* layer old-layer-bytes)
                               values (* layer new-layer-bytes) old-layer-bytes)))
      (.submit (.-queue device) #js [(.finish encoder)])
      (.destroy (.-keys entry)) (.destroy (.-values entry))
      (let [grown #js {:keys keys :values values :bytes bytes :layers (.-layers entry)
                       :context (.-context entry) :capacity capacity
                       :kvHeads (.-kvHeads entry) :headDim (.-headDim entry)}]
        (swap! kv-registry assoc id grown)
        (swap! metrics update :kv-grows (fnil inc 0))
        grown))))

(defn- encode-attention! [device cache-pipeline attention-pipeline encoder command]
  (let [id (aget command "id") original (get @kv-registry id)]
    (when-not original (throw (js/Error. (str "unknown KV handle: " id))))
    (let [position (aget command "position") entry (grow-kv! device id original position)
          heads (aget command "heads") kv-heads (.-kvHeads entry)
          head-dim (.-headDim entry)
          layer (aget command "layer") capacity (.-capacity entry)
          q (js/Float32Array. (aget command "q"))
          k (js/Float32Array. (aget command "k")) v (js/Float32Array. (aget command "v"))
          _ (when-not (and (= (.-length q) (* heads head-dim))
                           (= (.-length k) (* kv-heads head-dim))
                           (= (.-length v) (* kv-heads head-dim))
                           (< position (.-context entry)) (< layer (.-layers entry)))
              (throw (js/Error. "attention shape or cache position mismatch")))
          storage (bit-or (.-STORAGE usage) (.-COPY_DST usage))
          qbuf (gpu-buffer device q storage) kbuf (gpu-buffer device k storage)
          vbuf (gpu-buffer device v storage)
          out (.createBuffer device #js {:size (* heads head-dim 4)
                                          :usage (bit-or (.-STORAGE usage) (.-COPY_SRC usage))})
          read (.createBuffer device #js {:size (* heads head-dim 4)
                                           :usage (bit-or (.-COPY_DST usage) (.-MAP_READ usage))})
          params (gpu-buffer device
                             (js/Uint32Array. #js [heads kv-heads head-dim position
                                                   capacity layer 0 0])
                             (bit-or (.-UNIFORM usage) (.-COPY_DST usage)))
          cache-bind (.createBindGroup device
                                       #js {:layout (.getBindGroupLayout cache-pipeline 0)
                                            :entries #js [#js {:binding 0 :resource #js {:buffer kbuf}}
                                                          #js {:binding 1 :resource #js {:buffer vbuf}}
                                                          #js {:binding 2 :resource #js {:buffer (.-keys entry)}}
                                                          #js {:binding 3 :resource #js {:buffer (.-values entry)}}
                                                          #js {:binding 4 :resource #js {:buffer params}}]})
          attention-bind (.createBindGroup device
                                           #js {:layout (.getBindGroupLayout attention-pipeline 0)
                                                :entries #js [#js {:binding 0 :resource #js {:buffer qbuf}}
                                                              #js {:binding 1 :resource #js {:buffer (.-keys entry)}}
                                                              #js {:binding 2 :resource #js {:buffer (.-values entry)}}
                                                              #js {:binding 3 :resource #js {:buffer out}}
                                                              #js {:binding 4 :resource #js {:buffer params}}]})
          cache-pass (.beginComputePass encoder)]
      (.setPipeline cache-pass cache-pipeline) (.setBindGroup cache-pass 0 cache-bind)
      (.dispatchWorkgroups cache-pass (Math/ceil (/ (* kv-heads head-dim) 64)))
      (.end cache-pass)
      (let [pass (.beginComputePass encoder)]
        (.setPipeline pass attention-pipeline) (.setBindGroup pass 0 attention-bind)
        (.dispatchWorkgroups pass (Math/ceil (/ (* heads head-dim) 64))) (.end pass))
      (.copyBufferToBuffer encoder out 0 read 0 (* heads head-dim 4))
      #js {:id id :read read :buffers #js [qbuf kbuf vbuf out read params]})))

(defn- read-attention! [job]
  (-> (.mapAsync (.-read job) (.-READ map-mode))
      (.then (fn []
               (let [result {:id (.-id job)
                             :output (vec (js/Float32Array.
                                          (.getMappedRange (.-read job))))}]
                 (doseq [buffer (array-seq (.-buffers job))] (.destroy buffer))
                 result)))))

(defn- attention! [device cache-pipeline attention-pipeline command]
  (let [encoder (.createCommandEncoder device)
        job (encode-attention! device cache-pipeline attention-pipeline encoder command)]
    (swap! metrics update :attention (fnil inc 0))
    (.submit (.-queue device) #js [(.finish encoder)])
    (-> (read-attention! job)
        (.then #(reply (assoc % :ok true))))))

(defn- attention-many! [device cache-pipeline attention-pipeline command]
  (let [encoder (.createCommandEncoder device)
        jobs (mapv #(encode-attention! device cache-pipeline attention-pipeline encoder %)
                   (array-seq (aget command "requests")))]
    (swap! metrics update :attention-many (fnil inc 0))
    (.submit (.-queue device) #js [(.finish encoder)])
    (-> (js/Promise.all (clj->js (map read-attention! jobs)))
        (.then (fn [results]
                 (reply {:ok true :results (js->clj results :keywordize-keys true)}))))))

(defn- release-kv! [command]
  (let [id (aget command "id") entry (get @kv-registry id)]
    (when entry (.destroy (.-keys entry)) (.destroy (.-values entry))
          (swap! kv-registry dissoc id))
    (reply {:ok true :id id})))

(defn- release! [command]
  (let [id (aget command "id") entry (get @registry id)]
    (when entry
      (.destroy (.-q entry)) (.destroy (.-scales entry)) (.destroy (.-params entry))
      (swap! registry dissoc id))
    (reply {:ok true :id id})))

(defn- serve! [device]
  (let [pipeline (fn [source]
                   (let [module (.createShaderModule device #js {:code source})]
                     (.createComputePipeline device
                                             #js {:layout "auto"
                                                  :compute #js {:module module :entryPoint "main"}})))
        q8-pipeline (pipeline wgsl/q8-0-gemv-wgsl)
        q4-pipeline (pipeline wgsl/q4-0-gemv-wgsl)
        q4k-pipeline (pipeline wgsl/q4-k-gemv-wgsl)
        q5-pipeline (pipeline wgsl/q5-0-gemv-wgsl)
        q5-1-pipeline (pipeline wgsl/q5-1-gemv-wgsl)
        q5k-pipeline (pipeline wgsl/q5-k-gemv-wgsl)
        q6k-pipeline (pipeline wgsl/q6-k-gemv-wgsl)
        cache-pipeline (pipeline wgsl/kv-cache-write-wgsl)
        attention-pipeline (pipeline wgsl/causal-gqa-attention-wgsl)
        lines (.createInterface readline #js {:input (.-stdin js/process)})]
    (.on lines "line"
         (fn [line]
           (try
             (let [command (js/JSON.parse line) op (aget command "op")]
               (case op
                 "upload-q8" (upload! device q8-pipeline 32 command)
                 "upload-q4" (upload! device q4-pipeline 16 command)
                 "upload-q4k" (upload-raw! device q4k-pipeline 144 256 command)
                 "upload-q5" (upload-raw! device q5-pipeline 22 32 command)
                 "upload-q5-1" (upload-raw! device q5-1-pipeline 24 32 command)
                 "upload-q5k" (upload-raw! device q5k-pipeline 176 256 command)
                 "upload-q6k" (upload-raw! device q6k-pipeline 210 256 command)
                 "gemv" (.catch (gemv! device command)
                                 #(reply {:ok false :error (.-message %)}))
                 "gemv-many" (.catch (gemv-many! device command)
                                      #(reply {:ok false :error (.-message %)}))
                 "create-kv" (create-kv! device command)
                 "clone-kv" (clone-kv! device command)
                 "attention" (.catch (attention! device cache-pipeline attention-pipeline command)
                                      #(reply {:ok false :error (.-message %)}))
                 "attention-many" (.catch
                                   (attention-many! device cache-pipeline attention-pipeline command)
                                   #(reply {:ok false :error (.-message %)}))
                 "release-kv" (release-kv! command)
                 "release" (release! command)
                 "stats" (reply (merge {:ok true :handles (count @registry)
                                         :kv-handles (count @kv-registry)
                                         :kv-bytes (reduce + 0 (map #(* 2 (.-bytes %))
                                                                    (vals @kv-registry)))}
                                        @metrics))
                 (reply {:ok false :error (str "unknown op: " op)})))
             (catch :default error
               (reply {:ok false :error (.-message error)})))))))

(defn -main [& _]
  (-> (.requestAdapter (.-gpu js/navigator))
      (.then (fn [adapter]
               (when-not adapter (throw (js/Error. "no WebGPU adapter")))
               (.then (.requestDevice adapter) serve!)))
      (.catch (fn [error] (js/console.error error) (.exit js/Deno 1)))))

(set! *main-cli-fn* -main)
