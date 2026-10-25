(ns iso-8583.charcode
  "One function, because one wrong assumption shows up in enough places
  in a byte-oriented codec to be worth naming.

  `(int c)` on a character gives its ASCII/Unicode code point on the
  JVM — `(int \\0)` is `48`. Under ClojureScript, a Clojure character is
  a one-character JavaScript string, and `int` on a *string* does
  numeric-string parsing, not code-point extraction: `(int \\0)` is `0`
  (`Number(\"0\")`), and `(int \\A)` is also `0` (`Number(\"A\")` is
  `NaN`, coerced to `0`). For the digit characters this codec spends
  most of its time on, numeric-string-parsing a digit character happens
  to equal that digit's *value*, which is a different number from its
  *code point* that is nonetheless plausible enough to pass unnoticed —
  exactly the failure mode `org-modbus`'s README documents for
  `(map int \"123456789\")`, and this workspace's `org-hl7-v2` hit the
  same way in its MLLP framing. `char-code` is this library's single
  fix for it; every char-to-byte conversion in this codec goes through
  it rather than bare `int`.")

(defn char-code
  [c]
  #?(:clj (int c)
     :cljs (.charCodeAt (str c) 0)))
