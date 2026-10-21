(ns kotoba.string.truncate
  "truncate -- one definition, addressed on its own.

  Split out of kotoba.lang.text on 2026-09-09. The unit here is the
  DEFINITION, not the library: this repo holds truncate and names, in its
  deps.edn, exactly the definitions truncate reaches. Nothing else."
  )

(defn truncate
  "Truncate `s` to `max-len` chars. If `ellipsis` is given and `s` is longer
  than `max-len`, the result is `max-len` chars including the ellipsis."
  ([s max-len] (subs s 0 (min (count s) max-len)))
  ([s max-len ellipsis]
   (if (<= (count s) max-len)
     s
     (str (subs s 0 (max 0 (- max-len (count ellipsis)))) ellipsis))))
