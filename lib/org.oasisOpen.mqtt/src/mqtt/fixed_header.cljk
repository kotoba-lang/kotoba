(ns mqtt.fixed-header
  "The MQTT fixed header: one control byte, then the Remaining Length
  Variable Byte Integer (MQTT-3.1.1 §2.2, MQTT-5.0 §2.1.1/§2.1.2).

  The control byte packs two independent things into one byte because the
  spec fixes it that way: the high nibble is the Packet Type (1..15), the
  low nibble is per-type flags. For most types the low nibble is a fixed
  constant the receiver MUST reject if it doesn't match — PUBLISH is the one
  exception, where bits carry DUP/QoS/RETAIN and are meaningful data, not a
  reserved pattern to validate. Getting the reserved-flags check backwards
  (accepting whatever byte shows up, or rejecting PUBLISH's real flag bits
  as if they were reserved) is the two ways this is usually got wrong."
  (:require [mqtt.varint :as varint]))

(def packet-types
  "MQTT-3.1.1 §2.2.1 Table 2.1 / MQTT-5.0 §2.1.2 Table 2-1. Both versions
  use the same sixteen type codes; AUTH (15) is MQTT 5.0 only."
  {1 :connect 2 :connack 3 :publish 4 :puback 5 :pubrec 6 :pubrel 7 :pubcomp
   8 :subscribe 9 :suback 10 :unsubscribe 11 :unsuback 12 :pingreq
   13 :pingresp 14 :disconnect 15 :auth})

(def type->packet-type (into {} (map (fn [[k v]] [v k])) packet-types))

(def ^:private reserved-flags
  "MQTT-3.1.1 §2.2.2: the fixed value the low nibble MUST carry for every
  type except PUBLISH, whose flags are meaningful. SUBSCRIBE/UNSUBSCRIBE/
  PUBREL are `0b0010` for historical reasons the spec does not explain
  further than 'reserved and MUST be set to 0,0,1,0'."
  {:connect 0 :connack 0 :puback 0 :pubrec 0 :pubrel 2 :pubcomp 0
   :subscribe 2 :suback 0 :unsubscribe 2 :unsuback 0 :pingreq 0 :pingresp 0
   :disconnect 0 :auth 0})

(defn encode
  "`{:type kw :flags n :remaining-length n}` -> byte vector. `flags` is
  ignored (and the reserved value used) for every type except `:publish`."
  [{:keys [type flags remaining-length]}]
  (if-let [tc (type->packet-type type)]
    (let [f (if (= type :publish) (bit-and (or flags 0) 0x0F) (reserved-flags type))]
      {:status :ok
       :bytes (into [(bit-or (bit-shift-left tc 4) f)]
                    (varint/encode remaining-length))})
    {:status :error :reason :unknown-packet-type :type type}))

(defn decode
  "Bytes -> `{:status :ok :header {...} :next-index j}`, where `j` is the
  index the variable header starts at. `:incomplete` if the Remaining
  Length integer isn't fully present yet; the control byte itself is always
  1 byte so a zero-length input is simply :incomplete rather than a special
  case."
  [bs]
  (let [bs (vec bs)]
    (if (empty? bs)
      {:status :incomplete}
      (let [b0 (nth bs 0)
            tc (unsigned-bit-shift-right b0 4)
            flags (bit-and b0 0x0F)
            type (packet-types tc)]
        (cond
          (nil? type) {:status :error :reason :unknown-packet-type :code tc}

          (and (not= type :publish) (not= flags (reserved-flags type)))
          {:status :error :reason :malformed-reserved-flags :type type :flags flags}

          :else
          (let [r (varint/decode bs 1)]
            (case (:status r)
              :incomplete {:status :incomplete}
              :error r
              :ok {:status :ok
                   :header {:type type :flags flags
                            :remaining-length (:value r)}
                   :next-index (:next-index r)})))))))
