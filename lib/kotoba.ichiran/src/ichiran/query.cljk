(ns ichiran.query
  "Pure status lookups for an ichiran Store.

  No LLM/governor involved — `ichiran.operation`'s TallyActor is how a draft
  GETS to `:published` (tally-LLM proposes, TallyGovernor censors, publish
  always routes to a human). This ns only READS already-committed ground
  facts, for callers that need to gate on current status without running the
  actor (e.g. cloud-itonami's workspace projection checking whether an
  activity already has a pending/published tally)."
  (:require [ichiran.store :as store]))

(defn draft-status
  "\"proposed\"/\"published\", or \"none\" if no draft has ever been
  proposed for this artifact."
  [st artifact-id]
  (name (or (:status (store/draft-of st artifact-id)) :none)))

(defn published? [st artifact-id]
  (= :published (:status (store/draft-of st artifact-id))))
