(ns h264.rbsp
  "Remove H.264 emulation-prevention bytes: any 0x000003 byte triple inside
   a NAL unit has the 0x03 stripped (it exists only so the encoded bitstream
   never accidentally contains a byte sequence that looks like a start
   code). This must run before any bit-level (Exp-Golomb) parsing of NAL
   payload — SPS/PPS parsing reads the *unescaped* RBSP, not the raw NAL
   bytes. Pure cljc.

   New implementation as part of the kotoba-lang reverse-domain
   media/graphics standards-substrate split (com-junkawasaki/root)."
  )

(defn unescape
  "Remove emulation-prevention 0x03 bytes from `nal-bytes` (a byte vector
   that INCLUDES the 1-byte NAL header at index 0 — pass the header through
   unchanged, unescape only applies to bytes after it in the real spec, but
   including it here is harmless since 00 00 03 can't start at index 0)."
  [nal-bytes]
  (let [n (count nal-bytes)]
    (loop [i 0 zeros 0 out (transient [])]
      (if (>= i n)
        (persistent! out)
        (let [b (nth nal-bytes i)]
          (if (and (= zeros 2) (= b 3) (< (inc i) n) (<= (nth nal-bytes (inc i)) 3))
            (recur (inc i) 0 out)                          ; drop the 0x03
            (recur (inc i) (if (zero? b) (inc zeros) 0) (conj! out b))))))))

(defn escape
  "Insert emulation-prevention 0x03 bytes — the encode-side inverse of
   `unescape`. Whenever two zero bytes have just been emitted and the next
   byte to emit is <= 0x03 (which would otherwise be misread as a start
   code, or as an escape sequence itself), a 0x03 byte is inserted before
   it and the zero-run counter resets. `escape` then `unescape` is the
   identity on any byte sequence (round-trip verified in rbsp_test.clj)."
  [rbsp-bytes]
  (let [n (count rbsp-bytes)]
    (loop [i 0 zeros 0 out (transient [])]
      (if (>= i n)
        (persistent! out)
        (let [b (nth rbsp-bytes i)
              needs-escape? (and (= zeros 2) (<= b 3))
              out'   (if needs-escape? (conj! out 3) out)
              out''  (conj! out' b)
              zeros' (if needs-escape? (if (zero? b) 1 0) (if (zero? b) (inc zeros) 0))]
          (recur (inc i) zeros' out''))))))
