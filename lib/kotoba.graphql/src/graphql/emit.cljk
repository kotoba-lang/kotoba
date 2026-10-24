(ns graphql.emit
  "EDN hiccup-style GraphQL definitions to SDL."
  (:require [kotoba.lang.text :as str]))

(defn- valid-graphql-name?
  "Matches the GraphQL spec's Name production: /[_A-Za-z][_0-9A-Za-z]*/."
  [s]
  (boolean (re-matches #"[_A-Za-z][_0-9A-Za-z]*" s)))

(defn- id
  "Coerce `x` (a keyword or string) to a GraphQL Name, splicing it verbatim
  into the emitted SDL. Every field/type/enum-value/argument name funnels
  through this, so it's the single choke point that must reject anything
  outside the Name grammar -- a caller-supplied string containing `}` `{`
  or a newline could otherwise close the current block and inject an
  entirely new top-level SDL definition (verified: the resulting document
  round-trips through this repo's own graphql.sdl/parse-schema, which
  registers the injected type as legitimate)."
  [x]
  (let [s (if (keyword? x) (name x) (str x))]
    (when-not (valid-graphql-name? s)
      (throw (ex-info "graphql: invalid GraphQL Name (must match [_A-Za-z][_0-9A-Za-z]*)"
                       {:name s})))
    s))

(defn- gtype
  "Coerce `t` to a GraphQL type reference. Like `id`, but also allows a
  single trailing `!` (the non-null marker, e.g. `ID!` -- pervasive
  throughout this library's own test suite) after an otherwise-valid Name."
  [t]
  (cond
    (and (vector? t) (= :list (first t))) (str "[" (gtype (second t)) "]")
    (and (vector? t) (= :list! (first t))) (str "[" (gtype (second t)) "]!")
    :else
    (let [s (if (keyword? t) (name t) (str t))
          non-null? (str/ends-with? s "!")
          base (cond-> s non-null? (subs 0 (dec (count s))))]
      (when-not (valid-graphql-name? base)
        (throw (ex-info (str "graphql: invalid GraphQL type name (must match "
                              "[_A-Za-z][_0-9A-Za-z]*, optionally suffixed with a single !)")
                         {:name s})))
      s)))

(defn field
  "Compile one EDN GraphQL field definition to SDL."
  [[_ nm a b]]
  (let [[args typ] (if (map? a) [a b] [nil a])]
    (str (id nm)
         (when (seq args)
           (str "(" (str/join ", " (for [[an at] args] (str (id an) ": " (gtype at)))) ")"))
         ": " (gtype typ))))

(defn- block [fields] (str/join "\n" (map #(str "  " (field %)) fields)))

(defn item
  "Compile one EDN GraphQL definition to an SDL string."
  [form]
  (let [[op & more] form]
    (case op
      :type (let [[nm & r] more
                  opts (when (map? (first r)) (first r))
                  fields (if opts (rest r) r)]
              (str "type " (id nm)
                   (when (seq (:implements opts))
                     (str " implements " (str/join " & " (map id (:implements opts)))))
                   " {\n" (block fields) "\n}"))
      :interface (let [[nm & fields] more] (str "interface " (id nm) " {\n" (block fields) "\n}"))
      :input (let [[nm & fields] more] (str "input " (id nm) " {\n" (block fields) "\n}"))
      :enum (let [[nm & vals] more]
              (str "enum " (id nm) " {\n" (str/join "\n" (map #(str "  " (id %)) vals)) "\n}"))
      :union (let [[nm & types] more] (str "union " (id nm) " = " (str/join " | " (map id types))))
      :scalar (str "scalar " (id (first more)))
      :schema (str "schema {\n"
                   (str/join "\n" (for [[k v] (first more)] (str "  " (id k) ": " (id v)))) "\n}")
      (str (id op)))))

(defn graphql
  "Compile a sequence of GraphQL definitions to an SDL document string."
  [& defs]
  (str/join "\n\n" (map item defs)))
