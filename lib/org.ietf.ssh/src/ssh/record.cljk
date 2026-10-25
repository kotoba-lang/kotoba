(ns ssh.record
  "The `aes128-gcm@openssh.com` binary packet layer (RFC 5647 + the OpenSSH
  variant), which turns on for each side after it sends NEWKEYS. The AES-128-GCM
  cipher itself is supplied by the caller (Node's GCM in the tests, the kernel's
  AES-128-GCM object on the metal); this namespace is the wire framing, the nonce
  sequence, the AAD rule, and the padding rule -- the parts two implementations
  must agree on byte-for-byte or the tag will not verify.

  On the wire, one packet is:

     uint32  packet_length                 (NOT encrypted; this is the GCM AAD)
     bytes   ciphertext                    (GCM of: padding_length || payload || padding)
     bytes   auth_tag                      (16 bytes)

  `packet_length = 1 + len(payload) + len(padding)`. The encrypted portion
  (padding_length + payload + padding) is a multiple of the 16-byte block and the
  padding is at least 4 bytes (RFC 5647 §7.3). The length field is authenticated
  as additional data but sent in clear so the receiver knows how many bytes to
  read before it can decrypt.

  The nonce is a 12-byte IV: a 4-byte fixed field and an 8-byte invocation
  counter that starts at the derived IV's last 8 bytes and increments by one
  (as a big-endian 64-bit integer) after each packet. The counter add is done
  byte-wise because a 64-bit value does not survive ClojureScript's number type."
  (:require [ssh.transport :as t]))

(def block 16)
(def tag-len 16)

(defn pad-len
  "Padding so that (1 + payload-len + padding) is a multiple of the block and at
  least 4 bytes."
  [payload-len]
  (let [p (- block (mod (+ 1 payload-len) block))]
    (if (< p 4) (+ p block) p)))

(defn nonce
  "The 12-byte GCM nonce for packet number `seq`: iv[0..4] (fixed) followed by
  iv[4..12] as a big-endian 64-bit counter plus `seq`, added byte-wise with carry
  so it is exact for any 64-bit counter."
  [iv seq]
  (let [fixed (subvec iv 0 4)
        ctr (vec (subvec iv 4 12))]
    (loop [i 7 carry seq acc ctr]
      (if (or (neg? i) (zero? carry))
        (into fixed acc)
        (let [s (+ (nth acc i) carry)]
          (recur (dec i) (quot s 256) (assoc acc i (bit-and s 255))))))))

(defn seal
  "Build one outbound packet. `gcm-encrypt` is `(fn [key nonce aad plaintext] ->
  {:ciphertext v :tag v})`. `pad` supplies the padding bytes (random on the wire;
  a test may pass zeros). Returns the full wire bytes."
  [gcm-encrypt key iv seq payload pad]
  (let [pl (pad-len (count payload))
        packet-length (+ 1 (count payload) pl)
        aad (t/u32 packet-length)
        plaintext (-> [pl] (into payload) (into (vec (take pl pad))))
        {:keys [ciphertext tag]} (gcm-encrypt key (nonce iv seq) aad plaintext)]
    (-> aad (into ciphertext) (into tag))))

(defn open
  "Decrypt one inbound packet from `wire` (which must hold at least one full
  packet). `gcm-decrypt` is `(fn [key nonce aad ciphertext tag] -> plaintext | nil)`
  (nil on tag-verify failure). Returns `{:payload v :consumed n}` or nil if the
  framing is short or the tag does not verify -- a caller must treat nil as a
  fatal protocol error, never as an empty read."
  [gcm-decrypt key iv seq wire]
  (when (>= (count wire) 4)
    (let [packet-length (+ (* 16777216 (nth wire 0)) (* 65536 (nth wire 1))
                           (* 256 (nth wire 2)) (nth wire 3))
          total (+ 4 packet-length tag-len)]
      (when (and (>= packet-length (+ 1 4)) (<= total (count wire)))
        (let [aad (subvec (vec wire) 0 4)
              ciphertext (subvec (vec wire) 4 (+ 4 packet-length))
              tag (subvec (vec wire) (+ 4 packet-length) total)
              plaintext (gcm-decrypt key (nonce iv seq) aad ciphertext tag)]
          (when plaintext
            (let [padding-length (first plaintext)
                  payload-len (- packet-length padding-length 1)]
              (when (and (>= padding-length 4) (>= payload-len 0))
                {:payload (subvec (vec plaintext) 1 (+ 1 payload-len))
                 :consumed total}))))))))
