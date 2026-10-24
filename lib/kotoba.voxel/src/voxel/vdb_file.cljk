(ns voxel.vdb-file
  "The OpenVDB `.vdb` file container: the header, the file-level metadata map,
  and the grid descriptors that say what grids are in the file and where.

  This is the OTHER container. `voxel.nvdb` reads `.nvdb` (NanoVDB), which is
  a different format with a different header, and the two are often confused
  because the names differ by one letter. A `.vdb` is what Houdini, Maya and
  Blender write.

  The layout is transcribed, not inferred, from
  `AcademySoftwareFoundation/openvdb` read 2026-08-24 — `openvdb/io/Archive.cc`
  (`readHeader` / `writeHeader` / `readGridCount`), `openvdb/io/File.cc`
  (`open` and `readGridDescriptors`, which fix the ORDER), `openvdb/io/
  GridDescriptor.cc` (`writeHeader` / `read` / `writeStreamPos`),
  `openvdb/MetaMap.cc` (`readMeta`), `openvdb/Metadata.h` (`read` = size then
  value) and `openvdb/util/Name.h` (`readString` / `writeString`):

      header
        int64  magic          0x56444220 (\"VDB \" as little-endian bytes)
        uint32 file version   225 at time of writing; < 221 is refused
                              UPSTREAM, not merely warned about
        uint32 library major
        uint32 library minor
        uint8  hasGridOffsets 1 when the stream is seekable
        (a compression flag lived here only for versions 222 > v >= 220)
        char   uuid[36]       ASCII hex with hyphens, NOT 16 raw bytes.
                              36 is the on-disk width; a reader that takes
                              the struct comment literally and reads 16
                              lands 20 bytes early, in the middle of the
                              metadata count.

      then, in this order (File.cc `open`)
        metadata map          uint32 count, then per entry:
                                string name | string typeName |
                                uint32 numBytes | numBytes of value
        int32  grid count
        grid descriptors      per grid:
                                string uniqueName | string gridType |
                                string instanceParentName |
                                int64 gridPos | int64 blockPos | int64 endPos

      string
        uint32 length, then that many bytes. Not NUL-terminated.

  Two things here are load-bearing and quiet when wrong:

  - **The uuid is 36 ASCII bytes, not a 16-byte binary uuid.** Reading 16
    leaves the cursor inside the metadata count, which then reads as a huge
    number and the file looks corrupt — or, worse, as a small plausible one.
  - **Every metadata value is framed by its own byte count**, so an unknown
    type can be SKIPPED exactly rather than guessed at. That is why this can
    read a file written by a newer OpenVDB with types it has never heard of,
    and report them by name.

  **The grid buffers are not decoded.** A grid descriptor gives the byte
  offsets of its grid, and this returns those offsets — which is what
  `vdb_print` reports at the file level, and what a pipeline needs to answer
  \"what grids are in this file, of what type, and how are they named\". It
  does not read the tree topology or the voxel buffers: those are ZIP or
  BLOSC compressed per node, and neither codec is implemented here. Grids are
  returned with `:grid/data-decoded? false` so a caller cannot mistake the
  descriptor for the volume.

  `voxel.vdb` is the OpenVDB `Tree4<T,5,4,3>` structure and is NOT connected
  to this: nothing here turns a byte range into a `voxel.vdb` grid. Keeping
  that seam visible is deliberate — a reader that quietly produced an empty
  tree for every grid would look like it worked."
  (:require [kotoba.lang.text :as string]))

(def magic
  "`OPENVDB_MAGIC` — 0x56444220, the ASCII \"VDB \" read as a little-endian
  int32, stored in an int64 field."
  0x56444220)

(def file-version
  "`OPENVDB_FILE_VERSION` at the time of transcription. Files ARE read above
  this — upstream only warns — so this is not a ceiling."
  225)

(def minimum-file-version
  "`OPENVDB_FILE_VERSION_FLOAT_FRUSTUM_BBOX`. Upstream throws below it, so
  this refuses too rather than reading a layout it was not told about."
  221)

(def uuid-bytes
  "The uuid is written as fixed-length ASCII: 32 hex digits plus 4 hyphens."
  36)

;; ---------------------------------------------------------------------------
;; primitives
;; ---------------------------------------------------------------------------

(defn- u [bs pos n]
  (reduce + (map-indexed (fn [i x] (* x (Math/pow 256 i))) (subvec bs pos (+ pos n)))))

(defn- i32 [bs pos]
  (let [v (u bs pos 4)] (long (if (>= v 2147483648) (- v 4294967296) v))))

(defn- i64 [bs pos]
  (let [v (u bs pos 8)] (if (>= v 9223372036854775808) (- v 18446744073709551616) (long v))))

(defn- s [bs pos n]
  (apply str (map #(#?(:clj char :cljs js/String.fromCharCode) %) (subvec bs pos (+ pos n)))))

(defn- put-u [v n] (mapv #(mod (long (/ v (Math/pow 256 %))) 256) (range n)))

(defn- char-bytes
  "The code units of a string, as bytes.

  `#?(:clj int :cljs identity)` over a string looks portable and is not: on
  the JVM it yields code points, and in ClojureScript it yields single-
  character STRINGS, which then sit in the byte vector and read back as
  spaces. The JVM suite passes either way — this was found by running the
  probe under nbb, not by reading the code."
  [x]
  (mapv #(#?(:clj int :cljs (fn [c] (.charCodeAt c 0))) %) x))

(defn- put-str [x] (into (put-u (count x) 4) (char-bytes x)))

(defn- f64-at [bs pos]
  #?(:clj (Double/longBitsToDouble (unchecked-long (long (u bs pos 8))))
     :cljs (let [b (js/ArrayBuffer. 8) d (js/DataView. b)]
             (dotimes [i 8] (.setUint8 d i (nth bs (+ pos i))))
             (.getFloat64 d 0 true))))

(defn- f32-at [bs pos]
  #?(:clj (Float/intBitsToFloat (unchecked-int (long (u bs pos 4))))
     :cljs (let [b (js/ArrayBuffer. 4) d (js/DataView. b)]
             (dotimes [i 4] (.setUint8 d i (nth bs (+ pos i))))
             (.getFloat32 d 0 true))))

;; ---------------------------------------------------------------------------
;; metadata
;; ---------------------------------------------------------------------------

(def decoded-metadata-types
  "Metadata types whose VALUE this decodes. Everything else is kept with its
  type name and raw bytes — the per-value byte count makes that exact, so an
  unknown type is skipped rather than guessed at."
  {"string" (fn [bs pos n] (s bs pos n))
   "bool" (fn [bs pos _] (not (zero? (nth bs pos))))
   "int32" (fn [bs pos _] (i32 bs pos))
   "int64" (fn [bs pos _] (i64 bs pos))
   "float" (fn [bs pos _] (f32-at bs pos))
   "double" (fn [bs pos _] (f64-at bs pos))
   "vec3i" (fn [bs pos _] (mapv #(i32 bs (+ pos (* 4 %))) (range 3)))
   "vec3s" (fn [bs pos _] (mapv #(f32-at bs (+ pos (* 4 %))) (range 3)))
   "vec3d" (fn [bs pos _] (mapv #(f64-at bs (+ pos (* 8 %))) (range 3)))})

(defn read-string-at
  "`readString`: a uint32 length then that many bytes. Returns `[s next-pos]`."
  [bs pos]
  (let [n (long (u bs pos 4))]
    [(s bs (+ pos 4) n) (+ pos 4 n)]))

(defn read-metadata
  "The file-level metadata map. Returns `[entries next-pos]`, each entry a map
  with `:meta/name`, `:meta/type` and either `:meta/value` or `:meta/bytes`."
  [bs pos]
  (let [count* (long (u bs pos 4))]
    (loop [pos (+ pos 4) i 0 out []]
      (if (>= i count*)
        [out pos]
        (let [[nm pos] (read-string-at bs pos)
              [ty pos] (read-string-at bs pos)
              nbytes (long (u bs pos 4))
              pos (+ pos 4)
              dec* (decoded-metadata-types ty)]
          (recur (+ pos nbytes) (inc i)
                 (conj out (merge {:meta/name nm :meta/type ty :meta/bytes nbytes}
                                  (when (and dec* (<= (+ pos nbytes) (count bs)))
                                    {:meta/value (dec* bs pos nbytes)})))))))))

;; ---------------------------------------------------------------------------
;; the archive
;; ---------------------------------------------------------------------------

(def half-float-suffix
  "`HALF_FLOAT_TYPENAME_SUFFIX` — a grid type ending in this was saved with
  float values narrowed to half, and the suffix is not part of the type."
  "_HalfFloat")

(defn header-error
  "Why these bytes are not a `.vdb`, or nil."
  [bs]
  (let [n (count bs)]
    (cond
      (< n 25) (str "too short to hold a VDB header (" n " bytes, 25 minimum before the uuid)")
      (not= magic (i64 bs 0))
      (str "magic is " (i64 bs 0) ", and a VDB begins with " magic
           " —— this is not a .vdb. **`.nvdb` (NanoVDB) is a different format**"
           " with a different magic; `voxel.nvdb` reads that one")
      (< (long (u bs 8 4)) minimum-file-version)
      (str "file format version " (long (u bs 8 4)) " < " minimum-file-version
           " —— OpenVDB itself refuses these, so this does too rather than"
           " reading a layout it was not told about")
      (< n (+ 21 uuid-bytes 4))
      "truncated before the metadata count")))

(defn read-archive
  "Read the container of a `.vdb`. Returns `[:ok archive]` or `[:error msg]`.

  The archive has `:archive/file-version`, `:archive/library-version`,
  `:archive/has-grid-offsets?`, `:archive/uuid`, `:archive/metadata` and
  `:archive/grids`. Each grid has `:grid/name`, `:grid/type`,
  `:grid/instance-parent`, `:grid/half-float?`, the three byte offsets, and
  `:grid/data-decoded? false`."
  [bytes]
  (let [bs (vec bytes)]
    (if-let [e (header-error bs)]
      [:error e]
      (let [fv (long (u bs 8 4))
            lib [(long (u bs 12 4)) (long (u bs 16 4))]
            offsets? (not (zero? (nth bs 20)))
            ;; The compression flag exists only in this window. Outside it the
            ;; byte belongs to the uuid, and consuming it shifts everything.
            pos (if (and (>= fv 220) (< fv 222)) 22 21)
            uuid (s bs pos uuid-bytes)
            pos (+ pos uuid-bytes)]
        (if (> (+ pos 4) (count bs))
          [:error "truncated in the header, before the metadata"]
          (let [[meta pos] (read-metadata bs pos)]
            (if (> (+ pos 4) (count bs))
              [:error "truncated after the metadata, before the grid count"]
              (let [gc (i32 bs pos)]
                (if (or (neg? gc) (> gc (count bs)))
                  [:error (str "grid count " gc " is impossible for a file of "
                               (count bs) " bytes —— the cursor is not where the"
                               " count is (the uuid is 36 ASCII bytes, not 16 binary)")]
                  (loop [pos (+ pos 4) i 0 grids []]
                    (if (>= i gc)
                      [:ok {:archive/file-version fv
                            :archive/library-version lib
                            :archive/has-grid-offsets? offsets?
                            :archive/uuid uuid
                            :archive/metadata meta
                            :archive/grids grids}]
                      (if (> (+ pos 12) (count bs))
                        [:error (str "truncated inside grid descriptor " i " of " gc)]
                        (let [[uname pos] (read-string-at bs pos)
                              [gtype pos] (read-string-at bs pos)
                              [parent pos] (read-string-at bs pos)]
                          (if (> (+ pos 24) (count bs))
                            [:error (str "truncated before the offsets of grid " i)]
                            (let [half? (string/ends-with? gtype half-float-suffix)]
                              (recur (+ pos 24) (inc i)
                                     (conj grids
                                           {:grid/name uname
                                            :grid/type (if half?
                                                         (subs gtype 0 (- (count gtype)
                                                                          (count half-float-suffix)))
                                                         gtype)
                                            :grid/half-float? half?
                                            :grid/instance-parent parent
                                            :grid/pos (i64 bs pos)
                                            :grid/block-pos (i64 bs (+ pos 8))
                                            :grid/end-pos (i64 bs (+ pos 16))
                                            :grid/data-decoded? false})))))))))))))))))

(defn write-archive
  "Write a `.vdb` container. Returns bytes.

  The grid descriptors carry offsets, but no grid data is written — this
  exists so a reader can be tested against bytes assembled by the WRITE rules
  in `Archive.cc` / `GridDescriptor.cc`, which is a different transcription
  from the read rules. Nothing here writes a volume."
  [{:archive/keys [file-version library-version has-grid-offsets? uuid metadata grids]
    :or {file-version 225 library-version [12 0] has-grid-offsets? true
         uuid "00000000-0000-0000-0000-000000000000" metadata [] grids []}}]
  (vec (concat
        (put-u magic 8)
        (put-u file-version 4)
        (put-u (first library-version) 4)
        (put-u (second library-version) 4)
        [(if has-grid-offsets? 1 0)]
        (char-bytes uuid)
        (put-u (count metadata) 4)
        (mapcat (fn [{:meta/keys [name type raw]}]
                  (concat (put-str name) (put-str type)
                          (put-u (count raw) 4) raw))
                metadata)
        (put-u (count grids) 4)
        (mapcat (fn [{:grid/keys [name type instance-parent half-float?
                                  pos block-pos end-pos]
                      :or {instance-parent "" pos 0 block-pos 0 end-pos 0}}]
                  (concat (put-str name)
                          (put-str (if half-float? (str type half-float-suffix) type))
                          (put-str instance-parent)
                          (put-u pos 8) (put-u block-pos 8) (put-u end-pos 8)))
                grids))))

(defn describe
  "What is in this file, for saying it out loud. Grid data is never in here."
  [archive]
  {:file-version (:archive/file-version archive)
   :library-version (:archive/library-version archive)
   :grid-count (count (:archive/grids archive))
   :grids (mapv (fn [g] {:name (:grid/name g) :type (:grid/type g)
                         :half-float? (:grid/half-float? g)
                         :bytes (- (:grid/end-pos g) (:grid/pos g))})
                (:archive/grids archive))
   :metadata (into {} (map (fn [m] [(:meta/name m)
                                    (if (contains? m :meta/value)
                                      (:meta/value m)
                                      [:undecoded (:meta/type m) (:meta/bytes m)])])
                           (:archive/metadata archive)))
   :grid-data-decoded? false})
