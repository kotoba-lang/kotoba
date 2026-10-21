(ns kotoba.string.utf8-byte-offsets
  "utf8-byte-offsets -- one definition, addressed on its own.

  Split out of kotoba.lang.text on 2026-09-09. The unit here is the
  DEFINITION, not the library: this repo holds utf8-byte-offsets and names, in its
  deps.edn, exactly the definitions utf8-byte-offsets reaches. Nothing else."
  )

(defn utf8-byte-offsets
  "Byte offset of each code point index in cps (one past the end for the
  count). The kernel's index answers are UTF-8 byte offsets; this is how the
  oracle converts its code point indexes to the same units."
  [cps]
  (let [width (fn [cp] (cond (< cp 0x80) 1 (< cp 0x800) 2 (< cp 0x10000) 3 :else 4))]
    (loop [i 0 acc 0 offsets [0]]
      (if (= i (count cps))
        offsets
        (recur (inc i) (+ acc (width (nth cps i))) (conj offsets (+ acc (width (nth cps i)))))))))
