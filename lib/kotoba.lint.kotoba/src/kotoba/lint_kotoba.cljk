(ns kotoba.lint-kotoba
  "Assembled from one repo per definition.

  This namespace holds no implementation. It re-exports the definitions
  that each live in their own repo, so a call site can require one name
  and a library can require only the definitions it actually uses.

  Value vars are not re-exported either: default-known-globals. `(def x other/x)` copies, which is harmless for a function and makes
  with-redefs through this namespace a SILENT no-op for a value -- measured
  on kotoba.lang.edn, where three assertions passed against nothing at all.
  Require the repo that defines the value.
"
  (:require [kotoba.lint-kotoba.analyze :as analyze-ns]
            [kotoba.lint-kotoba.over-granted-capabilities :as over-granted-capabilities-ns]
            [kotoba.lint-kotoba.undeclared-refs :as undeclared-refs-ns]
            [kotoba.lint-kotoba.unused-decls :as unused-decls-ns]))

(def analyze "See kotoba.lint-kotoba.analyze/analyze." analyze-ns/analyze)
(def over-granted-capabilities "See kotoba.lint-kotoba.over-granted-capabilities/over-granted-capabilities." over-granted-capabilities-ns/over-granted-capabilities)
(def undeclared-refs "See kotoba.lint-kotoba.undeclared-refs/undeclared-refs." undeclared-refs-ns/undeclared-refs)
(def unused-decls "See kotoba.lint-kotoba.unused-decls/unused-decls." unused-decls-ns/unused-decls)
