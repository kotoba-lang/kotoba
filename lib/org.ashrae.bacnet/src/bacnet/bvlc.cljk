(ns bacnet.bvlc
  "BACnet Virtual Link Control — the BACnet/IP header, ASHRAE 135 Annex J.

  BACnet/IP wraps the NPDU (`bacnet.npdu`) in a 4-octet BVLC header before
  it goes on UDP port 47808 (0xBAC0):

  ```
  BVLC Type (1) = 0x81   Function (1)   Length (2, big-endian, WHOLE message)
  ```

  **Length counts itself.** It is the length of the entire BVLL message —
  header included — not just the NPDU that follows, the same 'off by the
  header size' trap `modbus.tcp`'s MBAP length documents for Modbus (there
  it under-counts by the unit id; here it under-counts by all four header
  bytes). A decoder that trusts a wrong length either truncates a valid
  NPDU or reads past the buffer into the next datagram — UDP has no stream
  to resynchronise, so unlike a TCP framing bug this one cannot recover on
  the next read.

  Functions implemented: Result (0x00), Original-Unicast-NPDU (0x0A),
  Original-Broadcast-NPDU (0x0B) — the three needed to carry an ordinary
  request/response and report a BBMD-side failure. BDT/FDT management
  (0x01-0x03, 0x05-0x09) and Forwarded-NPDU (0x04) are BBMD/foreign-device
  registration machinery this library does not implement; see the README.")

(defn- u8 [n] (bit-and n 0xFF))
(defn- be16 [n] [(u8 (unsigned-bit-shift-right n 8)) (u8 n)])
(defn- rd16 [bs i] (+ (* 256 (nth bs i)) (nth bs (inc i))))

(def bvlc-type 0x81)

(def functions
  {0x00 :bvlc-result
   0x0A :original-unicast-npdu
   0x0B :original-broadcast-npdu})

(def function->code (into {} (map (fn [[k v]] [v k])) functions))

(defn encode
  "`function` is `:original-unicast-npdu`, `:original-broadcast-npdu`, or
  `:bvlc-result` (whose `payload` is the 2-byte result code, Table J-1 —
  0x0000 successful completion is the only one this library names)."
  [function payload]
  (if-let [code (function->code function)]
    (let [total (+ 4 (count payload))]
      {:status :ok :bytes (into [bvlc-type code] (concat (be16 total) payload))})
    [:error :bacnet/unknown-bvlc-function]))

(defn decode
  [bs]
  (cond
    (< (count bs) 4) [:error :bacnet/frame-too-short]
    (not= (nth bs 0) bvlc-type) [:error :bacnet/not-bacnet-ip]
    :else
    (let [code (nth bs 1)
          declared-length (rd16 bs 2)]
      (cond
        (not (contains? functions code)) [:error :bacnet/unknown-bvlc-function]
        (not= declared-length (count bs)) [:error :bacnet/length-mismatch]
        :else {:status :ok :function (functions code)
               :payload (vec (subvec (vec bs) 4 (count bs)))}))))
