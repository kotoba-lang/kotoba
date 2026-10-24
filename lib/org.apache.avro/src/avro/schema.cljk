(ns avro.schema
  "Avro schemas, which arrive as JSON inside the file that uses them.

  This is what makes Avro **self-describing** and it is the format's real
  distinguishing feature: unlike CSV, an Avro file states its own field names
  and types, so a reader needs no declared schema from the caller and cannot
  disagree with one.

  ## A schema is a JSON value of three shapes

  A string names a primitive (`\"long\"`) or a previously-defined type. An
  object carries a `type` key (`record`, `array`, `map`, `enum`, `fixed`). An
  **array is a union** — `[\"null\", \"string\"]` is the nullable string that
  most real Avro data is made of.

  ## Named types can be referenced later, so resolution needs an environment

  A record defined once as `{\"type\": \"record\", \"name\": \"Addr\", ...}` may
  appear later as just `\"Addr\"`. `resolve` therefore threads a map of
  definitions, and a name it has never seen throws rather than being treated
  as a primitive — a schema referencing an undefined type would otherwise
  decode as though the field were a string and consume the wrong bytes."
  (:require [json.core :as json]))

(def primitives
  #{"null" "boolean" "int" "long" "float" "double" "bytes" "string"})

(declare resolve-schema)

(defn- named [env s]
  (cond
    (primitives s) {:type (keyword s)}
    (contains? env s) (get env s)
    :else (throw (ex-info (str "unknown Avro type " (pr-str s))
                          {:type :avro/unknown-type :name s
                           :known (vec (sort (concat primitives (keys env))))}))))

(defn- resolve-object [env m]
  (let [t (get m "type")]
    (case t
      "record" (let [nm (get m "name")
                     ;; Registered BEFORE the fields resolve, so a record whose
                     ;; field refers to itself terminates instead of recursing
                     ;; forever. Avro allows that shape and a linked list is
                     ;; the ordinary example of it.
                     placeholder {:type :record :name nm :fields []}
                     env' (assoc env nm placeholder)
                     fields (mapv (fn [f]
                                    {:name (get f "name")
                                     :schema (resolve-schema env' (get f "type"))})
                                  (get m "fields"))]
                 {:type :record :name nm :fields fields})
      "array" {:type :array :items (resolve-schema env (get m "items"))}
      "map" {:type :map :values (resolve-schema env (get m "values"))}
      "enum" {:type :enum :name (get m "name") :symbols (vec (get m "symbols"))}
      "fixed" {:type :fixed :name (get m "name") :size (long (get m "size"))}
      (if (primitives t)
        ;; `{"type": "long", "logicalType": "timestamp-millis"}` — the logical
        ;; type is carried but not applied. Applying it would turn a number
        ;; into a date whose representation this workspace has not chosen, and
        ;; a reader that guesses is worse than one that hands back the number.
        (cond-> {:type (keyword t)}
          (get m "logicalType") (assoc :logical (get m "logicalType")))
        (named env t)))))

(defn resolve-schema
  "A parsed JSON schema → the shape `avro.datum` decodes against."
  [env s]
  (cond
    (string? s) (named env s)
    (vector? s) {:type :union :branches (mapv #(resolve-schema env %) s)}
    (map? s) (resolve-object env s)
    :else (throw (ex-info "not an Avro schema" {:type :avro/malformed :schema s}))))

(defn parse
  "The `avro.schema` metadata string → a resolved schema."
  [s]
  (resolve-schema {} (json/decode s)))

(defn record-fields
  "Field names of a record schema, in order — the column names of the file.

  A top-level schema that is not a record has no field names, and this returns
  nil rather than inventing one: `avro.lake` uses that to refuse rather than
  materialise rows with a made-up column."
  [schema]
  (when (= :record (:type schema))
    (mapv :name (:fields schema))))
