(ns alembic.objects
  "The Alembic object layer that sits on top of Ogawa: the archive header, the
  object hierarchy, and the metadata attached to each object.

  `ogawa.core` gives a tree of anonymous groups and byte blocks. This namespace
  says what those mean, and — like the container — the layout is transcribed
  rather than inferred, from `AcademySoftwareFoundation/alembic`
  `lib/Alembic/AbcCoreOgawa`, read 2026-08-24:

      archive root group (ArImpl.cpp `init`), at least 6 children
        0  data, 4 bytes   Ogawa file version, int32
        1  data, 4 bytes   Alembic archive version, int32, must be >= 9999
        2  GROUP           the top object
        3  data            the archive's own metadata string
        4  data            time samples and max
        5  data            indexed metadata

      object group (OrData.cpp)
        0        GROUP     this object's compound properties
        1..n-2   GROUP     child objects, in the order their headers appear
        n-1      data      the packed headers of those children

      packed object headers (ReadUtil.cpp `ReadObjectHeaders`)
        the LAST 32 BYTES ARE HASHES and are skipped, then repeatedly
        uint32 nameSize | nameSize bytes of name | uint8 metadataIndex
        metadataIndex 0xff  -> uint32 size + that many bytes, inline
        otherwise           -> an index into the archive's indexed metadata

      indexed metadata (ReadUtil.cpp `ReadIndexedMetaData`)
        entry 0 is always the empty string, then repeatedly
        uint8 size | that many bytes

  **Properties and samples are not here.** This can tell you what objects an
  `.abc` contains, what each one's schema claims to be, and how they nest —
  which is the first question a pipeline tool asks — but it cannot read a
  PolyMesh's points out of one. `read-archive` returns objects with their
  metadata and children, and nothing that would let a caller believe otherwise.

  Metadata strings are returned RAW. Alembic serialises them as `key=value`
  pairs separated by `;`, and parsing that here would be inference: the
  serialise/deserialise pair lives in `AbcCoreAbstract/MetaData.h`, which was
  not read. `metadata-pairs` does the obvious split and says in its docstring
  that it is a convenience, not a verified decoding."
  (:require [ogawa.core :as ogawa]
            [kotoba.lang.text :as string]))

(def minimum-archive-version
  "`ArImpl.cpp` refuses anything below this."
  9999)

(defn- u32-at [bs pos]
  (reduce + (map-indexed (fn [i x] (* x (Math/pow 256 i))) (subvec bs pos (+ pos 4)))))

(defn- i32-at [bs pos]
  (let [v (u32-at bs pos)] (long (if (>= v 2147483648) (- v 4294967296) v))))

(defn- bytes->str [bs]
  (apply str (map #(#?(:clj char :cljs js/String.fromCharCode) %) bs)))

(defn indexed-metadata
  "The archive's metadata table. Entry 0 is always the empty string."
  [bs]
  (loop [pos 0 out [""]]
    (if (>= pos (count bs))
      out
      (let [n (nth bs pos)
            pos (inc pos)]
        (if (> (+ pos n) (count bs))
          out
          (recur (+ pos n) (conj out (bytes->str (subvec bs pos (+ pos n))))))))))

(defn object-headers
  "The packed child headers in a data block, as `[{:name :metadata}]`.

  The last 32 bytes are hashes and are skipped — a reader that does not skip
  them finds a name length in the middle of a digest and either throws or
  invents an object."
  [bs metadata-table]
  (if (<= (count bs) 32)
    []
    (let [buf (subvec bs 0 (- (count bs) 32))
          n (count buf)]
      (loop [pos 0 out []]
        (if (>= pos n)
          out
          (let [name-size (long (u32-at buf pos))
                pos (+ pos 4)]
            (if (or (zero? name-size) (> (+ pos name-size 1) n))
              out
              (let [nm (bytes->str (subvec buf pos (+ pos name-size)))
                    pos (+ pos name-size)
                    idx (nth buf pos)
                    pos (inc pos)]
                (if (= idx 0xff)
                  (let [size (long (u32-at buf pos))
                        pos (+ pos 4)]
                    (if (> (+ pos size) n)
                      out
                      (recur (+ pos size)
                             (conj out {:object/name nm
                                        :object/metadata (bytes->str (subvec buf pos (+ pos size)))
                                        :object/metadata-source :inline}))))
                  (recur pos (conj out {:object/name nm
                                        :object/metadata (get metadata-table idx "")
                                        :object/metadata-source :indexed})))))))))))

(defn- data-bytes [node]
  (when (and (map? node) (= :data (:ogawa/kind node))) (:ogawa/bytes node)))

(defn- group? [node] (and (map? node) (= :group (:ogawa/kind node))))

(defn- read-object [node parent-path metadata-table]
  (let [kids (:ogawa/children node)
        n (count kids)]
    (if (zero? n)
      {:object/children [] :object/properties? false}
      (let [headers (object-headers (or (data-bytes (nth kids (dec n))) []) metadata-table)
            ;; children 1 .. n-2 are the child objects, in header order
            child-groups (vec (filter group? (subvec kids 1 (max 1 (dec n)))))]
        {:object/properties? (group? (first kids))
         :object/children
         (vec (map-indexed
               (fn [i h]
                 (let [full (str parent-path "/" (:object/name h))]
                   (merge h
                          {:object/path full}
                          (if-let [g (get child-groups i)]
                            (read-object g full metadata-table)
                            {:object/children [] :object/properties? false}))))
               headers))}))))

(defn archive-error
  "Why this Ogawa tree is not an Alembic archive, or nil."
  [root]
  (let [kids (:ogawa/children root)
        n (count kids)]
    (cond
      (not (group? root)) "the Ogawa root is not a group"

      (<= n 5)
      (str "an Alembic archive's root group has more than 5 children (version,"
           " archive version, top object, metadata, time samples, indexed"
           " metadata); this one has " n)

      (not (and (data-bytes (nth kids 0)) (data-bytes (nth kids 1))
                (group? (nth kids 2))
                (data-bytes (nth kids 3)) (data-bytes (nth kids 4))
                (data-bytes (nth kids 5))))
      (str "the root group's first six children are not data, data, group,"
           " data, data, data — this is the shape ArImpl.cpp checks before it"
           " will call a file Alembic. Got "
           (pr-str (mapv (fn [k] (cond (group? k) :group (data-bytes k) :data :else :empty))
                         (take 6 kids))))

      (not= 4 (count (data-bytes (nth kids 0))))
      (str "child 0 should be a 4-byte Ogawa file version, and is "
           (count (data-bytes (nth kids 0))) " bytes")

      :else
      (let [av (i32-at (vec (data-bytes (nth kids 1))) 0)]
        (when (< av minimum-archive-version)
          (str "Alembic archive version " av ", and ArImpl.cpp refuses anything"
               " below " minimum-archive-version))))))

(defn read-archive
  "Read an Alembic archive from Ogawa bytes.

  Returns `[:ok archive]` or `[:error msg]`. The archive has
  `:archive/version`, `:archive/ogawa-version`, `:archive/metadata`,
  `:archive/indexed-metadata` and `:archive/top`, where the top object holds
  `:object/children` recursively.

  **No properties, no samples.** What comes back describes the objects in the
  file, not their geometry."
  [bytes]
  (let [[status tree] (ogawa/read-archive bytes)]
    (if (= :error status)
      [:error (str "the Ogawa container could not be read: " tree)]
      (if-let [e (archive-error tree)]
        [:error e]
        (let [kids (:ogawa/children tree)
              table (indexed-metadata (vec (data-bytes (nth kids 5))))]
          [:ok {:archive/ogawa-version (i32-at (vec (data-bytes (nth kids 0))) 0)
                :archive/version (i32-at (vec (data-bytes (nth kids 1))) 0)
                :archive/metadata (bytes->str (data-bytes (nth kids 3)))
                :archive/indexed-metadata table
                :archive/top (merge {:object/name "ABC" :object/path "/"}
                                    (read-object (nth kids 2) "" table))}])))))

(defn object-paths
  "Every object path in the archive, depth first — the answer to \"what is in
  this file\"."
  [archive]
  (letfn [(walk [o] (into [(:object/path o)] (mapcat walk (:object/children o))))]
    (vec (mapcat walk (:object/children (:archive/top archive))))))

(defn metadata-pairs
  "A metadata string split on `;` and `=`.

  A convenience, NOT a verified decoding: Alembic's serialise/deserialise pair
  lives in `AbcCoreAbstract/MetaData.h`, which this implementation has not
  read. Escaping rules, if any, are unknown here — so a value containing a
  semicolon would split wrongly and nothing would notice."
  [s]
  (into {} (for [part (remove string/blank? (string/split (or s "") #";"))
                 :let [[k v] (string/split part #"=" 2)]]
             [k (or v "")])))
