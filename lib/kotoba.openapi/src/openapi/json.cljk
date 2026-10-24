(ns openapi.json
  "Bidirectional conversion between a parsed OpenAPI 3 map with string keys (as you
  would get from any JSON parser) and the namespaced EDN model used internally.

  `from-data` — string-keyed parsed map → namespaced EDN model
  `to-data`   — namespaced EDN model → string-keyed map (round-trippable)

  No I/O, no third-party deps — portable .cljc (JVM, ClojureScript, SCI).")

;; --- from-data helpers ---

(defn- param-from-data [p]
  (cond-> {}
    (contains? p "name")     (assoc :openapi/name     (get p "name"))
    (contains? p "in")       (assoc :openapi/in       (keyword (get p "in")))
    (contains? p "required") (assoc :openapi/required (get p "required"))
    (contains? p "schema")   (assoc :openapi/schema   (get p "schema"))
    (contains? p "$ref")     (assoc :$ref              (get p "$ref"))))

(defn- response-from-data [r]
  (cond-> {}
    (contains? r "description") (assoc :openapi/description (get r "description"))))

(defn- op-from-data [op]
  (cond-> {}
    (contains? op "operationId")
    (assoc :openapi/operation-id (get op "operationId"))

    (contains? op "parameters")
    (assoc :openapi/parameters (mapv param-from-data (get op "parameters")))

    (contains? op "responses")
    (assoc :openapi/responses
           (into {} (for [[k v] (get op "responses")]
                      [k (response-from-data v)])))))

(defn- methods-from-data [methods]
  (into {} (for [[method op] methods]
             [(keyword method) (op-from-data op)])))

(defn from-data
  "Convert a parsed OpenAPI 3 map with string keys (e.g. from clojure.data.json/read-str)
  to the namespaced EDN model. Only top-level keys `info`, `paths`, and `components`
  are translated; extensions and unknown keys are dropped."
  [data]
  (cond-> {}
    (contains? data "info")
    (assoc :openapi/info
           (let [info (get data "info")]
             (cond-> {}
               (contains? info "title")   (assoc :openapi/title   (get info "title"))
               (contains? info "version") (assoc :openapi/version (get info "version")))))

    (contains? data "paths")
    (assoc :openapi/paths
           (into {} (for [[path methods] (get data "paths")]
                      [path (methods-from-data methods)])))

    (contains? data "components")
    (assoc :openapi/components (get data "components"))))

;; --- to-data helpers ---

(defn- param-to-data [p]
  (cond-> {}
    (contains? p :openapi/name)     (assoc "name"     (:openapi/name p))
    (contains? p :openapi/in)       (assoc "in"       (name (:openapi/in p)))
    (contains? p :openapi/required) (assoc "required" (:openapi/required p))
    (contains? p :openapi/schema)   (assoc "schema"   (:openapi/schema p))
    (contains? p :$ref)             (assoc "$ref"      (:$ref p))))

(defn- response-to-data [r]
  (cond-> {}
    (contains? r :openapi/description) (assoc "description" (:openapi/description r))))

(defn- op-to-data [op]
  (cond-> {}
    (contains? op :openapi/operation-id)
    (assoc "operationId" (:openapi/operation-id op))

    (contains? op :openapi/parameters)
    (assoc "parameters" (mapv param-to-data (:openapi/parameters op)))

    (contains? op :openapi/responses)
    (assoc "responses"
           (into {} (for [[k v] (:openapi/responses op)]
                      [k (response-to-data v)])))))

(defn to-data
  "Convert the namespaced EDN model back to a string-keyed map.
  Round-trips cleanly with `from-data` for the fields this library models."
  [model]
  (cond-> {}
    (contains? model :openapi/info)
    (assoc "info"
           (let [info (:openapi/info model)]
             (cond-> {}
               (contains? info :openapi/title)   (assoc "title"   (:openapi/title info))
               (contains? info :openapi/version) (assoc "version" (:openapi/version info)))))

    (contains? model :openapi/paths)
    (assoc "paths"
           (into {} (for [[path methods] (:openapi/paths model)]
                      [path (into {} (for [[method op] methods]
                                       [(name method) (op-to-data op)]))])))

    (contains? model :openapi/components)
    (assoc "components" (:openapi/components model))))
