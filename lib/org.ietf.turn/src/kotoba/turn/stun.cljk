;; kotoba.turn.stun — RFC 8489 (STUN) message primitives + the RFC 8656 (TURN)
;; attributes the relay needs: the 20-byte header, attribute TLV iteration
;; (with 4-byte padding), XOR-MAPPED-ADDRESS (IPv4), MESSAGE-INTEGRITY
;; (HMAC-SHA1) and FINGERPRINT (CRC-32). Pure/portable — every "message" here
;; is a `kotoba.bytes` byte-vector (vector<int 0..255>), never a
;; platform byte-array, so the same code runs on the JVM and in cljs.
;;
;; Out of scope (this repo, this module): the allocation state machine and the
;; UDP/TCP/TLS listener I/O — see docs/ADR-kotoba-turn-relay.md.
(ns kotoba.turn.stun
  (:require [kotoba.bytes :as b]
            [kotoba.turn.credential :as cred]))

;; RFC 8489 magic cookie — bytes 4..8 of every STUN message.
(def magic-cookie 0x2112A442)
(def magic-cookie-bytes (b/u32->bytes magic-cookie))

;; FINGERPRINT XOR constant (RFC 8489 §14.7).
(def fingerprint-xor 0x5354554E)

;; Message types (RFC 8489 / RFC 8656). For these low method numbers the
;; request-class encoding equals the method value.
(def binding-request            0x0001)
(def binding-response            0x0101)
(def allocate-request            0x0003)
(def allocate-response           0x0103)
(def allocate-error              0x0113)
(def refresh-request             0x0004)
(def refresh-response            0x0104)
(def create-permission-request   0x0008)
(def create-permission-response  0x0108)
(def channel-bind-request        0x0009)
(def channel-bind-response       0x0109)
(def send-indication             0x0016)
(def data-indication              0x0017)

;; Attribute types.
(def attr-username             0x0006)
(def attr-message-integrity    0x0008)
(def attr-error-code           0x0009)
(def attr-channel-number       0x000C)
(def attr-lifetime             0x000D)
(def attr-xor-peer-address     0x0012)
(def attr-data                 0x0013)
(def attr-xor-relayed-address  0x0016)
(def attr-requested-transport  0x0019)
(def attr-xor-mapped-address   0x0020)
(def attr-software              0x8022)
(def attr-fingerprint          0x8028)

;; ---------------------------------------------------------------------------
;; Header

(defrecord Header [typ length txid])

(defn encode-header
  "Encode the fixed 20-byte STUN header."
  [{:keys [typ length txid]}]
  (-> []
      (into (b/u16->bytes typ))
      (into (b/u16->bytes length))
      (into magic-cookie-bytes)
      (into txid)))

(defn decode-header
  "Decode the fixed 20-byte STUN header. Throws on short input or a bad magic
   cookie."
  [msg]
  (when (< (count msg) 20)
    (throw (ex-info "stun: message shorter than 20-byte header" {:len (count msg)})))
  (let [cookie (b/bytes->u32 (subvec (vec msg) 4 8))]
    (when (not= cookie magic-cookie)
      (throw (ex-info "stun: bad magic cookie" {:cookie cookie}))))
  (map->Header
    {:typ (b/bytes->u16 (subvec (vec msg) 0 2))
     :length (b/bytes->u16 (subvec (vec msg) 2 4))
     :txid (subvec (vec msg) 8 20)}))

;; ---------------------------------------------------------------------------
;; Attribute TLVs

(defn push-attr
  "Append one STUN attribute TLV (type, length, value) with RFC 8489 4-byte
   padding to byte-vector `buf`. Does not patch the header length field —
   callers do that via `set-attr-length!` / `append-message-integrity` /
   `append-fingerprint`."
  [buf typ value]
  (let [value (vec value)
        pad (mod (- 4 (mod (count value) 4)) 4)]
    (-> buf
        (into (b/u16->bytes typ))
        (into (b/u16->bytes (count value)))
        (into value)
        (into (repeat pad 0)))))

(defn set-attr-length
  "Return `msg` with the header length field patched to cover all attributes
   currently present (use for responses carrying no MI/FINGERPRINT trailer)."
  [msg]
  (let [msg (vec msg)
        len (- (count msg) 20)]
    (into (into (subvec msg 0 2) (b/u16->bytes len)) (subvec msg 4))))

(defn encode-error-code
  "ERROR-CODE attribute value (RFC 8489 §14.8): 2 reserved bytes, class
   (hundreds digit), number (mod 100), then the UTF-8 reason phrase."
  [code reason]
  (into [0 0 (quot code 100) (mod code 100)] (b/utf8-encode reason)))

(defn encode-u32-attr [n] (b/u32->bytes n))

(defn attributes
  "Iterate `(type value)` pairs from the message body (bytes after the
   20-byte header), honoring the 4-byte attribute padding. Throws if an
   attribute's length runs past the message."
  [body]
  (let [body (vec body) n (count body)]
    (loop [i 0 out []]
      (if (> (+ i 4) n)
        out
        (let [typ (b/bytes->u16 (subvec body i (+ i 2)))
              len (b/bytes->u16 (subvec body (+ i 2) (+ i 4)))
              start (+ i 4)
              end (+ start len)]
          (when (> end n)
            (throw (ex-info "stun: attribute length runs past the message"
                             {:typ typ :len len})))
          (recur (+ end (mod (- 4 (mod len 4)) 4))
                 (conj out [typ (subvec body start end)])))))))

(defn- attribute-offset
  "Byte offset (within `body`) of attribute `typ`'s TLV start, or nil."
  [body typ]
  (let [body (vec body) n (count body)]
    (loop [i 0]
      (when (<= (+ i 4) n)
        (let [t (b/bytes->u16 (subvec body i (+ i 2)))
              len (b/bytes->u16 (subvec body (+ i 2) (+ i 4)))]
          (if (= t typ)
            i
            (recur (+ i 4 len (mod (- 4 (mod len 4)) 4)))))))))

;; ---------------------------------------------------------------------------
;; XOR-MAPPED-ADDRESS (IPv4 only — RFC 8489 §14.2)

(defn encode-xor-mapped-v4
  "Encode an IPv4 XOR-MAPPED-ADDRESS attribute value (8 bytes). `ip` is
   [o1 o2 o3 o4]."
  [ip port]
  (let [ip-u32 (b/bytes->u32 ip)
        x-port (bit-xor port (unsigned-bit-shift-right magic-cookie 16))
        x-addr (bit-xor ip-u32 magic-cookie)]
    (into [0 0x01] (into (b/u16->bytes x-port) (b/u32->bytes x-addr)))))

(defn decode-xor-mapped-v4
  "Decode an IPv4 XOR-MAPPED-ADDRESS attribute value. Returns {:ip [.. ..] :port
   n}. Throws if the value isn't 8 bytes or isn't family IPv4 (0x01)."
  [v]
  (let [v (vec v)]
    (when (not= (count v) 8)
      (throw (ex-info "stun: XOR-MAPPED-ADDRESS must be 8 bytes" {:len (count v)})))
    (when (not= (nth v 1) 0x01)
      (throw (ex-info "stun: unsupported address family" {:family (nth v 1)})))
    (let [port (bit-xor (b/bytes->u16 (subvec v 2 4)) (unsigned-bit-shift-right magic-cookie 16))
          x-addr (b/bytes->u32 (subvec v 4 8))
          ip-u32 (bit-xor x-addr magic-cookie)]
      {:ip (b/u32->bytes ip-u32) :port port})))

;; ---------------------------------------------------------------------------
;; CRC-32 (IEEE 802.3, reflected) — the checksum FINGERPRINT is built on.

(def ^:private crc32-poly 0xEDB88320)

(defn crc32 [data]
  (let [crc0 (bit-and (bit-not 0) 0xffffffff)]
    (bit-and
      (bit-not
        (reduce
          (fn [crc byte]
            (loop [c (bit-xor crc (bit-and byte 0xff)) k 0]
              (if (= k 8)
                c
                (let [mask (- (bit-and c 1))]
                  (recur (bit-xor (unsigned-bit-shift-right c 1) (bit-and crc32-poly mask))
                         (inc k))))))
          crc0
          data))
      0xffffffff)))

;; ---------------------------------------------------------------------------
;; MESSAGE-INTEGRITY (RFC 8489 §14.5) — HMAC-SHA1 over the message up to (not
;; including) this attribute, with the header length temporarily patched to
;; cover it.

(defn append-message-integrity
  "Append a MESSAGE-INTEGRITY attribute to `msg` (header+attrs, no MI yet).
   `key` is the HMAC-SHA1 key as a byte vector (e.g. UTF-8 bytes of the
   long-term/short-term STUN credential, or an MD5 key per RFC 8489 §9.2.2) —
   patches the header length to cover the 24-byte MI TLV first, per spec,
   since the MAC is computed over that patched header."
  [msg key]
  (let [msg (vec msg)
        covered (+ (- (count msg) 20) 24)
        msg (into (into (subvec msg 0 2) (b/u16->bytes covered)) (subvec msg 4))
        tag (cred/hmac-sha1-bytes key msg)]
    (push-attr msg attr-message-integrity tag)))

(defn verify-message-integrity
  "Verify a message's MESSAGE-INTEGRITY attribute against byte-vector `key`.
   Returns true/false; independent of any trailing FINGERPRINT (recomputes the
   header length to point exactly at the end of the MI attribute)."
  [msg key]
  (let [msg (vec msg)]
    (boolean
      (when (>= (count msg) 20)
        (let [body (subvec msg 20)]
          (when-let [p (attribute-offset body attr-message-integrity)]
            (when (<= (+ p 24) (count body))
              (let [len-field (+ p 24)
                    header+prefix (into (into (subvec msg 0 2) (b/u16->bytes len-field))
                                         (into (subvec msg 4 20) (subvec body 0 p)))
                    expected (cred/hmac-sha1-bytes key header+prefix)
                    presented (subvec body (+ p 4) (+ p 24))]
                (b/constant-time-eq expected presented)))))))))

;; ---------------------------------------------------------------------------
;; FINGERPRINT (RFC 8489 §14.7) — must be the last attribute.

(defn append-fingerprint
  "Append a FINGERPRINT attribute to `msg` (header+attrs, no FINGERPRINT yet)."
  [msg]
  (let [msg (vec msg)
        covered (+ (- (count msg) 20) 8)
        msg (into (into (subvec msg 0 2) (b/u16->bytes covered)) (subvec msg 4))
        crc (bit-xor (crc32 msg) fingerprint-xor)]
    (push-attr msg attr-fingerprint (b/u32->bytes crc))))

(defn verify-fingerprint
  "Verify a trailing FINGERPRINT attribute."
  [msg]
  (let [msg (vec msg) n (count msg)]
    (boolean
      (when (>= n 28)
        (let [fp (- n 8)]
          (when (= (b/bytes->u16 (subvec msg fp (+ fp 2))) attr-fingerprint)
            (let [expected (bit-xor (crc32 (subvec msg 0 fp)) fingerprint-xor)
                  actual (b/bytes->u32 (subvec msg (+ fp 4) (+ fp 8)))]
              (= actual expected))))))))
