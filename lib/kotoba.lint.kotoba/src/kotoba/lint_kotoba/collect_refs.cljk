(ns kotoba.lint-kotoba.collect-refs
  "collect-refs -- addressed on its own.

  Split out of kotoba.lang.lint-kotoba on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  )

(defn collect-refs
  "Walk `form`, collect all symbols referenced. Returns a set."
  [form]
  (cond
    (symbol? form) #{form}
    (map? form)    (set (mapcat collect-refs (concat (keys form) (vals form))))
    (coll? form)   (set (mapcat collect-refs form))
    :else #{}))
