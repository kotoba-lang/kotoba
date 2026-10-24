(ns netconf.framing
  "RFC 6242 §4.2 chunked framing — the CURRENT NETCONF-over-SSH transport
  framing, negotiated once both peers' <hello> messages have advertised
  the base:1.1 capability (RFC 6242 §4.1). This is deliberately NOT the
  deprecated §4.3 end-of-message `]]>]]>` marker framing used only when a
  peer advertises :base:1.0 alone — see the README for why that framing
  was retired (it can legally appear inside well-formed XML: attributes,
  comments, processing instructions).

  RFC 6242 §4.2 ABNF:

    Chunked-Message = 1*chunk
                       end-of-chunks

    chunk           = LF HASH chunk-size LF
                       chunk-data
    chunk-size      = 1*DIGIT1 0*DIGIT
    chunk-data      = 1*OCTET

    end-of-chunks   = LF HASH HASH LF

    DIGIT1          = %x31-39
    DIGIT           = %x30-39
    HASH            = %x23
    LF              = %x0A
    OCTET           = %x00-FF

  \"The chunk-size field is a string of decimal digits indicating the
  number of octets in chunk-data. Leading zeros are prohibited, and the
  maximum allowed chunk-size value is 4294967295.\" (§4.2)

  This is purely byte-stream segmentation and knows NOTHING about XML
  structure — a sender may split a message at any byte boundary,
  including mid-tag, mid-attribute, or mid-entity, and a decoder MUST
  reassemble it correctly regardless (§4.2, and the worked example
  below, which splits `message-id=\"102\"` and the namespace declaration
  across chunk boundaries that have nothing to do with XML tokens).
  `feed` reflects that directly: chunk-data bytes are counted, never
  scanned for `\\n`/`#` — a chunk's declared length is authoritative even
  if its content happens to contain bytes that look like a chunk header.

  Bytes are Sequential collections of ints in 0..255, in and out (same
  convention as kotoba-lang/org-modbus).")

(def ^:const LF 0x0A)
(def ^:const HASH 0x23)

(def max-chunk-size
  "RFC 6242 §4.2: \"the maximum allowed chunk-size value is 4294967295.\""
  4294967295)

(defn- digit1? [b] (and (>= b 0x31) (<= b 0x39))) ; ASCII '1'..'9'
(defn- digit? [b] (and (>= b 0x30) (<= b 0x39)))  ; ASCII '0'..'9'

;; ------------------------------------------------------------- encode

(defn- ascii-digits
  "Positive int n -> its ASCII decimal digit bytes, most-significant
  first. Never produces a leading zero because n is always >= 1 here
  (chunk-size is 1*DIGIT1 0*DIGIT: the first digit is 1-9)."
  [n]
  (loop [n n acc '()]
    (if (zero? n)
      acc
      (recur (quot n 10) (cons (+ 0x30 (rem n 10)) acc)))))

(defn- one-chunk
  "One `chunk = LF HASH chunk-size LF chunk-data` (§4.2)."
  [data]
  (let [n (count data)]
    (when (or (< n 1) (> n max-chunk-size))
      (throw (ex-info "chunk-data must be 1..4294967295 octets (RFC 6242 §4.2)"
                       {:netconf/error :chunked-framing-chunk-size-out-of-range
                        :size n})))
    (vec (concat [LF HASH] (ascii-digits n) [LF] data))))

(def ^:private end-of-chunks-bytes
  "`end-of-chunks = LF HASH HASH LF` (§4.2)."
  [LF HASH HASH LF])

(defn encode-chunks
  "Encodes `data` (a byte-seq, Sequential of ints 0..255) as an RFC 6242
  §4.2 chunked-message. `policy` controls how `data` is split into
  chunks — chunking is purely a sender's choice, the ABNF places no
  constraint on it beyond each chunk-size being 1..4294967295:

    nil / :single         one chunk holding all of `data` (default)
    [:fixed n]              successive n-byte chunks, last one shorter
                            if `data` doesn't divide evenly
    [:sizes [s1 s2 ...]]    caller-chosen chunk sizes; MUST sum to
                            (count data), each MUST be in 1..4294967295

  Returns a byte-seq (vector of ints). This is the encode side, called
  with caller-controlled arguments (house style): throws ex-info with
  :netconf/error one of :chunked-framing-empty-payload,
  :chunked-framing-chunk-size-out-of-range,
  :chunked-framing-sizes-mismatch, :chunked-framing-unknown-policy."
  [data & [policy]]
  (let [data (vec data)
        n (count data)]
    (when (zero? n)
      (throw (ex-info "a chunked-message needs >= 1 chunk, and chunk-data is 1*OCTET (RFC 6242 §4.2) — nothing to frame"
                       {:netconf/error :chunked-framing-empty-payload})))
    (let [chunks
          (cond
            (or (nil? policy) (= :single policy))
            [data]

            (and (vector? policy) (= :fixed (first policy)))
            (let [size (second policy)]
              (when-not (and (integer? size) (pos? size))
                (throw (ex-info "fixed chunk size must be a positive integer"
                                 {:netconf/error :chunked-framing-chunk-size-out-of-range
                                  :size size})))
              (mapv vec (partition-all size data)))

            (and (vector? policy) (= :sizes (first policy)))
            (let [sizes (second policy)]
              (when-not (= n (reduce + 0 sizes))
                (throw (ex-info "explicit chunk sizes must sum to (count data)"
                                 {:netconf/error :chunked-framing-sizes-mismatch
                                  :expected n :got (reduce + 0 sizes)})))
              (loop [d data ss sizes acc []]
                (if (empty? ss)
                  acc
                  (let [s (first ss)]
                    (recur (subvec d s) (rest ss) (conj acc (subvec d 0 s)))))))

            :else
            (throw (ex-info "unknown chunk-size policy"
                             {:netconf/error :chunked-framing-unknown-policy :policy policy})))]
      (vec (concat (mapcat one-chunk chunks) end-of-chunks-bytes)))))

;; ------------------------------------------------------------- decode
;;
;; An explicit byte-at-a-time state machine so that `feed` can be called
;; with the wire bytes split at literally any point — including inside
;; the LF/HASH framing bytes themselves, inside the chunk-size digits,
;; inside chunk-data, or inside the end-of-chunks marker — and still
;; decode correctly, because state (which ABNF token we're mid-way
;; through, and how many chunk-data octets remain) is carried across
;; `feed` calls rather than assumed to arrive whole.

(def ^:private initial-state
  {:status :reading    ; :reading | :done | :error
   :sub :expect-lf1     ; sub-state within :reading, see `feed`
   :size 0              ; chunk-size accumulated so far (this chunk)
   :remaining 0         ; chunk-data octets still owed (this chunk)
   :payload []          ; reassembled message bytes so far
   :leftover []         ; bytes fed after :done was reached, unconsumed
   :reason nil
   :info nil})

(defn decoder
  "A fresh incremental RFC 6242 §4.2 chunk decoder. Feed it wire bytes
  with `feed`, in as many pieces as you like, split at any byte
  boundary — this is the piece a real streaming SSH transport needs,
  since bytes arrive in whatever pieces the OS/library hands over."
  [] initial-state)

(defn- fail [state reason info]
  (assoc state :status :error :reason reason :info info :leftover []))

(defn feed
  "Feeds `bytes` (a byte-seq) into decoder state `d`. Returns the
  updated state. Never throws — this is the wire-facing decode path.

  (:status state) is:
    :reading  more bytes are needed; keep calling `feed`
    :done     a complete chunked-message was decoded. (:payload state)
              is the reassembled bytes. (:leftover state) is any bytes
              fed past the end-of-chunks marker in this same call — the
              start of the NEXT chunked-message on the same stream, if
              the caller handed them over together. Feed a *fresh*
              `(decoder)` those leftover bytes to decode the next one;
              feeding more bytes to an already-:done state is a no-op
              (returned unchanged) rather than an error, since callers
              are expected to start over per message.
    :error    malformed framing. (:reason state) names which ABNF rule
              (RFC 6242 §4.2) was violated:
                :chunked-framing-malformed-header      missing LF/HASH
                :chunked-framing-malformed-size         bad chunk-size
                                                         syntax (incl. a
                                                         leading zero)
                :chunked-framing-size-too-large         > 4294967295
                :chunked-framing-malformed-end-marker   bad `##` LF"
  [d bytes]
  (if (not= :reading (:status d))
    d
    (let [bs (vec bytes) n (count bs)]
      (loop [d d i 0]
        (if (>= i n)
          d
          (let [b (nth bs i)]
            (case (:sub d)
              :expect-lf1
              (if (= b LF)
                (recur (assoc d :sub :expect-hash) (inc i))
                (fail d :chunked-framing-malformed-header {:expected LF :got b :at i}))

              :expect-hash
              (if (= b HASH)
                (recur (assoc d :sub :expect-size-or-hash) (inc i))
                (fail d :chunked-framing-malformed-header {:expected HASH :got b :at i}))

              :expect-size-or-hash
              (cond
                (= b HASH) (recur (assoc d :sub :expect-lf-end) (inc i))
                (digit1? b) (recur (assoc d :sub :reading-size :size (- b 0x30)) (inc i))
                :else (fail d :chunked-framing-malformed-size
                            {:reason "chunk-size must start with 1-9 (leading zero prohibited) or be ## (end-of-chunks)"
                             :got b :at i}))

              :reading-size
              (cond
                (= b LF)
                (recur (assoc d :sub :reading-data :remaining (:size d)) (inc i))
                (digit? b)
                (let [size' (+ (* 10 (:size d)) (- b 0x30))]
                  (if (> size' max-chunk-size)
                    (fail d :chunked-framing-size-too-large {:size size' :at i})
                    (recur (assoc d :size size') (inc i))))
                :else
                (fail d :chunked-framing-malformed-size {:reason "non-digit in chunk-size" :got b :at i}))

              :reading-data
              (let [remaining (:remaining d)
                    take-n (min remaining (- n i))
                    taken (subvec bs i (+ i take-n))
                    remaining' (- remaining take-n)]
                (if (pos? remaining')
                  (recur (-> d (update :payload into taken) (assoc :remaining remaining'))
                         (+ i take-n))
                  (recur (-> d (update :payload into taken) (assoc :sub :expect-lf1 :remaining 0 :size 0))
                         (+ i take-n))))

              :expect-lf-end
              (if (= b LF)
                (assoc d :status :done :sub :done :leftover (subvec bs (inc i) n))
                (fail d :chunked-framing-malformed-end-marker {:expected LF :got b :at i})))))))))

(defn decode-chunks
  "One-shot decode: `bytes` must hold EXACTLY one complete chunked-message
  and nothing else. Never throws. Returns [:ok payload-bytes] or
  [:error kw] with kw one of the `feed` reasons above, plus:
    :chunked-framing-truncated         the message never reached the
                                        end-of-chunks marker
    :chunked-framing-trailing-garbage  bytes remained after it did

  For a real stream, where a partial message may need more bytes later
  or a second message may already be present, use `decoder`/`feed`
  directly instead of this convenience wrapper."
  [bytes]
  (let [d (feed (decoder) bytes)]
    (cond
      (= :error (:status d)) [:error (:reason d)]
      (not= :done (:status d)) [:error :chunked-framing-truncated]
      (seq (:leftover d)) [:error :chunked-framing-trailing-garbage]
      :else [:ok (:payload d)])))
