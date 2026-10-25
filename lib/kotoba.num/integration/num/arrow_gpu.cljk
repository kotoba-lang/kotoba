(ns num.arrow-gpu
  "The optional Arrow IPC → Num CPU/GPU boundary.

  Arrow owns the file layout and exposes borrowed physical buffers. Num owns
  device storage. This adapter does not invent a third representation between
  them: a non-nullable little-endian float column becomes a Float32Array view
  over the same ArrayBuffer on CPU, and that identical byte view is passed to
  WebGPU for the one device upload the ownership boundary requires.

  Null bitmaps, unsupported dtypes and unaligned buffers fail closed. A future
  masked kernel may admit nullable columns, but silently treating invalid slots
  as real values would make a fast answer wrong."
  (:require [arrow.source :as arrow]
            [columnar.bytes :as bytes]
            [num.deno-gpu :as gpu]))

(defn- fail [message data]
  (throw (ex-info message (assoc data :type :num/arrow-upload-refused))))

(defn- buffer-for [column-view role]
  (or (some #(when (= role (:role %)) %) (:buffers column-view))
      (fail "Arrow column is missing the required physical buffer"
            {:role role :available (mapv :role (:buffers column-view))})))

(defn- f32-values-view [column-view]
  (let [logical (get-in column-view [:field :logical :type])
        validity (buffer-for column-view :validity)
        values (buffer-for column-view :values)
        native (bytes/native-view (:view values))]
    (when-not (= :float logical)
      (fail "Arrow GPU upload currently admits float32 columns only"
            {:logical logical :column (get-in column-view [:field :name])}))
    (when (pos? (:length validity))
      (fail "nullable Arrow buffers require an explicit masked kernel"
            {:validity-bytes (:length validity)
             :column (get-in column-view [:field :name])}))
    (when-not (instance? js/Uint8Array native)
      (fail "Deno Arrow upload requires a native Uint8Array backing"
            {:native-type (type native)}))
    (when-not (zero? (mod (.-byteOffset native) 4))
      (fail "Arrow float32 values buffer is not four-byte aligned"
            {:byte-offset (.-byteOffset native)}))
    (when-not (zero? (mod (.-byteLength native) 4))
      (fail "Arrow float32 values buffer has a partial element"
            {:byte-length (.-byteLength native)}))
    native))

(defn borrow-f32-column
  "Return a Float32Array over the Arrow values buffer without copying.

  The returned typed array has the same `.buffer` identity as the source
  Uint8Array. It is a CPU vectorization seam, not a claim that a particular JS
  engine emitted SIMD for a later consumer."
  [column-view]
  (let [native (f32-values-view column-view)]
    (js/Float32Array. (.-buffer native)
                      (.-byteOffset native)
                      (/ (.-byteLength native) 4))))

(defn upload-column
  "Borrow `column` from an opened Arrow source and upload it once to Num.

  Returns `{:array NDArray :column-view .. :cpu-view Float32Array}` so tests and
  hosts can audit backing identity and transfer counters. Shape defaults to the
  Arrow row count and must preserve the exact element count."
  ([backend source chunk column]
   (upload-column backend source chunk column nil))
  ([backend source chunk column shape]
   (let [column-view (arrow/column-buffer-views source chunk column)
         cpu-view (borrow-f32-column column-view)
         shape (vec (or shape [(:rows column-view)]))
         elements (reduce * 1 shape)]
     (when-not (= elements (.-length cpu-view))
       (fail "Arrow column length does not match requested Num shape"
             {:rows (:rows column-view) :elements (.-length cpu-view)
              :shape shape :column column}))
     {:array (gpu/upload-byte-view
              backend
              (js/Uint8Array. (.-buffer cpu-view)
                              (.-byteOffset cpu-view)
                              (.-byteLength cpu-view))
              shape :f32)
      :column-view column-view
      :cpu-view cpu-view})))
