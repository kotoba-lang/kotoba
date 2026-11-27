(ns kotoba.ontology-viz.escape
  "Pure .cljc escaping, ID sanitization, cross-runtime canonical number
  formatting, and deterministic JSON encoding.

  Zero external dependencies; guarantees byte-identical outputs across JVM
  Clojure, Babashka, nbb, and ClojureScript."
  (:require [clojure.string :as str]))

(defn strip-control-chars
  "Remove NUL and XML 1.0 illegal control characters (0x00-0x08, 0x0B, 0x0C,
  0x0E-0x1F, 0x7F), preserving tab (0x09), LF (0x0A), and CR (0x0D)."
  [s]
  (if (nil? s)
    ""
    (let [text (str s)]
      (str/replace text #"[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]" ""))))

(defn escape-xml
  "Escape XML/SVG/HTML special characters after stripping illegal control chars."
  [s]
  (-> (strip-control-chars s)
      (str/replace "&" "&amp;")
      (str/replace "<" "&lt;")
      (str/replace ">" "&gt;")
      (str/replace "\"" "&quot;")
      (str/replace "'" "&#39;")))

(def escape-html
  "Alias of `escape-xml` for HTML text and attribute content."
  escape-xml)

(defn escape-attr
  "Escape an XML/HTML attribute value, collapsing CR/LF into spaces."
  [s]
  (-> (escape-xml s)
      (str/replace "\r" " ")
      (str/replace "\n" " ")))

(defn sanitize-id
  "Produce a deterministic, safe DOM/SVG identifier fragment from `raw`."
  [raw]
  (let [cleaned (-> (strip-control-chars raw)
                    (str/replace #"[^A-Za-z0-9_.:-]" "_"))]
    (if (str/blank? cleaned) "id" cleaned)))

(defn truncate-display
  "Safely truncate a string for compact visual badges (e.g. CID pills)."
  [s max-len]
  (let [text (strip-control-chars s)]
    (if (<= (count text) max-len)
      text
      (let [keep-n (max 1 (- max-len 3))]
        (str (subs text 0 keep-n) "...")))))

(defn short-cid
  "Format a CIDv1 string for compact display, e.g. bafyrei...abcd."
  [cid]
  (let [text (strip-control-chars cid)
        n (count text)]
    (if (<= n 18)
      text
      (str (subs text 0 10) "..." (subs text (- n 6))))))

;; ── Cross-runtime canonical number formatting ────────────────────────────────

(defn finite-number?
  "True when `x` is a finite number (not NaN or +/-Infinity)."
  [x]
  (and (number? x)
       #?(:clj (not (or (Double/isNaN (double x))
                        (Double/isInfinite (double x))))
          :cljs (js/Number.isFinite x))))

(defn round-int
  "Portable nearest-integer rounding across JVM Clojure, Babashka, and CLJS/nbb."
  [x]
  #?(:clj (Math/round (double x))
     :cljs (js/Math.round x)))

(defn canonical-decimal-str
  "Format a finite number without 4-decimal rounding, matching ECMAScript
  `String(value)` / Yataverse `toDagCborSafe` across JVM Clojure, Babashka,
  nbb, and ClojureScript. Integers and integer-valued floats (e.g. `120.0`,
  `-0.0`) render without `.0` (`\"120\"`, `\"0\"`)."
  [x]
  (when-not (finite-number? x)
    (throw (ex-info (str "non-finite number cannot be formatted: " (pr-str x))
                    {:reason :invalid-number :value x})))
  (cond
    (integer? x) (str x)
    :else
    #?(:cljs (let [d (double x)]
               (if (zero? d) "0" (js/String d)))
       :clj (let [d (double x)]
              (if (zero? d)
                "0"
                (let [r (round-int d)]
                  (if (and (== d (double r))
                           (<= -9007199254740991 r 9007199254740991))
                    (str r)
                    (let [abs-d (Math/abs d)]
                      (if (and (>= abs-d 1.0e-6) (< abs-d 1.0e21))
                        (.toPlainString (.stripTrailingZeros (java.math.BigDecimal/valueOf d)))
                        (let [s (str d)
                              [mant exp] (str/split s #"E")
                              mant-clean (if (str/ends-with? mant ".0")
                                           (subs mant 0 (- (count mant) 2))
                                           mant)
                              exp-int (Long/parseLong exp)
                              exp-str (if (neg? exp-int) (str "e" exp-int) (str "e+" exp-int))]
                          (str mant-clean exp-str)))))))))))

(defn fmt-num
  "Format a finite number for SVG layout coordinates identically across JVM,
  Babashka, and CLJS/nbb. Integers and integer-valued floats (e.g. `120.0`)
  always render without `.0` (`\"120\"`). Non-integer floats round to at most 4
  decimal places with trailing fractional zeros stripped."
  [x]
  (when-not (finite-number? x)
    (throw (ex-info (str "non-finite number cannot be formatted: " (pr-str x))
                    {:reason :invalid-number :value x})))
  (if (integer? x)
    (str x)
    (let [scaled (round-int (* (double x) 10000.0))
          neg? (neg? scaled)
          abs-scaled (if neg? (- scaled) scaled)
          whole (quot abs-scaled 10000)
          frac (rem abs-scaled 10000)]
      (if (zero? frac)
        (if (and neg? (pos? whole)) (str "-" whole) (str whole))
        (let [frac-raw (str frac)
              padded (str (apply str (repeat (- 4 (count frac-raw)) "0")) frac-raw)
              trimmed (str/replace padded #"0+$" "")]
          (str (when neg? "-") whole "." trimmed))))))

;; ── Pure deterministic JSON encoder ──────────────────────────────────────────

(defn- hex4 [code]
  (let [hex #?(:clj (Integer/toHexString code)
               :cljs (.toString code 16))
        pad (apply str (repeat (max 0 (- 4 (count hex))) "0"))]
    (str pad hex)))

(defn- escape-json-string [s]
  (let [text (str s)
        n (count text)]
    (loop [i 0
           acc (transient ["\""])]
      (if (= i n)
        (apply str (persistent! (conj! acc "\"")))
        (let [ch (.charAt text i)
              code #?(:clj (int ch) :cljs (.charCodeAt text i))
              rep (cond
                    (= ch \") "\\\""
                    (= ch \\) "\\\\"
                    (= ch \backspace) "\\b"
                    (= ch \formfeed) "\\f"
                    (= ch \newline) "\\n"
                    (= ch \return) "\\r"
                    (= ch \tab) "\\t"
                    (< code 0x20) (str "\\u" (hex4 code))
                    (= code 0x2028) "\\u2028"
                    (= code 0x2029) "\\u2029"
                    :else (str ch))]
          (recur (inc i) (conj! acc rep)))))))

(defn- json-key-str [k]
  (cond
    (string? k) k
    (keyword? k) (if (namespace k)
                   (str (namespace k) "/" (name k))
                   (name k))
    (symbol? k) (str k)
    :else (str k)))

(defn json-encode
  "Deterministically encode Clojure/ClojureScript data to compact JSON.
  Map keys are sorted lexicographically and finite numbers use full-precision
  `canonical-decimal-str` (matching DAG-CBOR `toDagCborSafe` and JS
  `JSON.stringify`), so outputs are byte-identical across JVM, Babashka, nbb,
  and ClojureScript without 4-decimal rounding drift."
  [v]
  (cond
    (nil? v) "null"
    (true? v) "true"
    (false? v) "false"
    (number? v) (if (finite-number? v) (canonical-decimal-str v) "null")
    (string? v) (escape-json-string v)
    (keyword? v) (escape-json-string (json-key-str v))
    (symbol? v) (escape-json-string (str v))
    (map? v)
    (let [entries (->> v
                       (map (fn [[k val]] [(json-key-str k) val]))
                       (sort-by first))]
      (str "{"
           (str/join "," (map (fn [[ks val]]
                                (str (escape-json-string ks) ":" (json-encode val)))
                              entries))
           "}"))
    (or (sequential? v) (set? v))
    (let [items (if (set? v)
                  (sort-by str v)
                  v)]
      (str "[" (str/join "," (map json-encode items)) "]"))
    :else
    (escape-json-string (str v))))

(defn json-for-script
  "Encode `v` as JSON safe to embed inside an HTML `<script>` element.
  Escapes `<`, `>`, `&`, and `/` so `</script>` or `<!--` injection cannot
  break out of the script tag."
  [v]
  (-> (json-encode v)
      (str/replace "<" "\\u003c")
      (str/replace ">" "\\u003e")
      (str/replace "&" "\\u0026")
      (str/replace "/" "\\/")))
