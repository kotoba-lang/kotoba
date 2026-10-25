(ns denrei.query
  "Pure status lookups for a denrei Store.

  No LLM/governor involved — `denrei.operation`'s ChannelActor is how a draft
  GETS to `:posted` (post-LLM proposes, MembershipGovernor censors, posting
  always routes to a human). This ns only READS already-committed ground
  facts, for callers that need to gate on current status without running the
  actor (e.g. cloud-itonami's workspace projection checking whether a
  message already has a pending/posted draft)."
  (:require [denrei.store :as store]))

(defn draft-status
  "\"proposed\"/\"posted\", or \"none\" if no draft has ever been proposed."
  [st message-id]
  (name (or (:status (store/draft-of st message-id)) "none")))

(defn posted? [st message-id]
  (= :posted (:status (store/draft-of st message-id))))
