(ns voxel.nvdb
  "The `.nvdb` file container: NanoVDB segments, their headers, and the
  per-grid metadata.

  A `.nvdb` file is one or more SEGMENTS, and an uncompressed segment is
  exactly four things in a row (`NanoVDB.h`, `writeUncompressedGrid`):

      FileHeader | FileMetaData | grid name | grid buffer

  Both structs are fixed size and the layout is transcribed, not inferred,
  from `AcademySoftwareFoundation/openvdb` `nanovdb/nanovdb/NanoVDB.h`, read
  2026-08-24:

      FileHeader, 16 bytes
        uint64 magic        NANOVDB_MAGIC_NUMB / _FILE / _GRID
        uint32 version      11 + 11 + 10 bit packing of major, minor, patch
        uint16 gridCount
        uint16 codec        0 NONE, 1 ZIP, 2 BLOSC

      FileMetaData, 176 bytes, in declaration order
        uint64 gridSize, fileSize, nameKey, voxelCount     32
        uint32 gridType, gridClass                          8
        double worldBBox[6]                                48
        int32  indexBBox[6]                                24
        double voxelSize[3]                                24
        uint32 nameSize                                     4
        uint32 nodeCount[4]                                16
        uint32 tileCount[3]                                12
        uint16 codec, blindDataCount                        4
        uint32 version                                      4

  Two earlier iterations left this unimplemented, correctly: the sizes were
  known from `io/IO.h` but the FIELDS were not, and a reader written from
  sizes alone round-trips with itself while opening nobody else's file. The
  fields were obtainable — from the source, with a tool that does not
  summarise. That is the same lesson as Ogawa, learned twice.

  **The grid buffer itself is opaque here.** This reads and writes the
  container and its metadata — which is what `nanovdb_print` reports and what
  a pipeline needs to answer \"what grids are in this file, how big, what
  bounds\" — but it does not decode the tree inside a grid. `voxel.vdb` is
  that tree, and the two are not connected: nothing here turns a `.nvdb` grid
  buffer into a `voxel.vdb` grid, and `read-segments` returns the bytes
  rather than pretending otherwise.

  Compressed segments are REFUSED rather than mis-read: ZIP and BLOSC change
  what follows the metadata, and this decodes neither."
  (:require [kotoba.lang.text :as string]))

(def magic-strings
  "The magic numbers are ASCII read little-endian, which is why they are held
  as STRINGS here rather than as the 0x3242… constants the header prints.

  A 64-bit magic cannot survive `(reduce + (map * byte (pow 256 i)))`: those
  values are around 3.6e18, well past 2^53, so the double that comes back is
  close to the constant and not equal to it. Measured — the first version of
  this namespace compared numbers and rejected its own output. Comparing the
  eight bytes has no such range."
  {:numb "NanoVDB0" :grid "NanoVDB1" :file "NanoVDB2"})

(def codecs {0 :none 1 :zip 2 :blosc})
(def header-size 16)
(def metadata-size 176)

(defn- str->bytes* [s] (mapv #?(:clj int :cljs #(.charCodeAt % 0)) s))
(defn- bytes->str* [bs] (apply str (map #(#?(:clj char :cljs js/String.fromCharCode) %) bs)))

(defn- byte-at [n i] (mod (long (/ n (Math/pow 256 i))) 256))
(defn- uN-le [n width] (mapv #(byte-at n %) (range width)))
(defn- read-uN [bs pos width]
  (long (reduce + (map-indexed (fn [i x] (* x (Math/pow 256 i))) (subvec bs pos (+ pos width))))))
(defn- read-i32 [bs pos]
  (let [v (read-uN bs pos 4)] (if (>= v 2147483648) (- v 4294967296) v)))

;; Doubles are carried as IEEE-754 bytes. There is no portable bit-level double
;; in `.cljc`, so the conversion goes through the host's own buffer — the one
;; place this namespace is not pure arithmetic.
(defn- double->bytes [x]
  #?(:clj (let [bits (Double/doubleToLongBits (double x))]
            (mapv (fn [i] (bit-and (bit-shift-right bits (* 8 i)) 0xff)) (range 8)))
     :cljs (let [b (js/ArrayBuffer. 8)]
             (.setFloat64 (js/DataView. b) 0 x true)
             (vec (js/Uint8Array. b)))))

(defn- bytes->double [bs pos]
  #?(:clj (let [bits (reduce (fn [acc i]
                              (bit-or acc (bit-shift-left (long (nth bs (+ pos i))) (* 8 i))))
                            0 (range 8))]
            (Double/longBitsToDouble bits))
     :cljs (let [b (js/ArrayBuffer. 8) v (js/DataView. b)]
             (dotimes [i 8] (.setUint8 v i (nth bs (+ pos i))))
             (.getFloat64 v 0 true))))

(defn version
  "Pack major/minor/patch into the 11+11+10 bit field NanoVDB uses."
  [major minor patch]
  (bit-or (bit-shift-left major 21) (bit-shift-left minor 10) patch))

(defn version-parts [v]
  {:major (bit-and (unsigned-bit-shift-right v 21) 0x7ff)
   :minor (bit-and (unsigned-bit-shift-right v 10) 0x7ff)
   :patch (bit-and v 0x3ff)})

(defn- hex
  "A number in hex, portably — `(.toString n 16)` is a JavaScript idiom that
  the JVM's Long does not have."
  [n]
  #?(:clj (Long/toHexString n) :cljs (.toString n 16)))

(defn- str->bytes [s] (mapv #?(:clj int :cljs #(.charCodeAt % 0)) s))
(defn- bytes->str [bs] (apply str (map #(#?(:clj char :cljs js/String.fromCharCode) %) bs)))

;; ---------------------------------------------------------------------------
;; Metadata
;; ---------------------------------------------------------------------------

(defn write-metadata
  "A 176-byte FileMetaData block."
  [{:keys [grid-size file-size name-key voxel-count grid-type grid-class
           world-bbox index-bbox voxel-size name-size node-count tile-count
           codec blind-data-count version]
    :or {grid-size 0 file-size 0 name-key 0 voxel-count 0 grid-type 0 grid-class 0
         world-bbox [0.0 0.0 0.0 0.0 0.0 0.0] index-bbox [0 0 0 0 0 0]
         voxel-size [1.0 1.0 1.0] name-size 0 node-count [0 0 0 0]
         tile-count [0 0 0] codec 0 blind-data-count 0 version 0}}]
  (vec (concat (uN-le grid-size 8) (uN-le file-size 8) (uN-le name-key 8) (uN-le voxel-count 8)
               (uN-le grid-type 4) (uN-le grid-class 4)
               (mapcat double->bytes world-bbox)
               (mapcat #(uN-le (if (neg? %) (+ % 4294967296) %) 4) index-bbox)
               (mapcat double->bytes voxel-size)
               (uN-le name-size 4)
               (mapcat #(uN-le % 4) node-count)
               (mapcat #(uN-le % 4) tile-count)
               (uN-le codec 2) (uN-le blind-data-count 2) (uN-le version 4))))

(defn read-metadata [bs pos]
  {:grid-size (read-uN bs pos 8)
   :file-size (read-uN bs (+ pos 8) 8)
   :name-key (read-uN bs (+ pos 16) 8)
   :voxel-count (read-uN bs (+ pos 24) 8)
   :grid-type (read-uN bs (+ pos 32) 4)
   :grid-class (read-uN bs (+ pos 36) 4)
   :world-bbox (mapv #(bytes->double bs (+ pos 40 (* 8 %))) (range 6))
   :index-bbox (mapv #(read-i32 bs (+ pos 88 (* 4 %))) (range 6))
   :voxel-size (mapv #(bytes->double bs (+ pos 112 (* 8 %))) (range 3))
   :name-size (read-uN bs (+ pos 136) 4)
   :node-count (mapv #(read-uN bs (+ pos 140 (* 4 %)) 4) (range 4))
   :tile-count (mapv #(read-uN bs (+ pos 156 (* 4 %)) 4) (range 3))
   :codec (read-uN bs (+ pos 168) 2)
   :blind-data-count (read-uN bs (+ pos 170) 2)
   :version (read-uN bs (+ pos 172) 4)})

;; ---------------------------------------------------------------------------
;; Segments
;; ---------------------------------------------------------------------------

(defn segment
  "One uncompressed segment: header, metadata, name, grid bytes.

  `:name-size` and `:grid-size` in the metadata are OVERWRITTEN from the
  actual name and buffer — a file whose declared sizes disagree with what
  follows them is unreadable by everything downstream, and having two places
  that can disagree is how that happens."
  [{:keys [name grid metadata version-value]
    :or {name "" grid [] metadata {} version-value (version 32 6 0)}}]
  (let [nm (str->bytes name)
        meta (write-metadata (merge metadata
                                    {:name-size (count nm)
                                     :grid-size (count grid)
                                     :file-size (count grid)
                                     :codec 0
                                     :version version-value}))]
    (vec (concat (str->bytes* (:file magic-strings)) (uN-le version-value 4)
                 (uN-le 1 2) (uN-le 0 2)
                 meta nm grid))))

(defn segments-error
  "Why these bytes are not readable NanoVDB segments, or nil."
  [bs]
  (cond
    (< (count bs) header-size)
    (str "shorter than a 16-byte FileHeader (" (count bs) " bytes)")

    (not (contains? (set (vals magic-strings)) (bytes->str* (subvec bs 0 8))))
    (str "the first eight bytes are not a NanoVDB magic number. Got "
         (pr-str (bytes->str* (subvec bs 0 8))) ", expected one of "
         (string/join ", " (map pr-str (vals magic-strings))))

    :else
    (let [codec (read-uN bs 14 2)]
      (cond
        (not (contains? codecs codec))
        (str "codec " codec " is not one this knows (0 NONE, 1 ZIP, 2 BLOSC)")
        (pos? codec)
        (str "this segment is " (string/upper (clojure.core/name (codecs codec)))
             "-compressed, and this decodes neither ZIP nor BLOSC. Compression"
             " changes what follows the metadata, so reading on would return"
             " a grid buffer of compressed bytes labelled as a grid.")))))

(defn read-segments
  "Read every segment. Returns `[:ok segments]` or `[:error msg]`.

  Each segment is `{:header :metadata :name :grid}` where `:grid` is the RAW
  buffer — this container reader does not decode the tree inside it."
  [bs]
  (if-let [e (segments-error bs)]
    [:error e]
    (loop [pos 0 out []]
      (if (>= (+ pos header-size) (count bs))
        [:ok out]
        (let [mg (bytes->str* (subvec bs pos (+ pos 8)))
              ver (read-uN bs (+ pos 8) 4)
              grid-count (read-uN bs (+ pos 12) 2)
              codec (read-uN bs (+ pos 14) 2)]
          (if-not (contains? (set (vals magic-strings)) mg)
            [:ok out]
            (let [header {:magic mg :version ver :version-parts (version-parts ver)
                          :grid-count grid-count :codec (codecs codec)}
                  [pos' segs]
                  (reduce (fn [[p acc] _]
                            (let [md (read-metadata bs p)
                                  np (+ p metadata-size)
                                  nm (bytes->str (subvec bs np (+ np (:name-size md))))
                                  gp (+ np (:name-size md))
                                  ge (min (count bs) (+ gp (:grid-size md)))]
                              [ge (conj acc {:header header :metadata md :name nm
                                             :grid (subvec bs gp ge)})]))
                          [(+ pos header-size) []] (range grid-count))]
              (recur pos' (into out segs)))))))))

(defn describe
  "What `nanovdb_print` reports: one line of facts per grid."
  [segments]
  (mapv (fn [{:keys [name metadata header]}]
          {:grid/name name
           :grid/voxels (:voxel-count metadata)
           :grid/index-bbox (:index-bbox metadata)
           :grid/voxel-size (:voxel-size metadata)
           :grid/bytes (:grid-size metadata)
           :grid/codec (:codec header)
           :grid/version (:version-parts header)})
        segments))
