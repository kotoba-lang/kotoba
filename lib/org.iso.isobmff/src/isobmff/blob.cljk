(ns isobmff.blob
  "Content-address (CID-like) placeholder. Deterministic: same byte vector →
   same id. Real deployments should replace this with a cryptographic CID
   (e.g. blake3-based BlobManifest CID); this exists only so sample/packet
   references have a stable identity to test against.

   Extracted from kotoba-lang/utsushi (utsushi.blob, ADR-2606272200) as
   part of `org-iso-isobmff`."
  )

(defn content-id
  "Deterministic content id string for a byte vector. `isobmff-fnv1a32-<8hex>`."
  [bytes]
  (let [;; FNV-1a 32bit: h = (h XOR byte) * 16777619 (= h<<24+h<<8+h<<7+h<<4+h<<1+h)
        h (reduce
           (fn [h x]
             (let [h (bit-xor h (bit-and (int x) 0xff))]
               (bit-and (+ h (bit-shift-left h 1) (bit-shift-left h 4)
                           (bit-shift-left h 7) (bit-shift-left h 8)
                           (bit-shift-left h 24))
                        0xffffffff)))
           2166136261
           bytes)
        digits "0123456789abcdef"
        hex8 (apply str (map (fn [shift]
                               (nth digits (bit-and (unsigned-bit-shift-right h shift) 0xf)))
                             [28 24 20 16 12 8 4 0]))]
    (str "isobmff-fnv1a32-" hex8)))
