(ns kotoba.glyph.text
  "Codepoint-correct string utilities. Rust `char` is always one Unicode
  scalar value; JVM/JS strings are UTF-16 code units, so naive char-by-char
  iteration splits supplementary-plane codepoints (most emoji, U+10000+)
  into two surrogate halves. `codepoint-seq` restores 1-codepoint-per-
  element iteration on both hosts so the rest of `kotoba.glyph.*` can treat
  a codepoint the way the original Rust code did.")

(defn codepoint-seq
  "Split `s` into a seq of single-codepoint strings, correctly handling
  UTF-16 surrogate pairs."
  [s]
  #?(:clj (let [^String s s
                n (.length s)]
            (loop [i 0 out (transient [])]
              (if (>= i n)
                (persistent! out)
                (let [cp (.codePointAt s i)
                      w  (Character/charCount cp)]
                  (recur (+ i w) (conj! out (subs s i (+ i w))))))))
     :cljs (vec (js/Array.from s))))

(defn codepoint-int
  "The Unicode scalar value of a one-codepoint string `s`."
  [s]
  #?(:clj (.codePointAt ^String s 0)
     :cljs (.codePointAt s 0)))

(defn char-code
  "Normalize `x` (an int codepoint, a Clojure char, or a one-codepoint
  string) to its integer Unicode scalar value."
  [x]
  (cond
    (integer? x) x
    (char? x) (int x)
    (string? x) (codepoint-int x)
    :else (throw (ex-info "char-code: unsupported type" {:value x}))))
