(ns actor-ipc.ipc
  "KAMI Interface: columnar zero-copy game data format. Restored from the legacy
  kami-engine/kami-core Rust crate's `src/ipc.rs` (447 lines), deleted in
  kotoba-lang/kami-engine PR #82 \"Remove Rust workspace from kami-engine\", as
  part of the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root).

  Original doc comment:
    Shannon η = 99.5% — Arrow essence (columnar + zero-copy) with
    game-unnecessary concepts removed (null bitmap, dictionary, nested types,
    Flatbuffer metadata).
    Data flow: Storage (Arrow IPC) <-> ECS (KamiFrame) <-> GPU (wgpu buffer)
    <-> Network (KamiDelta). All transitions are zero-copy or single memcpy
    (CPU->GPU DMA).

  Zero-copy-to-value adaptation: the original `Column` held a raw `*const u8`
  pointer into shared memory and exposed `unsafe` typed-slice views
  (`as_bytes` / `as_f32_slice` / `as_u32_slice`) for true zero-copy access. CLJC
  has no raw pointers, so a `Column` here is a plain map holding its data as an
  ordinary CLJC vector of numbers (`:data`), not a byte buffer — there is no
  unsafe view step because the data is already typed. The wire (de)serialization
  in `Delta/to_bytes` / `Delta/from_bytes` (originally hand-rolled little-endian
  byte packing) uses the org-owned canonical `kotoba.value.v1` byte boundary.
  Float column elements are explicitly tagged at the private wire adapter so
  ordinary actor APIs keep ordinary numbers without cross-runtime ambiguity.
  `dtype-item-size` / metadata-byte constants below remain documented for
  original wire-size accounting."
  (:require [kotoba.value.codec :as value]))

;; --- Dtype -----------------------------------------------------------------
;; Rust: `#[repr(u8)] pub enum Dtype { F32=0, F16=1, U32=2, U16=3, U8=4, I16=5,
;;         Mat4=6, Quat=7 }`
;; Column element type. 8 types cover all game data needs.
(def dtype-values
  "Valid Dtype keywords."
  #{:f32 :f16 :u32 :u16 :u8 :i16 :mat4 :quat})

(def dtype-codes
  "Dtype keyword -> original Rust `#[repr(u8)]` discriminant, preserved for
  wire-format parity with any consumer still expecting the numeric code."
  {:f32 0, :f16 1, :u32 2, :u16 3, :u8 4, :i16 5, :mat4 6, :quat 7})

(def code->dtype
  "Numeric discriminant -> Dtype keyword (inverse of `dtype-codes`)."
  (into {} (map (fn [[k v]] [v k]) dtype-codes)))

(defn dtype-element-size
  "Size in bytes of one element (before stride multiplication). Mirrors Rust
  `Dtype::element_size(self) -> usize`."
  [dtype]
  (case dtype
    :f32 4
    :f16 2
    :u32 4
    :u16 2
    :u8 1
    :i16 2
    :mat4 64                                                ; 16 x f32
    :quat 8))                                                ; 4 x f16 (smallest-3 encoding)

(defn dtype-item-size
  "Size in bytes of one item (element_size x stride). Mirrors Rust
  `Dtype::item_size(self, stride: u8) -> usize`."
  [dtype stride]
  (* (dtype-element-size dtype) stride))

;; --- Column ------------------------------------------------------------
;; Rust: `#[repr(C, align(16))] pub struct Column { data: *const u8, len: u32,
;;         dtype: Dtype, stride: u8, _pad: [u8; 2] }`
;; A single column of homogeneous data. In the original, 16 bytes, GPU-aligned
;; (data ptr 8B + len 4B + dtype 1B + stride 1B + pad 2B = 16B); no null bitmap,
;; dictionary, offset, or release callback (vs. Arrow C Data Interface's 80B).
;; That 16B metadata size is preserved here only as a documented constant for
;; wire-size-accounting parity — there is no raw pointer/struct layout in CLJC.
(def column-metadata-bytes
  "Metadata overhead of one Column in the original wire/GPU layout (16 bytes:
  8 ptr + 4 len + 1 dtype + 1 stride + 2 pad). Kept for size-accounting parity;
  a CLJC Column map itself has no fixed byte size."
  16)

(defn make-column
  "Create a Column map from a flat data vector and a stride (elements per item).
  `:len` is the item count, i.e. `(count data) / stride`. Mirrors Rust
  `Column::from_f32_slice` / `Column::from_raw`, generalized to any dtype since
  CLJC has no raw pointer to type-punn."
  [data dtype stride]
  {:data data
   :len (quot (count data) stride)
   :dtype dtype
   :stride stride})

(defn column-byte-len
  "Total data size in bytes (conceptual — CLJC data is a typed vector, not raw
  bytes). Mirrors Rust `Column::byte_len(&self) -> usize`."
  [column]
  (* (:len column) (dtype-item-size (:dtype column) (:stride column))))

;; --- Frame ---------------------------------------------------------------
;; Rust:
;;   pub struct Frame { pub tick: Tick, pub n_entities: u32, columns: Vec<Column>,
;;                       _buffers: Vec<Vec<u8>> }
;; One tick's worth of entity data. All columns share the same `n_entities`
;; length. Original wire format: [KamiFrame header][Column x n_columns][data
;; buffers...], header = 12 bytes. `_buffers` (owned backing storage kept alive
;; for zero-copy column pointers) has no CLJC equivalent since columns already
;; own their data vector directly.
(def frame-header-bytes
  "Frame header size in the original wire format (12 bytes: tick 4 + n_entities
  4 + n_columns-ish bookkeeping 4)." 12)

(defn make-frame
  "Construct an empty Frame. Mirrors Rust `Frame::new(tick, n_entities) -> Self`."
  [tick n-entities]
  {:tick tick :n-entities n-entities :columns []})

(defn push-column-owned
  "Add a column built from an owned data vector. Mirrors Rust
  `Frame::push_column_owned(&mut self, data, dtype, stride)`, adapted to return
  the updated Frame (immutable) rather than mutate in place."
  [frame data dtype stride]
  (update frame :columns conj (make-column data dtype stride)))

(defn push-f32-column
  "Add an f32 column from a data vector. Mirrors Rust
  `Frame::push_f32_column(&mut self, data: &[f32], stride: u8)`."
  [frame data stride]
  (push-column-owned frame data :f32 stride))

(defn frame-n-columns
  "Number of columns. Mirrors Rust `Frame::n_columns(&self) -> usize`."
  [frame]
  (count (:columns frame)))

(defn frame-column
  "Get column by index. Mirrors Rust `Frame::column(&self, index) -> &Column`."
  [frame index]
  (nth (:columns frame) index))

(defn frame-data-bytes
  "Total data size (all columns, excluding metadata). Mirrors Rust
  `Frame::data_bytes(&self) -> usize`."
  [frame]
  (reduce + 0 (map column-byte-len (:columns frame))))

(defn frame-metadata-bytes
  "Metadata overhead in bytes. Mirrors Rust `Frame::metadata_bytes(&self) ->
  usize`."
  [frame]
  (+ frame-header-bytes (* (frame-n-columns frame) column-metadata-bytes)))

(defn frame-efficiency
  "Shannon efficiency: data / (data + metadata). Mirrors Rust
  `Frame::efficiency(&self) -> f64`."
  [frame]
  (let [d (double (frame-data-bytes frame))
        m (double (frame-metadata-bytes frame))]
    (/ d (+ d m))))

;; --- Delta -----------------------------------------------------------------
;; Rust:
;;   pub struct Delta { pub base_tick: Tick, pub tick: Tick,
;;                       pub changed_indices: Vec<u32>, columns: Vec<Column>,
;;                       _buffers: Vec<Vec<u8>> }
;; Delta frame: only changed entities. Used for network transmission. Shannon:
;; sends only changed columns for changed entities. Compression ratio ~=
;; change_rate x (dtype_delta_size / dtype_full_size).
(def delta-header-bytes
  "Delta header size in the original wire format (16 bytes: base_tick 4 + tick 4
  + n_changed 4 + n_columns 1 + pad 3)." 16)

(def delta-wire-format :actor-ipc.delta/v1)

(def max-delta-envelope-bytes
  "Actor IPC ability limit for one canonical delta envelope (16 MiB)."
  (* 16 1024 1024))

(defn make-delta
  "Construct an empty Delta. Mirrors Rust `Delta::new(base_tick, tick) -> Self`."
  [base-tick tick]
  {:base-tick base-tick :tick tick :changed-indices [] :columns []})

(defn delta-push-column-owned
  "Add a column built from an owned data vector. Mirrors Rust
  `Delta::push_column_owned(&mut self, data, dtype, stride)`, adapted to return
  the updated Delta (immutable) rather than mutate in place."
  [delta data dtype stride]
  (update delta :columns conj (make-column data dtype stride)))

(defn delta-n-columns
  "Number of columns. Mirrors Rust `Delta::n_columns(&self) -> usize`."
  [delta]
  (count (:columns delta)))

(defn delta-column
  "Get column by index. Mirrors Rust `Delta::column(&self, index) -> &Column`."
  [delta index]
  (nth (:columns delta) index))

(def ^:private max-u32 4294967295)

(defn- u32? [x]
  (and (integer? x) (<= 0 x max-u32)))

(defn- strictly-increasing? [xs]
  (or (empty? xs)
      (every? true? (map < xs (next xs)))))

(defn- floating-dtype? [dtype]
  (contains? #{:f32 :f16 :mat4 :quat} dtype))

(defn- valid-element? [dtype x]
  (cond
    (floating-dtype? dtype) (number? x)
    (= :u32 dtype) (u32? x)
    (= :u16 dtype) (and (integer? x) (<= 0 x 65535))
    (= :u8 dtype) (and (integer? x) (<= 0 x 255))
    (= :i16 dtype) (and (integer? x) (<= -32768 x 32767))
    :else false))

(defn- valid-column-shape? [{:keys [data len dtype stride] :as column}]
  (and (map? column)
       (= #{:data :len :dtype :stride} (set (keys column)))
       (vector? data)
       (contains? dtype-values dtype)
       (integer? stride) (<= 1 stride 255)
       (u32? len)
       (= (count data) (* len stride))
       (every? #(valid-element? dtype %) data)))

(defn- valid-delta-shape? [{:keys [base-tick tick changed-indices columns] :as delta}]
  (and (map? delta)
       (= #{:base-tick :tick :changed-indices :columns} (set (keys delta)))
       (u32? base-tick)
       (u32? tick)
       (vector? changed-indices)
       (every? u32? changed-indices)
       (strictly-increasing? changed-indices)
       (vector? columns)
       (or (seq columns) (empty? changed-indices))
       (every? valid-column-shape? columns)
       (every? #(= (count changed-indices) (:len %)) columns)))

(defn- wire-column [{:keys [data dtype] :as column}]
  (if (floating-dtype? dtype)
    (assoc column :data (mapv #(value/float64 (double %)) data))
    column))

(defn- host-column [{:keys [data dtype] :as column}]
  (if (floating-dtype? dtype)
    (when (every? value/float64? data)
      (assoc column :data (mapv value/float64-value data)))
    column))

(defn- delta->wire-value [delta]
  (when-not (valid-delta-shape? delta)
    (throw (ex-info "actor IPC delta is malformed"
                    {:phase :actor-ipc/delta-encode})))
  {:format delta-wire-format
   :delta (update delta :columns #(mapv wire-column %))})

(defn- wire-value->delta [envelope]
  (when (and (map? envelope)
             (= #{:format :delta} (set (keys envelope)))
             (= delta-wire-format (:format envelope))
             (map? (:delta envelope))
             (vector? (get-in envelope [:delta :columns])))
    (let [wire-delta (:delta envelope)
          columns (mapv host-column (:columns wire-delta))]
      (when (every? some? columns)
        (let [delta (assoc wire-delta :columns columns)]
          (when (valid-delta-shape? delta)
            delta))))))

(defn delta-to-bytes
  "Serialize a Delta as canonical `kotoba.value.v1` bytes for KNP.

  The optional MAX-BYTES is an ability-owned limit; the default is the actor
  IPC v1 envelope limit. Malformed or oversized deltas fail closed."
  ([delta] (delta-to-bytes delta max-delta-envelope-bytes))
  ([delta max-bytes]
   (value/encode-bounded (delta->wire-value delta) max-bytes)))

(defn delta-from-bytes
  "Deserialize canonical KNP bytes, returning nil for an invalid envelope.

  Size is checked before decoding. Legacy EDN strings are intentionally not
  accepted because they were never bytes and were not canonical."
  ([bytes] (delta-from-bytes bytes max-delta-envelope-bytes))
  ([bytes max-bytes]
   (try
     (wire-value->delta (value/decode-bounded bytes max-bytes))
     (catch #?(:clj Exception :cljs :default) _
       nil))))

(defn delta-wire-size
  "Wire size in bytes of the original binary format (conceptual — kept for
  size-accounting parity with the Rust format; the actual `delta-to-bytes`
  payload is canonical `kotoba.value.v1`). Mirrors Rust
  `Delta::wire_size(&self) -> usize`."
  [delta]
  (+ delta-header-bytes
     (* (delta-n-columns delta) 2)
     (* (count (:changed-indices delta)) 4)
     (reduce + 0 (map column-byte-len (:columns delta)))))

;; --- compute-delta -----------------------------------------------------
;; Rust: `pub fn compute_delta(prev: &Frame, curr: &Frame) -> Delta`
;; Compute delta between two frames. Only changed entities are included.
;; Columns must have the same layout (same n_columns, same dtypes/strides).
(defn compute-delta
  "Compute the Delta between two Frames. Detects changed entities by comparing
  the first column's per-item slices (typically position), then emits delta
  columns containing only the changed entities' items, for every column.
  Mirrors Rust `compute_delta(prev: &Frame, curr: &Frame) -> Delta`."
  [prev curr]
  (assert (= (:n-entities prev) (:n-entities curr)))
  (assert (= (frame-n-columns prev) (frame-n-columns curr)))
  (let [n (:n-entities curr)
        changed (if (pos? (frame-n-columns curr))
                  (let [prev-col (frame-column prev 0)
                        curr-col (frame-column curr 0)
                        stride (:stride curr-col)]
                    (vec (for [i (range n)
                               :let [start (* i stride)
                                     end (+ start stride)]
                               :when (not= (subvec (:data prev-col) start end)
                                           (subvec (:data curr-col) start end))]
                           i)))
                  [])
        base (assoc (make-delta (:tick prev) (:tick curr)) :changed-indices changed)]
    (reduce
     (fn [delta col-idx]
       (let [col (frame-column curr col-idx)
             stride (:stride col)
             data (:data col)
             delta-data (vec (mapcat (fn [entity-idx]
                                        (let [start (* entity-idx stride)]
                                          (subvec data start (+ start stride))))
                                      changed))]
         (delta-push-column-owned delta delta-data (:dtype col) stride)))
     base
     (range (frame-n-columns curr)))))
