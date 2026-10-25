(ns coap.message
  "The CoAP message layer — RFC 7252 §3 (Binary Message Format Summary,
  Figure 7) and §3.1 (Option Format, Figure 8).

  ```
   0                   1                   2                   3
   0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |Ver| T |  TKL  |      Code     |          Message ID          |
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |   Token (if any, TKL bytes) ...
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |   Options (if any) ...
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |1 1 1 1 1 1 1 1|    Payload (if any) ...
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  ```

  Everything CoAP does above this — retransmission of Confirmable
  messages, deduplication by Message ID, matching a Piggybacked or
  Separate response to its request by Token, the request/response
  semantics of each method and response code — needs a clock, a socket,
  and retry state, none of which this namespace has. What it has is the
  4-byte header plus Token plus Options plus Payload turned into bytes and
  back, which is the part that is the same no matter what runs the
  transport underneath it (UDP per RFC 7252, or DTLS, or a CoAP-over-TCP
  variant carrying the same message shape)."
  (:require [coap.code :as code]
            [coap.options :as opt]))

(def types "RFC 7252 §3 Figure 7." {0 :con 1 :non 2 :ack 3 :rst})
(def type->code (into {} (map (fn [[k v]] [v k])) types))

(defn ascii->bytes
  "ASCII string -> byte vector. Not a general Unicode encoder — for the
  common case (Uri-Path segments, Uri-Query, simple text payloads) and for
  building test vectors without pulling in a UTF-8 codec.

  `(mapv int s)` looks equivalent and silently is not under ClojureScript,
  where a string's `seq` yields one-character strings and `int` of one is
  0, not a code point — the same 'vector of zeros' trap this workspace's
  `org-modbus` and `org-mqtt` both document hitting. The reader-conditional
  below is what keeps the wrong branch from ever compiling into the cljs
  build."
  [s]
  #?(:clj (mapv int s)
     :cljs (mapv #(.charCodeAt % 0) s)))

(defn bytes->ascii [bs] (apply str (map char bs)))

;; ── header ───────────────────────────────────────────────────────────────

(defn- be16 [n] [(bit-and (unsigned-bit-shift-right n 8) 0xFF) (bit-and n 0xFF)])
(defn- ok? [m] (= :ok (:status m)))

;; ── options ──────────────────────────────────────────────────────────────

(defn- encode-option
  "One option, given the running delta from the previous option's number.
  `[option-number-or-name value-bytes]` -> bytes, first-byte nibble pair
  plus extension bytes plus the value itself (RFC 7252 §3.1 Figure 8)."
  [prev-number [num-or-name value]]
  (let [num (if (keyword? num-or-name) (opt/name->option-number num-or-name) num-or-name)]
    (if (nil? num)
      {:status :error :reason :unknown-option-name :name num-or-name}
      (let [delta (- num prev-number)]
        (if (neg? delta)
          {:status :error :reason :options-out-of-order :option num}
          (let [dn (opt/nibble-encode delta)
                ln (opt/nibble-encode (count value))]
            (cond
              (not (ok? dn)) dn
              (not (ok? ln)) ln
              :else
              {:status :ok
               :number num
               :bytes (into [(bit-or (bit-shift-left (:nibble dn) 4) (:nibble ln))]
                            (into (:ext dn) (into (:ext ln) value)))})))))))

(defn encode-options
  "`[[option-number-or-name value-bytes] ...]` -> the whole encoded Options
  section. The list is first stably sorted by option number — RFC 7252
  §3.1 requires ascending order on the wire but places no requirement on
  the caller's own list order, and sorting here (rather than refusing an
  unsorted list) is what lets a caller build `{:content-format ... :uri-path
  [...]}`-shaped requests without hand-computing wire order themselves."
  [options]
  (let [resolved (map (fn [[n v]] [(if (keyword? n) (opt/name->option-number n) n) n v]) options)]
    (if (some (comp nil? first) resolved)
      {:status :error :reason :unknown-option-name}
      (loop [prev 0 opts (sort-by first resolved) out []]
        (if (empty? opts)
          {:status :ok :bytes out}
          (let [[num _ v] (first opts)
                r (encode-option prev [num v])]
            (if-not (ok? r)
              r
              (recur num (rest opts) (into out (:bytes r))))))))))

(defn decode-options
  "Reads options starting at index `i` until the payload marker (`0xFF`)
  or the end of `bs`. Returns `{:status :ok :options [[number bytes] ...]
  :next-index j}`, where `j` is either `(count bs)` or the index just past
  the `0xFF` marker (i.e. where the payload begins)."
  [bs i]
  (let [bs (vec bs) n (count bs)]
    (loop [i i prev 0 out []]
      (cond
        (>= i n) {:status :ok :options out :next-index i}
        (= 0xFF (nth bs i))
        (if (= (inc i) n)
          {:status :error :reason :payload-marker-with-no-payload}
          {:status :ok :options out :next-index (inc i)})
        :else
        (let [b (nth bs i)
              dnib (unsigned-bit-shift-right b 4)
              lnib (bit-and b 0x0F)]
          (if (or (= dnib 15) (= lnib 15))
            {:status :error :reason :reserved-option-nibble}
            (let [dr (opt/nibble-decode dnib bs (inc i))]
              (if-not (ok? dr) dr
                (let [lr (opt/nibble-decode lnib bs (:next-index dr))]
                  (if-not (ok? lr) lr
                    (let [vstart (:next-index lr) vend (+ vstart (:value lr))
                          num (+ prev (:value dr))]
                      (if (> vend n)
                        {:status :incomplete}
                        (recur vend num (conj out [num (subvec bs vstart vend)]))))))))))))))

;; ── whole message ────────────────────────────────────────────────────────

(defn encode
  "`{:type :con|:non|:ack|:rst :code kw-or-[class detail] :message-id u16
    :token bytes :options [[num-or-name value] ...] :payload bytes}`
  -> `{:status :ok :bytes [...]}`.

  `:token` is at most 8 bytes (RFC 7252 §3: lengths 9-15 are reserved and
  MUST NOT be sent). `:code` may be a keyword from `coap.code/code-names`
  or a raw `[class detail]` pair, for codes this table doesn't happen to
  name."
  [{:keys [type code message-id token options payload] :or {token [] options [] payload []}}]
  (let [tc (type->code type)
        cb (if (keyword? code) (:byte (code/encode code)) (code/->byte code))]
    (cond
      (nil? tc) {:status :error :reason :unknown-type :type type}
      (nil? cb) {:status :error :reason :unknown-code :code code}
      (> (count token) 8) {:status :error :reason :token-too-long :length (count token)}
      (not (<= 0 message-id 0xFFFF)) {:status :error :reason :message-id-out-of-range}
      :else
      (let [opts (encode-options options)]
        (if-not (ok? opts)
          opts
          {:status :ok
           :bytes (into (into [(bit-or (bit-shift-left 1 6) (bit-shift-left tc 4) (count token))
                               cb]
                              (be16 message-id))
                        (into token (into (:bytes opts) (when (seq payload) (into [0xFF] payload)))))})))))

(defn decode
  "Bytes -> `{:status :ok :message {...}}`. RFC 7252 §3 constraints
  enforced here rather than left to a caller who might not know to check
  them: Version must be 1 (`:unsupported-version` — other values are
  reserved for a future CoAP revision this codec doesn't speak), Token
  Length 9-15 is a message format error (`:reserved-token-length`), and a
  Code of 0.00 (Empty) MUST carry a zero-length Token and no
  options/payload (`:non-empty-empty-message`) — an Empty message exists
  purely to carry a Message ID for the ACK/RST machinery, and one that
  also tried to carry a Token or Options would be ambiguous about whether
  it's Empty or a genuinely code-0 request."
  [bs]
  (let [bs (vec bs)]
    (if (< (count bs) 4)
      {:status :incomplete}
      (let [b0 (nth bs 0)
            ver (unsigned-bit-shift-right b0 6)
            tc (bit-and (unsigned-bit-shift-right b0 4) 0x03)
            tkl (bit-and b0 0x0F)
            cb (nth bs 1)
            mid (+ (* 256 (nth bs 2)) (nth bs 3))]
        (cond
          (not= ver 1) {:status :error :reason :unsupported-version :version ver}
          (> tkl 8) {:status :error :reason :reserved-token-length :length tkl}
          (> (+ 4 tkl) (count bs)) {:status :incomplete}
          :else
          (let [token (subvec bs 4 (+ 4 tkl))
                code-r (code/decode cb)]
            (if (and (= cb 0) (pos? tkl))
              {:status :error :reason :non-empty-empty-message}
              (let [or- (decode-options bs (+ 4 tkl))]
                (if-not (ok? or-) or-
                  (let [payload (subvec bs (:next-index or-) (count bs))]
                    (if (and (= cb 0) (or (seq (:options or-)) (seq payload)))
                      {:status :error :reason :non-empty-empty-message}
                      {:status :ok
                       :message {:type (types tc)
                                 :code (:name code-r)
                                 :class (:class code-r)
                                 :detail (:detail code-r)
                                 :message-id mid
                                 :token token
                                 :options (:options or-)
                                 :payload payload}})))))))))))
