(ns gltf
  "Zero-dep portable CLJC. Restored from the legacy kami-engine/kami-gltf Rust
  crate (kotoba-lang/kami-engine, deleted in PR #82 \"Remove Rust workspace
  from kami-engine\") as part of the clj-wgsl migration (ADR-2607010930,
  com-junkawasaki/root).

  Purpose: minimal binary glTF 2.0 (.glb) *writer* — takes a `LoadedMesh`-shaped
  map (interleaved [pos3 norm3 uv2] × N float vertices + u32 indices) plus a
  flat RGBA base color, and emits a self-contained .glb byte sequence (JSON
  chunk + BIN chunk, 4-byte aligned, per the glTF 2.0 binary container spec).
  No external glTF/JSON dependency — the JSON chunk is hand-serialized here,
  matching the original Rust's `serde_json::json!` literal shape exactly.

  Despite the crate name suggesting a *loader*, the original `kami-gltf/src/lib.rs`
  contained only an *exporter* (`export_glb`) with no parsing/loading logic —
  this port is faithful to that (there was nothing else to port).

  Platform divergence (f32 <-> IEEE-754 le bytes, byte-array construction) is
  isolated behind `#?(:clj ... :cljs ...)` reader conditionals; all shape/JSON
  logic above that is pure, portable data + functions.

  GLB binary-container framing (12-byte header + JSON chunk + BIN chunk) is
  delegated to `kotoba-lang/glb` (ADR-0048 §5, `com-junkawasaki/root`) —
  extracted because the same container format was also independently
  hand-rolled (read-only) in `kotoba-lang/vrm`'s `vrm.glb`. `u32->le-bytes`
  / `le-bytes->u32` / `string->byte-seq` / `pad-len` / the GLB magic+version+
  chunk-type constants below are re-exported from `glb` for call-site
  backward compatibility (nothing here reimplements them anymore); this
  namespace still owns everything glTF-JSON-specific (`build-gltf-json`,
  `->json`, `compute-bounds`, mesh vertex/index byte encoding).

  **Parser (ADR-0048 §3, com-junkawasaki/root).** This namespace was
  write-only until this addition — its own former docstring said so
  plainly ('there was no parsing/loading logic in the file'). `parse-gltf`
  closes ADR-0044's gap-inventory row ('glTF loader | export-only stub |
  full GLTFLoader'): given a `.glb` byte sequence (via `glb/parse-glb`,
  chunk framing + generic JSON decode) or an already-parsed glTF-JSON map
  (the JSON-only `.gltf` case), it decodes every accessor's ACTUAL
  typed-array bytes per `componentType`/`type` (`decode-accessor`) into
  real EDN vectors — not raw buffers — for `POSITION`/`NORMAL`/
  `TEXCOORD_0`/`JOINTS_0`/`WEIGHTS_0`/indices. See `decode-accessor`'s and
  `parse-gltf`'s own docstrings for the exact shape and v0 limitations
  (sparse accessors, external-file buffer URIs)."
  (:require [kotoba.lang.text] [glb]
            [glb.json :as glb-json]))

;; ---------------------------------------------------------------------------
;; Little-endian byte encoding — re-exported from `glb` (see ns docstring)
;; ---------------------------------------------------------------------------

(def u32->le-bytes glb/u32->le-bytes)
(def le-bytes->u32 glb/le-bytes->u32)

(defn f32->le-bytes
  "f32 -> 4 little-endian byte ints (0-255) of the IEEE-754 single-precision
  bit pattern, matching Rust's `f32::to_le_bytes`."
  [x]
  #?(:clj
     (u32->le-bytes (Float/floatToIntBits (float x)))
     :cljs
     (let [buf (js/ArrayBuffer. 4)
           view (js/DataView. buf)]
       (.setFloat32 view 0 x true)
       [(.getUint8 view 0) (.getUint8 view 1) (.getUint8 view 2) (.getUint8 view 3)])))

(def string->byte-seq glb/string->byte-seq)

(defn bytes-seq->platform
  "Convert a seq of byte ints (0-255) to the platform's native byte buffer:
  a `byte[]` on the JVM, a `js/Uint8Array` in ClojureScript."
  [s]
  #?(:clj (byte-array (map unchecked-byte s))
     :cljs (js/Uint8Array. (clj->js (vec s)))))

(defn platform-bytes->byte-seq
  "Inverse of `bytes-seq->platform`: the platform's native byte buffer
  (`byte[]` on the JVM, `js/Uint8Array` in ClojureScript) -> a plain vector
  of byte ints (0-255). Idempotent on an already-plain byte-int vector (the
  JVM branch just re-masks each element to 0-255), so callers can pass
  either a platform buffer or a byte-seq like `export-glb-byte-seq`'s own
  output."
  [buf]
  #?(:clj (mapv #(bit-and (int %) 0xFF) buf)
     :cljs (vec buf)))

(def pad-len glb/pad-len)

(defn le-bytes->f32
  "4 little-endian byte ints -> IEEE-754 single-precision float. Inverse of
  `f32->le-bytes`."
  [bs]
  #?(:clj (Float/intBitsToFloat (unchecked-int (glb/le-bytes->u32 bs)))
     :cljs (let [buf (js/ArrayBuffer. 4)
                 view (js/DataView. buf)]
             (doseq [i (range 4)] (.setUint8 view i (nth bs i)))
             (.getFloat32 view 0 true))))

(defn le-bytes->u16
  "2 little-endian byte ints -> unsigned 16-bit int."
  [[b0 b1]]
  (bit-or b0 (bit-shift-left b1 8)))

(defn le-bytes->i16
  "2 little-endian byte ints -> signed 16-bit int (two's complement)."
  [bs]
  (let [u (le-bytes->u16 bs)]
    (if (>= u 0x8000) (- u 0x10000) u)))

(defn byte->i8
  "1 byte int (0-255) -> signed 8-bit int (two's complement)."
  [b]
  (if (>= b 0x80) (- b 0x100) b))

;; ---------------------------------------------------------------------------
;; Minimal JSON serialization (only what the glTF JSON chunk needs)
;; ---------------------------------------------------------------------------

(defn json-escape [^String s]
  (-> s
      (kotoba.lang.text/replace "\\" "\\\\")
      (kotoba.lang.text/replace "\"" "\\\"")))

(defn ->json
  "Serialize a plain CLJC value (nil/bool/number/string/keyword/map/sequential)
  to a JSON string. Map keys may be keywords or strings."
  [v]
  (cond
    (nil? v) "null"
    (true? v) "true"
    (false? v) "false"
    (keyword? v) (str "\"" (json-escape (name v)) "\"")
    (string? v) (str "\"" (json-escape v) "\"")
    (map? v) (str "{"
                   (kotoba.lang.text/join ","
                     (map (fn [[k val]]
                            (str "\"" (json-escape (if (keyword? k) (name k) (str k))) "\""
                                 ":" (->json val)))
                          v))
                   "}")
    (number? v) (str v)
    (sequential? v) (str "[" (kotoba.lang.text/join "," (map ->json v)) "]")
    :else (throw (ex-info "gltf/->json: unsupported value" {:value v}))))

;; ---------------------------------------------------------------------------
;; Mesh bounds
;; ---------------------------------------------------------------------------

(defn compute-bounds
  "Compute [min max] position bounds (each a 3-vector) over the first
  `vertex-count` interleaved [pos3 norm3 uv2] vertices (stride 8 floats)."
  [vertices vertex-count]
  (loop [i 0
         mn [##Inf ##Inf ##Inf]
         mx [##-Inf ##-Inf ##-Inf]]
    (if (>= i vertex-count)
      [mn mx]
      (let [base (* i 8)
            p [(nth vertices base) (nth vertices (+ base 1)) (nth vertices (+ base 2))]]
        (recur (inc i) (mapv min mn p) (mapv max mx p))))))

;; ---------------------------------------------------------------------------
;; glTF JSON chunk
;; ---------------------------------------------------------------------------

(defn build-gltf-json
  "Build the glTF 2.0 JSON chunk (as a plain CLJC map) describing a single
  scene/node/mesh/material, matching the original Rust's `serde_json::json!`
  literal 1:1."
  [{:keys [color vertex-count index-count vertex-byte-len index-byte-len
           total-buffer-len min-pos max-pos]}]
  {:asset {:version "2.0" :generator "kami-scad"}
   :scene 0
   :scenes [{:nodes [0]}]
   :nodes [{:mesh 0}]
   :meshes [{:primitives [{:attributes {:POSITION 0 :NORMAL 1 :TEXCOORD_0 2}
                            :indices 3
                            :material 0}]}]
   :materials [{:pbrMetallicRoughness {:baseColorFactor color
                                        :metallicFactor 0.0
                                        :roughnessFactor 0.5}}]
   :accessors [{:bufferView 0
                :componentType 5126 ;; FLOAT
                :count vertex-count
                :type "VEC3"
                :byteOffset 0
                :min min-pos
                :max max-pos}
               {:bufferView 0
                :componentType 5126
                :count vertex-count
                :type "VEC3"
                :byteOffset 12} ;; after position (3 floats)
               {:bufferView 0
                :componentType 5126
                :count vertex-count
                :type "VEC2"
                :byteOffset 24} ;; after position + normal (6 floats)
               {:bufferView 1
                :componentType 5125 ;; UNSIGNED_INT
                :count index-count
                :type "SCALAR"}]
   :bufferViews [{:buffer 0
                   :byteOffset 0
                   :byteLength vertex-byte-len
                   :byteStride 32 ;; 8 floats × 4 bytes
                   :target 34962} ;; ARRAY_BUFFER
                  {:buffer 0
                   :byteOffset vertex-byte-len
                   :byteLength index-byte-len
                   :target 34963}] ;; ELEMENT_ARRAY_BUFFER
   :buffers [{:byteLength total-buffer-len}]})

;; ---------------------------------------------------------------------------
;; GLB (binary container) assembly — delegated to kotoba-lang/glb (ADR-0048 §5)
;; ---------------------------------------------------------------------------

(def glb-magic glb/glb-magic) ;; "glTF"
(def glb-version glb/glb-version)
(def json-chunk-type glb/chunk-type-json) ;; "JSON"
(def bin-chunk-type glb/chunk-type-bin)  ;; "BIN\0"

(defn export-glb-byte-seq
  "Pure, portable core: `mesh` (map with :vertices :indices :vertex-count
  :index-count) + `color` (RGBA 4-vector) -> vector of byte ints (0-255)
  forming a complete binary glTF 2.0 (.glb) file. No platform-specific types
  involved — safe to unit test directly on any platform.

  glTF-JSON building (`build-gltf-json`) and mesh vertex/index byte encoding
  stay here; the actual GLB container framing (header + chunk assembly +
  padding) is delegated to `glb/write-glb-raw` (`kotoba-lang/glb`, the
  canonical GLB codec, ADR-0048 §5) — the JSON bytes handed to it are already
  fully serialized (via this namespace's own `->json`), so `glb` does no
  re-encoding, just pure chunk framing."
  [{:keys [vertices indices vertex-count index-count] :as mesh} color]
  (let [vertex-bytes (vec (mapcat f32->le-bytes vertices))
        index-bytes (vec (mapcat u32->le-bytes indices))
        vertex-byte-len (count vertex-bytes)
        index-byte-len (count index-bytes)
        total-buffer-len (+ vertex-byte-len index-byte-len)
        [min-pos max-pos] (compute-bounds vertices vertex-count)
        json-map (build-gltf-json {:color color
                                    :vertex-count vertex-count
                                    :index-count index-count
                                    :vertex-byte-len vertex-byte-len
                                    :index-byte-len index-byte-len
                                    :total-buffer-len total-buffer-len
                                    :min-pos min-pos
                                    :max-pos max-pos})
        json-bytes (string->byte-seq (->json json-map))
        bin-bytes (vec (concat vertex-bytes index-bytes))]
    (glb/write-glb-raw json-bytes bin-bytes)))

(defn export-glb
  "Export `mesh` + RGBA `color` to a binary glTF 2.0 (.glb) buffer in the
  platform's native byte type (`byte[]` on the JVM, `js/Uint8Array` in cljs).
  Equivalent to the original Rust `export_glb`."
  [mesh color]
  (bytes-seq->platform (export-glb-byte-seq mesh color)))

;; ---------------------------------------------------------------------------
;; Multi-node scene graph (ADR-2607100100 M7, com-junkawasaki/root). Everything
;; above this point assembles exactly one node/one mesh/one material —
;; `build-gltf-json` is a fixed literal shape, not a general builder.
;; `build-gltf-scene-json`/`export-glb-scene-byte-seq` generalize it to an
;; arbitrary node tree (organizational/transform-only nodes freely mixed with
;; real-mesh leaf nodes, at any depth) — the shape `kami-app-amenominaka`'s
;; USD export already gets for free from `usd.core/usda`'s variadic
;; `[:def "Xform" name & children]` hiccup form, which glTF's JSON has no
;; equivalent primitive for, so it has to be assembled here explicitly.
;; ---------------------------------------------------------------------------

(defn- default-materials []
  [{:pbrMetallicRoughness {:baseColorFactor [0.62 0.60 0.66 1.0]
                            :metallicFactor 0.0
                            :roughnessFactor 0.65}}])

(defn- layout-meshes
  "Concatenate every mesh's [pos3 norm3 uv2]-interleaved vertex bytes + u32
  index bytes into ONE combined buffer (glTF `:buffers` index 0 throughout —
  same one-implicit-buffer convention `resolve-buffers` already documents),
  emitting each mesh's own 4 accessors (POSITION/NORMAL/TEXCOORD_0/indices)
  + 2 bufferViews (vertex/index) at the right global index/byte offset.
  `meshes`: a seq of `{:vertices :indices :vertex-count :index-count
  :material}` maps (`:material` an index into the scene's `:materials`,
  defaults to 0). Returns `{:accessors :buffer-views :gltf-meshes :bin-bytes}`
  — `gltf-meshes` is glTF JSON `:meshes` (one entry per input mesh, its
  primitive's `:attributes`/`:indices` pointing at the right global accessor
  indices)."
  [meshes]
  (reduce
   (fn [acc {:keys [vertices indices vertex-count index-count material]}]
     (let [vertex-bytes (vec (mapcat f32->le-bytes vertices))
           index-bytes (vec (mapcat u32->le-bytes indices))
           vertex-byte-len (count vertex-bytes)
           index-byte-len (count index-bytes)
           [min-pos max-pos] (compute-bounds vertices vertex-count)
           buf-offset (:cursor acc)
           bv-base (count (:buffer-views acc))
           acc-base (count (:accessors acc))
           pos-accessor {:bufferView bv-base :componentType 5126 :count vertex-count
                         :type "VEC3" :byteOffset 0 :min min-pos :max max-pos}
           normal-accessor {:bufferView bv-base :componentType 5126 :count vertex-count
                            :type "VEC3" :byteOffset 12}
           uv-accessor {:bufferView bv-base :componentType 5126 :count vertex-count
                       :type "VEC2" :byteOffset 24}
           index-accessor {:bufferView (inc bv-base) :componentType 5125
                           :count index-count :type "SCALAR"}
           vertex-bv {:buffer 0 :byteOffset buf-offset :byteLength vertex-byte-len
                     :byteStride 32 :target 34962}
           index-bv {:buffer 0 :byteOffset (+ buf-offset vertex-byte-len)
                    :byteLength index-byte-len :target 34963}
           gltf-mesh {:primitives [{:attributes {:POSITION acc-base :NORMAL (+ acc-base 1)
                                                 :TEXCOORD_0 (+ acc-base 2)}
                                    :indices (+ acc-base 3)
                                    :material (or material 0)}]}]
       (-> acc
           (update :accessors into [pos-accessor normal-accessor uv-accessor index-accessor])
           (update :buffer-views into [vertex-bv index-bv])
           (update :gltf-meshes conj gltf-mesh)
           (update :bin-bytes into (concat vertex-bytes index-bytes))
           (assoc :cursor (+ buf-offset vertex-byte-len index-byte-len)))))
   {:accessors [] :buffer-views [] :gltf-meshes [] :bin-bytes [] :cursor 0}
   meshes))

(defn- flatten-node
  "DFS-flatten one nested `node` ({:name :translation :mesh :children}, all
  optional except `:children` defaulting to `[]`) into `state`
  ({:nodes [] :meshes []}), children first (their indices are needed to
  build the parent's own `:children` array). `:mesh`, if present, is a mesh
  map (per `layout-meshes`'s input shape) — appended to `state`'s `:meshes`
  and referenced from the emitted glTF node by that index; a node with no
  `:mesh` is a pure transform/organizational node (glTF has no separate
  \"Xform\" type — an empty node IS the equivalent). Returns `[state'
  node-index]`."
  [state node]
  (let [{:keys [name translation mesh children]} node
        [state mesh-idx] (if mesh
                            [(update state :meshes conj mesh) (count (:meshes state))]
                            [state nil])
        [state child-idxs] (reduce (fn [[state idxs] child]
                                      (let [[state' idx] (flatten-node state child)]
                                        [state' (conj idxs idx)]))
                                    [state []]
                                    children)
        gltf-node (cond-> {}
                    name (assoc :name name)
                    translation (assoc :translation translation)
                    mesh-idx (assoc :mesh mesh-idx)
                    (seq child-idxs) (assoc :children (vec child-idxs)))
        node-idx (count (:nodes state))]
    [(update state :nodes conj gltf-node) node-idx]))

(defn build-gltf-scene-json
  "Build a full multi-node glTF 2.0 JSON scene (as a plain CLJC map) from
  `roots` (a seq of nested node trees — see `flatten-node`'s docstring for
  the node shape) + `total-buffer-len`/the pre-laid-out `accessors`/
  `buffer-views`/`gltf-meshes`/`nodes`/`root-idxs` from
  `layout-meshes`+`flatten-node`. Call `export-glb-scene-byte-seq` instead
  of this directly unless you need the JSON map on its own (e.g. for a
  JSON-only `.gltf`, no BIN chunk)."
  [{:keys [accessors buffer-views gltf-meshes nodes root-idxs materials total-buffer-len]}]
  {:asset {:version "2.0" :generator "kami-app-amenominaka"}
   :scene 0
   :scenes [{:nodes (vec root-idxs)}]
   :nodes nodes
   :meshes gltf-meshes
   :materials (or materials (default-materials))
   :accessors accessors
   :bufferViews buffer-views
   :buffers [{:byteLength total-buffer-len}]})

(defn export-glb-scene-byte-seq
  "Pure, portable: `roots` (a seq of nested node trees, see `flatten-node`'s
  docstring) + optional `:materials` (glTF material JSON maps, defaults to
  one neutral grey `pbrMetallicRoughness` material, index 0 — every mesh's
  own `:material` index, if given, indexes into this) -> vector of byte
  ints (0-255) forming a complete binary glTF 2.0 (.glb) file with the full
  node hierarchy, mixing real-mesh leaf nodes and pure transform/
  organizational nodes freely at any depth (unlike `export-glb-byte-seq`,
  which only ever emits exactly one node/one mesh)."
  ([roots] (export-glb-scene-byte-seq roots nil))
  ([roots {:keys [materials]}]
   (let [[{:keys [nodes meshes]} root-idxs]
         (reduce (fn [[state idxs] root]
                    (let [[state' idx] (flatten-node state root)]
                      [state' (conj idxs idx)]))
                  [{:nodes [] :meshes []} []]
                  roots)
         {:keys [accessors buffer-views gltf-meshes bin-bytes cursor]} (layout-meshes meshes)
         json-map (build-gltf-scene-json {:accessors accessors :buffer-views buffer-views
                                          :gltf-meshes gltf-meshes :nodes nodes
                                          :root-idxs root-idxs :materials materials
                                          :total-buffer-len cursor})
         json-bytes (string->byte-seq (->json json-map))]
     (glb/write-glb-raw json-bytes (vec bin-bytes)))))

(defn export-glb-scene
  "`export-glb-scene-byte-seq` in the platform's native byte type (`byte[]`
  on the JVM, `js/Uint8Array` in cljs)."
  ([roots] (export-glb-scene roots nil))
  ([roots opts] (bytes-seq->platform (export-glb-scene-byte-seq roots opts))))

;; ---------------------------------------------------------------------------
;; Accessor decoding (ADR-0048 §3) — componentType/type -> real typed
;; values, not raw buffer bytes
;; ---------------------------------------------------------------------------

(def ^:private component-type-byte-size
  "glTF `componentType` -> byte size. 5120 BYTE / 5121 UNSIGNED_BYTE / 5122
  SHORT / 5123 UNSIGNED_SHORT / 5125 UNSIGNED_INT / 5126 FLOAT (5124 INT
  does not exist in the glTF spec)."
  {5120 1 5121 1 5122 2 5123 2 5125 4 5126 4})

(def ^:private type-component-count
  "glTF accessor `type` string -> number of components per element."
  {"SCALAR" 1 "VEC2" 2 "VEC3" 3 "VEC4" 4 "MAT2" 4 "MAT3" 9 "MAT4" 16})

(def ^:private normalized-max
  "componentType -> divisor for `:normalized true` accessors, per the glTF
  2.0 spec's normalized-integer rule (unsigned types map to [0,1], signed
  to [-1,1])."
  {5120 127 5121 255 5122 32767 5123 65535})

(defn- decode-component
  "Decode one scalar component from `bs` (a byte-int seq of
  `component-type-byte-size` length) per glTF `component-type`."
  [component-type bs]
  (case component-type
    5120 (byte->i8 (first bs))
    5121 (first bs)
    5122 (le-bytes->i16 bs)
    5123 (le-bytes->u16 bs)
    5125 (glb/le-bytes->u32 bs)
    5126 (le-bytes->f32 bs)
    (throw (ex-info "gltf/decode-component: unsupported componentType"
                     {:component-type component-type}))))

(defn decode-accessor
  "Decode accessor `idx` out of parsed glTF `json` (keyword keys, camelCase
  names verbatim — the shape `glb/parse-glb`/`glb.json/parse` produce)
  against `buffers` (a vector of byte-int-vectors, index-aligned with glTF
  `:buffers` — see `resolve-buffers`). Returns a vector of `:count`
  elements: a bare scalar for a `\"SCALAR\"` accessor, or a `[c0 c1 ...]`
  vector for VEC2/VEC3/VEC4/MAT2/MAT3/MAT4 — decoding the ACTUAL
  typed-array bytes per `componentType`/`type`/`byteStride`/`normalized`,
  not returning raw buffers (ADR-0048 §3's whole point).

  v0 limitations (documented, not silently ignored):
  - sparse accessors (`:sparse`) are not supported — throws if present.
  - MATn-of-BYTE/SHORT column-alignment padding (the spec pads each column
    of a matrix accessor to a 4-byte boundary when the component type is
    BYTE/SHORT) is not applied — every writer in this org only ever emits
    FLOAT MAT4 (inverseBindMatrices) or non-matrix types, so this has no
    known real input that would decode wrong today, but a MATn-of-BYTE/
    SHORT accessor from an external file would."
  [json buffers idx]
  (let [accessor (nth (:accessors json) idx)]
    (when (:sparse accessor)
      (throw (ex-info "gltf/decode-accessor: sparse accessors not supported"
                       {:accessor accessor})))
    (let [acc-component-type (:componentType accessor)
          acc-count (:count accessor)
          acc-type (:type accessor)
          acc-normalized (:normalized accessor)
          acc-byte-offset (or (:byteOffset accessor) 0)
          bv-idx (:bufferView accessor)
          buffer-view (nth (:bufferViews json) bv-idx)
          bv-byte-offset (or (:byteOffset buffer-view) 0)
          bv-byte-stride (:byteStride buffer-view)
          buf (nth buffers (or (:buffer buffer-view) 0))
          n-comp (get type-component-count acc-type)
          comp-size (get component-type-byte-size acc-component-type)
          elem-size (* n-comp comp-size)
          stride (or bv-byte-stride elem-size)
          base (+ bv-byte-offset acc-byte-offset)
          divisor (get normalized-max acc-component-type)
          normalize (fn [v] (if (and acc-normalized divisor) (/ (double v) divisor) v))]
      (vec (for [i (range acc-count)]
             (let [elem-off (+ base (* i stride))
                   comps (vec (for [c (range n-comp)]
                                (let [off (+ elem-off (* c comp-size))]
                                  (normalize (decode-component
                                              acc-component-type
                                              (subvec buf off (+ off comp-size)))))))]
               (if (= n-comp 1) (first comps) comps)))))))

;; ---------------------------------------------------------------------------
;; Base64 (JSON-only `.gltf` + `data:` URI buffers only — GLB embeds its
;; buffer directly in the BIN chunk, no base64 involved there)
;; ---------------------------------------------------------------------------

(def ^:private base64-alphabet
  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/")

(def ^:private base64-char->val
  (into {} (map-indexed (fn [i c] [c i]) base64-alphabet)))

(defn base64->byte-seq
  "Decode a base64 string (line breaks/non-alphabet chars ignored, `=`
  padding optional) to a byte-int vector. Only used for JSON-only `.gltf`
  `data:` URI buffers — see `resolve-buffers`."
  [s]
  (let [clean (kotoba.lang.text/replace s #"[^A-Za-z0-9+/]" "")
        n (count clean)]
    (loop [i 0 out (transient [])]
      (if (>= i n)
        (persistent! out)
        (let [c0 (get base64-char->val (nth clean i))
              c1 (when (< (inc i) n) (get base64-char->val (nth clean (inc i))))
              c2 (when (< (+ i 2) n) (get base64-char->val (nth clean (+ i 2))))
              c3 (when (< (+ i 3) n) (get base64-char->val (nth clean (+ i 3))))
              out (conj! out (bit-and (bit-or (bit-shift-left c0 2)
                                               (bit-shift-right (or c1 0) 4))
                                       0xFF))
              out (if c2
                    (conj! out (bit-and (bit-or (bit-shift-left (or c1 0) 4)
                                                 (bit-shift-right c2 2))
                                         0xFF))
                    out)
              out (if c3
                    (conj! out (bit-and (bit-or (bit-shift-left c2 6) c3) 0xFF))
                    out)]
          (recur (+ i 4) out))))))

;; ---------------------------------------------------------------------------
;; GLB / glTF parsing (bidirectional — closes ADR-0044's "glTF loader:
;; export-only stub" gap, per ADR-0048 §3)
;; ---------------------------------------------------------------------------

(defn- resolve-buffers
  "glTF `:buffers` -> vector of byte-int-vectors, index-aligned. Buffer 0
  resolves to the GLB BIN chunk when present (the convention every writer
  in this org uses — `export-glb-byte-seq`/`character.export/export-glb`/
  `vrm.export/export-glb` all emit exactly one implicit buffer backed by
  the BIN chunk); a buffer with a `data:` URI is base64-decoded; anything
  else (an external-file URI) resolves to `nil` — this is a pure, IO-free
  library, it does not fetch files. Decoding an accessor that needs an
  unresolved buffer throws (a `nil` buffer fails loudly at `subvec` inside
  `decode-accessor`, not silently)."
  [json bin]
  (mapv (fn [i {:keys [uri]}]
          (cond
            (and (zero? i) bin) bin
            (and uri (kotoba.lang.text/starts-with? uri "data:"))
            (let [comma (kotoba.lang.text/index-of uri ",")]
              (base64->byte-seq (subs uri (inc comma))))
            :else nil))
        (range) (:buffers json)))

(def ^:private attribute->key
  "glTF primitive `:attributes` key -> the EDN key `decode-primitive` puts
  its decoded values under."
  {:POSITION :positions :NORMAL :normals :TANGENT :tangents
   :TEXCOORD_0 :uvs :TEXCOORD_1 :uvs-1
   :COLOR_0 :colors :JOINTS_0 :joints :WEIGHTS_0 :weights})

(defn- decode-primitive [json buffers {:keys [attributes indices material mode]}]
  (cond-> (reduce-kv (fn [acc attr acc-idx]
                        (if-let [k (get attribute->key attr)]
                          (assoc acc k (decode-accessor json buffers acc-idx))
                          acc))
                      {} attributes)
    indices (assoc :indices (decode-accessor json buffers indices))
    material (assoc :material material)
    mode (assoc :mode mode)))

(defn parse-gltf
  "Parse a glTF asset -> `{:json <parsed glTF-JSON map> :buffers
  [byte-int-vector ...] :meshes [{:primitives [{:positions :normals :uvs
  :tangents :colors :joints :weights :indices :material :mode} ...]} ...]}`,
  with every accessor DECODED into real typed values (vectors of vec3/vec2/
  scalar per componentType/type — see `decode-accessor`), not raw buffer
  bytes. Closes ADR-0044's 'glTF loader: export-only stub' gap (ADR-0048
  §3) — this namespace was write-only before this function existed.

  Accepts any of:
  - a `.glb` byte sequence — platform-native (`byte[]`/`js/Uint8Array`) or
    already a byte-int vector (e.g. straight from `export-glb-byte-seq`'s
    own output) — parsed via `kotoba-lang/glb`'s `parse-glb` (chunk framing
    + generic JSON decode, ADR-0048 §5);
  - an already-parsed glTF-JSON map (the JSON-only `.gltf` case) — buffers
    are resolved from `:buffers` `data:` URIs only (see `resolve-buffers`;
    external-file `.bin` URIs are not fetched, this is a pure IO-free
    library);
  - a raw glTF-JSON string (parsed via `glb.json/parse` first).

  A primitive with no accessor for a given attribute simply omits that key
  (e.g. a primitive with no `JOINTS_0`/`WEIGHTS_0` has no `:joints`/
  `:weights`) rather than filling in a placeholder."
  [glb-bytes-or-json]
  (let [glb-bytes-or-json (if (string? glb-bytes-or-json)
                             (glb-json/parse glb-bytes-or-json)
                             glb-bytes-or-json)
        {:keys [json bin]}
        (if (map? glb-bytes-or-json)
          {:json glb-bytes-or-json :bin nil}
          (glb/parse-glb (platform-bytes->byte-seq glb-bytes-or-json)))
        buffers (resolve-buffers json bin)]
    {:json json
     :buffers buffers
     :meshes (mapv (fn [mesh]
                      {:primitives (mapv #(decode-primitive json buffers %) (:primitives mesh))})
                    (:meshes json))}))
