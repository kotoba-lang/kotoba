(ns ddl.validate
  "Structural validation of a DDL-as-EDN schema. Pure: returns a vector of problem
  maps {:ddl/severity :error|:warn :ddl/code … :ddl/id … :ddl/msg …} so a caller
  decides how to surface them. valid? is true iff there are no :error-level problems
  (warnings are advisory)."
  (:require [ddl.model :as m]))

(defn- problem [severity code id msg]
  {:ddl/severity severity :ddl/code code :ddl/id id :ddl/msg msg})

(defn problems
  "Return a vector of structural problems with `schema`."
  [schema]
  (let [tbl-names (m/table-names schema)
        ps        (transient [])]
    (doseq [tbl (m/tables schema)]
      (let [tname     (:ddl/name tbl)
            cols      (:ddl/columns tbl)
            col-names (m/column-names tbl)]
        ;; duplicate column names
        (let [freq (frequencies col-names)]
          (doseq [[cn cnt] freq]
            (when (> cnt 1)
              (conj! ps (problem :error :column/duplicate tname
                                 (str "table " tname " has duplicate column " cn))))))
        ;; empty/nil type
        (doseq [col cols]
          (when (or (nil? (:ddl/type col)) (= "" (:ddl/type col)))
            (conj! ps (problem :error :column/empty-type tname
                               (str "column " (:ddl/name col)
                                    " in table " tname " has no type")))))
        ;; no primary key (warning only)
        (when (empty? (:ddl/primary-key tbl))
          (conj! ps (problem :warn :table/no-pk tname
                             (str "table " tname " has no primary key"))))
        ;; dangling foreign-key references
        (doseq [fk (:ddl/foreign-keys tbl)]
          (when-not (contains? tbl-names (:ddl/ref-table fk))
            (conj! ps (problem :error :fk/dangling tname
                               (str "table " tname " references unknown table "
                                    (:ddl/ref-table fk))))))))
    (persistent! ps)))

(defn errors
  "Subset of problems with :error severity."
  [schema]
  (filterv #(= :error (:ddl/severity %)) (problems schema)))

(defn valid?
  "True iff `schema` has no :error-level structural problems."
  [schema]
  (empty? (errors schema)))
