(ns kotoba.lint-kotoba.over-granted-capabilities
  "over-granted-capabilities -- addressed on its own.

  Split out of kotoba.lang.lint-kotoba on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.lint-kotoba.grants-from-form :refer [grants-from-form]])
)

(defn over-granted-capabilities
  "Granted-but-unused capabilities in `form` vs `used`."
  [form used]
  (let [granted (grants-from-form form)
        used    (set (map str used))]
    (set (filter (complement used) granted))))
