(ns ogawa.core
  "Ogawa — the binary container Alembic files are written in.

  An `.abc` file is two layers: Ogawa underneath, a tree of GROUPS and DATA
  blocks with 64-bit offsets, and the Alembic object model above it, which
  gives those blocks meaning (objects, properties, samples, time sampling).
  This namespace is the lower layer only, and says so everywhere it might be
  mistaken for the other one.

  The layout is not inferred. It is transcribed from the upstream sources at
  AcademySoftwareFoundation/alembic `lib/Alembic/Ogawa`, read on 2026-08-23:

      header, 16 bytes
        0..4   'O' 'g' 'a' 'w' 'a'                        (OStream.cpp)
        5      0 while writing, 0xff when the archive is complete
        6..7   version, (byte6 << 8) | byte7 — written as 0, 1
        8..15  uint64 little-endian position of the root group

      group at P
        P      uint64 child count
        P+8    that many uint64 child values

      child value                                          (Foundation.h)
        0x0000000000000000  EMPTY_GROUP
        0x8000000000000000  EMPTY_DATA
        high bit set        data at (value & 0x7fff…)
        high bit clear      group at value
        0x7fffffffffffffff  INVALID_GROUP
        0xffffffffffffffff  INVALID_DATA

      data at P
        P      uint64 size
        P+8    that many bytes                             (IData.cpp)

  **The reader is tested against bytes assembled from that spec by hand, not
  only against this library's own writer.** A reader checked only by
  round-tripping its own output agrees with itself; it does not agree with
  Alembic. That distinction is the reason this namespace exists at all — the
  format was left unimplemented for two iterations precisely because the
  layout could not be obtained without guessing, and guessing produces exactly
  that self-agreeing parser.

  Not here: the Alembic object model. No objects, properties, samples, time
  sampling, or schemas — so this cannot yet read a PolyMesh out of a real
  `.abc`, and `read-archive` returns the raw tree rather than pretending
  otherwise.

  Positions are handled as ordinary numbers, which is exact for files below
  2^53 bytes (8 petabytes). The high bit that tags a child as data is read
  from the top byte rather than by 64-bit arithmetic, because a JavaScript
  number cannot hold 0x8000000000000000."
  (:require [kotoba.lang.text :as string]))

(def magic [0x4f 0x67 0x61 0x77 0x61])   ; "Ogawa"
(def version 1)
(def frozen-byte 0xff)
(def header-size 16)

(def empty-group 0)
(def empty-data :ogawa/empty-data)

(defn- byte-at
  "`(n >> (8*i)) & 0xff` without 32-bit truncation — ClojureScript's
  `bit-shift-right` is a 32-bit operation, so anything above byte 3 would come
  back wrong. Division by a power of 256 is exact over the range positions
  live in."
  [n i]
  (mod (long (/ n (Math/pow 256 i))) 256))

(defn- u64-le
  "`n` as 8 little-endian bytes. `data?` sets the high bit that tags a child
  value as data."
  [n data?]
  (let [bs (mapv #(byte-at n %) (range 8))]
    (if data? (assoc bs 7 (bit-or (nth bs 7) 0x80)) bs)))

(defn- read-u64
  "The 8 bytes at `pos` as `[value data?]`. The tag bit is read off the top
  byte; the remaining 63 bits become the value."
  [bytes pos]
  (let [b (mapv #(nth bytes (+ pos %)) (range 8))
        data? (pos? (bit-and (nth b 7) 0x80))
        top (bit-and (nth b 7) 0x7f)
        v (reduce + (map-indexed (fn [i x] (* x (Math/pow 256 i)))
                                 (assoc b 7 top)))]
    [(long v) data?]))

;; ---------------------------------------------------------------------------
;; Writing
;; ---------------------------------------------------------------------------

(defn group
  "A group node. `children` is a vector of groups, data nodes, or the two
  empty markers."
  [& children] {:ogawa/kind :group :ogawa/children (vec children)})

(defn data
  "A data node holding `bytes` (a sequence of 0-255)."
  [bytes] {:ogawa/kind :data :ogawa/bytes (vec bytes)})

(defn- node-error [n]
  (cond
    (= n empty-group) nil
    (= n empty-data) nil
    (not (map? n)) (str "not an Ogawa node: " (pr-str n))
    (= :data (:ogawa/kind n))
    (when-let [bad (first (remove #(and (integer? %) (<= 0 % 255)) (:ogawa/bytes n)))]
      (str "a data node must hold bytes 0-255, got " (pr-str bad)))
    (= :group (:ogawa/kind n)) (some node-error (:ogawa/children n))
    :else (str "unknown node kind " (pr-str (:ogawa/kind n)))))

(defn write-archive
  "Serialise a tree into Ogawa bytes. Returns `[:ok bytes]` or `[:error msg]`.

  The archive is written frozen — byte 5 is 0xff — because a file this
  function returns IS complete. Alembic writes 0 there first and stamps 0xff
  at the end, and a reader that ignores the byte accepts a half-written file."
  [root]
  (if-let [e (node-error root)]
    [:error e]
    (let [out (atom (vec (concat magic [frozen-byte 0 version] (repeat 8 0))))
          emit! (fn [bs] (let [p (count @out)] (swap! out into bs) p))]
      (letfn [(write-node [n]
                (cond
                  (= n empty-group) [empty-group false]
                  (= n empty-data) [:empty-data true]
                  (= :data (:ogawa/kind n))
                  (let [bs (:ogawa/bytes n)
                        p (emit! (concat (u64-le (count bs) false) bs))]
                    [p true])
                  :else
                  ;; Children are written first, because a group records where
                  ;; each child lives and cannot know that until it exists.
                  (let [kids (mapv write-node (:ogawa/children n))
                        p (emit! (concat (u64-le (count kids) false)
                                         (mapcat (fn [[v data?]]
                                                   (cond (= v :empty-data) (u64-le 0 true)
                                                         (and (= v 0) (not data?)) (u64-le 0 false)
                                                         :else (u64-le v data?)))
                                                 kids)))]
                    [p false])))]
        (let [[root-pos _] (write-node (if (= :group (:ogawa/kind root)) root (group root)))]
          [:ok (vec (concat (take 8 @out) (u64-le root-pos false) (drop 16 @out)))])))))

;; ---------------------------------------------------------------------------
;; Reading
;; ---------------------------------------------------------------------------

(defn archive-error
  "Why these bytes are not a readable Ogawa archive, or nil."
  [bytes]
  (cond
    (< (count bytes) header-size)
    (str "shorter than the 16-byte header (" (count bytes) " bytes)")

    (not= magic (vec (take 5 bytes)))
    (str "not an Ogawa archive: the first five bytes are "
         (pr-str (vec (take 5 bytes))) ", not " (pr-str magic) " (\"Ogawa\")")

    (not= frozen-byte (nth bytes 5))
    (str "byte 5 is " (nth bytes 5) ", not 0xff — Alembic writes 0 there while"
         " the archive is being written and stamps 0xff when it is complete, so"
         " this is a file that was never finished. Reading it would produce a"
         " tree that is partly there.")

    :else
    (let [v (+ (* 256 (nth bytes 6)) (nth bytes 7))]
      (when-not (= version v)
        (str "format version " v ", and this reads version " version)))))

(defn read-archive
  "Parse Ogawa bytes into a tree of `group` / `data` nodes.

  Returns `[:ok tree]` or `[:error msg]`. The tree is RAW — Ogawa has no
  notion of objects or properties, so neither has this."
  [bytes]
  (if-let [e (archive-error bytes)]
    [:error e]
    (let [n (count bytes)
          [root-pos _] (read-u64 bytes 8)]
      (letfn [(read-group [pos]
                (if (= pos empty-group)
                  (group)
                  (let [[cnt _] (read-u64 bytes pos)]
                    ;; The upstream reader refuses a child count larger than
                    ;; the file could hold; a corrupt count would otherwise
                    ;; allocate against a number an attacker chose.
                    (if (or (zero? cnt) (> cnt (quot n 8)))
                      (group)
                      (apply group
                             (mapv (fn [i]
                                     (let [[v data?] (read-u64 bytes (+ pos 8 (* 8 i)))]
                                       (cond
                                         (and data? (zero? v)) empty-data
                                         data? (read-data v)
                                         (zero? v) empty-group
                                         :else (read-group v))))
                                   (range cnt)))))))
              (read-data [pos]
                (let [[size _] (read-u64 bytes pos)]
                  (if (> (+ pos 8 size) n)
                    (data [])
                    (data (subvec (vec bytes) (+ pos 8) (+ pos 8 size))))))]
        [:ok (read-group root-pos)]))))

(defn tree-summary
  "Counts, for saying what came out of a file without printing it."
  [node]
  (letfn [(walk [n acc]
            (cond
              (= n empty-group) (update acc :empty-groups inc)
              (= n empty-data) (update acc :empty-data inc)
              (= :data (:ogawa/kind n))
              (-> acc (update :data inc) (update :bytes + (count (:ogawa/bytes n))))
              :else (reduce (fn [a c] (walk c a)) (update acc :groups inc)
                            (:ogawa/children n))))]
    (walk node {:groups 0 :data 0 :bytes 0 :empty-groups 0 :empty-data 0})))
