(ns knp.packet
  "KNP wire packet format: pure header/payload encode-decode.

  Restored from the legacy kami-engine/kami-knp Rust crate (deleted in PR #82,
  path `kami-knp/src/packet.rs`) as part of ADR-2607010930
  (com-junkawasaki/root, kami-engine Rust-workspace restoration to CLJC).

  Purpose: 5-byte post-session wire header (7-byte pre-session with \"KN\"
  magic), 4 channel kinds (Unreliable / ReliableOrdered / ReliableUnordered /
  Voice), and packet payload framing. This is pure byte-format logic with no
  socket I/O, so it ports 1:1.

  Nothing was excluded from `packet.rs` itself — the whole file is portable.
  (Native-only socket I/O lives in the sibling `socket.rs` / `client.rs` /
  `server.rs`, which were NOT ported; see repo README.)"
  #?(:clj (:import [java.nio ByteBuffer ByteOrder])))

;; ---------------------------------------------------------------------------
;; Channel

(def channel->byte
  "Channel keyword -> wire byte (Rust `#[repr(u8)] enum Channel`)."
  {:unreliable 0
   :reliable-ordered 1
   :reliable-unordered 2
   :voice 3})

(def byte->channel
  "Wire byte -> channel keyword. Unknown values fall back to :unreliable,
  matching the Rust `_ => Channel::Unreliable` catch-all."
  {0 :unreliable
   1 :reliable-ordered
   2 :reliable-unordered
   3 :voice})

(defn channel-from-byte
  "Decode a channel nibble (0-15) to a channel keyword, defaulting to
  :unreliable for out-of-range values (mirrors Rust's wildcard arm)."
  [b]
  (get byte->channel (bit-and (long b) 0x0F) :unreliable))

;; ---------------------------------------------------------------------------
;; Flags (upper 4 bits of flags_channel byte)

(def flag->bit
  "Packet flag keyword -> bit value (Rust `bitflags! Flags`)."
  {:reliable 2r0001
   :ordered 2r0010
   :encrypted 2r0100
   :fragment 2r1000})

(defn flags->bits
  "Encode a set of flag keywords into the 4-bit flags nibble."
  [flags]
  (reduce (fn [acc f] (bit-or acc (get flag->bit f 0))) 0 (or flags #{}))
  )

(defn bits->flags
  "Decode a 4-bit flags nibble into a set of flag keywords (truncates to
  known bits, mirroring `Flags::from_bits_truncate`)."
  [bits]
  (into #{}
        (keep (fn [[k b]] (when (pos? (bit-and bits b)) k)))
        flag->bit))

;; ---------------------------------------------------------------------------
;; Header (5 bytes post-session)

(def header-size 5)
(def magic [0x4B 0x4E]) ;; "KN"

(defn make-header
  "Build a header map. `channel` and `flags` (a set of flag keywords) are
  packed into a single flags_channel byte; sequence/ack are u16."
  [channel flags sequence ack]
  {:flags-channel (bit-or (bit-shift-left (flags->bits flags) 4)
                           (get channel->byte channel 0))
   :sequence (bit-and (long sequence) 0xFFFF)
   :ack (bit-and (long ack) 0xFFFF)})

(defn header-channel [header]
  (channel-from-byte (:flags-channel header)))

(defn header-flags [header]
  (bits->flags (bit-and (unsigned-bit-shift-right (:flags-channel header) 4) 0x0F)))

(defn header-sequence [header]
  (:sequence header))

(defn header-ack [header]
  (:ack header))

#?(:clj
   (defn header->bytes
     "Serialize a header map to a 5-byte little-endian byte-array."
     [{:keys [flags-channel sequence ack]}]
     (let [bb (doto (ByteBuffer/allocate header-size)
                (.order ByteOrder/LITTLE_ENDIAN)
                (.put (unchecked-byte flags-channel))
                (.putShort (unchecked-short sequence))
                (.putShort (unchecked-short ack)))]
       (.array bb)))
   :cljs
   (defn header->bytes
     "Serialize a header map to a 5-byte little-endian Uint8Array."
     [{:keys [flags-channel sequence ack]}]
     (let [buf (js/ArrayBuffer. header-size)
           dv (js/DataView. buf)]
       (.setUint8 dv 0 flags-channel)
       (.setUint16 dv 1 sequence true)
       (.setUint16 dv 3 ack true)
       (js/Uint8Array. buf))))

#?(:clj
   (defn bytes->header
     "Parse the first 5 bytes of `bytes` (byte-array) into a header map."
     [bytes]
     (let [bb (doto (ByteBuffer/wrap bytes 0 header-size)
                (.order ByteOrder/LITTLE_ENDIAN))
           flags-channel (bit-and (int (.get bb)) 0xFF)
           sequence (bit-and (int (.getShort bb)) 0xFFFF)
           ack (bit-and (int (.getShort bb)) 0xFFFF)]
       {:flags-channel flags-channel :sequence sequence :ack ack}))
   :cljs
   (defn bytes->header
     "Parse the first 5 bytes of `bytes` (Uint8Array) into a header map."
     [bytes]
     (let [dv (js/DataView. (.-buffer bytes) (.-byteOffset bytes) header-size)]
       {:flags-channel (.getUint8 dv 0)
        :sequence (.getUint16 dv 1 true)
        :ack (.getUint16 dv 3 true)})))

;; ---------------------------------------------------------------------------
;; Packet (header + payload)

#?(:clj
   (defn- concat-bytes [^bytes a ^bytes b]
     (let [out (byte-array (+ (alength a) (alength b)))]
       (System/arraycopy a 0 out 0 (alength a))
       (System/arraycopy b 0 out (alength a) (alength b))
       out))
   :cljs
   (defn- concat-bytes [a b]
     (let [out (js/Uint8Array. (+ (.-length a) (.-length b)))]
       (.set out a 0)
       (.set out b (.-length a))
       out)))

#?(:clj (defn- bytes-length [^bytes b] (alength b))
   :cljs (defn- bytes-length [b] (.-length b)))

(defn make-packet
  [channel flags seq ack payload]
  {:header (make-header channel flags seq ack)
   :payload payload})

(defn packet->bytes
  "Serialize a packet map ({:header .. :payload ..}) to wire bytes."
  [{:keys [header payload]}]
  (concat-bytes (header->bytes header) payload))

(defn bytes->packet
  "Deserialize wire bytes into a packet map, or nil if too short."
  [bytes]
  (when (>= (bytes-length bytes) header-size)
    (let [header (bytes->header bytes)
          #?@(:clj [payload (java.util.Arrays/copyOfRange ^bytes bytes header-size (bytes-length bytes))]
              :cljs [payload (.slice bytes header-size)])]
      {:header header :payload payload})))

(defn wire-size
  "Wire size in bytes: header-size + payload length."
  [{:keys [payload]}]
  (+ header-size (bytes-length payload)))
