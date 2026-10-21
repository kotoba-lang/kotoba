(ns kotoba.fmt.emit-scalar
  "emit-scalar -- addressed on its own.

  Split out of kotoba.lang.fmt on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  )

(defn emit-scalar [x]
  (cond
    (nil? x) "nil"
    (string? x) (pr-str x)
    (char? x) (pr-str x)
    (keyword? x) (str x)
    (symbol? x) (str x)
    :else (str x)))
