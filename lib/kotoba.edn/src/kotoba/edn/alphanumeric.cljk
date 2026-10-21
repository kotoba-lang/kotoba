(ns kotoba.edn.alphanumeric
  "alphanumeric? -- addressed on its own.

  Split out of kotoba.lang.edn on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  )

(defn alphanumeric? [ch]
  (let [c #?(:clj (int ch) :cljs (.charCodeAt (str ch) 0))]
    (or (<= 48 c 57) (<= 65 c 90) (<= 97 c 122))))
