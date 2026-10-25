(ns shoko.query
  "Pure status lookups for a shoko Store.

  No LLM/governor involved — `shoko.operation`'s ArchiveActor is how a file
  gets a draft/grant (archive-LLM proposes, ArchiveGovernor censors, sharing
  always routes to a human). This ns only READS already-committed ground
  facts, for callers that need to gate on current status without running the
  actor (e.g. cloud-itonami's workspace projection checking whether a file
  already has a pending draft or whether a principal already has access)."
  (:require [shoko.store :as store]))

(defn draft-status
  "\"proposed\", or \"none\" if no draft has ever been proposed for this
  file."
  [st file-id]
  (name (or (:status (store/draft-of st file-id)) :none)))

(defn shared-with?
  "Does `principal` already hold a grant on `file-id`?"
  [st principal file-id]
  (some? (store/grant-of st principal file-id)))

(defn known-principal?
  "Has `principal` received a grant WITHIN `tenant`? — the same tenant-scoped
  deny-by-default check shoko.governor's share-requires-acl invariant uses
  (a grant recorded under a different tenant never counts here)."
  [st principal tenant]
  (store/principal-known? st principal tenant))
