(ns iceberg.schema
  "An Iceberg table schema, and the Avro schemas the manifests are written
  against.

  Iceberg is not a file format. It is a set of JSON and Avro files that say
  which data files a table consists of, so a reader can list a table without
  listing a directory and can prune it without opening one. This namespace
  holds the schema half of that: the table's own schema as it appears in
  `metadata.json`, and the two fixed Avro schemas -- `manifest_entry` and
  `manifest_file` -- whose shape the specification pins.

  ## Field ids are the schema, and names are a convenience

  Every field in an Iceberg schema carries an integer id, and readers resolve
  by id, not by name -- that is what makes renaming a column a metadata-only
  operation. The ids in the manifest schemas below are **not free choices**:
  they are assigned by the specification (`file_path` is 100, `record_count`
  is 103, `manifest_path` is 500) and a reader looking for 103 will not find a
  field this repo decided to call something else. They are written into the
  Avro schema as `field-id` attributes, which is how they survive into the
  file.

  ## What this writes, and what it does not

  Enough of the v2 specification to publish an append: a schema of primitive
  columns, an unpartitioned spec, and data files with a row count and a size.
  Column statistics (`lower_bounds`, `upper_bounds`, `value_counts`) are
  nullable in the specification and are omitted rather than guessed --
  a bound that is wrong in the narrowing direction silently deletes rows from
  a query's answer, and this repo has no statistics of its own to offer yet.
  Deletes, partitioning and schema evolution are absent, not stubbed."
  (:require [json.core :as json]))

(def ^:const format-version 2)

;; ---------------------------------------------------------------------------
;; Table schema.
;; ---------------------------------------------------------------------------

(def primitive->iceberg
  "The subset of Iceberg's primitive types this writer will name.

  Deliberately small. An Iceberg type this cannot produce is better as a
  missing key than as a plausible neighbour: writing `long` where the caller
  meant `timestamptz` produces a table that reads back as numbers and loses
  what they were."
  {:boolean "boolean"
   :int "int"
   :long "long"
   :float "float"
   :double "double"
   :string "string"
   :binary "binary"
   :date "date"
   :timestamptz "timestamptz"})

(defn field
  "One schema field. `id` is the caller's, and must be stable across commits
  for the same column -- that is the whole contract Iceberg's ids carry."
  [id name type & {:keys [required] :or {required false}}]
  (when-not (contains? primitive->iceberg type)
    (throw (ex-info (str "iceberg: no mapping for type " (pr-str type))
                    {:type :iceberg/unsupported-type :given type
                     :known (vec (sort (keys primitive->iceberg)))})))
  {"id" id "name" name "required" required "type" (primitive->iceberg type)})

(defn schema
  "A struct schema. `fields` come from `field`."
  ([fields] (schema 0 fields))
  ([schema-id fields]
   {"type" "struct" "schema-id" schema-id "fields" (vec fields)}))

(defn last-column-id [s] (reduce max 0 (map #(get % "id") (get s "fields"))))

(defn name-mapping
  "The `schema.name-mapping.default` value for a schema.

  Iceberg resolves columns by field id, and a data file is supposed to carry
  those ids. Parquet written by a plain writer does not -- it has names only.
  The name mapping is how a table says which name meant which id, and without
  it a reader that finds no ids REFUSES rather than guessing by position
  (measured against pyiceberg: `Parquet file does not have field-ids and the
  Iceberg table does not have schema.name-mapping.default defined`).

  Refusing is the right behaviour and this is the right fix: matching by
  position would silently swap two columns of the same type."
  [schema]
  (mapv (fn [f] {"field-id" (get f "id") "names" [(get f "name")]})
        (get schema "fields")))

;; ---------------------------------------------------------------------------
;; The Avro schemas the specification pins.
;; ---------------------------------------------------------------------------

(defn- kv-map
  "Iceberg writes a map<int,X> as an Avro ARRAY of key/value records tagged
  `logicalType: map`, not as an Avro map -- an Avro map's keys are strings and
  these keys are column ids. The key and value carry their own field ids,
  which the specification assigns separately from the map's own."
  [record-name value-type key-id value-id]
  {"type" "array"
   "logicalType" "map"
   "items" {"type" "record"
            "name" record-name
            "fields" [{"name" "key" "type" "int" "field-id" key-id}
                      {"name" "value" "type" value-type "field-id" value-id}]}})

(defn- avro-field
  ([name type field-id] {"name" name "type" type "field-id" field-id})
  ([name type field-id default] {"name" name "type" type "field-id" field-id
                                 "default" default}))

(defn partition-record
  "The `partition` struct inside a data file entry.

  An unpartitioned table still has this field -- it is a struct with no
  members, not an absent field. Omitting it produces a manifest that readers
  reject, and writing null in its place produces one that reads as a table
  whose partition values are unknown."
  [spec-fields]
  {"type" "record" "name" "r102" "fields" (vec spec-fields)})

(defn manifest-entry-schema
  "`manifest_entry` -- one row per data file in a manifest.

  Field ids are the specification's, not this repo's. See the namespace
  docstring."
  [spec-fields]
  {"type" "record"
   "name" "manifest_entry"
   "fields"
   [(avro-field "status" "int" 0)
    (avro-field "snapshot_id" ["null" "long"] 1 nil)
    (avro-field "sequence_number" ["null" "long"] 3 nil)
    (avro-field "file_sequence_number" ["null" "long"] 4 nil)
    (avro-field
     "data_file"
     {"type" "record"
      "name" "r2"
      "fields"
      [(avro-field "content" "int" 134)
       (avro-field "file_path" "string" 100)
       (avro-field "file_format" "string" 101)
       (avro-field "partition" (partition-record spec-fields) 102)
       (avro-field "record_count" "long" 103)
       (avro-field "file_size_in_bytes" "long" 104)
       ;; The statistics a reader prunes with. Nullable, and null is a
       ;; truthful answer -- see `iceberg.manifest/data-file`.
       (avro-field "column_sizes"
                   ["null" (kv-map "k117_v118" "long" 117 118)] 108 nil)
       (avro-field "value_counts"
                   ["null" (kv-map "k119_v120" "long" 119 120)] 109 nil)
       (avro-field "null_value_counts"
                   ["null" (kv-map "k121_v122" "long" 121 122)] 110 nil)
       (avro-field "lower_bounds"
                   ["null" (kv-map "k126_v127" "bytes" 126 127)] 125 nil)
       (avro-field "upper_bounds"
                   ["null" (kv-map "k129_v130" "bytes" 129 130)] 128 nil)]}
     2)]})

(def manifest-file-schema
  "`manifest_file` -- one row per manifest in a manifest list."
  {"type" "record"
   "name" "manifest_file"
   "fields"
   [(avro-field "manifest_path" "string" 500)
    (avro-field "manifest_length" "long" 501)
    (avro-field "partition_spec_id" "int" 502)
    (avro-field "content" "int" 517)
    (avro-field "sequence_number" "long" 515)
    (avro-field "min_sequence_number" "long" 516)
    (avro-field "added_snapshot_id" "long" 503)
    (avro-field "added_files_count" "int" 504)
    (avro-field "existing_files_count" "int" 505)
    (avro-field "deleted_files_count" "int" 506)
    (avro-field "added_rows_count" "long" 512)
    (avro-field "existing_rows_count" "long" 513)
    (avro-field "deleted_rows_count" "long" 514)
    ;; `element-id` is required on an array, not optional decoration: a
    ;; reader resolves the element type by id and refuses an array without
    ;; one (measured against pyiceberg: "Cannot convert array-type, missing
    ;; element-id"). 508 is the specification's id for this array's element.
    (avro-field "partitions" ["null" {"type" "array"
                                      "element-id" 508
                                      "items" {"type" "record"
                                               "name" "r508"
                                               "fields" [(avro-field "contains_null" "boolean" 509)
                                                         (avro-field "contains_nan" ["null" "boolean"] 518 nil)
                                                         (avro-field "lower_bound" ["null" "bytes"] 510 nil)
                                                         (avro-field "upper_bound" ["null" "bytes"] 511 nil)]}}]
                 507 nil)
    (avro-field "key_metadata" ["null" "bytes"] 519 nil)]})

(defn json-of [x] (json/encode x))
