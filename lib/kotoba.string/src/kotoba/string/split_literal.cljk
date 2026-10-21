(ns kotoba.string.split-literal
  "split-literal -- one definition, addressed on its own.

  Split out of kotoba.lang.text on 2026-09-09. The unit here is the
  DEFINITION, not the library: this repo holds split-literal and names, in its
  deps.edn, exactly the definitions split-literal reaches. Nothing else."
  )

(defn split-literal
  "Split s on the LITERAL separator (no regex), portable. The kernel's
  segment face over the same walk its index-of does."
  [s sep]
  (if (empty? sep)
    [s]
    (loop [i 0 start 0 parts []]
      (if (> (+ i (count sep)) (count s))
        (conj parts (subs s start))
        (if (= (subs s i (+ i (count sep))) sep)
          (recur (+ i (count sep)) (+ i (count sep))
                 (conj parts (subs s start i)))
          (recur (inc i) start parts))))))
