(ns mqtt.utf8
  "MQTT UTF-8 Encoded Strings and Binary Data (MQTT-3.1.1 §1.5.3,
  MQTT-5.0 §1.5.4 / §1.5.6).

  Both are a two-byte big-endian length prefix followed by that many raw
  bytes — a string is additionally required to be well-formed UTF-8 with no
  embedded null (U+0000) and, per MQTT-5.0 §1.5.4, no unpaired UTF-16
  surrogate (U+D800..U+DFFF) or U+FEFF encoded anywhere but the first
  character. This module works on bytes, not host-language strings, so
  ASCII-only helpers are provided for building test vectors without pulling
  in a UTF-8 codec; encoding an already-UTF-8 byte sequence is the codec's
  job, decoding one is not, and this module does not decide what a valid
  Unicode string is on your behalf beyond the null-byte and length checks
  the spec ties to the wire format itself.

  The two-byte length field caps a single string or binary field at 65535
  bytes (MQTT-3.1.1 §1.5.3) — the same ceiling the CONNECT/PUBLISH payload
  fields share, and a value that does not fit is a caller error, not
  something this codec truncates.")

(defn- be16 [n] [(bit-and (unsigned-bit-shift-right n 8) 0xFF) (bit-and n 0xFF)])

(defn ascii->bytes
  "ASCII string -> byte vector. A convenience for building test vectors and
  simple client identifiers; not a general Unicode encoder.

  `(mapv int s)` is the tempting one-liner and the wrong one: on the JVM a
  character IS a code point, so `int` of one is correct, but under
  ClojureScript a string's `seq` yields one-character *strings*, and `int`
  of a one-character string is not a code point — it's 0, silently, for
  every character. `modbus.crc` in this workspace's `org-modbus` documents
  hitting exactly this 'vector of zeros' bug three separate times before it
  got a docstring warning about it; here it gets a reader-conditional
  instead, so the wrong form never compiles into the cljs build at all."
  [s]
  #?(:clj (mapv int s)
     :cljs (mapv #(.charCodeAt % 0) s)))

(defn bytes->ascii
  [bs]
  (apply str (map char bs)))

(defn encode
  "`bs` (a byte sequence, at most 65535 bytes) as an MQTT UTF-8 string or
  binary-data field: length-prefixed with 2 big-endian bytes."
  [bs]
  (let [bs (vec bs)]
    (if (> (count bs) 0xFFFF)
      {:status :error :reason :string-too-long :length (count bs)}
      {:status :ok :bytes (into (be16 (count bs)) bs)})))

(defn decode
  "Reads a length-prefixed field starting at index `i`. Returns
  `{:status :ok :bytes [...] :next-index j}`, `{:status :incomplete}` if
  `bs` runs out before the declared length is satisfied, or
  `{:status :error :reason :embedded-null}` if a `0x00` byte appears inside
  the field — MQTT-3.1.1 §1.5.3 forbids it explicitly, and a decoder that
  passes it through hands the caller a string a C-based subscriber will
  silently truncate at the null while this decoder reports the full length,
  a mismatch that is worse than an outright rejection."
  [bs i]
  (let [bs (vec bs) n (count bs)]
    (if (> (+ i 2) n)
      {:status :incomplete}
      (let [len (+ (* 256 (nth bs i)) (nth bs (inc i)))
            start (+ i 2)
            end (+ start len)]
        (cond
          (> end n) {:status :incomplete}
          (some zero? (subvec bs start end)) {:status :error :reason :embedded-null}
          :else {:status :ok :bytes (subvec bs start end) :next-index end})))))
