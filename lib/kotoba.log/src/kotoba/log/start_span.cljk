(ns kotoba.log.start-span
  "start-span -- addressed on its own.

  Split out of kotoba.lang.log on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.log.next-span-id :refer [next-span-id]]
            [kotoba.log.with-span :refer [with-span]])
)

(defn start-span
  "Start a span named `name`. Returns `[logger' span]` where `logger'` tags
  child records with the span id, and `span` is `{:span-id :name :start-ts}`."
  ([logger name] (start-span logger name nil))
  ([logger name opts]
   (let [sid (or (:span-id opts) (next-span-id))
         span {:span-id sid :name name
               :start-ts (when (:clock logger) ((:clock logger)))
               :parent-id (:span-id logger)}
         logger' (with-span logger sid)]
     [logger' span])))
