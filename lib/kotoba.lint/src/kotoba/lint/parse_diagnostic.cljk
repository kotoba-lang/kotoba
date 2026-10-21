(ns kotoba.lint.parse-diagnostic
  "parse-diagnostic -- addressed on its own.

  Split out of kotoba.lang.lint on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.lang.lsp :as lsp])
)

(defn parse-diagnostic
  "Build an lsp diagnostic for a parse failure. EDN parse errors do not carry
  column info, so the range points at 0:0 (best-effort position)."
  [msg]
  (lsp/diagnostic (lsp/range (lsp/position 0 0) (lsp/position 0 0))
                  :error "lint" (str msg)))
