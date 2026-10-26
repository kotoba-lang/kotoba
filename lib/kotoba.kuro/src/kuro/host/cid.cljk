(ns kuro.host.cid
  "CIDv1 / raw / sha2-256 content addressing for terminal output.

  `kuro.terminal` records `:stdout-cid` / `:stderr-cid` but never computes
  them — it is pure and has no hash seam. This namespace is the host side of
  that split, so a receipt can name what a command produced without carrying
  the bytes.

  ClojureScript-only (not `.cljc`): the hash seam is `node:crypto`. The
  base32 encoder is a port of `kotoba-lang/kotobase-client`'s
  `kotobase.cid/base32-lower-no-pad` (same 32-bit accumulator draining 5-bit
  groups MSB-first), so a CID minted here is byte-identical to one minted by
  the kotobase edge for the same bytes. The codec differs on purpose: kotobase
  addresses dag-cbor graphs (0x71), terminal output is opaque bytes (raw,
  0x55)."
  (:require ["node:crypto" :as crypto]))

(def ^:private b32-alphabet "abcdefghijklmnopqrstuvwxyz234567")

(defn base32-lower-no-pad
  "CIDv1 base32-lower, no padding (multibase 'b' payload)."
  [^js bytes]
  (let [{:keys [bits value out]}
        (reduce
         (fn [{:keys [bits value out]} b]
           (let [value (bit-or (bit-shift-left value 8) b)
                 bits (+ bits 8)]
             (loop [bits bits out out]
               (if (>= bits 5)
                 (recur (- bits 5)
                        (str out (nth b32-alphabet
                                      (bit-and (unsigned-bit-shift-right value (- bits 5)) 31))))
                 {:bits bits :value value :out out}))))
         {:bits 0 :value 0 :out ""}
         (array-seq bytes))]
    (if (pos? bits)
      (str out (nth b32-alphabet (bit-and (bit-shift-left value (- 5 bits)) 31)))
      out)))

(defn sha256
  "SHA-256 digest of a Buffer/Uint8Array, as a Uint8Array."
  [^js buf]
  (-> (crypto/createHash "sha256") (.update buf) (.digest)))

(defn raw-cid
  "CIDv1 / raw (0x55) / sha2-256 of `buf`, multibase base32-lower ('b').

  Header is 0x01 0x55 0x12 0x20, which always renders as the `bafkrei` prefix
  — the same string IPFS gives for `ipfs add --raw-leaves` of these bytes."
  [^js buf]
  (let [digest (sha256 buf)
        cid (js/Uint8Array. 36)]
    (aset cid 0 0x01)
    (aset cid 1 0x55)
    (aset cid 2 0x12)
    (aset cid 3 0x20)
    (.set cid digest 4)
    (str "b" (base32-lower-no-pad cid))))

(defn text-cid
  "raw-cid of the UTF-8 encoding of `s`."
  [^string s]
  (raw-cid (js/Buffer.from s "utf8")))

(defn sha256-raw-cid
  "raw-cid of a Uint8Array — the browser/Worker-facing name.

  `raw-cid` above is typed against node:crypto's Buffer (the Node host path).
  This fn accepts a plain Uint8Array so the same mint can run anywhere the
  digest is supplied (the OPFS Worker computes sha-256 via WebCrypto and
  calls this with the digest bytes; see kuro.host.opfs). Header 0x01 0x55
  0x12 0x20 = CIDv1 / raw / sha2-256, always `bafkrei…`."
  [^js buf]
  (let [digest (js/Uint8Array. (.from js/Array buf))
        cid (js/Uint8Array. 36)]
    (aset cid 0 0x01)
    (aset cid 1 0x55)
    (aset cid 2 0x12)
    (aset cid 3 0x20)
    (.set cid digest 4)
    (str "b" (base32-lower-no-pad cid))))
