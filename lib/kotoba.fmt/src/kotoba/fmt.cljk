(ns kotoba.fmt
  "Assembled from one repo per definition.

  This namespace holds no implementation. It re-exports the definitions
  that each live in their own repo, so a call site can require one name
  and a library can require only the definitions it actually uses.

  Value vars are not re-exported either: default-opts. `(def x other/x)` copies, which is harmless for a function and makes
  with-redefs through this namespace a SILENT no-op for a value -- measured
  on kotoba.lang.edn, where three assertions passed against nothing at all.
  Require the repo that defines the value.
"
  (:refer-clojure :exclude [format])
  (:require [kotoba.fmt.emit :as emit-ns]
            [kotoba.fmt.emit-inline :as emit-inline-ns]
            [kotoba.fmt.format :as format-ns]
            [kotoba.fmt.format-str :as format-str-ns]
            [kotoba.fmt.pprint :as pprint-ns]
            [kotoba.fmt.pprint-str :as pprint-str-ns]))

(def emit "See kotoba.fmt.emit/emit." emit-ns/emit)
(def emit-inline "See kotoba.fmt.emit-inline/emit-inline." emit-inline-ns/emit-inline)
(def format "See kotoba.fmt.format/format." format-ns/format)
(def format-str "See kotoba.fmt.format-str/format-str." format-str-ns/format-str)
(def pprint "See kotoba.fmt.pprint/pprint." pprint-ns/pprint)
(def pprint-str "See kotoba.fmt.pprint-str/pprint-str." pprint-str-ns/pprint-str)
