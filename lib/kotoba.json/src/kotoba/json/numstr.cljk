(ns kotoba.json.numstr
  "numstr -- addressed on its own.

  Split out of json.core on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  )

(defn numstr [n]
  #?(:clj
     (if (and (float? n) (== (double n) (Math/rint (double n))))
       (str (long n))
       (str n))
     :cljs
     (if (and (number? n) (js/Number.isInteger n))
       (str (js/Math.trunc n))
       (str n))))
