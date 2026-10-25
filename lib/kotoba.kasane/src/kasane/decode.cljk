(ns kasane.decode
  "The data-driven binary decoder. A *grammar* is plain EDN data:

     {:meta  {:endian :big :root :psd-file}
      :enums {:color-mode {3 :rgb 4 :cmyk ...}}
      :types {:psd-file [{:id :sig :type :magic :value \"8BPS\"} ...]
              ...}}

   `decode` walks the grammar over a byte cursor and returns a nested EDN
   map. Adding a format means adding EDN, not code — the engine here is
   small and pure (loop/recur + byte ops), so it compiles via kotoba-clj
   to WASM. See ADR-2606272100."
  (:require [kasane.bytes :as b]))

(def ^:private prefix-bytes {:u8 1 :u16 2 :u32 4})

(defn- abs* [x] (if (neg? x) (- x) x))

(defn- resolve-num
  "Resolve a count/size expression against the current struct context.
   Number → itself; [:field k] → ctx value; [:abs n] → n;
   [:expr op a b ...] → arithmetic (:+ :- :* :abs)."
  [v ctx]
  (cond
    (number? v) v
    (vector? v) (case (first v)
                  :field (let [x (get ctx (second v))]
                           (if (number? x) x
                               (throw (ex-info "decode: field is not numeric" {:field (second v) :value x}))))
                  :abs   (second v)
                  :expr  (let [op   (second v)
                               args (map #(resolve-num % ctx) (drop 2 v))]
                           (case op
                             :+   (apply + args)
                             :-   (apply - args)
                             :*   (apply * args)
                             :abs (abs* (first args))
                             (throw (ex-info "decode: bad expr op" {:op op}))))
                  (throw (ex-info "decode: bad num expr" {:expr v})))
    :else (throw (ex-info "decode: bad num" {:value v}))))

(defn- apply-enum [grammar field v]
  (if-let [en (:enum field)]
    (get-in grammar [:enums en v] v)
    v))

(declare read-struct)

(defn- read-value [grammar field ctx cur]
  (let [big? (= (or (:endian field) (get-in grammar [:meta :endian] :big)) :big)]
    (case (:type field)
      :magic (let [s (b/bytes->ascii (b/read-bytes! cur (count (:value field))))]
               (when (not= s (:value field))
                 (throw (ex-info "decode: magic mismatch"
                                 {:expected (:value field) :got s :pos (b/pos cur)})))
               s)
      :skip  (do (b/skip! cur (resolve-num (:size field) ctx)) nil)
      :u8    (b/u8! cur)
      :u16   (b/uint! cur 2 big?)
      :u32   (b/uint! cur 4 big?)
      :u64   (b/uint! cur 8 big?)
      :i8    (b/sint! cur 1 big?)
      :i16   (b/sint! cur 2 big?)
      :i32   (b/sint! cur 4 big?)
      :bytes (let [n (if-let [sp (:size-prefix field)]
                       (b/uint! cur (prefix-bytes sp) big?)
                       (resolve-num (:size field) ctx))]
               (b/read-bytes! cur n))
      :blob  (let [n (b/uint! cur (prefix-bytes (:size-prefix field)) big?)]
               {:length n :bytes (b/read-bytes! cur n)})
      :str   (let [n (cond (:size-prefix field) (b/uint! cur (prefix-bytes (:size-prefix field)) big?)
                           (:size field)        (resolve-num (:size field) ctx)
                           :else (throw (ex-info "decode: :str needs :size or :size-prefix" {:field field})))]
               (b/bytes->ascii (b/read-bytes! cur n)))
      ;; nested struct, optionally length-bounded (we seek past trailing bytes)
      :struct (if-let [sp (:size-prefix field)]
                (let [n   (b/uint! cur (prefix-bytes sp) big?)
                      end (+ (b/pos cur) n)
                      v   (read-struct grammar (:of field) cur)]
                  (b/seek! cur end)
                  (assoc v :_length n))
                (read-struct grammar (:of field) cur))
      :seq   (if (:until-eof field)
               (loop [acc []]                                  ; read structs until cursor EOF
                 (if (b/eof? cur) acc
                     (recur (conj acc (read-struct grammar (:of field) cur)))))
               (let [n (resolve-num (:count field) ctx)]
                 (vec (repeatedly n #(read-struct grammar (:of field) cur)))))
      (throw (ex-info "decode: unknown field type" {:type (:type field) :field field})))))

(defn read-struct
  "Read the named struct type from the cursor, returning a map keyed by
   each field's :id."
  [grammar tname cur]
  (let [fields (get-in grammar [:types tname])]
    (when-not fields (throw (ex-info "decode: unknown type" {:type tname})))
    (reduce (fn [ctx field]
              (let [v (apply-enum grammar field (read-value grammar field ctx cur))]
                (if (:id field) (assoc ctx (:id field) v) ctx)))
            {} fields)))

(defn decode
  "Decode `data` (seq of unsigned bytes) against an EDN `grammar`,
   starting from the root type (`:meta :root` unless given explicitly)."
  ([grammar data]
   (decode grammar (get-in grammar [:meta :root]) data))
  ([grammar root data]
   (when-not root (throw (ex-info "decode: no root type" {})))
   (read-struct grammar root (b/cursor data))))
