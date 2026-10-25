(ns coap.options
  "CoAP Option numbers (RFC 7252 §12.2 Table 4) and the nibble/extended-byte
  arithmetic (RFC 7252 §3.1) that both an option's Delta and its Length use
  — the same little encoding twice per option, which is why it lives here
  as one function rather than being written out inline in `coap.message`
  twice and risking the two copies disagreeing.

  A CoAP option number is never sent on the wire directly. Each option
  carries a DELTA from the previous option's number (so options MUST
  appear in ascending numeric order, and two options with the same number
  are simply written back to back with a delta of 0), and both that delta
  and the option's value length are encoded with the identical rule:

    0..12          -> the nibble itself, no extension bytes
    13..268        -> nibble 13, one extension byte  = n - 13
    269..65804     -> nibble 14, two extension bytes  = n - 269 (big-endian)
    (nibble 15 is reserved — see `coap.message` for the payload-marker
     interaction, which is the actual reason it's reserved rather than
     simply meaning 'even bigger')

  This is arithmetically the same shape as an HPACK/QPACK Huffman-adjacent
  prefix-extension integer and structurally unrelated to MQTT's Variable
  Byte Integer in this workspace's `org-mqtt` — worth naming because both
  are 'CoAP/MQTT have a compact variable-length integer' at a glance, and
  conflating the two encodings is an easy way to build a decoder that
  passes its own tests and nothing else's.")

(def option-numbers
  "RFC 7252 §12.2 Table 4, the core option set (block-wise transfer's
  Block1/Block2, options 27 and 23, are RFC 7959 and live in `coap.block`,
  not here — they use this same nibble arithmetic for their OPTION framing,
  but their VALUE bytes have their own sub-structure)."
  {1 :if-match 3 :uri-host 4 :etag 5 :if-none-match 7 :uri-port
   8 :location-path 11 :uri-path 12 :content-format 14 :max-age
   15 :uri-query 17 :accept 20 :location-query 35 :proxy-uri
   39 :proxy-scheme 60 :size1})

(def name->option-number (into {} (map (fn [[k v]] [v k])) option-numbers))

(defn nibble-encode
  "`n` (a Delta or a Length, 0..65804) -> `{:nibble n' :ext [bytes]}`."
  [n]
  (cond
    (< n 0) {:status :error :reason :negative-value}
    (< n 13) {:status :ok :nibble n :ext []}
    (< n 269) {:status :ok :nibble 13 :ext [(- n 13)]}
    (<= n 65804) (let [v (- n 269)]
                   {:status :ok :nibble 14
                    :ext [(bit-and (unsigned-bit-shift-right v 8) 0xFF) (bit-and v 0xFF)]})
    :else {:status :error :reason :value-too-large :value n}))

(defn nibble-decode
  "Reads the extension bytes (if any) that follow a nibble value `nib`
  (0..14 — the caller has already rejected 15, since what 15 means depends
  on context: reserved in most positions, the payload marker in exactly
  one). `bs`/`i` are the byte sequence and the index just past the nibble
  byte itself."
  [nib bs i]
  (let [bs (vec bs) n (count bs)]
    (cond
      (< nib 13) {:status :ok :value nib :next-index i}
      (= nib 13) (if (>= i n) {:status :incomplete}
                    {:status :ok :value (+ 13 (nth bs i)) :next-index (inc i)})
      (= nib 14) (if (> (+ i 2) n) {:status :incomplete}
                    {:status :ok
                     :value (+ 269 (+ (* 256 (nth bs i)) (nth bs (inc i))))
                     :next-index (+ i 2)}))))
