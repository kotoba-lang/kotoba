(ns ddl.model
  "DDL-as-EDN: a plain-data representation of a relational schema, plus a
  threading-friendly builder and the queries a validator or diff engine needs.
  No I/O, no third-party deps — portable .cljc (JVM, ClojureScript, SCI).

  A schema is a map keyed by namespaced :ddl/* keys. Tables are name-keyed maps;
  columns are ordered vectors (document order preserved); primary-key and
  foreign-keys are first-class fields:

    {:ddl/tables
     {\"users\" {:ddl/name \"users\"
                :ddl/columns [{:ddl/name \"id\" :ddl/type \"INTEGER\"
                               :ddl/nullable false :ddl/pk true :ddl/default nil}
                              {:ddl/name \"email\" :ddl/type \"VARCHAR(255)\"
                               :ddl/nullable false :ddl/pk false :ddl/default nil}]
                :ddl/primary-key [\"id\"]
                :ddl/foreign-keys [{:ddl/columns [\"org_id\"]
                                    :ddl/ref-table \"orgs\"
                                    :ddl/ref-columns [\"id\"]}]}}}")

;; --- constructors ---

(defn schema
  "A fresh, empty schema."
  []
  {:ddl/tables {}})

(defn column
  "Construct a normalised column map.
  opts keyword args: :nullable (default true) :pk (default false) :default (default nil)."
  [name type & {:keys [nullable pk default] :or {nullable true pk false default nil}}]
  {:ddl/name     name
   :ddl/type     type
   :ddl/nullable (boolean nullable)
   :ddl/pk       (boolean pk)
   :ddl/default  default})

(defn table
  "Construct a table map from a seq of column maps.
  :ddl/primary-key is derived from columns with :ddl/pk true unless opts overrides it.
  opts: {:primary-key [names] :foreign-keys [fk-maps]}"
  ([name columns] (table name columns nil))
  ([name columns opts]
   {:ddl/name        name
    :ddl/columns     (vec columns)
    :ddl/primary-key (or (:primary-key opts)
                         (vec (keep #(when (:ddl/pk %) (:ddl/name %)) columns)))
    :ddl/foreign-keys (or (:foreign-keys opts) [])}))

(defn add-table
  "Add a table map to a schema, keyed by :ddl/name."
  [schema tbl]
  (assoc-in schema [:ddl/tables (:ddl/name tbl)] tbl))

;; --- queries ---

(defn tables
  "All table maps in the schema (unordered)."
  [schema]
  (vals (:ddl/tables schema)))

(defn table-names
  "Set of table names in the schema."
  [schema]
  (set (keys (:ddl/tables schema))))

(defn get-table
  "Look up a table by name."
  [schema name]
  (get-in schema [:ddl/tables name]))

(defn columns
  "Column maps for a table, in document order."
  [tbl]
  (:ddl/columns tbl))

(defn column-names
  "Column names for a table, in document order."
  [tbl]
  (mapv :ddl/name (columns tbl)))
