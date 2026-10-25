(ns mqtt.packet
  "MQTT Control Packets — OASIS MQTT Version 3.1.1 (`mqtt-v3.1.1-os.html`,
  the two-versions-in-one namespace is deliberate: `:version 4` selects
  3.1.1 wire rules (protocol level byte 0x04, no properties anywhere) and
  `:version 5` selects MQTT Version 5.0 (`mqtt-v5.0.html`, protocol level
  byte 0x05, Properties on most packet types). The two protocols share a
  fixed header, a Packet Identifier field, and almost every payload
  encoding; splitting them into separate namespaces would duplicate all of
  that and let the duplicate drift, which is exactly the kind of
  wrong-and-plausible bug a shared reserved-flags table (`mqtt.fixed-header`)
  is supposed to prevent.

  Every `encode-*`/`decode-*` here returns a whole packet — fixed header
  through payload — as `{:status :ok :bytes [...]}` or the reverse. Nothing
  throws; a malformed input comes back as `{:status :error :reason kw}` with
  a keyword that names what was wrong, and a truncated one comes back as
  `{:status :incomplete}`, which on a stream transport is normal, not an
  error — the same distinction `modbus.pdu` in this workspace makes for the
  same reason."
  (:require [mqtt.utf8 :as utf8]
            [mqtt.fixed-header :as fh]
            [mqtt.properties :as props]))

;; ── shared field readers/writers ────────────────────────────────────────────

(defn- be16 [n] [(bit-and (unsigned-bit-shift-right n 8) 0xFF) (bit-and n 0xFF)])

(defn- read-u16 [bs i]
  (if (> (+ i 2) (count bs))
    {:status :incomplete}
    {:status :ok :value (+ (* 256 (nth bs i)) (nth bs (inc i))) :next-index (+ i 2)}))

(defn- read-u8 [bs i]
  (if (>= i (count bs))
    {:status :incomplete}
    {:status :ok :value (nth bs i) :next-index (inc i)}))

(defn- read-utf8 [bs i]
  (let [r (utf8/decode bs i)]
    (if (= :ok (:status r))
      {:status :ok :value (utf8/bytes->ascii (:bytes r)) :next-index (:next-index r)}
      r)))

(defn- ok? [m] (= :ok (:status m)))

(defn- frame
  "Wraps an encoded variable-header+payload byte vector with its fixed
  header. The only place `Remaining Length` gets computed, so every packet
  type reports it the same (correct) way: the length of everything *after*
  the fixed header, never guessed or hand-maintained per type."
  [type flags body]
  (let [h (fh/encode {:type type :flags flags :remaining-length (count body)})]
    (if (ok? h)
      {:status :ok :bytes (into (:bytes h) body)}
      h)))

(defn- maybe-props
  "MQTT 5.0 properties are absent entirely from the wire in v3.1.1 — not an
  empty property list, no bytes at all, not even a zero Property Length.
  Getting this wrong (emitting `0x00` for 'no properties' under v4) desyncs
  every field that follows for a peer speaking 3.1.1."
  [version props-vec]
  (if (= version 5) (:bytes (props/encode (or props-vec []))) []))

(defn- run-steps
  "Runs `steps` — `[key reader-fn]` pairs, each `reader-fn` a function of
  `i -> {:status :ok :value v :next-index j}` or an error/:incomplete map —
  in order, threading `:next-index` from one into the next and
  short-circuiting on the first non-:ok result. This is what keeps
  multi-field variable headers (CONNECT's is the longest: Properties,
  Client Identifier, and four more optional fields gated by Connect Flags)
  from turning into a hand-nested nest of nine `if-not` forms, which is
  exactly what this function replaced here after that version proved too
  easy to close a paren wrong in."
  [i steps]
  (loop [i i steps steps values {}]
    (if (empty? steps)
      {:status :ok :values values :next-index i}
      (let [[k f] (first steps)
            r (f i)]
        (if (ok? r)
          (recur (:next-index r) (rest steps) (assoc values k (:value r)))
          r)))))

(defn- read-props-value
  "`mqtt.properties/decode`, normalised to `run-steps`'s `{:value ...}`
  shape, and a no-op that consumes zero bytes under v3.1.1 where properties
  do not exist on the wire at all."
  [bs i version]
  (if (= version 5)
    (let [r (props/decode bs i)]
      (if (ok? r) {:status :ok :value (:properties r) :next-index (:next-index r)} r))
    {:status :ok :value [] :next-index i}))

(defn- read-utf8-str-value [bs i] (read-utf8 bs i))

(defn- read-utf8-bytes-value
  [bs i]
  (let [r (utf8/decode bs i)]
    (if (ok? r) {:status :ok :value (:bytes r) :next-index (:next-index r)} r)))


;; ── CONNECT (MQTT-3.1.1 §3.1, MQTT-5.0 §3.1) ────────────────────────────────

(def protocol-name-bytes
  "MQTT-3.1.1 §3.1.2.1 / MQTT-5.0 §3.1.2.1: both versions use the literal
  UTF-8 string \"MQTT\", length-prefixed like any other UTF-8 field —
  `[0x00 0x04 0x4D 0x51 0x54 0x54]`. The pre-3.1.1 wire protocol used
  \"MQIsdp\" instead; a decoder that accepts either without being told to
  is silently widening what it claims to speak."
  (:bytes (utf8/encode (utf8/ascii->bytes "MQTT"))))

(defn encode-connect
  "`{:version 4|5 :client-id str :clean-session? bool :keep-alive u16
    :will {:topic str :payload bytes :qos 0|1|2 :retain? bool
           :properties [...]}
    :username str :password bytes :properties [...]}`
  -> a full CONNECT packet."
  [{:keys [version client-id clean-session? keep-alive will username password properties]
    :or {version 4 clean-session? true keep-alive 60}}]
  (if-not (#{4 5} version)
    {:status :error :reason :unsupported-protocol-version :version version}
    (let [flags (bit-or (if username 0x80 0)
                        (if password 0x40 0)
                        (if (:retain? will) 0x20 0)
                        (bit-shift-left (or (:qos will) 0) 3)
                        (if will 0x04 0)
                        (if clean-session? 0x02 0))
          var-header (into (into protocol-name-bytes [version])
                           (into [flags] (be16 keep-alive)))
          var-header (into var-header (maybe-props version properties))
          payload (-> []
                     (into (:bytes (utf8/encode (utf8/ascii->bytes client-id))))
                     (into (if will (maybe-props version (:properties will)) []))
                     (into (if will (:bytes (utf8/encode (utf8/ascii->bytes (:topic will)))) []))
                     (into (if will (:bytes (utf8/encode (:payload will))) []))
                     (into (if username (:bytes (utf8/encode (utf8/ascii->bytes username))) []))
                     (into (if password (:bytes (utf8/encode password)) [])))]
      (frame :connect 0 (into var-header payload)))))

(defn- decode-connect-body
  "Parses the CONNECT variable header and payload — everything after the
  fixed header. Split out from `decode-connect` so the fixed-header framing
  (shared with every other packet type) and the CONNECT-specific field
  sequence are each easy to get right in isolation."
  [bs]
  (let [bs (vec bs)]
    (cond
      (< (count bs) 10) {:status :incomplete}

      (not= (subvec bs 0 6) protocol-name-bytes)
      {:status :error :reason :unrecognised-protocol-name}

      :else
      (let [version (nth bs 6)]
        (if-not (#{4 5} version)
          {:status :error :reason :unsupported-protocol-version :version version}
          (let [cflags (nth bs 7)
                ka (read-u16 bs 8)]
            (cond
              (not (ok? ka)) ka
              (odd? cflags) {:status :error :reason :malformed-connect-flags-reserved-bit-set}
              :else
              (let [will? (pos? (bit-and cflags 0x04))
                    un? (pos? (bit-and cflags 0x80))
                    pw? (pos? (bit-and cflags 0x40))
                    steps (cond-> [[:properties (fn [i] (read-props-value bs i version))]
                                   [:client-id (fn [i] (read-utf8-str-value bs i))]]
                            will? (conj [:will-properties (fn [i] (read-props-value bs i version))]
                                        [:will-topic (fn [i] (read-utf8-str-value bs i))]
                                        [:will-payload (fn [i] (read-utf8-bytes-value bs i))])
                            un? (conj [:username (fn [i] (read-utf8-str-value bs i))])
                            pw? (conj [:password (fn [i] (read-utf8-bytes-value bs i))]))
                    r (run-steps (:next-index ka) steps)]
                (if-not (ok? r)
                  r
                  {:status :ok
                   :packet
                   (cond-> {:version version
                            :client-id (get-in r [:values :client-id])
                            :clean-session? (pos? (bit-and cflags 0x02))
                            :keep-alive (:value ka)
                            :properties (get-in r [:values :properties])}
                     will? (assoc :will
                                  {:qos (bit-and (unsigned-bit-shift-right cflags 3) 0x03)
                                   :retain? (pos? (bit-and cflags 0x20))
                                   :topic (get-in r [:values :will-topic])
                                   :payload (get-in r [:values :will-payload])
                                   :properties (get-in r [:values :will-properties])})
                     un? (assoc :username (get-in r [:values :username]))
                     pw? (assoc :password (get-in r [:values :password])))})))))))))

(defn decode-connect
  "Bytes -> `{:status :ok :packet {...}}`. Takes a WHOLE CONNECT packet,
  fixed header included (the same shape `encode-connect` returns), unlike
  most of the other `decode-*` functions in this namespace, which take the
  post-fixed-header body — `decode-connect` is exercised directly a lot
  (it is the packet with by far the most fields) and being able to feed it
  exactly what `encode-connect` produced, unsliced, is worth the asymmetry."
  [bs]
  (let [bs (vec bs)
        h (fh/decode bs)]
    (if-not (ok? h)
      h
      (if (not= :connect (get-in h [:header :type]))
        {:status :error :reason :not-a-connect-packet}
        (let [start (:next-index h)
              end (+ start (get-in h [:header :remaining-length]))]
          (if (> end (count bs))
            {:status :incomplete}
            (decode-connect-body (subvec bs start end))))))))

;; ── CONNACK (MQTT-3.1.1 §3.2, MQTT-5.0 §3.2) ────────────────────────────────

(def connack-return-codes
  "MQTT-3.1.1 §3.2.2.3. MQTT 5.0 replaces this small fixed table with a much
  larger Reason Code table (§3.2.2.2) that this codec passes through as a
  raw byte for v5 rather than re-deriving — the 3.1.1 table is closed and
  small enough to name in full; the 5.0 one is not worth re-litigating here."
  {0 :accepted 1 :unacceptable-protocol-version 2 :identifier-rejected
   3 :server-unavailable 4 :bad-username-or-password 5 :not-authorized})

(def return-code->connack (into {} (map (fn [[k v]] [v k])) connack-return-codes))

(defn encode-connack
  "`{:version 4|5 :session-present? bool :return-code kw :reason-code u8
    :properties [...]}`. `:return-code` (a v3.1.1 keyword from
  `connack-return-codes`) and `:reason-code` (a raw v5 byte) are
  alternatives — pass whichever matches `:version`."
  [{:keys [version session-present? return-code reason-code properties]
    :or {version 4}}]
  (let [rc (if (= version 5)
             reason-code
             (return-code->connack return-code))]
    (if (nil? rc)
      {:status :error :reason :unknown-return-code}
      (frame :connack 0
             (into [(if session-present? 1 0) rc] (maybe-props version properties))))))

(defn decode-connack
  [bs]
  (let [bs (vec bs)]
    (if (< (count bs) 2)
      {:status :incomplete}
      (let [ackf (nth bs 0)]
        (if (> ackf 1)
          {:status :error :reason :malformed-connect-acknowledge-flags}
          (let [code (nth bs 1)
                pr (if (> (count bs) 2) (props/decode bs 2) {:status :ok :properties []})]
            (if-not (ok? pr)
              pr
              {:status :ok
               :packet {:session-present? (= 1 ackf)
                        :return-code (connack-return-codes code)
                        :reason-code code
                        :properties (:properties pr)}})))))))

;; ── PUBLISH (MQTT-3.1.1 §3.3, MQTT-5.0 §3.3) ────────────────────────────────

(defn encode-publish
  "`{:version 4|5 :dup? bool :qos 0|1|2 :retain? bool :topic str
    :packet-id u16 :properties [...] :payload bytes}`. `:packet-id` is
  required iff `:qos` is non-zero (MQTT-3.1.1 §2.3.1) — supplying it at
  QoS 0 or omitting it above QoS 0 is a caller error this function refuses
  rather than silently drops or invents an id for."
  [{:keys [version dup? qos retain? topic packet-id properties payload]
    :or {version 4 qos 0 payload []}}]
  (cond
    (not (#{0 1 2} qos)) {:status :error :reason :invalid-qos :qos qos}
    (and (pos? qos) (nil? packet-id))
    {:status :error :reason :packet-identifier-required-for-qos-above-zero}
    (and (zero? qos) (some? packet-id))
    {:status :error :reason :packet-identifier-forbidden-at-qos-zero}
    :else
    (let [flags (bit-or (if dup? 0x08 0) (bit-shift-left qos 1) (if retain? 0x01 0))
          var-header (-> []
                        (into (:bytes (utf8/encode (utf8/ascii->bytes topic))))
                        (into (if (pos? qos) (be16 packet-id) []))
                        (into (maybe-props version properties)))]
      (frame :publish flags (into var-header payload)))))

(defn decode-publish
  "`total-length` (the whole packet, fixed header included) is needed to
  find where the payload — which has no length prefix of its own — ends:
  it runs from the end of the variable header to the end of the frame."
  [bs version]
  (let [bs (vec bs)
        h (fh/decode bs)]
    (if-not (ok? h) h
      (let [{:keys [header next-index]} h
            end (+ next-index (:remaining-length header))]
        (if (> end (count bs))
          {:status :incomplete}
          (let [flags (:flags header)
                qos (bit-and (unsigned-bit-shift-right flags 1) 0x03)]
            (if (= qos 3)
              {:status :error :reason :invalid-qos}
              (let [t (read-utf8 bs next-index)]
                (if-not (ok? t) t
                  (let [i (:next-index t)
                        pid (if (pos? qos) (read-u16 bs i) {:status :ok :value nil :next-index i})]
                    (if-not (ok? pid) pid
                      (let [i (:next-index pid)
                            pr (if (= version 5) (props/decode bs i) {:status :ok :properties [] :next-index i})]
                        (if-not (ok? pr) pr
                          {:status :ok
                           :packet {:dup? (pos? (bit-and flags 0x08))
                                    :qos qos
                                    :retain? (pos? (bit-and flags 0x01))
                                    :topic (:value t)
                                    :packet-id (:value pid)
                                    :properties (:properties pr)
                                    :payload (subvec bs (:next-index pr) end)}
                           :next-index end})))))))))))))

;; ── PUBACK / PUBREC / PUBREL / PUBCOMP (MQTT-3.1.1 §3.4/5/6/7,
;;    MQTT-5.0 §3.4/5/6/7) ────────────────────────────────────────────────────

(def ack-type-flags
  {:puback 0 :pubrec 0 :pubrel 2 :pubcomp 0})

(defn encode-ack
  "The four packet-identifier-only acknowledgements share one shape:
  `{:type :puback|:pubrec|:pubrel|:pubcomp :version 4|5 :packet-id u16
    :reason-code u8 :properties [...]}`.

  MQTT-5.0 §3.4.2.1: a Reason Code of Success (0x00) with no properties may
  be omitted entirely, leaving Remaining Length at exactly 2 — the same
  shape v3.1.1 always uses. This function takes that shortcut automatically
  whenever `:reason-code` is 0 or absent and `:properties` is empty, which
  is what makes v5's optional short form actually get exercised rather than
  a caller having to know to ask for it."
  [{:keys [type version packet-id reason-code properties] :or {version 4 reason-code 0}}]
  (let [short? (or (= version 4) (and (zero? reason-code) (empty? properties)))
        body (if short?
               (be16 packet-id)
               (into (be16 packet-id) (into [reason-code] (:bytes (props/encode (or properties []))))))]
    (frame type (ack-type-flags type) body)))

(defn decode-ack
  [type bs version]
  (let [bs (vec bs)]
    (cond
      (< (count bs) 2) {:status :incomplete}
      (= (count bs) 2)
      {:status :ok :packet {:packet-id (+ (* 256 (nth bs 0)) (nth bs 1))
                             :reason-code 0 :properties []}}
      (not= version 5) {:status :error :reason :malformed-remaining-length}
      (= (count bs) 3)
      {:status :ok :packet {:packet-id (+ (* 256 (nth bs 0)) (nth bs 1))
                             :reason-code (nth bs 2) :properties []}}
      :else
      (let [pid (+ (* 256 (nth bs 0)) (nth bs 1))
            rc (nth bs 2)
            pr (props/decode bs 3)]
        (if-not (ok? pr) pr
          {:status :ok :packet {:packet-id pid :reason-code rc :properties (:properties pr)}})))))

;; ── SUBSCRIBE / SUBACK (MQTT-3.1.1 §3.8/9, MQTT-5.0 §3.8/9) ─────────────────

(defn encode-subscribe
  "`{:version 4|5 :packet-id u16 :properties [...]
    :topics [{:filter str :qos 0|1|2 :no-local? bool :retain-as-published? bool
              :retain-handling 0|1|2}]}`. The v5-only sub-options
  (no-local/retain-as-published/retain-handling, MQTT-5.0 §3.8.3.1) are
  ignored under v3.1.1, where the Subscription Options byte is Requested
  QoS alone with the upper six bits reserved at 0 (MQTT-3.1.1 §3.8.3)."
  [{:keys [version packet-id properties topics] :or {version 4}}]
  (if (empty? topics)
    {:status :error :reason :no-topics}
    (let [opt (fn [{:keys [qos no-local? retain-as-published? retain-handling]}]
                (if (= version 5)
                  (bit-or (bit-and (or qos 0) 0x03)
                          (if no-local? 0x04 0)
                          (if retain-as-published? 0x08 0)
                          (bit-shift-left (or retain-handling 0) 4))
                  (bit-and (or qos 0) 0x03)))
          payload (mapcat (fn [t] (into (:bytes (utf8/encode (utf8/ascii->bytes (:filter t))))
                                        [(opt t)]))
                          topics)]
      (frame :subscribe 2
             (into (into (be16 packet-id) (maybe-props version properties)) payload)))))

(defn decode-subscribe
  [bs version]
  (let [bs (vec bs)
        pid (read-u16 bs 0)]
    (if-not (ok? pid) pid
      (let [pr (if (= version 5) (props/decode bs (:next-index pid))
                 {:status :ok :properties [] :next-index (:next-index pid)})]
        (if-not (ok? pr) pr
          (loop [i (:next-index pr) topics []]
            (if (>= i (count bs))
              {:status :ok :packet {:packet-id (:value pid) :properties (:properties pr) :topics topics}}
              (let [f (read-utf8 bs i)]
                (if-not (ok? f) f
                  (let [o (read-u8 bs (:next-index f))]
                    (if-not (ok? o) o
                      (recur (:next-index o)
                             (conj topics
                                   {:filter (:value f)
                                    :qos (bit-and (:value o) 0x03)
                                    :no-local? (pos? (bit-and (:value o) 0x04))
                                    :retain-as-published? (pos? (bit-and (:value o) 0x08))
                                    :retain-handling (bit-and (unsigned-bit-shift-right (:value o) 4) 0x03)})))))))))))))

(def suback-return-codes
  "MQTT-3.1.1 §3.9.3. MQTT 5.0's Reason Code superset (§3.9.3) is passed
  through as the raw byte; a granted QoS and a v5 success reason code
  happen to share values 0/1/2 by design, so `:granted-qos` reads correctly
  either way, but `0x80` (Failure in 3.1.1) is one of many distinct failure
  reasons in 5.0, so it is not translated to a v5 name here."
  {0 :granted-qos-0 1 :granted-qos-1 2 :granted-qos-2 0x80 :failure})

(defn encode-suback
  [{:keys [version packet-id properties codes] :or {version 4}}]
  (frame :suback 0
         (into (into (be16 packet-id) (maybe-props version properties)) codes)))

(defn decode-suback
  [bs version]
  (let [bs (vec bs)
        pid (read-u16 bs 0)]
    (if-not (ok? pid) pid
      (let [pr (if (= version 5) (props/decode bs (:next-index pid))
                 {:status :ok :properties [] :next-index (:next-index pid)})]
        (if-not (ok? pr) pr
          {:status :ok
           :packet {:packet-id (:value pid) :properties (:properties pr)
                    :codes (vec (subvec bs (:next-index pr) (count bs)))}})))))

;; ── UNSUBSCRIBE / UNSUBACK (MQTT-3.1.1 §3.10/11, MQTT-5.0 §3.10/11) ─────────

(defn encode-unsubscribe
  [{:keys [version packet-id properties filters] :or {version 4}}]
  (if (empty? filters)
    {:status :error :reason :no-topic-filters}
    (frame :unsubscribe 2
           (into (into (be16 packet-id) (maybe-props version properties))
                 (mapcat (fn [f] (:bytes (utf8/encode (utf8/ascii->bytes f)))) filters)))))

(defn decode-unsubscribe
  [bs version]
  (let [bs (vec bs)
        pid (read-u16 bs 0)]
    (if-not (ok? pid) pid
      (let [pr (if (= version 5) (props/decode bs (:next-index pid))
                 {:status :ok :properties [] :next-index (:next-index pid)})]
        (if-not (ok? pr) pr
          (loop [i (:next-index pr) filters []]
            (if (>= i (count bs))
              {:status :ok :packet {:packet-id (:value pid) :properties (:properties pr) :filters filters}}
              (let [f (read-utf8 bs i)]
                (if-not (ok? f) f
                  (recur (:next-index f) (conj filters (:value f))))))))))))

(defn encode-unsuback
  "v3.1.1 (MQTT-3.1.1 §3.11): Packet Identifier only, no payload — pass no
  `:codes` (or an empty vector). v5 (MQTT-5.0 §3.11): adds Properties and,
  per-filter, a Reason Code payload."
  [{:keys [version packet-id properties codes] :or {version 4}}]
  (frame :unsuback 0
         (into (into (be16 packet-id) (maybe-props version properties)) (or codes []))))

(defn decode-unsuback
  [bs version]
  (let [bs (vec bs)
        pid (read-u16 bs 0)]
    (if-not (ok? pid) pid
      (if (= version 4)
        (if (not= (count bs) 2)
          {:status :error :reason :malformed-remaining-length}
          {:status :ok :packet {:packet-id (:value pid) :properties [] :codes []}})
        (let [pr (props/decode bs (:next-index pid))]
          (if-not (ok? pr) pr
            {:status :ok
             :packet {:packet-id (:value pid) :properties (:properties pr)
                      :codes (vec (subvec bs (:next-index pr) (count bs)))}}))))))

;; ── PINGREQ / PINGRESP / DISCONNECT / AUTH ──────────────────────────────────

(defn encode-pingreq [] (frame :pingreq 0 []))
(defn encode-pingresp [] (frame :pingresp 0 []))

(defn decode-empty
  "PINGREQ and PINGRESP (MQTT-3.1.1 §3.12/§3.13) carry nothing at all — a
  non-empty body is malformed, not a forward-compatible extension point."
  [bs]
  (if (empty? bs) {:status :ok :packet {}} {:status :error :reason :non-empty-body}))

(defn encode-disconnect
  "MQTT-3.1.1 §3.14: always the bare fixed header, no variable header, no
  payload — `:reason-code`/`:properties` are accepted but ignored under
  `:version 4`. MQTT-5.0 §3.14.2.1 allows the same zero-length shortcut
  when the reason is Normal Disconnection (0x00) and there are no
  properties, mirroring the PUBACK-family short form above."
  [{:keys [version reason-code properties] :or {version 4 reason-code 0}}]
  (if (or (= version 4) (and (zero? reason-code) (empty? properties)))
    (frame :disconnect 0 [])
    (frame :disconnect 0 (into [reason-code] (:bytes (props/encode properties))))))

(defn decode-disconnect
  [bs version]
  (let [bs (vec bs)]
    (cond
      (empty? bs) {:status :ok :packet {:reason-code 0 :properties []}}
      (not= version 5) {:status :error :reason :malformed-remaining-length}
      (= (count bs) 1) {:status :ok :packet {:reason-code (nth bs 0) :properties []}}
      :else
      (let [pr (props/decode bs 1)]
        (if-not (ok? pr) pr
          {:status :ok :packet {:reason-code (nth bs 0) :properties (:properties pr)}})))))

;; ── whole-packet dispatch ────────────────────────────────────────────────────

(defn decode
  "Bytes -> `{:status :ok :type kw :packet {...} :next-index j}` for exactly
  one packet, dispatching on the fixed header's Packet Type. `version` (4 or
  5) must be supplied by the caller — nothing in the fixed header says which
  protocol version a packet belongs to; that is only ever known from the
  CONNECT packet at the start of the connection, which is why this function
  cannot infer it and does not try to."
  [bs version]
  (let [bs (vec bs)
        h (fh/decode bs)]
    (if-not (ok? h) h
      (let [{:keys [header next-index]} h
            end (+ next-index (:remaining-length header))]
        (if (> end (count bs))
          {:status :incomplete}
          (let [body (subvec bs next-index end)
                r (case (:type header)
                    :connect (decode-connect (subvec bs 0 end))
                    :connack (decode-connack body)
                    :publish (decode-publish (subvec bs 0 end) version)
                    (:puback :pubrec :pubrel :pubcomp) (decode-ack (:type header) body version)
                    :subscribe (decode-subscribe body version)
                    :suback (decode-suback body version)
                    :unsubscribe (decode-unsubscribe body version)
                    :unsuback (decode-unsuback body version)
                    (:pingreq :pingresp) (decode-empty body)
                    :disconnect (decode-disconnect body version))]
            (if (ok? r)
              (assoc r :type (:type header) :next-index end)
              r)))))))
