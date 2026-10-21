(ns kotoba.lsp
  "Assembled from one repo per definition.

  This namespace holds no implementation. It re-exports the definitions
  that each live in their own repo, so a call site can require one name
  and a library can require only the definitions it actually uses.

  Value vars are not re-exported either: severities, severity-rank. `(def x other/x)` copies, which is harmless for a function and makes
  with-redefs through this namespace a SILENT no-op for a value -- measured
  on kotoba.lang.edn, where three assertions passed against nothing at all.
  Require the repo that defines the value.
"
  (:require [kotoba.lsp.diagnostic :as diagnostic-ns]
            [kotoba.lsp.diagnostics-by-severity :as diagnostics-by-severity-ns]
            [kotoba.lsp.offset-to-position :as offset-to-position-ns]
            [kotoba.lsp.position :as position-ns]
            [kotoba.lsp.position-to-offset :as position-to-offset-ns]
            [kotoba.lsp.range :as range-ns]
            [kotoba.lsp.text-document :as text-document-ns]
            [kotoba.lsp.within-range :as within-range-ns]))

(def diagnostic "See kotoba.lsp.diagnostic/diagnostic." diagnostic-ns/diagnostic)
(def diagnostics-by-severity "See kotoba.lsp.diagnostics-by-severity/diagnostics-by-severity." diagnostics-by-severity-ns/diagnostics-by-severity)
(def offset->position "See kotoba.lsp.offset-to-position/offset->position." offset-to-position-ns/offset->position)
(def position "See kotoba.lsp.position/position." position-ns/position)
(def position->offset "See kotoba.lsp.position-to-offset/position->offset." position-to-offset-ns/position->offset)
(def range "See kotoba.lsp.range/range." range-ns/range)
(def text-document "See kotoba.lsp.text-document/text-document." text-document-ns/text-document)
(def within-range? "See kotoba.lsp.within-range/within-range?." within-range-ns/within-range?)
