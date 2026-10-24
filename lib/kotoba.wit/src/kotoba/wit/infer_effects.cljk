(ns kotoba.wit.infer-effects
  "infer-effects -- addressed on its own.

  Split out of kotoba.lang.wit on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  )

(defn infer-effects [fn-name]
  ;; a conservative, name-based inference for the common kotoba host imports.
  ;; A function may override via :wit/effects. Anything unrecognized is just
  ;; :call — the gate still checks it, it simply carries no finer effect.
  (let [n (name fn-name)]
    (cond
      (re-find #"^(get|read|list|head|peek)" n) #{:read}
      (re-find #"^(put|write|set|delete|remove|create|update|post|patch)" n) #{:write}
      :else #{:call})))
