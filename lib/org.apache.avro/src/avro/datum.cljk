(ns avro.datum
  "Decoding one value against a schema.

  Avro writes **no type tags**. The bytes of a long and the bytes of a string
  length are the same varint, and which one a position holds is known only
  from the schema. So decoding is schema-directed from the first byte, and a
  schema that disagrees with the writer's does not fail — it produces
  plausible wrong values and then desynchronises.

  That is why `avro.file` reads the schema out of the file rather than taking
  one from the caller: the only schema guaranteed to agree with the bytes is
  the one shipped beside them.

  ## Encoding has one decision decoding does not: which union branch

  Reading a union is told the branch by an index in the bytes. Writing one has
  to CHOOSE it from the value, and Avro gives the writer no help: a union of
  bytes-or-array is two schemas that both accept a sequence. `encode` takes
  the FIRST branch that accepts the value and refuses when none does -- never
  a default branch, because writing a value under the wrong branch is the
  encoder's version of the desynchronisation described above. It produces a
  file that decodes without error into the wrong thing.

  In practice this is not a constraint worth designing around: the union that
  appears in real Avro data, and in every Iceberg manifest, is the nullable
  one, which is never ambiguous."
  (:require [avro.binary :as b]))

(declare decode)

(defn- decode-array [schema bs i]
  ;; Blocks of (count, items...) terminated by a zero count. A NEGATIVE count
  ;; means the block is followed by its byte size -- writers emit that so a
  ;; reader can skip a block without decoding it -- and reading the size as
  ;; another item is how that turns into garbage.
  (loop [i i out []]
    (let [[n i'] (b/long-at bs i)
          n (long n)]
      (cond
        (zero? n) [out i']
        :else
        (let [[cnt i'] (if (neg? n)
                         (let [[_size i''] (b/long-at bs i')] [(- n) i''])
                         [n i'])
              [items i''] (reduce (fn [[acc j] _]
                                    (let [[v j'] (decode (:items schema) bs j)]
                                      [(conj acc v) j']))
                                  [out i'] (range cnt))]
          (recur i'' items))))))

(defn- decode-map [schema bs i]
  (loop [i i out {}]
    (let [[n i'] (b/long-at bs i)
          n (long n)]
      (cond
        (zero? n) [out i']
        :else
        (let [[cnt i'] (if (neg? n)
                         (let [[_size i''] (b/long-at bs i')] [(- n) i''])
                         [n i'])
              [m i''] (reduce (fn [[acc j] _]
                                (let [[k j'] (b/string-at bs j)
                                      [v j''] (decode (:values schema) bs j')]
                                  [(assoc acc k v) j'']))
                              [out i'] (range cnt))]
          (recur i'' m))))))

(defn decode
  "One value of `schema` at `i` → `[value next-index]`."
  [schema bs i]
  (case (:type schema)
    :null [nil i]
    :boolean (b/boolean-at bs i)
    (:int :long) (b/long-at bs i)
    :float (b/float-at bs i)
    :double (b/double-at bs i)
    :bytes (b/bytes-at bs i)
    :string (b/string-at bs i)
    :enum (let [[idx i'] (b/long-at bs i)]
            [(nth (:symbols schema) (long idx)) i'])
    :fixed [(subvec (vec bs) i (+ i (:size schema))) (+ i (:size schema))]
    :union (let [[idx i'] (b/long-at bs i)
                 branch (nth (:branches schema) (long idx) nil)]
             (when-not branch
               (throw (ex-info "union branch index is outside the schema"
                               {:type :avro/malformed :index idx
                                :branches (count (:branches schema))})))
             (decode branch bs i'))
    :array (decode-array schema bs i)
    :map (decode-map schema bs i)
    :record (reduce (fn [[acc j] {:keys [name schema]}]
                      (let [[v j'] (decode schema bs j)]
                        [(assoc acc name v) j']))
                    [{} i] (:fields schema))
    (throw (ex-info (str "avro: decoding " (pr-str (:type schema))
                         " is not implemented")
                    {:type :avro/unsupported-type :schema (:type schema)}))))

;; ---------------------------------------------------------------------------
;; Encoding.
;; ---------------------------------------------------------------------------

(defn- integral?
  "Is `v` a whole number this encoder can write as an int/long?

  On ClojureScript that includes a BigInt, which is how `avro.binary` hands
  back values past 2^53. There is no portable predicate for one, so the test
  is whether `js/BigInt` accepts it -- with strings and booleans excluded
  first, because BigInt of a string and BigInt of a boolean both succeed and
  neither is an integer the caller meant."
  [v]
  #?(:clj (integer? v)
     :cljs (cond
             (number? v) (and (js/Number.isFinite v) (js/Number.isInteger v))
             (or (nil? v) (string? v) (boolean? v)) false
             :else (try (js/BigInt v) true (catch :default _ false)))))

(defn- byte-seq?
  "A sequence of byte-sized integers -- what this repo's reader produces for
  `bytes` and `fixed`."
  [v]
  (and (sequential? v) (every? #(and (integral? %) (<= 0 % 255)) v)))

(defn- nullable?
  "Can `schema` represent nil? Used to decide whether an absent record field
  is an omission the writer may fill in, or one it must refuse."
  [schema]
  (or (= :null (:type schema))
      (and (= :union (:type schema))
           (boolean (some #(= :null (:type %)) (:branches schema))))))

(defn accepts?
  "Would `encode` write `v` under `schema` without lying about it?

  Deliberately structural rather than clever. `bytes` and `array` both accept
  a sequence and `map` and `record` both accept a map -- this does not try to
  break those ties, it reports them honestly and lets union branch order
  decide."
  [schema v]
  (case (:type schema)
    :null (nil? v)
    :boolean (boolean? v)
    (:int :long) (integral? v)
    (:float :double) (and (number? v) #?(:clj true :cljs (js/Number.isFinite v)))
    :bytes (byte-seq? v)
    :string (string? v)
    :enum (and (string? v) (boolean (some #{v} (:symbols schema))))
    :fixed (and (byte-seq? v) (= (count v) (:size schema)))
    :array (sequential? v)
    :map (map? v)
    :record (map? v)
    :union (boolean (some #(accepts? % v) (:branches schema)))
    false))

(declare encode)

(defn- encode-block
  "One array/map block: count, items, then the zero terminator.

  Written as a single block rather than chunked. The negative-count form (a
  block that declares its byte size so a reader can skip it) is legal and this
  writer does not emit it: it costs a second size pass and buys a reader
  nothing it cannot get by decoding, and `avro.datum/decode` reads both."
  [items encode-item]
  (if (empty? items)
    (b/long-of 0)
    (into (into (b/long-of (count items)) (mapcat encode-item) items)
          (b/long-of 0))))

(defn encode
  "One value → bytes, against `schema`.

  The mirror of `decode`: `(decode schema (encode schema v) 0)` is `[v _]` for
  every value this returns bytes for."
  [schema v]
  (case (:type schema)
    :null []
    :boolean (if (boolean? v)
               (b/boolean-of v)
               (throw (ex-info "avro: not a boolean" {:type :avro/value-mismatch :value v})))
    (:int :long) (if (integral? v)
                   (b/long-of v)
                   (throw (ex-info "avro: not an integer"
                                   {:type :avro/value-mismatch :value v :schema (:type schema)})))
    :float (b/float-of v)
    :double (b/double-of v)
    :bytes (b/bytes-of v)
    :string (b/string-of v)
    :enum (let [idx (first (keep-indexed #(when (= %2 v) %1) (:symbols schema)))]
            (if idx
              (b/long-of idx)
              (throw (ex-info "avro: value is not one of the enum's symbols"
                              {:type :avro/value-mismatch :value v
                               :symbols (:symbols schema)}))))
    :fixed (if (and (byte-seq? v) (= (count v) (:size schema)))
             (mapv #(bit-and % 0xff) v)
             ;; A fixed of the wrong length would silently consume the
             ;; following field's bytes on the way back in.
             (throw (ex-info "avro: fixed value has the wrong length"
                             {:type :avro/value-mismatch
                              :expected (:size schema) :actual (count v)})))
    :union (let [idx (first (keep-indexed #(when (accepts? %2 v) %1) (:branches schema)))]
             (if idx
               (into (b/long-of idx) (encode (nth (:branches schema) idx) v))
               (throw (ex-info "avro: no union branch accepts this value"
                               {:type :avro/value-mismatch :value v
                                :branches (mapv :type (:branches schema))}))))
    :array (encode-block (vec v) #(encode (:items schema) %))
    :map (encode-block (vec v)
                       (fn [[k val]]
                         (into (b/string-of k) (encode (:values schema) val))))
    :record (reduce (fn [acc {:keys [name schema]}]
                      (let [present? (contains? v name)
                            fv (get v name)]
                        (when-not (or present? (nullable? schema))
                          ;; Filling in a missing non-nullable field would
                          ;; write a value the caller never supplied, and Avro
                          ;; has no way to say "absent" -- refuse instead.
                          (throw (ex-info (str "avro: record field " (pr-str name)
                                               " is missing and its schema cannot be null")
                                          {:type :avro/missing-field :field name})))
                        (into acc (encode schema fv))))
                    [] (:fields schema))
    (throw (ex-info (str "avro: encoding " (pr-str (:type schema))
                         " is not implemented")
                    {:type :avro/unsupported-type :schema (:type schema)}))))
