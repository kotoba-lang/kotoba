(ns kotoba.lint
  "Assembled from one repo per definition.

  This namespace holds no implementation. It re-exports the definitions
  that each live in their own repo, so a call site can require one name
  and a library can require only the definitions it actually uses.
"
  (:require [kotoba.lint.lint-file :as lint-file-ns]
            [kotoba.lint.lint-source :as lint-source-ns]
            [kotoba.lint.ok :as ok-ns]
            [kotoba.lint.summary :as summary-ns]))

(def lint-file "See kotoba.lint.lint-file/lint-file." lint-file-ns/lint-file)
(def lint-source "See kotoba.lint.lint-source/lint-source." lint-source-ns/lint-source)
(def ok? "See kotoba.lint.ok/ok?." ok-ns/ok?)
(def summary "See kotoba.lint.summary/summary." summary-ns/summary)
