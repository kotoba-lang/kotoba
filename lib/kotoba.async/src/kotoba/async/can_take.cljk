(ns kotoba.async.can-take
  "can-take? -- addressed on its own.

  Split out of kotoba.lang.async on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  )

(defn can-take?
  "True iff a value is immediately available."
  [ch]
  (pos? (count (:buffer ch))))
