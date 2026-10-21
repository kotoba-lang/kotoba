(ns kotoba.io.to-bytes
  "to-bytes -- addressed on its own.

  Split out of kotoba.lang.io on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  )

(defn to-bytes
  "Materialize the buffer as a fresh byte array."
  [buf]
  (let [v @buf
        n (count v)
        arr #?(:clj (byte-array n) :cljs (js/Uint8Array. n))]
    (reduce-kv (fn [_ i b] #?(:clj (aset-byte arr i (unchecked-byte b))
                              :cljs (aset arr i b)))
               arr v)
    arr))
