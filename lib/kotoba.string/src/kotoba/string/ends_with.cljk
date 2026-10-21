(ns kotoba.string.ends-with
  "ends-with? -- one definition, addressed on its own.

  Split out of kotoba.lang.text on 2026-09-09. The unit here is the
  DEFINITION, not the library: this repo holds ends-with? and names, in its
  deps.edn, exactly the definitions ends-with? reaches. Nothing else."
  )

(defn ends-with? [s suffix]
  #?(:clj  (.endsWith ^String (str s) ^String (str suffix))
     :cljs (.endsWith (str s) (str suffix))))
