(ns kotoba.string.ascii-ws
  "ascii-ws? -- one definition, addressed on its own.

  Split out of kotoba.lang.text on 2026-09-09. The unit here is the
  DEFINITION, not the library: this repo holds ascii-ws? and names, in its
  deps.edn, exactly the definitions ascii-ws? reaches. Nothing else."
  )

(defn ascii-ws?
  "The kernel's whitespace class: ASCII space, tab, newline, CR, FF, VT.
  Unicode spaces (U+00A0, U+3000, ...) are NOT whitespace here, where
  clojure.string/trim's Character/isWhitespace answers for them."
  [^long cp]
  (contains? #{32 9 10 13 12 11} cp))
