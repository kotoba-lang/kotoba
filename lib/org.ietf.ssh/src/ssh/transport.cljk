(ns ssh.transport
  "The reusable core of the SSH-2 transport layer (RFC 4253) with the
  curve25519-sha256 key exchange (RFC 8731 / RFC 5656): message numbers, the
  KEXINIT algorithm profile, binary-packet framing, the SSH `string` and
  `mpint` encodings, and -- the piece everything else exists for -- the ordered
  transcript whose SHA-256 is the exchange hash H.

  This namespace is the single source of truth for those wire rules. It is
  pure and portable: the caller supplies the hash (SHA-256) and the X25519
  scalar multiplication, so the same definitions drive a host-side reference
  and the aiueos bare-metal kernel, which imports this repo and compiles
  `ssh/exchange_hash.kotoba` (a byte-for-byte port of `h-transcript` below) into
  a kernel object. Nothing here does I/O or randomness.

  Bytes are plain vectors of 0..255 integers so the code runs identically under
  Clojure and nbb/SCI without a platform byte-array type."
  (:require [kotoba.lang.text :as str]))

;; ── message numbers (RFC 4253 §12, RFC 5656 §7.1) ───────────────────────────
(def msg-disconnect 1)
(def msg-kexinit 20)
(def msg-newkeys 21)
(def msg-kex-ecdh-init 30)   ; client -> server: Q_C
(def msg-kex-ecdh-reply 31)  ; server -> client: K_S, Q_S, signature

;; ── the algorithm profile aiueos speaks (ssh-v1.edn) ────────────────────────
;; Named here so the kernel and any host reference negotiate the SAME set. The
;; server offers exactly these; a peer that shares none of a required list is a
;; failed negotiation, not a silent fallback.
(def profile
  {:kex ["curve25519-sha256" "curve25519-sha256@libssh.org"]
   :host-key ["ecdsa-sha2-nistp256"]
   :cipher ["aes128-gcm@openssh.com"]
   :mac ["none"]                 ; the GCM tag is the MAC; no separate algorithm
   :compression ["none"]
   :languages [""]})

;; ── primitive encodings (RFC 4251 §5) ───────────────────────────────────────

(defn str->bytes
  "ASCII byte codes of a string, portable across Clojure and ClojureScript. SSH
  identification strings and algorithm names are ASCII (RFC 4253 §4.2, §6.3), so
  a per-code-unit read is exact. NB: `(mapv int s)` is NOT portable -- under
  ClojureScript a string seqs into single-character strings and `(int \"S\")` is
  0, so it silently zeroes the bytes."
  [s]
  #?(:clj  (mapv int s)
     :cljs (mapv #(.charCodeAt s %) (range (count s)))))

(defn u32
  "A uint32 as 4 big-endian bytes."
  [n]
  [(bit-and (quot n 16777216) 255)
   (bit-and (quot n 65536) 255)
   (bit-and (quot n 256) 255)
   (bit-and n 255)])

(defn string-bytes
  "SSH `string`: a uint32 length prefix then the raw bytes."
  [bytes]
  (into (u32 (count bytes)) bytes))

(defn name-list
  "SSH `name-list`: comma-joined names, encoded as a `string`."
  [names]
  (string-bytes (str->bytes (str/join "," names))))

(defn mpint
  "SSH `mpint`: two's-complement big-endian with the shortest length, and a
  leading 0x00 when the high bit would otherwise make it negative. Leading
  zero bytes are stripped; zero itself is the empty string. RFC 4251 §5."
  [bytes]
  (let [trimmed (drop-while zero? bytes)
        v (vec trimmed)]
    (cond
      (empty? v) (u32 0)
      (>= (first v) 128) (string-bytes (into [0] v))
      :else (string-bytes v))))

;; ── binary packet framing (RFC 4253 §6) ─────────────────────────────────────

(defn pad-length
  "Padding so that (4 + 1 + payload + padding) is a multiple of `block` and the
  padding is at least 4 bytes. `block` is 8 before a cipher is negotiated."
  [payload-len block]
  (let [unpadded (+ 5 payload-len)
        p (- block (mod unpadded block))
        p (if (< p 4) (+ p block) p)]
    p))

(defn packet
  "Wrap a payload as an unencrypted binary packet (pre-NEWKEYS): uint32
  packet_length, uint8 padding_length, payload, padding. `pad` supplies the
  padding bytes (random on the wire; a caller may pass zeros for a
  deterministic test). No MAC before keys are taken into use."
  ([payload] (packet payload 8 (repeat 0)))
  ([payload block pad]
   (let [pl (pad-length (count payload) block)
         padding (vec (take pl pad))
         packet-length (+ 1 (count payload) pl)]
     (-> (u32 packet-length)
         (conj pl)
         (into payload)
         (into padding)))))

(defn packet-payload
  "Return the payload of an unencrypted binary packet, or nil if the framing is
  inconsistent. Validates the length fields against the buffer -- the same
  admission the kernel object performs before trusting a received packet."
  [bytes]
  (when (>= (count bytes) 6)
    (let [packet-length (+ (* 16777216 (nth bytes 0)) (* 65536 (nth bytes 1))
                           (* 256 (nth bytes 2)) (nth bytes 3))
          padding-length (nth bytes 4)
          payload-len (- packet-length padding-length 1)]
      (when (and (>= payload-len 0)
                 (>= padding-length 4)
                 (<= (+ 4 packet-length) (count bytes)))
        (subvec (vec bytes) 5 (+ 5 payload-len))))))

;; ── KEXINIT payload (RFC 4253 §7.1) ─────────────────────────────────────────

(defn kexinit-payload
  "The SSH_MSG_KEXINIT payload: the message number, a 16-byte cookie, the six
  algorithm name-lists in order, first_kex_packet_follows (0), and a reserved
  uint32 (0). `cookie` is 16 bytes (random on the wire)."
  [cookie]
  (-> [msg-kexinit]
      (into cookie)
      (into (name-list (:kex profile)))
      (into (name-list (:host-key profile)))
      (into (name-list (:cipher profile)))      ; client->server
      (into (name-list (:cipher profile)))      ; server->client
      (into (name-list (:mac profile)))         ; client->server
      (into (name-list (:mac profile)))         ; server->client
      (into (name-list (:compression profile))) ; client->server
      (into (name-list (:compression profile))) ; server->client
      (into (name-list (:languages profile)))   ; client->server
      (into (name-list (:languages profile)))   ; server->client
      (conj 0)                                  ; first_kex_packet_follows
      (into (u32 0))))                          ; reserved

;; ── the exchange hash transcript (RFC 5656 §4, RFC 8731) ─────────────────────

(defn h-transcript
  "The exact byte sequence whose SHA-256 is the curve25519-sha256 exchange hash
  H:  string(V_C) string(V_S) string(I_C) string(I_S) string(K_S)
      string(Q_C) string(Q_S) mpint(K).

  V_C/V_S are the identification strings WITHOUT CR-LF; I_C/I_S are the full
  KEXINIT payloads (message number included); K_S is the server host-key blob;
  Q_C/Q_S are the 32-byte ephemeral public keys; K is the 32-byte X25519 shared
  secret. This is the function the kernel object mirrors byte-for-byte."
  [{:keys [v-c v-s i-c i-s k-s q-c q-s k]}]
  (-> []
      (into (string-bytes (str->bytes v-c)))
      (into (string-bytes (str->bytes v-s)))
      (into (string-bytes i-c))
      (into (string-bytes i-s))
      (into (string-bytes k-s))
      (into (string-bytes q-c))
      (into (string-bytes q-s))
      (into (mpint k))))

(defn exchange-hash
  "H = SHA256(h-transcript inputs). `sha256` is supplied by the caller (the
  kernel's Kotoba SHA-256, or a host reference) so this stays pure."
  [sha256 inputs]
  (sha256 (h-transcript inputs)))
