(ns kotobase.lake.columnar
  "The join between `kotobase.lake.tabular` and the `columnar` engine.

  It is ten lines because both sides were built to meet here:
  `columnar.plan/select` already emits the row shape `ITabularEngine`
  consumes, and takes the row key as an argument precisely so that neither
  library has to depend on the namespace that owns it.

  What travels intact from a triple pattern all the way to a file's index:

      [?row \"price\" 42]
        -> tabular:  {:columns [\"price\"] :filters [[\"price\" 42]]}
        -> columnar: predicates [[:= \"price\" 42]], row groups pruned by
                     min/max before a byte is fetched
        -> parquet:  one column chunk, at its offset, of its exact size

  Nothing in that chain re-parses or re-plans. A projection stays a
  projection and a filter stays a filter."
  (:require [columnar.plan :as plan]
            [columnar.source :as csrc]
            [kotobase.lake.tabular :as tab]))

(defn engine
  "An `ITabularEngine` over a `columnar/IColumnSource`."
  [column-source]
  (reify tab/ITabularEngine
    (-columns [_] (csrc/-schema column-source))
    (-select [_ request]
      (:rows (plan/select column-source request tab/row-attribute)))))

(defn scan-reader
  "Turn `(fn [handle] -> IColumnSource)` into a reader for
  `kotobase.lake.reader/register-scan`.

  The format library supplies the column source and nothing else — it never
  learns about tenants, catalogs, subjects or triple patterns, and this repo
  never learns about footers or codecs."
  [open-column-source]
  (fn [{:keys [subject-prefix] :as handle}]
    (tab/wide-source {:engine (engine (open-column-source handle))
                      :subject-prefix subject-prefix})))
