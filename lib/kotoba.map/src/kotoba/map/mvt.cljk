(ns kotoba.map.mvt
  "Minimal MVT (Mapbox Vector Tile) PBF decoder.

  Ported 1:1 from `kami-map/src/mvt.rs` (Rust, kotoba-lang/kami-engine), per
  ADR-2607010930 (clj-wgsl migration Phase 4). Self-contained, no external
  protobuf dependency, no I/O — pure byte-buffer parsing, decodes the subset
  of the MVT spec used for line/point/polygon geometry extraction:

  - Tile (3 = repeated Layer)
  - Layer (1 name, 2 features, 5 extent uint32, 15 version)
  - Feature (3 type enum, 4 packed uint32 geometry)
  - GeomType: 1=POINT, 2=LINESTRING, 3=POLYGON
  - Geometry commands: 1 MoveTo, 2 LineTo, 7 ClosePath with zigzag-encoded
    deltas

  Tags / property values are decoded; the caller filters by layer name only.

  Byte buffers are accepted as any indexed, `count`-able collection of byte
  values (a Clojure vector of ints 0-255, or a JVM `byte-array`/`bytes`, or a
  JS `Uint8Array`/`Array`) — `normalize-bytes` converts to a Clojure vector
  of unsigned ints once up front so the rest of the decoder is host-neutral.")

;; ---------------------------------------------------------------------------
;; Byte buffer normalization
;; ---------------------------------------------------------------------------

(defn normalize-bytes
  "Convert any indexed byte-ish collection into a Clojure vector of unsigned
  ints (0-255). Accepts a JVM byte-array (signed bytes, masked here), a
  Clojure vector/seq of ints, or a JS array/typed array."
  [buf]
  (mapv #(bit-and (int %) 0xff) (seq buf)))

;; ---------------------------------------------------------------------------
;; Tiny PBF reader — pure functions over [buf pos], mirrors mvt.rs PbfReader
;; ---------------------------------------------------------------------------

(def ^:const wire-varint 0)
(def ^:const wire-64bit 1)
(def ^:const wire-len 2)
(def ^:const wire-32bit 5)

(defn read-varint
  "Read a base-128 varint from `buf` (vector of unsigned byte ints) starting
  at `pos`. Returns `[value new-pos]`."
  [buf pos]
  (let [n (count buf)]
    (loop [shift 0 out 0 pos pos]
      (if (>= pos n)
        [out pos]
        (let [b (nth buf pos)
              pos' (inc pos)
              out' (bit-or out (bit-shift-left (bit-and b 0x7f) shift))]
          (if (zero? (bit-and b 0x80))
            [out' pos']
            (if (>= (+ shift 7) 64)
              [out' pos']
              (recur (+ shift 7) out' pos'))))))))

(defn read-tag
  "Read a protobuf field tag. Returns `[[field wire] new-pos]`, or nil at
  end of buffer."
  [buf pos]
  (when (< pos (count buf))
    (let [[v pos'] (read-varint buf pos)]
      [[(bit-shift-right v 3) (bit-and v 0x7)] pos'])))

(defn read-len-delim
  "Read a length-delimited field's payload. Returns `[payload-vec new-pos]`."
  [buf pos]
  (let [[len pos'] (read-varint buf pos)
        end (min (+ pos' len) (count buf))]
    [(subvec (vec buf) pos' end) end]))

(defn read-fixed32
  "Read 4 little-endian bytes as an unsigned 32-bit int. Returns
  `[u32 new-pos]`."
  [buf pos]
  (let [n (count buf)
        b (fn [i] (if (< (+ pos i) n) (nth buf (+ pos i)) 0))]
    [(bit-or (b 0)
             (bit-shift-left (b 1) 8)
             (bit-shift-left (b 2) 16)
             (bit-shift-left (b 3) 24))
     (min (+ pos 4) n)]))

(def ^:private byte-scale
  ;; 2^(8*i). Literals, not `(bit-shift-left 1 (* 8 i))`: cljs takes shift
  ;; counts mod 32, so that expression is 1 at i=4 and 2^24 at i=7. Each of
  ;; these is a power of two, exact as a JVM long and as a JS double alike.
  [1 256 65536 16777216 4294967296 1099511627776 281474976710656 72057594037927936])

(defn fixed64-bytes
  "The 8 little-endian bytes at `pos`, zero-padded past the end.
  Returns `[bytes new-pos]`."
  [buf pos]
  (let [n (count buf)]
    [(mapv (fn [i] (if (< (+ pos i) n) (bit-and (nth buf (+ pos i)) 0xff) 0)) (range 8))
     (min (+ pos 8) n)]))

(defn read-fixed64
  "Read 8 little-endian bytes as an unsigned 64-bit int. Returns `[u64 new-pos]`.

  This used to accumulate with `(bit-shift-left b (* 8 i))`. cljs takes shift
  counts mod 32, so bytes 4 through 7 were shifted by 0, 8, 16 and 24 -- they
  landed on top of bytes 0 through 3 instead of above them.

  On ClojureScript a value above 2^53 is not exactly representable whatever the
  arithmetic; that limit is the runtime's. Decoding a float64 no longer goes
  through this function at all -- see `read-f64`, which never forms the integer."
  [buf pos]
  (let [[bs new-pos] (fixed64-bytes buf pos)]
    [(reduce (fn [acc i] (+ acc (* (nth bs i) (nth byte-scale i)))) 0 (range 8))
     new-pos]))

(defn skip-field
  "Advance `pos` past a field of the given wire type without decoding it."
  [buf pos wire]
  (cond
    (= wire wire-varint) (second (read-varint buf pos))
    (= wire wire-len) (second (read-len-delim buf pos))
    (= wire wire-64bit) (min (+ pos 8) (count buf))
    (= wire wire-32bit) (min (+ pos 4) (count buf))
    :else pos)) ; unknown wire type — stop scanning safely (matches Rust)

;; ---------------------------------------------------------------------------
;; Varint helpers
;; ---------------------------------------------------------------------------

(defn zigzag
  "Decode a zigzag-encoded 32-bit varint into a signed int."
  [n]
  (bit-xor (unsigned-bit-shift-right n 1) (- (bit-and n 1))))

(defn zigzag64
  "Decode a zigzag-encoded 64-bit varint into a signed long."
  [n]
  (bit-xor (unsigned-bit-shift-right n 1) (- (bit-and n 1))))

(defn- read-packed-uint32
  "Decode a packed-varint payload (already length-delimited) into a vector
  of uint32 values."
  [buf]
  (let [n (count buf)]
    (loop [pos 0 out []]
      (if (>= pos n)
        out
        (let [[v pos'] (read-varint buf pos)]
          (recur pos' (conj out v)))))))

;; ---------------------------------------------------------------------------
;; Tile coordinate projection
;; ---------------------------------------------------------------------------

(defn tile-local-to-lng-lat
  "Convert tile-local pixel coords `[x y]` (within `[0, extent]`) at tile
  `{:z :x :y}` into geographic `[lng lat]`."
  [x y extent tile]
  (let [z (:z tile)
        n (double (bit-shift-left 1 z))
        tx (+ (double (:x tile)) (/ (double x) extent))
        ty (+ (double (:y tile)) (/ (double y) extent))
        lng (- (* (/ tx n) 360.0) 180.0)
        lat-rad #?(:clj  (Math/atan (Math/sinh (* Math/PI (- 1.0 (* 2.0 (/ ty n))))))
                   :cljs (js/Math.atan (.sinh js/Math (* js/Math.PI (- 1.0 (* 2.0 (/ ty n)))))))
        lat #?(:clj  (Math/toDegrees lat-rad)
               :cljs (/ (* lat-rad 180.0) js/Math.PI))]
    [lng lat]))

;; ---------------------------------------------------------------------------
;; Value / tag decoding
;; ---------------------------------------------------------------------------

(defn- bytes->str [buf]
  #?(:clj  (String. (byte-array (map unchecked-byte buf)) "UTF-8")
     :cljs (.decode (js/TextDecoder. "utf-8") (js/Uint8Array. (clj->js buf)))))

(defn- f32-bits->double [bits]
  #?(:clj  (double (Float/intBitsToFloat (unchecked-int bits)))
     :cljs (let [dv (js/DataView. (js/ArrayBuffer. 4))]
             (.setUint32 dv 0 bits true)
             (.getFloat32 dv 0 true))))

(defn- f64-from-bytes
  "The IEEE-754 double whose little-endian representation is `bs`.

  The `:cljs` branch used to take a u64 and split it with
  `(unsigned-bit-shift-right bits 32)` for the high word -- which on
  ClojureScript is `bits >>> 0`, the LOW word. The high word equalled the low
  word, in a branch that exists only for ClojureScript. Measured 2026-08-25:
  a Value message carrying 3.14 decoded as 4.293144868248468e+86 on nbb and
  3.14 on the JVM.

  Taking bytes rather than an assembled integer removes the second problem
  underneath it as well: a float64 bit pattern is routinely above 2^53, where a
  JS number cannot hold it exactly, so no arithmetic on the u64 could have been
  correct. Here the bytes go straight into the view."
  [bs]
  #?(:clj  (Double/longBitsToDouble
            (reduce (fn [acc i] (bit-or acc (bit-shift-left (long (nth bs i)) (* 8 i))))
                    0 (range 8)))
     :cljs (let [dv (js/DataView. (js/ArrayBuffer. 8))]
             (dotimes [i 8] (.setUint8 dv i (nth bs i)))
             (.getFloat64 dv 0 true))))

(defn read-f64
  "Read 8 little-endian bytes at `pos` as a double. Returns `[double new-pos]`."
  [buf pos]
  (let [[bs new-pos] (fixed64-bytes buf pos)]
    [(f64-from-bytes bs) new-pos]))

(defn decode-value-message
  "Decode a MVT `Value` message payload into a Clojure scalar: string,
  double, long, or boolean. Returns nil for an empty/unknown value."
  [buf]
  (loop [pos 0]
    (if-let [[[field wire] pos'] (read-tag buf pos)]
      (cond
        (and (= field 1) (= wire wire-len))
        (let [[v _] (read-len-delim buf pos')] (bytes->str v))

        (and (= field 2) (= wire wire-32bit))
        (let [[bits _] (read-fixed32 buf pos')] (f32-bits->double bits))

        (and (= field 3) (= wire wire-64bit))
        (let [[value _] (read-f64 buf pos')] value)

        (and (= field 4) (= wire wire-varint))
        (let [[v _] (read-varint buf pos')] v)

        (and (= field 5) (= wire wire-varint))
        (let [[v _] (read-varint buf pos')] v)

        (and (= field 6) (= wire wire-varint))
        (let [[v _] (read-varint buf pos')] (zigzag64 v))

        (and (= field 7) (= wire wire-varint))
        (let [[v _] (read-varint buf pos')] (not (zero? v)))

        :else
        (recur (skip-field buf pos' wire)))
      nil)))

(defn- decode-feature-tags [tags-payload keys-vec values-vec]
  (if (nil? tags-payload)
    {}
    (let [tags (read-packed-uint32 tags-payload)]
      (into {}
            (comp (partition-all 2)
                  (filter #(= 2 (count %)))
                  (keep (fn [[ki vi]]
                          (let [k (get keys-vec ki)
                                v (get values-vec vi)]
                            (when (and k v) [k v])))))
            tags))))

;; ---------------------------------------------------------------------------
;; Geometry command stream decoding
;; ---------------------------------------------------------------------------

(defn- apply-points
  "Process `cnt` (dx,dy) point pairs for a MoveTo(1)/LineTo(2) command,
  advancing the decoder state map. Mirrors the Rust `for _ in 0..count`
  inner loop in `decode_feature`."
  [cmds cmd cnt geom-type extent tile state]
  (let [n (count cmds)]
    (loop [k 0 {:keys [i x-local y-local current-path start-pt paths] :as st} state]
      (if (or (>= k cnt) (>= (inc i) n))
        st
        (let [dx (zigzag (nth cmds i))
              dy (zigzag (nth cmds (inc i)))
              i' (+ i 2)
              x' (+ x-local dx)
              y' (+ y-local dy)
              geo (tile-local-to-lng-lat x' y' extent tile)]
          (if (= cmd 1)
            ;; MoveTo: end any open line, start a new one (or store a point).
            (let [line-flush? (and (seq current-path) (= geom-type 2))
                  paths' (if line-flush? (conj paths current-path) paths)]
              (if (= geom-type 1)
                (recur (inc k) {:i i' :x-local x' :y-local y' :current-path []
                                 :start-pt start-pt :paths (conj paths' [geo])})
                (recur (inc k) {:i i' :x-local x' :y-local y' :current-path [geo]
                                 :start-pt geo :paths paths'})))
            ;; LineTo
            (recur (inc k) {:i i' :x-local x' :y-local y'
                             :current-path (conj current-path geo)
                             :start-pt start-pt :paths paths})))))))

(defn- decode-geometry-commands
  "Decode a packed uint32 command stream into `paths` (vector of vector of
  `[lng lat]`), then assemble the final geometry per `geom-type`."
  [cmds geom-type extent tile]
  (let [n (count cmds)]
    (loop [i 0 x-local 0 y-local 0 current-path [] start-pt nil paths []]
      (if (< i n)
        (let [header (nth cmds i)
              cmd (bit-and header 0x7)
              cnt (bit-shift-right header 3)
              i1 (inc i)]
          (cond
            (or (= cmd 1) (= cmd 2))
            (let [{:keys [i x-local y-local current-path start-pt paths]}
                  (apply-points cmds cmd cnt geom-type extent tile
                                {:i i1 :x-local x-local :y-local y-local
                                 :current-path current-path :start-pt start-pt
                                 :paths paths})]
              (recur i x-local y-local current-path start-pt paths))

            (= cmd 7) ; ClosePath — ring close.
            (let [closed (if start-pt (conj current-path start-pt) current-path)
                  flush? (and (seq closed) (= geom-type 3))
                  paths' (if flush? (conj paths closed) paths)
                  current-path' (if flush? [] closed)]
              (recur i1 x-local y-local current-path' nil paths'))

            :else
            (recur i1 x-local y-local current-path start-pt paths)))
        (let [paths (if (seq current-path) (conj paths current-path) paths)]
          (case (int geom-type)
            1 (if (and (= (count paths) 1) (= (count (first paths)) 1))
                {:type :point :coordinates (first (first paths))}
                {:type :multi-point
                 :coordinates (vec (keep #(when (= (count %) 1) (first %)) paths))})
            2 (if (= (count paths) 1)
                {:type :line-string :coordinates (first paths)}
                {:type :multi-line-string :coordinates paths})
            3 {:type :polygon :coordinates paths}
            nil))))))

;; ---------------------------------------------------------------------------
;; Feature / layer decoding
;; ---------------------------------------------------------------------------

(defn- decode-feature [payload tile extent keys-vec values-vec]
  (loop [pos 0 geom-type 0 tags-payload nil geometry-payload nil]
    (if-let [[[field wire] pos'] (read-tag payload pos)]
      (cond
        (and (= field 2) (= wire wire-len))
        (let [[v pos''] (read-len-delim payload pos')]
          (recur pos'' geom-type v geometry-payload))

        (and (= field 3) (= wire wire-varint))
        (let [[v pos''] (read-varint payload pos')]
          (recur pos'' v tags-payload geometry-payload))

        (and (= field 4) (= wire wire-len))
        (let [[v pos''] (read-len-delim payload pos')]
          (recur pos'' geom-type tags-payload v))

        :else
        (recur (skip-field payload pos' wire) geom-type tags-payload geometry-payload))
      (when geometry-payload
        (let [properties (decode-feature-tags tags-payload keys-vec values-vec)
              cmds (read-packed-uint32 geometry-payload)
              geometry (decode-geometry-commands cmds geom-type extent tile)]
          (when geometry
            {:geometry geometry :properties properties}))))))

(defn- parse-layer
  "Decode a Layer message payload into `{:name :keys :values :extent
  :feature-payloads}`."
  [layer-buf]
  (loop [lpos 0 name nil keys-vec [] values-vec [] extent 4096 feature-payloads []]
    (if-let [[[lf lw] lpos'] (read-tag layer-buf lpos)]
      (cond
        (and (= lf 1) (= lw wire-len))
        (let [[raw lpos''] (read-len-delim layer-buf lpos')]
          (recur lpos'' (bytes->str raw) keys-vec values-vec extent feature-payloads))

        (and (= lf 2) (= lw wire-len))
        (let [[fp lpos''] (read-len-delim layer-buf lpos')]
          (recur lpos'' name keys-vec values-vec extent (conj feature-payloads fp)))

        (and (= lf 3) (= lw wire-len))
        (let [[raw lpos''] (read-len-delim layer-buf lpos')]
          (recur lpos'' name (conj keys-vec (bytes->str raw)) values-vec extent feature-payloads))

        (and (= lf 4) (= lw wire-len))
        (let [[raw lpos''] (read-len-delim layer-buf lpos')]
          (recur lpos'' name keys-vec (conj values-vec (decode-value-message raw)) extent feature-payloads))

        (and (= lf 5) (= lw wire-varint))
        (let [[v lpos''] (read-varint layer-buf lpos')]
          (recur lpos'' name keys-vec values-vec (int v) feature-payloads))

        :else
        (recur (skip-field layer-buf lpos' lw) name keys-vec values-vec extent feature-payloads))
      {:name name :keys keys-vec :values values-vec :extent extent
       :feature-payloads feature-payloads})))

(defn decode-layer-features
  "Decode an MVT PBF blob (any byte-ish buffer, see `normalize-bytes`) and
  return the named layer's features as
  `{:features [{:geometry {:type ... :coordinates ...} :properties {...}} ...]}`.
  `tile` is `{:z :x :y}`."
  [pbf tile layer-name]
  (let [buf (normalize-bytes pbf)]
    {:features
     (loop [pos 0 out []]
       (if-let [[[field wire] pos'] (read-tag buf pos)]
         (if (and (= field 3) (= wire wire-len))
           (let [[layer-buf pos''] (read-len-delim buf pos')
                 {:keys [name keys values extent feature-payloads]} (parse-layer layer-buf)
                 out' (if (and (= name layer-name) (pos? extent))
                        (into out (keep #(decode-feature % tile extent keys values)) feature-payloads)
                        out)]
             (recur pos'' out'))
           (recur (skip-field buf pos' wire) out))
         out))}))

(defn decode-layer
  "Decode an MVT PBF blob and flatten the named layer's geometries to
  `{:lines [...] :polygons [...] :points [...]}` in geographic coordinates
  (mirrors the Rust `decode_layer` convenience wrapper)."
  [pbf tile layer-name]
  (reduce
   (fn [acc {:keys [geometry]}]
     (case (:type geometry)
       :point (update acc :points conj (:coordinates geometry))
       :multi-point (update acc :points into (:coordinates geometry))
       :line-string (update acc :lines conj (:coordinates geometry))
       :multi-line-string (update acc :lines into (:coordinates geometry))
       :polygon (update acc :polygons into (:coordinates geometry))
       acc))
   {:lines [] :polygons [] :points []}
   (:features (decode-layer-features pbf tile layer-name))))
