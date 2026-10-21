(ns kotoba.async.drain
  "drain -- addressed on its own.

  Split out of kotoba.lang.async on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  )

(defn drain
  "Take every immediately-available value from `ch`. Returns `[ch' [vals…]]`."
  [ch]
  (let [buf (:buffer ch)]
    [(assoc ch :buffer []) buf]))
