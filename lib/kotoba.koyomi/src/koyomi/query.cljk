(ns koyomi.query
  "Pure status lookups for a koyomi Store.

  No LLM/governor involved — `koyomi.operation`'s ScheduleActor is how a draft
  GETS to `:shared` (schedule-LLM proposes, ComplianceGovernor censors,
  sharing always routes to a human). This ns only READS already-committed
  ground facts, for callers that need to gate on current status without
  running the actor (e.g. cloud-itonami's workspace projection checking
  whether an event already has a pending/shared draft)."
  (:require [koyomi.store :as store]))

(defn draft-status
  "\"proposed\"/\"shared\", or \"none\" if no draft has ever been proposed."
  [st event-id]
  (name (or (:status (store/draft-of st event-id)) "none")))

(defn shared? [st event-id]
  (= :shared (:status (store/draft-of st event-id))))
