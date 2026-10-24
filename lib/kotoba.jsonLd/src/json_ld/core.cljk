(ns json-ld.core
  "Small EDN constructors for JSON-LD 1.1 documents.")

(def context-key (keyword "@context"))
(def id-key (keyword "@id"))
(def type-key (keyword "@type"))
(def value-key (keyword "@value"))
(def language-key (keyword "@language"))
(def list-key (keyword "@list"))
(def set-key (keyword "@set"))
(def graph-key (keyword "@graph"))
(def vocab-key (keyword "@vocab"))

(def json-ld-11
  "https://www.w3.org/TR/json-ld11/")

(defn keyword-name [x]
  (cond
    (keyword? x) (name x)
    (symbol? x) (name x)
    :else x))

(defn context
  [& entries]
  (into {} (map (fn [[k v]] [(keyword-name k) v])) (partition 2 entries)))

(defn term
  ([id] {(keyword "@id") id})
  ([id opts] (merge {(keyword "@id") id} opts)))

(defn compact-iri [prefix suffix]
  (str (keyword-name prefix) ":" (keyword-name suffix)))

(defn iri? [s]
  (and (string? s)
       (boolean (re-matches #"[A-Za-z][A-Za-z0-9+.-]*:.*" s))))

(defn node
  ([id] {id-key id})
  ([id props] (merge {id-key id} props)))

(defn typed [id props]
  (assoc props type-key id))

(defn value
  ([v] {value-key v})
  ([v opts] (merge {value-key v} opts)))

(defn lang [v language]
  (value v {language-key (keyword-name language)}))

(defn list-of [xs]
  {list-key (vec xs)})

(defn set-of [xs]
  {set-key (vec xs)})

(defn graph
  ([nodes] {graph-key (vec nodes)})
  ([ctx nodes] {context-key ctx graph-key (vec nodes)}))

(defn with-context [doc ctx]
  (assoc doc context-key ctx))

(defn json-ld-map? [x]
  (map? x))

(defn errors [doc]
  (cond-> []
    (not (map? doc))
    (conj {:error :json-ld/document-must-be-map})

    (and (map? doc) (contains? doc id-key) (not (string? (get doc id-key))))
    (conj {:error :json-ld/id-must-be-string :value (get doc id-key)})

    (and (map? doc) (contains? doc graph-key) (not (sequential? (get doc graph-key))))
    (conj {:error :json-ld/graph-must-be-sequential :value (get doc graph-key)})))

(defn validate [doc]
  (let [es (errors doc)]
    {:valid? (empty? es) :errors es}))
