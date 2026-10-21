(ns kotoba.lint-kotoba.def-name
  "def-name -- addressed on its own.

  Split out of kotoba.lang.lint-kotoba on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  )

(defn def-name
  "If form is a (def name ...) or (defn name ...), return the name symbol."
  [form]
  (when (and (seq? form)
             (#{'def 'defn 'defn- 'defmacro} (first form))
             (next form))
    (second form)))
