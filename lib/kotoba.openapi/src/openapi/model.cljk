(ns openapi.model
  "OpenAPI 3 as EDN: a plain-data representation of an OpenAPI 3 specification, plus
  the graph queries a validator or request builder needs. No I/O, no third-party deps —
  portable .cljc (JVM, ClojureScript, SCI).

  A spec is a map keyed by namespaced `:openapi/*` keys:

    {:openapi/info    {:openapi/title \"Pets\" :openapi/version \"1.0\"}
     :openapi/paths   {\"/pets/{id}\" {:get {:openapi/operation-id \"getPet\"
                                             :openapi/parameters  [{:openapi/name \"id\"
                                                                    :openapi/in   :path
                                                                    :openapi/required true
                                                                    :openapi/schema {\"type\" \"string\"}}]
                                             :openapi/responses {\"200\" {:openapi/description \"ok\"}}}}}
     :openapi/components {}}")

;; --- queries ---

(defn operations
  "Return a seq of {:path path :method method-kw :op op-map} for every operation
  declared in :openapi/paths. Method is a keyword (:get :post …)."
  [model]
  (for [[path methods] (:openapi/paths model)
        [method op]    methods]
    {:path path :method method :op op}))

(defn operation-by-id
  "Find the first operation whose :openapi/operation-id equals `operation-id`.
  Returns {:path :method :op} or nil."
  [model operation-id]
  (->> (operations model)
       (filter #(= operation-id (get-in % [:op :openapi/operation-id])))
       first))

(defn parameters-for
  "Return the parameter vector for an operation map (defaults to [])."
  [op]
  (get op :openapi/parameters []))

(defn path-params
  "Parse a path template like \"/a/{x}/{y}\" and return a vector of param-name strings.
  Order matches left-to-right occurrence in the template."
  [path]
  (->> (re-seq #"\{([^}]+)\}" path)
       (mapv second)))
