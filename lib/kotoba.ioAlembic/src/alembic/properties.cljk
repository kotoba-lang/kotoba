(ns alembic.properties
  "The Alembic property and sample layer: what an object actually holds.

  `alembic.objects` answers \"what objects are in this file\". This answers
  \"what is in an object\" and \"what are the numbers\" — the point at which a
  `.abc` stops being an inventory and becomes geometry.

  Like the two layers below it, the layout is TRANSCRIBED rather than inferred,
  from `alembic/alembic` `lib/Alembic/AbcCoreOgawa`, read 2026-08-24:

      compound property group (CprData.cpp)
        0..n-2  GROUP    one per property header, in header order
        n-1     data     the packed property headers
        (a compound with no properties has zero children, and a group whose
         last child is not data is not a property group at all)

      packed property headers (ReadUtil.cpp `ReadPropertyHeaders`)
        uint32 info, then fields whose WIDTH DEPENDS ON `info`:

          info & 0x0003        0 compound, 1 scalar, 2 array
                               (bit 0 also means \"scalar-like\")
          (info & 0x000c) >> 2 size hint: 0 -> uint8, 1 -> uint16, 2 -> uint32.
                               **Every length below is read at this width.**
                               Reading them all as uint32 walks off the end of
                               a small header and invents properties.
          (info & 0x00f0) >> 4 POD type (non-compound only)
          info & 0x0100        a time sampling index follows
          info & 0x0200        first/last changed indices follow
          info & 0x0400        the sample size varies (not homogenous)
          info & 0x0800        the value is the same over all samples
          (info & 0xff000) >> 12    extent — components per element
          (info & 0xff00000) >> 20  metadata index, 0xff meaning inline

        non-compound, in order: nextSampleIndex, then (if 0x0200) firstChanged
        and lastChanged, then (if 0x0100) timeSamplingIndex — all at hint width.
        Then, for every kind: nameSize + name, and if the metadata index is
        0xff, metaDataSize + metadata.

        When 0x0200 is absent the changed range is IMPLIED, and the two cases
        differ: with 0x0800 it is [0,0] (constant), otherwise
        [1, nextSampleIndex-1]. Defaulting to [0,0] would make every animated
        property read as constant — the first sample is right, so the mistake
        looks like \"the cache is not animating\" rather than like a parse bug.

      sample storage
        scalar (SprImpl.cpp)   child `i` of the property group is the data for
                               stored sample i
        array  (AprImpl.cpp)   child `2i` is the data, child `2i+1` the
                               dimensions

      every sample data block (ReadUtil.cpp `ReadData`)
        the FIRST 16 BYTES ARE A KEY (a hash) and are not values. A block
        smaller than 16 bytes holds nothing.

      dimensions (ReadUtil.cpp `ReadDimensions`)
        an empty dims block means rank 1, and the count is derived:
        (dataSize - 16) / bytes-per-element. Otherwise the block is
        uint64 per rank.

      stored index (ReadUtil.h `verifyIndex`)
        i < firstChanged                     -> 0
        firstChanged == lastChanged == 0     -> 0   (constant)
        i >= lastChanged                     -> lastChanged - firstChanged + 1
        otherwise                            -> i - firstChanged + 1

  **What this does not do.** String and wstring PODs are recognised but their
  samples are refused, not guessed: `ReadData` splits them on NUL and the
  wstring path has a width this implementation has not verified. Float16 is
  refused for the same reason — the half decode was not transcribed. Refusing
  is deliberate: a wrong number that arrives looks exactly like a right one,
  and a caller cannot tell. Schema interpretation (that `P` on a PolyMesh is
  the point list, that `.faceIndices` winds a particular way) is NOT here
  either — this returns named, typed arrays, and `AbcGeom` is the layer that
  would say what the names mean."
  (:require [kotoba.lang.text] [ogawa.core :as ogawa]))

;; ---------------------------------------------------------------------------
;; bytes
;; ---------------------------------------------------------------------------

(defn- uint-at
  "Little-endian unsigned integer of `n` bytes."
  [bs pos n]
  (reduce + (map-indexed (fn [i x] (* x (Math/pow 256 i))) (subvec bs pos (+ pos n)))))

(defn- sint-at [bs pos n]
  (let [v (uint-at bs pos n) half (Math/pow 256 (dec n))]
    (long (if (>= v (* 128 half)) (- v (* 256 half)) v))))

(defn- bytes->str [bs]
  (apply str (map #(#?(:clj char :cljs js/String.fromCharCode) %) bs)))

(defn- f32-at [bs pos]
  #?(:clj (Float/intBitsToFloat (unchecked-int (long (uint-at bs pos 4))))
     :cljs (let [b (js/ArrayBuffer. 4) d (js/DataView. b)]
             (dotimes [i 4] (.setUint8 d i (nth bs (+ pos i))))
             (.getFloat32 d 0 true))))

(defn- f64-at [bs pos]
  #?(:clj (Double/longBitsToDouble (unchecked-long (long (uint-at bs pos 8))))
     :cljs (let [b (js/ArrayBuffer. 8) d (js/DataView. b)]
             (dotimes [i 8] (.setUint8 d i (nth bs (+ pos i))))
             (.getFloat64 d 0 true))))

;; ---------------------------------------------------------------------------
;; POD types
;; ---------------------------------------------------------------------------

(def pod-types
  "`Alembic/Util/PlainOldDataType.h`, in declaration order — the enum value IS
  the index, so the order of this vector is load-bearing."
  [:bool :uint8 :int8 :uint16 :int16 :uint32 :int32 :uint64 :int64
   :float16 :float32 :float64 :string :wstring])

(def pod-bytes
  {:bool 1 :uint8 1 :int8 1 :uint16 2 :int16 2 :uint32 4 :int32 4
   :uint64 8 :int64 8 :float16 2 :float32 4 :float64 8 :string 1 :wstring 1})

(def readable-pods
  "The PODs whose samples this decodes. The rest are recognised in headers and
  REFUSED at the sample, rather than approximated."
  #{:bool :uint8 :int8 :uint16 :int16 :uint32 :int32 :uint64 :int64
    :float32 :float64})

(defn- read-pod [pod bs pos]
  (case pod
    :bool (not (zero? (nth bs pos)))
    (:uint8 :uint16 :uint32 :uint64) (long (uint-at bs pos (pod-bytes pod)))
    (:int8 :int16 :int32 :int64) (sint-at bs pos (pod-bytes pod))
    :float32 (f32-at bs pos)
    :float64 (f64-at bs pos)))

;; ---------------------------------------------------------------------------
;; property headers
;; ---------------------------------------------------------------------------

(def ^:private hint-width {0 1 1 2 2 4})

(defn property-headers
  "Decode the packed property headers in a data block.

  Returns a vector of headers, each with `:property/kind`
  (`:compound`/`:scalar`/`:array`), `:property/name`, `:property/metadata`,
  and — for non-compound — `:property/pod`, `:property/extent`,
  `:property/sample-count`, `:property/first-changed`, `:property/last-changed`,
  `:property/homogenous?` and `:property/time-sampling-index`.

  Unlike the object headers, there is no trailing hash block here."
  [bs metadata-table]
  (let [n (count bs)]
    (loop [pos 0 out []]
      (if (or (>= pos n) (> (+ pos 4) n))
        out
        (let [info (long (uint-at bs pos 4))
              pos (+ pos 4)
              ptype (bit-and info 0x0003)
              kind (case (long ptype) 0 :compound 1 :scalar :array)
              w (hint-width (bit-shift-right (bit-and info 0x000c) 2))
              ;; `get` at hint width, threading position
              g (fn [p] [(long (uint-at bs p w)) (+ p w)])]
          (if (or (nil? w) (> (+ pos w) n))
            out
            (let [[h pos]
                  (if (= :compound kind)
                    [{} pos]
                    (let [pod (get pod-types (bit-shift-right (bit-and info 0x00f0) 4))
                          extent (bit-shift-right (bit-and info 0xff000) 12)
                          [next-i pos] (g pos)
                          [first-c last-c pos]
                          (cond
                            (not (zero? (bit-and info 0x0200)))
                            (let [[f p] (g pos) [l p] (g p)] [f l p])
                            (not (zero? (bit-and info 0x0800))) [0 0 pos]
                            :else [1 (dec next-i) pos])
                          [ts pos] (if (zero? (bit-and info 0x0100))
                                     [0 pos]
                                     (g pos))]
                      [{:property/pod pod
                        :property/extent extent
                        :property/sample-count next-i
                        :property/first-changed first-c
                        :property/last-changed last-c
                        :property/homogenous? (not (zero? (bit-and info 0x0400)))
                        :property/time-sampling-index ts}
                       pos]))]
              (if (> (+ pos w) n)
                out
                (let [[name-size pos] (g pos)]
                  (if (or (zero? name-size) (> (+ pos name-size) n))
                    out
                    (let [nm (bytes->str (subvec bs pos (+ pos name-size)))
                          pos (+ pos name-size)
                          mi (bit-shift-right (bit-and info 0xff00000) 20)]
                      (if (= mi 0xff)
                        (let [[msize pos] (g pos)]
                          (if (> (+ pos msize) n)
                            out
                            (recur (+ pos msize)
                                   (conj out (merge h {:property/kind kind
                                                       :property/name nm
                                                       :property/scalar-like? (odd? ptype)
                                                       :property/metadata
                                                       (bytes->str (subvec bs pos (+ pos msize)))
                                                       :property/metadata-source :inline})))))
                        (recur pos
                               (conj out (merge h {:property/kind kind
                                                   :property/name nm
                                                   :property/scalar-like? (odd? ptype)
                                                   :property/metadata (get metadata-table mi "")
                                                   :property/metadata-source :indexed})))))))))))))))

;; ---------------------------------------------------------------------------
;; the property tree
;; ---------------------------------------------------------------------------

(defn- data-bytes [node]
  (when (and (map? node) (= :data (:ogawa/kind node))) (vec (:ogawa/bytes node))))

(defn- group? [node] (and (map? node) (= :group (:ogawa/kind node))))

(defn read-compound
  "Read a compound property group into a vector of properties.

  Each property carries `:property/group` — the Ogawa node holding its
  samples — and compounds carry `:property/children` instead."
  [node metadata-table]
  (let [kids (vec (:ogawa/children node))
        n (count kids)]
    (if (or (zero? n) (nil? (data-bytes (nth kids (dec n)))))
      []
      (let [headers (property-headers (data-bytes (nth kids (dec n))) metadata-table)]
        (vec (map-indexed
              (fn [i h]
                (let [g (get kids i)]
                  (if (= :compound (:property/kind h))
                    (assoc h :property/children
                           (if (group? g) (read-compound g metadata-table) []))
                    (assoc h :property/group g))))
              headers))))))

(defn properties
  "The property tree of an object read by `alembic.objects/read-archive`.

  Takes the object's Ogawa node — child 0 of an object group is its compound
  property group."
  [object-node metadata-table]
  (let [kids (vec (:ogawa/children object-node))]
    (if (and (seq kids) (group? (first kids)))
      (read-compound (first kids) metadata-table)
      [])))

(defn property-paths
  "Every property path under a compound, depth first."
  ([props] (property-paths props ""))
  ([props prefix]
   (vec (mapcat (fn [p]
                  (let [path (str prefix "/" (:property/name p))]
                    (if (= :compound (:property/kind p))
                      (into [path] (property-paths (:property/children p) path))
                      [path])))
                props))))

(defn find-property
  "The property at `path` (e.g. `\"/.geom/P\"`), or nil."
  [props path]
  (let [segs (remove empty? (kotoba.lang.text/split path #"/"))]
    (loop [ps props segs segs]
      (when-let [s (first segs)]
        (when-let [hit (first (filter #(= s (:property/name %)) ps))]
          (if (empty? (rest segs))
            hit
            (recur (:property/children hit) (rest segs))))))))

;; ---------------------------------------------------------------------------
;; samples
;; ---------------------------------------------------------------------------

(defn stored-index
  "Which stored sample serves logical sample `i` — `verifyIndex` in
  `ReadUtil.h`.

  A constant property stores ONE sample and every index maps to it. Getting
  this wrong reads past the end of the group for animated properties and
  returns nothing for constant ones."
  [{:property/keys [first-changed last-changed sample-count]} i]
  (cond
    (or (neg? i) (>= i sample-count)) nil
    (< i first-changed) 0
    (and (= first-changed last-changed) (zero? first-changed)) 0
    (>= i last-changed) (inc (- last-changed first-changed))
    :else (inc (- i first-changed))))

(def key-bytes
  "Every sample data block starts with a 16-byte key. It is not data."
  16)

(defn sample-error
  "Why sample `i` of this property cannot be read, or nil."
  [{:property/keys [kind pod sample-count] :as p} i]
  (cond
    (= :compound kind) "a compound property has no samples of its own"
    (nil? (stored-index p i))
    (str "sample " i " is outside [0, " (dec (or sample-count 0)) "]")
    (not (readable-pods pod))
    (str "the POD type " (pr-str pod) " is recognised but not decoded here"
         " —— string/wstring are NUL-separated and float16 needs a half decode,"
         " neither of which was transcribed. **A guessed number is"
         " indistinguishable from a right one**, so this refuses instead")))

(defn- child-at [node i]
  (let [kids (vec (:ogawa/children node))]
    (when (< i (count kids)) (nth kids i))))

(defn read-sample
  "Sample `i` of a scalar or array property, as `[:ok {...}]` or `[:error msg]`.

  The map has `:sample/values` (a flat vector of PODs), `:sample/count`
  (elements, i.e. values / extent) and `:sample/dimensions`."
  [{:property/keys [kind pod extent group] :as p} i]
  (if-let [e (sample-error p i)]
    [:error e]
    (let [si (stored-index p i)
          [dnode dimnode] (if (= :scalar kind)
                            [(child-at group si) nil]
                            [(child-at group (* 2 si)) (child-at group (inc (* 2 si)))])
          bs (data-bytes dnode)
          w (pod-bytes pod)
          elem (* w (max 1 extent))]
      (cond
        (nil? bs) [:error (str "sample " i " has no data block at child "
                               (if (= :scalar kind) si (* 2 si))
                               " —— the group holds " (count (:ogawa/children group))
                               " children")]
        (< (count bs) key-bytes) [:ok {:sample/values [] :sample/count 0
                                       :sample/dimensions [0]}]
        :else
        (let [payload (- (count bs) key-bytes)
              n (quot payload w)
              vals (mapv #(read-pod pod bs (+ key-bytes (* w %))) (range n))
              dimbs (data-bytes dimnode)
              dims (if (and dimbs (seq dimbs))
                     (mapv #(long (uint-at dimbs (* 8 %) 8)) (range (quot (count dimbs) 8)))
                     [(let [q (quot payload elem)]
                        (if (zero? (rem payload elem)) q (inc q)))])]
          [:ok {:sample/values vals
                :sample/count (quot (count vals) (max 1 extent))
                :sample/dimensions dims}])))))

(defn read-elements
  "Sample `i` grouped into elements of `:property/extent` components —
  `[[x y z] [x y z] ...]` for a point list, rather than a flat vector."
  [{:property/keys [extent] :as p} i]
  (let [[status s] (read-sample p i)]
    (if (= :error status)
      [:error s]
      [:ok (mapv vec (partition-all (max 1 extent) (:sample/values s)))])))
