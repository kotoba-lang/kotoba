(ns mqtt.properties
  "MQTT 5.0 Properties (MQTT-5.0 §2.2.2 / §3.1.2.11). Absent from MQTT
  3.1.1 entirely — this namespace is not used by that side of the codec at
  all, which is itself the main compatibility fact about it.

  On the wire a property list is a Property Length (Variable Byte Integer,
  `mqtt.varint`) followed by that many bytes of `Identifier, Value` pairs.
  The identifier is itself a Variable Byte Integer, but every identifier
  the spec defines fits in one byte (1..42), so this module reads it with
  `varint/decode` for correctness rather than assuming one byte.

  Property IDENTIFIERS are stable across the whole protocol; which packet
  types are ALLOWED to carry which property is a per-type table this
  namespace does not enforce — a decoder that rejects a syntactically valid
  property because THIS packet type shouldn't carry it is answering a
  different, and cheaper, question than 'are these bytes well-formed'."
  (:require [mqtt.varint :as varint]
            [mqtt.utf8 :as utf8]))

(def value-kinds
  "MQTT-5.0 §2.2.2.2, one row per Property Identifier — the wire TYPE of the
  value that follows, not the field's name. `:byte` 1 byte, `:u16`/`:u32`
  big-endian, `:varint` a Variable Byte Integer, `:utf8` an
  `mqtt.utf8`-encoded string, `:binary` an `mqtt.utf8`-encoded byte string,
  `:utf8-pair` two consecutive `:utf8` values (User Property's key/value)."
  {1 :byte      ; Payload Format Indicator
   2 :u32       ; Message Expiry Interval
   3 :utf8      ; Content Type
   8 :utf8      ; Response Topic
   9 :binary    ; Correlation Data
   11 :varint   ; Subscription Identifier
   17 :u32      ; Session Expiry Interval
   18 :utf8     ; Assigned Client Identifier
   19 :u16      ; Server Keep Alive
   21 :utf8     ; Authentication Method
   22 :binary   ; Authentication Data
   23 :byte     ; Request Problem Information
   24 :u32      ; Will Delay Interval
   25 :byte     ; Request Response Information
   26 :utf8     ; Response Information
   28 :utf8     ; Server Reference
   31 :utf8     ; Reason String
   33 :u16      ; Receive Maximum
   34 :u16      ; Topic Alias Maximum
   35 :u16      ; Topic Alias
   36 :byte     ; Maximum QoS
   37 :byte     ; Retain Available
   38 :utf8-pair ; User Property
   39 :u32      ; Maximum Packet Size
   40 :byte     ; Wildcard Subscription Available
   41 :byte     ; Subscription Identifier Available
   42 :byte})   ; Shared Subscription Available

(def property-name
  "Human-readable name of each identifier, for error messages and tests —
  not part of the wire format."
  {1 :payload-format-indicator 2 :message-expiry-interval 3 :content-type
   8 :response-topic 9 :correlation-data 11 :subscription-identifier
   17 :session-expiry-interval 18 :assigned-client-identifier
   19 :server-keep-alive 21 :authentication-method 22 :authentication-data
   23 :request-problem-information 24 :will-delay-interval
   25 :request-response-information 26 :response-information
   28 :server-reference 31 :reason-string 33 :receive-maximum
   34 :topic-alias-maximum 35 :topic-alias 36 :maximum-qos
   37 :retain-available 38 :user-property 39 :maximum-packet-size
   40 :wildcard-subscription-available
   41 :subscription-identifier-available
   42 :shared-subscription-available})

(def name->property (into {} (map (fn [[k v]] [v k])) property-name))

(defn- be [n bytes]
  (vec (for [i (range (dec bytes) -1 -1)] (bit-and (unsigned-bit-shift-right n (* 8 i)) 0xFF))))

(defn- rd-be [bs i bytes]
  (reduce (fn [acc k] (+ (* acc 256) (nth bs (+ i k)))) 0 (range bytes)))

(defn- encode-value [kind v]
  (case kind
    :byte [(bit-and v 0xFF)]
    :u16 (be v 2)
    :u32 (be v 4)
    :varint (varint/encode v)
    ;; `v` is a host string for :utf8/:utf8-pair — `utf8/encode` wants a byte
    ;; sequence, and `(vec "a string")` produces a vector of Characters, not
    ;; ints, which then poisons every downstream `bit-and`/`zero?` on those
    ;; "bytes" with a ClassCastException far from this line. `ascii->bytes`
    ;; converts first so the property's bytes are ordinary ints like every
    ;; other field's.
    :utf8 (:bytes (utf8/encode (utf8/ascii->bytes v)))
    :binary (:bytes (utf8/encode v))
    :utf8-pair (into (:bytes (utf8/encode (utf8/ascii->bytes (first v))))
                     (:bytes (utf8/encode (utf8/ascii->bytes (second v)))))))

(defn encode-one
  "`[identifier-name value]` -> bytes, including the identifier itself."
  [[nm v]]
  (if-let [id (name->property nm)]
    (let [kind (value-kinds id)]
      {:status :ok
       :bytes (into (varint/encode id) (encode-value kind v))})
    {:status :error :reason :unknown-property :name nm}))

(defn encode
  "A property list — `[[name value] ...]` — as a `Property Length`-prefixed
  byte vector, ready to splice into a variable header."
  [props]
  (loop [ps props out []]
    (if (empty? ps)
      {:status :ok :bytes (into (varint/encode (count out)) out)}
      (let [r (encode-one (first ps))]
        (if (= :error (:status r))
          r
          (recur (rest ps) (into out (:bytes r))))))))

(defn- decode-value [kind bs i]
  (case kind
    :byte (if (< i (count bs))
            {:status :ok :value (nth bs i) :next-index (inc i)}
            {:status :incomplete})
    (:u16 :u32)
    (let [w (if (= kind :u16) 2 4)]
      (if (> (+ i w) (count bs))
        {:status :incomplete}
        {:status :ok :value (rd-be bs i w) :next-index (+ i w)}))
    :varint
    (let [r (varint/decode bs i)]
      (if (= :ok (:status r))
        {:status :ok :value (:value r) :next-index (:next-index r)}
        r))
    :utf8
    (let [r (utf8/decode bs i)]
      (if (= :ok (:status r))
        {:status :ok :value (utf8/bytes->ascii (:bytes r)) :next-index (:next-index r)}
        r))
    :binary
    (let [r (utf8/decode bs i)]
      (if (= :ok (:status r))
        {:status :ok :value (:bytes r) :next-index (:next-index r)}
        r))
    :utf8-pair
    (let [k (utf8/decode bs i)]
      (if (not= :ok (:status k))
        k
        (let [v (utf8/decode bs (:next-index k))]
          (if (not= :ok (:status v))
            v
            {:status :ok
             :value [(utf8/bytes->ascii (:bytes k)) (utf8/bytes->ascii (:bytes v))]
             :next-index (:next-index v)}))))))

(defn decode
  "Reads a `Property Length`-prefixed property list starting at index `i`.
  Returns `{:status :ok :properties [[name value] ...] :next-index j}`.
  `:reason :unknown-property-identifier` on an identifier this table does
  not know (a real deployment would need an allow-list of extensions; this
  codec has none, so an unrecognised identifier is reported rather than
  silently skipped by guessing its value's length from nothing)."
  [bs i]
  (let [bs (vec bs)
        len-r (varint/decode bs i)]
    (case (:status len-r)
      :incomplete {:status :incomplete}
      :error len-r
      :ok
      (let [end (+ (:next-index len-r) (:value len-r))]
        (if (> end (count bs))
          {:status :incomplete}
          (loop [j (:next-index len-r) out []]
            (if (>= j end)
              {:status :ok :properties out :next-index j}
              (let [id-r (varint/decode bs j)]
                (if (not= :ok (:status id-r))
                  {:status :error :reason :malformed-property-identifier}
                  (let [id (:value id-r)
                        kind (value-kinds id)]
                    (if (nil? kind)
                      {:status :error :reason :unknown-property-identifier :identifier id}
                      (let [v-r (decode-value kind bs (:next-index id-r))]
                        (if (not= :ok (:status v-r))
                          v-r
                          (recur (:next-index v-r)
                                 (conj out [(property-name id) (:value v-r)])))))))))))))))
