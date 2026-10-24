(ns kotoba.wit.revoke
  "revoke -- addressed on its own.

  Split out of kotoba.lang.wit on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.wit.capability :refer [capability]]))

(defn revoke
  "Return a policy that no longer allows `cap`."
  [pol cap]
  (disj pol (if (map? cap) (:wit/capability cap) cap)))
