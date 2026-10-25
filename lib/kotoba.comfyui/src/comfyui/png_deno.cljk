(ns comfyui.png-deno
  "Minimal dependency-free RGB8 PNG encoder for Deno/browser hosts.")

(def ^:private signature
  (js/Uint8Array. #js [137 80 78 71 13 10 26 10]))

(defn- crc32 [bytes]
  (let [crc (reduce
             (fn [crc byte]
               (loop [value (bit-xor crc byte) bit 0]
                 (if (= bit 8)
                   value
                   (recur (if (odd? value)
                            (bit-xor (unsigned-bit-shift-right value 1) 0xedb88320)
                            (unsigned-bit-shift-right value 1))
                          (inc bit)))))
             -1 (js/Array.from bytes))]
    (unsigned-bit-shift-right (bit-xor crc -1) 0)))

(defn- concat-bytes [parts]
  (let [length (reduce + (map #(.-byteLength %) parts))
        output (js/Uint8Array. length)]
    (loop [remaining parts offset 0]
      (if-let [part (first remaining)]
        (do (.set output part offset)
            (recur (next remaining) (+ offset (.-byteLength part))))
        output))))

(defn- png-chunk [type data]
  (let [type-bytes (.encode (js/TextEncoder.) type)
        crc-input (concat-bytes [type-bytes data])
        output (js/Uint8Array. (+ 12 (.-byteLength data)))
        view (js/DataView. (.-buffer output))]
    (.setUint32 view 0 (.-byteLength data) false)
    (.set output type-bytes 4)
    (.set output data 8)
    (.setUint32 view (+ 8 (.-byteLength data)) (crc32 crc-input) false)
    output))

(defn- ihdr [width height]
  (let [data (js/Uint8Array. 13)
        view (js/DataView. (.-buffer data))]
    (.setUint32 view 0 width false)
    (.setUint32 view 4 height false)
    (aset data 8 8)  ; bit depth
    (aset data 9 2)  ; truecolor RGB
    data))

(defn- scanlines [values width height]
  (let [row-bytes (* width 3)
        output (js/Uint8Array. (* height (inc row-bytes)))]
    (dotimes [row height]
      (let [destination (+ (* row (inc row-bytes)) 1)
            source (* row row-bytes)]
        (dotimes [column row-bytes]
          (let [value (nth values (+ source column))
                byte (Math/round (* 255.0 (max 0.0 (min 1.0 value))))]
            (aset output (+ destination column) byte)))))
    output))

(defn encode-rgb
  "Return Promise<Uint8Array> for flat RGB values in [0,1]."
  [values width height]
  (when-not (and (pos-int? width) (pos-int? height)
                 (= (count values) (* width height 3)))
    (throw (ex-info "RGB data length does not match PNG dimensions"
                    {:count (count values) :width width :height height})))
  (let [raw (scanlines values width height)
        compressed-stream (-> (js/Blob. #js [raw])
                              (.stream)
                              (.pipeThrough (js/CompressionStream. "deflate")))]
    (-> (.arrayBuffer (js/Response. compressed-stream))
        (.then (fn [buffer]
                 (concat-bytes
                  [signature
                   (png-chunk "IHDR" (ihdr width height))
                   (png-chunk "IDAT" (js/Uint8Array. buffer))
                   (png-chunk "IEND" (js/Uint8Array. 0))]))))))

(defn dimensions [png]
  (when-not (and (>= (.-byteLength png) 33)
                 (every? true? (map = (js/Array.from signature)
                                    (take 8 (js/Array.from png)))))
    (throw (ex-info "invalid PNG signature/header" {})))
  (let [view (js/DataView. (.-buffer png) (.-byteOffset png) (.-byteLength png))]
    [(.getUint32 view 16 false) (.getUint32 view 20 false)]))

(defn- chunk-type [png offset]
  (.decode (js/TextDecoder.) (.slice png (+ offset 4) (+ offset 8))))

(defn- paeth [a b c]
  (let [p (- (+ a b) c) pa (Math/abs (- p a))
        pb (Math/abs (- p b)) pc (Math/abs (- p c))]
    (cond (and (<= pa pb) (<= pa pc)) a (<= pb pc) b :else c)))

(defn- unfilter [raw width height channels]
  (let [stride (* width channels)
        output (js/Uint8Array. (* height stride))]
    (dotimes [row height]
      (let [source-row (* row (inc stride))
            filter-type (aget raw source-row)
            source (inc source-row)
            destination (* row stride)]
        (when-not (<= 0 filter-type 4)
          (throw (ex-info "unsupported PNG scanline filter"
                          {:filter filter-type :row row})))
        (dotimes [column stride]
          (let [x (aget raw (+ source column))
                left (if (>= column channels)
                       (aget output (+ destination (- column channels))) 0)
                up (if (pos? row)
                     (aget output (+ (- destination stride) column)) 0)
                upper-left (if (and (pos? row) (>= column channels))
                             (aget output (+ (- destination stride)
                                             (- column channels))) 0)
                predictor (case filter-type
                            0 0 1 left 2 up
                            3 (bit-shift-right (+ left up) 1)
                            4 (paeth left up upper-left))]
            (aset output (+ destination column) (bit-and 255 (+ x predictor)))))))
    output))

(defn decode-rgb
  "Decode a non-interlaced RGB/RGBA 8-bit PNG into normalized RGB and inverse
  alpha mask vectors. Returns a Promise map with width/height/values/mask."
  [png]
  (dimensions png)
  (let [view (js/DataView. (.-buffer png) (.-byteOffset png) (.-byteLength png))
        parsed
        (loop [offset 8 ihdr nil idat []]
          (when (> (+ offset 12) (.-byteLength png))
            (throw (ex-info "truncated PNG chunk" {:offset offset})))
          (let [length (.getUint32 view offset false)
                end (+ offset 12 length)
                _ (when (> end (.-byteLength png))
                    (throw (ex-info "PNG chunk exceeds file" {:offset offset})))
                type (chunk-type png offset)
                data (.slice png (+ offset 8) (+ offset 8 length))
                expected-crc (.getUint32 view (+ offset 8 length) false)
                actual-crc (crc32 (.slice png (+ offset 4) (+ offset 8 length)))
                _ (when-not (= expected-crc actual-crc)
                    (throw (ex-info "PNG chunk CRC mismatch"
                                    {:type type :offset offset})))]
            (case type
              "IHDR" (recur end data idat)
              "IDAT" (recur end ihdr (conj idat data))
              "IEND" {:ihdr ihdr :idat idat}
              (recur end ihdr idat))))
        ihdr (:ihdr parsed)
        _ (when-not (= 13 (some-> ihdr .-byteLength))
            (throw (ex-info "PNG has no valid IHDR" {})))
        header (js/DataView. (.-buffer ihdr) (.-byteOffset ihdr) 13)
        width (.getUint32 header 0 false) height (.getUint32 header 4 false)
        bit-depth (aget ihdr 8) color-type (aget ihdr 9)
        compression (aget ihdr 10) filter-method (aget ihdr 11)
        interlace (aget ihdr 12)
        channels (case color-type 2 3 6 4 nil)
        _ (when-not (and channels (= 8 bit-depth) (zero? compression)
                         (zero? filter-method) (zero? interlace) (seq (:idat parsed)))
            (throw (ex-info "unsupported PNG format"
                            {:bit-depth bit-depth :color-type color-type
                             :interlace interlace})))
        compressed (concat-bytes (:idat parsed))
        stream (-> (js/Blob. #js [compressed]) (.stream)
                   (.pipeThrough (js/DecompressionStream. "deflate")))]
    (-> (.arrayBuffer (js/Response. stream))
        (.then
         (fn [buffer]
           (let [raw (js/Uint8Array. buffer)
                 expected-bytes (* height (inc (* width channels)))
                 _ (when-not (= expected-bytes (.-byteLength raw))
                     (throw (ex-info "PNG decompressed data length mismatch"
                                     {:expected expected-bytes
                                      :actual (.-byteLength raw)})))
                 pixels (unfilter raw width height channels)
                 pixel-count (* width height)
                 values (vec (mapcat (fn [index]
                                       (mapv #(/ (aget pixels (+ (* index channels) %)) 255.0)
                                             (range 3)))
                                     (range pixel-count)))
                 mask (if (= channels 4)
                        (mapv #(- 1.0 (/ (aget pixels (+ (* % channels) 3)) 255.0))
                              (range pixel-count))
                        (vec (repeat pixel-count 0.0)))]
             {:width width :height height :values values :mask mask}))))))
