(ns kotoba.string.pad-left-text
  "pad-left-text -- one definition, addressed on its own.

  Split out of kotoba.lang.text on 2026-09-09. The unit here is the
  DEFINITION, not the library: this repo holds pad-left-text and names, in its
  deps.edn, exactly the definitions pad-left-text reaches. Nothing else."
  (:require [kotoba.string.codepoints-of :refer [codepoints-of]]))

(defn pad-left-text
  "Oracle for the kernel's pad-left-text: prepend fill until the string's
  BYTE length reaches width. The kernel measures bytes; this measures code
  points, which agree on ASCII fills -- the divergence the kernel names."
  [s width fill]
  (let [w (count (codepoints-of s))]
    (if (>= w width)
      s
      (if (empty? fill)
        s
        (loop [acc s]
          (if (>= (count (codepoints-of acc)) width)
            acc
            (recur (str fill acc))))))))
