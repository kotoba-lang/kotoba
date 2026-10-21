(ns kotoba.string.java-whitespace
  "java-whitespace? -- one definition, addressed on its own.

  Split out of kotoba.lang.text on 2026-09-09. The unit here is the
  DEFINITION, not the library: this repo holds java-whitespace? and names, in its
  deps.edn, exactly the definitions java-whitespace? reaches. Nothing else."
  )

(defn java-whitespace?
  "The whitespace class this namespace trims: exactly what
  `java.lang.Character/isWhitespace` accepts, written out.

  Included: the C0 controls U+0009-U+000D and the four separators
  U+001C-U+001F, SPACE, and the Unicode space separators.
  DELIBERATELY EXCLUDED: the non-breaking spaces U+00A0, U+2007 and U+202F --
  Java does not consider them whitespace, JavaScript's `\\s` does, and this
  namespace answers the same on both hosts by choosing Java's."
  [ch]
  (let [c #?(:clj (int ch) :cljs (.charCodeAt (str ch) 0))]
    (or (<= 9 c 13)
        (<= 28 c 31)
        (= c 32)
        (= c 0x1680)
        (<= 0x2000 c 0x2006)
        (<= 0x2008 c 0x200A)
        (= c 0x2028)
        (= c 0x2029)
        (= c 0x205F)
        (= c 0x3000))))
