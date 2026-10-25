(ns toml.core
  "TOML as data — 'hiccup for config'. TOML is essentially an ordered nested map, so a Clojure map maps
   onto it directly — a Cargo.toml / pyproject.toml / config is composable data you fork and diff. A
   config sibling to kotoba.yaml/kotoba.json. `.cljc`.

   A map compiles to TOML: scalar/array/inline-table values become `key = value`, nested maps become
   `[table]` sections (dotted on nesting), and a vector-of-maps becomes an array of tables `[[name]]`.
   TOML's rule that bare key/values precede sub-tables is handled automatically.

     {:title \"x\"
      :package {:name \"kami\" :version \"0.1.0\" :keywords [\"edn\" \"hiccup\"]}
      :bin [{:name \"app\" :path \"src/main.rs\"}]}
     ⇒  title = \"x\"
        [package]
        name = \"kami\" …
        [[bin]]
        name = \"app\" …"
  (:require [kotoba.lang.text :as str]))

(def ^:private hex-digits "0123456789ABCDEF")

(defn- hex4
  "4-digit uppercase hex for a TOML `\\uXXXX` escape (portable: bit ops +
  a lookup table, no Long/Integer interop that would only work on :clj)."
  [n]
  (apply str (for [shift [12 8 4 0]] (nth hex-digits (bit-and (bit-shift-right n shift) 0xf)))))

(defn- char-code-at [s i]
  #?(:clj (int (.charAt ^String s (int i)))
     :cljs (.charCodeAt s i)))

(defn- toml-escape-string
  "Quote+escape `s` as a TOML basic string. `pr-str` escapes the same six
  characters TOML's own \\b \\t \\n \\f \\r/\\\\/\\\" do, but passes every OTHER
  ASCII control character (0x00-0x1F except tab, and 0x7F) through raw --
  a spec-compliant TOML parser (e.g. taplo) rejects those as an invalid
  unescaped control character in a basic string, even though pr-str's
  output looks fine to the eye. Escape those via \\uXXXX instead."
  [s]
  (str \"
       (apply str
              (for [i (range (count s))]
                (let [ch   (subs s i (inc i))
                      code (char-code-at s i)]
                  (cond
                    (= ch "\"") "\\\""
                    (= ch "\\") "\\\\"
                    (= code 8)  "\\b"
                    (= code 9)  "\\t"
                    (= code 10) "\\n"
                    (= code 12) "\\f"
                    (= code 13) "\\r"
                    (or (< code 0x20) (= code 0x7f)) (str "\\u" (hex4 code))
                    :else ch))))
       \"))

(defn- scalar [v]
  (cond
    (string? v)  (toml-escape-string v)
    (boolean? v) (str v)
    (keyword? v) (toml-escape-string (name v)) ;; a keyword value → string
    (number? v)  (str v)
    (vector? v)  (str "[" (str/join ", " (map scalar v)) "]")                       ;; inline array
    (map? v)     (str "{ " (str/join ", " (for [[k vv] v] (str (name k) " = " (scalar vv)))) " }")  ;; inline table
    :else        (pr-str (str v))))

(defn- table-value? [v]                     ;; values that become [table] / [[table]] sections
  (or (map? v) (and (vector? v) (seq v) (every? map? v))))

(defn- lines [path m]
  (let [scalars (remove (comp table-value? val) m)
        tables  (filter (comp table-value? val) m)]
    (concat
      (for [[k v] scalars] (str (name k) " = " (scalar v)))
      (mapcat (fn [[k v]]
                (let [p (str (when (seq path) (str (str/join "." path) ".")) (name k))
                      sub (conj (vec path) (name k))]
                  (if (map? v)
                    (concat ["" (str "[" p "]")] (lines sub v))
                    (mapcat (fn [item] (concat ["" (str "[[" p "]]")] (lines sub item))) v))))
              tables))))

(defn toml
  "Compile an EDN map to a TOML document string."
  [m]
  (let [ls (lines [] m)
        ls (if (= "" (first ls)) (rest ls) ls)]   ;; no leading blank line when the doc starts with a table
    (str (str/join "\n" ls) "\n")))
