(ns opcua.variant
  "OPC UA Variant (§7.14 / Part 6 §5.2.2.16), ExtensionObject (§7.8), and
  DataValue (§7.7) — the container types built out of every other type in
  `opcua.builtin`/`opcua.nodeid`.

  A Variant starts with one encoding-mask byte:

  ```
  bit:  7          6              5 4 3 2 3 2 1 0
        array?     has-dimensions?  BuiltInType id (6 bits, 1-25)
  ```

  - Neither bit 6 nor bit 7 set: a single scalar value of the named type
    follows.
  - Bit 7 set: an Int32 array length (the -1/null convention from
    `opcua.builtin/decode-string` applies here too — -1 is 'no array', not
    an empty one) followed by that many encoded values.
  - Bit 7 AND bit 6 set: after the array elements, ANOTHER Int32-length-
    prefixed array follows — of Int32 dimension sizes for a multi-
    dimensional array laid out in row-major order. **Bit 6 without bit 7 is
    not a legal combination** (dimensions describe an array; there is
    nothing to have dimensions without one) and this library rejects it
    rather than silently ignoring the orphaned bit.

  A decoder that checks only bit 7 and ignores bit 6 will read a
  multi-dimensional array as a flat one — the elements decode fine (the
  dimensions block is a separate trailing structure, not interleaved with
  the data), but the caller loses the shape and a client expecting a 3×4
  matrix gets 12 numbers with no explanation of how they were meant to be
  arranged.

  ExtensionObject (§7.8): a NodeId (naming the DataType's binary encoding),
  an encoding-format Byte (0 = no body, 1 = ByteString body, 2 = XmlElement
  body), and the body itself when the format is not 0. This library treats
  the body as opaque bytes either way — decoding the *contents* of a
  specific DataType's ExtensionObject body is a generated-from-schema
  concern this codec does not take on (see README).

  DataValue (§7.7): another encoding-mask byte, this time with SIX
  optional fields (Value, StatusCode, SourceTimestamp, SourceTimestamp
  PicoSeconds, ServerTimestamp, ServerTimestamp PicoSeconds) each gated by
  its own mask bit and present only in that case, in that fixed order."
  (:require [opcua.builtin :as b] [opcua.nodeid :as nid]))

;; ── Variant type table ───────────────────────────────────────────────────

(def type-ids
  {:boolean 1 :sbyte 2 :byte 3 :int16 4 :uint16 5 :int32 6 :uint32 7
   :int64 8 :uint64 9 :float 10 :double 11 :string 12 :date-time 13
   :guid 14 :byte-string 15 :xml-element 16 :node-id 17 :expanded-node-id 18
   :status-code 19 :qualified-name 20 :localized-text 21 :extension-object 22})
(def id->type (into {} (map (fn [[k v]] [v k])) type-ids))

;; NodeId/ExpandedNodeId return `{:bytes […]}` / consume `(bs offset)` and
;; return `{:next …}` with the payload spread across top-level keys rather
;; than under `:value` — these adapters normalize both to the shape every
;; other builtin encoder/decoder already uses.
(defn- encode-node-id [v] (:bytes (nid/encode v)))
(defn- decode-node-id [bs offset]
  (let [r (nid/decode bs offset)]
    (if (= :error (first r)) r
        {:status :ok :value (dissoc r :status :next) :next (:next r)})))
(defn- encode-expanded-node-id [v] (:bytes (nid/encode-expanded v)))
(defn- decode-expanded-node-id [bs offset]
  (let [r (nid/decode-expanded bs offset)]
    (if (= :error (first r)) r
        {:status :ok :value (dissoc r :status :next) :next (:next r)})))

(declare encode-extension-object decode-extension-object)

(def codecs
  {:boolean [b/encode-boolean b/decode-boolean]
   :sbyte [b/encode-sbyte b/decode-sbyte]
   :byte [b/encode-byte b/decode-byte]
   :int16 [b/encode-int16 b/decode-int16]
   :uint16 [b/encode-uint16 b/decode-uint16]
   :int32 [b/encode-int32 b/decode-int32]
   :uint32 [b/encode-uint32 b/decode-uint32]
   :int64 [b/encode-int64 b/decode-int64]
   :uint64 [b/encode-uint64 b/decode-uint64]
   :float [b/encode-float b/decode-float]
   :double [b/encode-double b/decode-double]
   :string [b/encode-string b/decode-string]
   :date-time [b/encode-date-time b/decode-date-time]
   :guid [b/encode-guid b/decode-guid]
   :byte-string [b/encode-byte-string b/decode-byte-string]
   :xml-element [b/encode-xml-element b/decode-xml-element]
   :node-id [encode-node-id decode-node-id]
   :expanded-node-id [encode-expanded-node-id decode-expanded-node-id]
   :status-code [b/encode-status-code b/decode-status-code]
   :qualified-name [b/encode-qualified-name b/decode-qualified-name]
   :localized-text [b/encode-localized-text b/decode-localized-text]
   :extension-object [encode-extension-object decode-extension-object]})

;; ── ExtensionObject (§7.8) ───────────────────────────────────────────────

(def extension-formats {:none 0 :byte-string 1 :xml-element 2})
(def format->kw (into {} (map (fn [[k v]] [v k])) extension-formats))

(defn encode-extension-object
  "`{:type-id node-id-map :format :none|:byte-string|:xml-element :body bytes}`
  `:body` is required (and ignored if given) exactly when `:format` says so —
  `:none` with a non-nil `:body` is rejected rather than silently dropping it."
  [{:keys [type-id format body]}]
  (if (and (= format :none) (some? body))
    [:error :opcua/body-not-allowed]
    (let [fmt (extension-formats format)]
      (if (nil? fmt)
        [:error :opcua/unknown-extension-format]
        (into (into (:bytes (nid/encode type-id)) [fmt])
              (when (not= format :none) (b/encode-byte-string body)))))))

(defn decode-extension-object
  [bs offset]
  (let [tid (nid/decode bs offset)]
    (if (= :error (first tid)) tid
        (let [fmt-r (b/decode-byte bs (:next tid))]
          (if (= :error (first fmt-r)) fmt-r
              (let [fmt (format->kw (:value fmt-r))]
                (cond
                  (nil? fmt) [:error :opcua/unknown-extension-format]
                  (= fmt :none) {:status :ok :value {:type-id (dissoc tid :status :next)
                                                       :format :none :body nil}
                                 :next (:next fmt-r)}
                  :else
                  (let [body-r (b/decode-byte-string bs (:next fmt-r))]
                    (if (= :error (first body-r)) body-r
                        {:status :ok
                         :value {:type-id (dissoc tid :status :next) :format fmt
                                 :body (:value body-r)}
                         :next (:next body-r)})))))))))

;; ── Variant (§7.14) ────────────────────────────────────────────────────

(def array-flag 0x80)
(def dimensions-flag 0x40)
(def type-id-mask 0x3F)

(defn- encode-array [encode-fn values]
  (if (nil? values)
    (b/encode-int32 -1)
    (into (b/encode-int32 (count values)) (mapcat encode-fn values))))

(defn- decode-array [decode-fn bs offset]
  (let [len-r (b/decode-int32 bs offset)]
    (if (= :error (first len-r)) len-r
        (let [len (:value len-r)]
          (cond
            (= len -1) {:status :ok :value nil :next (:next len-r)}
            (neg? len) [:error :opcua/negative-length]
            :else
            (loop [i 0 offset (:next len-r) acc []]
              (if (= i len)
                {:status :ok :value acc :next offset}
                (let [r (decode-fn bs offset)]
                  (if (= :error (first r)) r
                      (recur (inc i) (:next r) (conj acc (:value r))))))))))))

(defn encode
  "`{:type kw :array? bool :dimensions [n ...] :value v-or-[v...]}`. Scalar:
  `:array?` false/absent, `:value` a single value. Array: `:array?` true,
  `:value` a vector of values (or nil for the null-array encoding).
  `:dimensions`, if given, requires `:array?` true — see namespace
  docstring on why bit 6 without bit 7 is refused rather than tolerated."
  [{:keys [type array? dimensions value]}]
  (let [tid (type-ids type)]
    (cond
      (nil? tid) [:error :opcua/unknown-type]
      (and dimensions (not array?)) [:error :opcua/dimensions-without-array]
      :else
      (let [[encode-fn] (codecs type)
            mask (bit-or tid (if array? array-flag 0) (if dimensions dimensions-flag 0))]
        (if array?
          {:status :ok
           :bytes (into (into [mask] (encode-array encode-fn value))
                        (when dimensions (encode-array b/encode-int32 dimensions)))}
          {:status :ok :bytes (into [mask] (encode-fn value))})))))

(defn decode
  [bs offset]
  (if-let [mask (b/safe-nth bs offset)]
    (let [array? (not (zero? (bit-and mask array-flag)))
          has-dims? (not (zero? (bit-and mask dimensions-flag)))
          tid (bit-and mask type-id-mask)
          type (id->type tid)]
      (cond
        (nil? type) [:error :opcua/unknown-type]
        (and has-dims? (not array?)) [:error :opcua/dimensions-without-array]
        :else
        (let [[_ decode-fn] (codecs type)]
          (if array?
            (let [arr (decode-array decode-fn bs (inc offset))]
              (if (= :error (first arr)) arr
                  (if has-dims?
                    (let [dims (decode-array b/decode-int32 bs (:next arr))]
                      (if (= :error (first dims)) dims
                          {:status :ok :type type :array? true :value (:value arr)
                           :dimensions (:value dims) :next (:next dims)}))
                    {:status :ok :type type :array? true :value (:value arr)
                     :dimensions nil :next (:next arr)})))
            (let [v (decode-fn bs (inc offset))]
              (if (= :error (first v)) v
                  {:status :ok :type type :array? false :value (:value v) :next (:next v)}))))))
    [:error :opcua/truncated]))

;; ── DataValue (§7.7) ───────────────────────────────────────────────────

(def data-value-flags
  {:value 0x01 :status-code 0x02 :source-timestamp 0x04
   :source-picoseconds 0x08 :server-timestamp 0x10 :server-picoseconds 0x20})

(defn encode-data-value
  "`{:value variant-map-or-nil :status-code n-or-nil :source-timestamp
  tick-pair-or-nil :source-picoseconds n-or-nil :server-timestamp
  tick-pair-or-nil :server-picoseconds n-or-nil}`. Each field's presence in
  the mask is derived from whether that key is non-nil in the input, in the
  fixed field order §7.7 specifies — Value, StatusCode, SourceTimestamp,
  SourcePicoSeconds, ServerTimestamp, ServerPicoSeconds."
  [{:keys [value status-code source-timestamp source-picoseconds
           server-timestamp server-picoseconds]}]
  (let [variant-enc (when value (encode value))]
    (if (and variant-enc (= :error (first variant-enc)))
      variant-enc
      (let [mask (bit-or (if value (:value data-value-flags) 0)
                          (if status-code (:status-code data-value-flags) 0)
                          (if source-timestamp (:source-timestamp data-value-flags) 0)
                          (if source-picoseconds (:source-picoseconds data-value-flags) 0)
                          (if server-timestamp (:server-timestamp data-value-flags) 0)
                          (if server-picoseconds (:server-picoseconds data-value-flags) 0))]
        {:status :ok
         :bytes (into [mask]
                      (concat (when value (:bytes variant-enc))
                              (when status-code (b/encode-status-code status-code))
                              (when source-timestamp (b/encode-date-time source-timestamp))
                              (when source-picoseconds (b/encode-uint16 source-picoseconds))
                              (when server-timestamp (b/encode-date-time server-timestamp))
                              (when server-picoseconds (b/encode-uint16 server-picoseconds))))}))))

(defn decode-data-value
  [bs offset]
  (if-let [mask (b/safe-nth bs offset)]
    (let [has-value? (not (zero? (bit-and mask (:value data-value-flags))))
          has-status? (not (zero? (bit-and mask (:status-code data-value-flags))))
          has-src-ts? (not (zero? (bit-and mask (:source-timestamp data-value-flags))))
          has-src-ps? (not (zero? (bit-and mask (:source-picoseconds data-value-flags))))
          has-srv-ts? (not (zero? (bit-and mask (:server-timestamp data-value-flags))))
          has-srv-ps? (not (zero? (bit-and mask (:server-picoseconds data-value-flags))))
          none {:status :ok :value nil}]
      (let [v (if has-value? (decode bs (inc offset)) (assoc none :next (inc offset)))]
        (if (= :error (first v)) v
            (let [sc (if has-status? (b/decode-status-code bs (:next v)) (assoc none :next (:next v)))]
              (if (= :error (first sc)) sc
                  (let [st (if has-src-ts? (b/decode-date-time bs (:next sc)) (assoc none :next (:next sc)))]
                    (if (= :error (first st)) st
                        (let [sp (if has-src-ps? (b/decode-uint16 bs (:next st)) (assoc none :next (:next st)))]
                          (if (= :error (first sp)) sp
                              (let [zt (if has-srv-ts? (b/decode-date-time bs (:next sp)) (assoc none :next (:next sp)))]
                                (if (= :error (first zt)) zt
                                    (let [zp (if has-srv-ps? (b/decode-uint16 bs (:next zt)) (assoc none :next (:next zt)))]
                                      (if (= :error (first zp)) zp
                                          {:status :ok
                                           :value (when has-value? (dissoc v :status :next))
                                           :status-code (:value sc)
                                           :source-timestamp (:value st) :source-picoseconds (:value sp)
                                           :server-timestamp (:value zt) :server-picoseconds (:value zp)
                                           :next (:next zp)})))))))))))))
    [:error :opcua/truncated]))
