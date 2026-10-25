(ns iec60870.apci
  "IEC 60870-5-104 APCI — the Application Protocol Control Information, the
  TCP-carried frame envelope wrapped around an ASDU:

      Start   Length  Control(4 octets)
      0x68    1 byte  I/S/U-format, see below

  `Length` counts everything after itself: the 4 control octets plus the
  ASDU, so a control-only frame (S- or U-format, no ASDU) has Length 4.
  There is no checksum in this header, the same reasoning `org-modbus`'s
  `tcp.cljc` gives for Modbus TCP's MBAP header: TCP already guarantees
  byte-stream integrity, so a link-layer-style CRC here would be redundant.

  The control field has three formats, discriminated by its first octet's
  low bits:

      bit0=0            I-format (numbered information transfer): carries
                         an ASDU and both a 15-bit send sequence number
                         N(S) and a 15-bit receive sequence number N(R)
      bits1-0 = 01       S-format (numbered supervisory function, a bare
                         acknowledgement): carries only N(R)
      bits1-0 = 11       U-format (unnumbered control function): STARTDT/
                         STOPDT/TESTFR, act and con, one bit each

  A 15-bit sequence number is packed across two octets with its own low
  bit forced to 0 in the low octet (`N(S)*2` and `N(R)*2`, conceptually) —
  the same convention that reserves octet 1's bit 0 as the I/S/U
  discriminator carries through to octets 3-4's N(R) field for symmetry.

  ;; constructed, not a published spec vector — the bit-position
  ;; conventions above (I/S/U discriminator bits, U-format's six function
  ;; bits, the 253-octet APDU ceiling) are reproduced from this session's
  ;; recollection of widely documented IEC 60870-5-104 framing, not
  ;; cross-checked against the standard's own text this session."
  )

(def start-byte 0x68)
(def header-bytes 6) ;; start(1) + length(1) + control(4)
(def max-apdu-length
  "The companion standard restricts an APDU (control + ASDU) to at most 253
  octets, even though the single-byte Length field could physically state
  up to 255."
  253)
(def max-asdu-bytes (- max-apdu-length 4))

(defn- pack-15bit [n]
  [(bit-and (bit-shift-left n 1) 0xFE)
   (bit-and (unsigned-bit-shift-right n 7) 0xFF)])

(defn- unpack-15bit [lo hi]
  (bit-or (unsigned-bit-shift-right lo 1) (bit-shift-left hi 7)))

(defn encode-i
  "An I-format frame: `{:send-seq :recv-seq}` plus the ASDU bytes
  (`iec60870.asdu`'s job to produce)."
  [{:keys [send-seq recv-seq]} asdu-bytes]
  (cond
    (not (<= 0 send-seq 0x7FFF)) {:status :error :reason :send-seq-out-of-range :value send-seq}
    (not (<= 0 recv-seq 0x7FFF)) {:status :error :reason :recv-seq-out-of-range :value recv-seq}
    (> (count asdu-bytes) max-asdu-bytes)
    {:status :error :reason :asdu-too-long :length (count asdu-bytes) :maximum max-asdu-bytes}
    :else
    (let [[s0 s1] (pack-15bit send-seq)
          [r0 r1] (pack-15bit recv-seq)
          len (+ 4 (count asdu-bytes))]
      {:status :ok :bytes (into [start-byte len s0 s1 r0 r1] asdu-bytes)})))

(defn encode-s
  "An S-format frame: a bare acknowledgement carrying only N(R)."
  [{:keys [recv-seq]}]
  (if (not (<= 0 recv-seq 0x7FFF))
    {:status :error :reason :recv-seq-out-of-range :value recv-seq}
    (let [[r0 r1] (pack-15bit recv-seq)]
      {:status :ok :bytes [start-byte 4 0x01 0x00 r0 r1]})))

(def u-function-bits
  {:startdt-act 0x04 :startdt-con 0x08 :stopdt-act 0x10 :stopdt-con 0x20
   :testfr-act 0x40 :testfr-con 0x80})

(defn encode-u
  "A U-format frame: one of the six link-management functions."
  [function]
  (if-let [bit (get u-function-bits function)]
    {:status :ok :bytes [start-byte 4 (bit-or 0x03 bit) 0x00 0x00 0x00]}
    {:status :error :reason :unknown-u-function :function function}))

(defn decode
  "Read one APCI frame from the front of `buf`.

  Returns `{:status :ok :frame {…} :consumed n}`, `{:status :incomplete
  :need n}`, or a named `:error`. `:frame` is `{:format :i :send-seq
  :recv-seq :asdu-bytes}`, `{:format :s :recv-seq}`, or `{:format :u
  :functions #{...}}` — decoding `:asdu-bytes` further is
  `iec60870.asdu/decode`, because only the I-format carries one."
  [buf]
  (let [buf (vec buf) n (count buf)]
    (cond
      (< n 2) {:status :incomplete :need (- 2 n)}
      (not= (nth buf 0) start-byte) {:status :error :reason :bad-start-byte :got (nth buf 0)}
      :else
      (let [len (nth buf 1)]
        (cond
          (< len 4) {:status :error :reason :length-too-small :length len}
          (> len max-apdu-length) {:status :error :reason :length-too-large :length len :maximum max-apdu-length}
          :else
          (let [total (+ 2 len)]
            (if (< n total)
              {:status :incomplete :need (- total n)}
              (let [c1 (nth buf 2) c2 (nth buf 3) c3 (nth buf 4) c4 (nth buf 5)
                    asdu-bytes (subvec buf 6 total)]
                (cond
                  (zero? (bit-and c1 0x01))
                  {:status :ok :consumed total
                   :frame {:format :i
                           :send-seq (unpack-15bit c1 c2)
                           :recv-seq (unpack-15bit c3 c4)
                           :asdu-bytes asdu-bytes}}
                  (= (bit-and c1 0x03) 0x01)
                  {:status :ok :consumed total
                   :frame {:format :s :recv-seq (unpack-15bit c3 c4)}}
                  :else
                  (let [fns (into #{} (keep (fn [[k bit]] (when (pos? (bit-and c1 bit)) k)))
                                  u-function-bits)]
                    {:status :ok :consumed total :frame {:format :u :functions fns}}))))))))))
