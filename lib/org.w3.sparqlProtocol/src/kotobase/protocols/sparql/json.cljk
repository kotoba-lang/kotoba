(ns kotobase.protocols.sparql.json
  "Minimal, dependency-free EDN->JSON encoder -- this repo's own copy of
  the pattern `kotoba-lang/kotobase-protocols`'s `kotobase.protocols.json`
  establishes for wire-protocol handlers in this family (read before
  depending on this repo: that repo's `json.cljc` docstring is the
  original statement of the \"no host-JSON dependency, same handler runs
  under nbb/cljs and the :clj compat suite\" rationale).

  This is a deliberate VENDORED COPY, not a dependency on
  `kotobase-protocols` -- ADR-2607172300's dependency table for
  `org-w3-sparql-protocol` lists exactly two deps (`kotoba-lang/sparql`,
  `kotoba-lang/kotobase-query`); `kotobase-protocols` is this effort's
  STYLE reference for wire-protocol handler shape, not a code dependency
  of this repo. Only `encode` is needed here (SPARQL JSON Results output
  only; nothing in this protocol's request path is JSON to PARSE -- GET
  query params and POST bodies are SPARQL query text or form-urlencoded,
  never JSON)."
  (:require [kotoba.lang.text :as str]))

(defn- escape-str [s]
  (str/replace s #"[\"\\\u0000-\u001f]"
               (fn [c]
                 (case c
                   "\"" "\\\"" "\\" "\\\\" "\n" "\\n" "\r" "\\r"
                   "\t" "\\t" "\b" "\\b" "\f" "\\f"
                   (let [code #?(:clj (int (.charAt ^String c 0))
                                 :cljs (.charCodeAt c 0))
                         hexs #?(:clj (format "%04x" code)
                                 :cljs (.padStart (.toString code 16) 4 "0"))]
                     (str "\\u" hexs))))))

(defn encode
  "EDN value -> JSON string. Map keys may be keywords or strings; keywords
  render as their bare name (no leading colon)."
  [x]
  (cond
    (nil? x)     "null"
    (true? x)    "true"
    (false? x)   "false"
    (number? x)  (str x)
    (string? x)  (str "\"" (escape-str x) "\"")
    (keyword? x) (str "\"" (escape-str (name x)) "\"")
    (map? x)     (str "{"
                      (str/join "," (map (fn [[k v]]
                                           (str (encode (if (keyword? k) (name k) (str k)))
                                                ":" (encode v)))
                                         x))
                      "}")
    (sequential? x) (str "[" (str/join "," (map encode x)) "]")
    :else (encode (str x))))
