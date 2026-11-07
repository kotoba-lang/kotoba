(ns dango.value
  "The part of `kotoba.value.v1` dango blocks use: nil, booleans, safe integers,
  strings, keywords, bytes, links, vectors, sets and maps. Each value is
  `[type-code payload]` in DAG-CBOR, with sets and maps ordered by encoded bytes,
  shorter first. The bytes match `ipld.value`; `vectors/` holds the check.

  Decoding is closed. Anything else is refused, and bytes that do not re-encode
  to themselves are refused, which rejects every non-shortest or reordered form."
  (:require [clojure.string :as str]
            [dango.bytes :as b]
            [dango.cid :as cid]))

(def max-depth 64)
(def max-safe 9007199254740991)

(defn- reject! [problem detail]
  (throw (ex-info (str "dango.value: " (name problem)) {:problem problem :detail detail})))

(defrecord Link [cid])

(defn link [c]
  (when-not (and (string? c) (str/starts-with? c "b"))
    (reject! :link-not-a-cid c))
  (->Link c))

(defn link? [x] (instance? Link x))

(defrecord Tag [n payload])

;; ── CBOR ─────────────────────────────────────────────────────────────────────

(defn- head [major n]
  (let [m (* 32 major)
        be (fn [size] (loop [i size x n out ()]
                        (if (zero? i) out (recur (dec i) (quot x 256) (cons (mod x 256) out)))))]
    (cond
      (< n 24) [(+ m n)]
      (< n 256) (into [(+ m 24)] (be 1))
      (< n 65536) (into [(+ m 25)] (be 2))
      (< n 4294967296) (into [(+ m 26)] (be 4))
      :else (into [(+ m 27)] (be 8)))))

(defn- cbor [x]
  (cond
    (nil? x) [0xf6]
    (true? x) [0xf5]
    (false? x) [0xf4]
    (integer? x) (if (neg? x) (head 1 (- -1 x)) (head 0 x))
    (string? x) (let [u (b/utf8 x)] (into (head 3 (count u)) u))
    (b/bytes? x) (let [u (b/->vec x)] (into (head 2 (count u)) u))
    (instance? Tag x) (into (head 6 (:n x)) (cbor (:payload x)))
    (vector? x) (reduce (fn [out v] (into out (cbor v))) (head 4 (count x)) x)
    :else (reject! :not-encodable (str x))))

(declare parse)

(defn- parse-n [v i info]
  (let [size (case info 24 1 25 2 26 4 27 8 nil)]
    (cond
      (< info 24) [info (inc i)]
      (nil? size) (reject! :bad-length info)
      (> (+ i 1 size) (count v)) (reject! :truncated i)
      :else [(reduce (fn [a x] (+ (* a 256) x)) 0 (subvec v (inc i) (+ i 1 size)))
             (+ i 1 size)])))

(defn- parse [v i depth]
  (when (> depth max-depth) (reject! :too-deep depth))
  (when (>= i (count v)) (reject! :truncated i))
  (let [ib (nth v i) major (quot ib 32) info (mod ib 32)]
    (if (= major 7)
      (case ib
        0xf6 [nil (inc i)]
        0xf5 [true (inc i)]
        0xf4 [false (inc i)]
        (reject! :unsupported-simple ib))
      (let [[n j] (parse-n v i info)
            slice (fn []
                    (when (> (+ j n) (count v)) (reject! :truncated j))
                    (subvec v j (+ j n)))]
        (when (> n max-safe) (reject! :integer-out-of-range n))
        (case major
          0 [n j]
          1 [(- -1 n) j]
          2 [(b/->bytes (slice)) (+ j n)]
          3 [(b/from-utf8 (slice)) (+ j n)]
          4 (do
              ;; every item takes a byte, so a bigger count cannot be real
              (when (> n (- (count v) j)) (reject! :truncated j))
              (loop [k 0 p j out []]
                (if (= k n)
                  [out p]
                  (let [[x q] (parse v p (inc depth))]
                    (recur (inc k) q (conj out x))))))
          6 (let [[x q] (parse v j (inc depth))] [(->Tag n x) q])
          (reject! :unsupported-major major))))))

(defn- cbor-decode [bs]
  (let [v (b/->vec bs)
        [x end] (parse v 0 0)]
    (when-not (= end (count v)) (reject! :trailing-bytes end))
    (when-not (= v (cbor x)) (reject! :not-canonical nil))
    x))

;; ── values ───────────────────────────────────────────────────────────────────

(declare value->form)

(defn- order-key [form] (cbor form))
(defn- keyword-text [k] (subs (str k) 1))

(defn- link->tag [l]
  (->Tag 42 (b/->bytes (into [0] (cid/cid-bytes (:cid l))))))

(defn value->form [x]
  (cond
    (nil? x) [0 nil]
    (boolean? x) [1 x]
    (link? x) [8 (link->tag x)]
    (integer? x) (if (<= (- max-safe) x max-safe) [2 x] (reject! :integer-out-of-range x))
    (string? x) [4 x]
    (keyword? x) (let [t (keyword-text x)]
                   (if (= x (keyword t)) [5 t] (reject! :keyword-not-round-trippable t)))
    (b/bytes? x) [7 x]
    (vector? x) [16 (mapv value->form x)]
    (set? x) [18 (vec (sort-by order-key (map value->form x)))]
    (map? x) [19 (vec (sort-by (comp order-key first)
                               (map (fn [[k v]] [(value->form k) (value->form v)]) x)))]
    :else (reject! :unsupported-type (str x))))

(defn- ascending! [forms]
  (doseq [[a b*] (partition 2 1 (map order-key forms))]
    (when-not (neg? (compare a b*)) (reject! :not-canonical-order nil))))

(defn- tag->link [t]
  (when-not (and (instance? Tag t) (= 42 (:n t)) (b/bytes? (:payload t)))
    (reject! :bad-link nil))
  (let [v (b/->vec (:payload t))]
    (when-not (= 0 (first v)) (reject! :bad-link-prefix nil))
    (link (cid/bytes->cid (rest v)))))

(defn form->value [form]
  (when-not (and (vector? form) (= 2 (count form)) (integer? (first form)))
    (reject! :form-malformed nil))
  (let [[code p] form
        items! #(if (vector? p) p (reject! :payload-not-a-vector code))]
    (case (int code)
      0 (if (nil? p) nil (reject! :bad-payload code))
      1 (if (boolean? p) p (reject! :bad-payload code))
      2 (if (and (integer? p) (<= (- max-safe) p max-safe)) p (reject! :bad-payload code))
      4 (if (string? p) p (reject! :bad-payload code))
      5 (if (string? p)
          (let [k (keyword p)] (if (= p (keyword-text k)) k (reject! :bad-payload code)))
          (reject! :bad-payload code))
      7 (if (b/bytes? p) p (reject! :bad-payload code))
      8 (tag->link p)
      16 (mapv form->value (items!))
      18 (do (ascending! (items!)) (into #{} (map form->value) p))
      19 (do (doseq [e (items!)]
               (when-not (and (vector? e) (= 2 (count e))) (reject! :bad-map-entry nil)))
             (ascending! (map first p))
             (into {} (map (fn [[k v]] [(form->value k) (form->value v)])) p))
      (reject! :unknown-type-code code))))

(defn encode
  "Canonical bytes for a value."
  [x]
  (b/->bytes (cbor (value->form x))))

(defn decode
  "The value of canonical bytes, or a thrown refusal."
  [bs]
  (form->value (cbor-decode bs)))
