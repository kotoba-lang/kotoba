(ns kagami.governor-bridge
  "Governor integration (ADR-2607160005 / ADR-2607141700): map a fleet quorum
  land-back outcome (propose -> govern -> canonical advance) to the shape the
  cloud-itonami ops-runner audit ledger uses, so a fleet governance decision
  is verifiable by the EXISTING governor (ops-runner) and appended to its
  signed audit trail (refs/itonami/audit/main) in a format it already
  understands.

  The two governance loops converge here: fleet's `govern` (quorum signatures
  over a canonical pin advance) produces the same kind of terminal, signed,
  outcome-carrying receipt the ops-runner produces (verify -> handler ->
  signed receipt). This module is the pure mapping; signing/verification uses
  the real cloud-itonami.ops-runner/sign-receipt + verify-receipt (proven
  interoperable under nbb: a fleet-shaped receipt signs and verifies TRUE with
  the actual ops-runner, tamper rejected).

  Pure cljc — no ops-runner require here (the ops-runner is on a heavier
  classpath); a bin entrypoint composes this mapping with the real
  sign/verify. This mirrors the ops-runner-vs-VCS-stack decoupling: compose by
  the plain-map receipt shape, not by a hard dependency."
  (:require [kotoba.lang.text :as str]))

(defn land->ops-receipt
  "A fleet govern outcome -> ops-runner receipt map.
  outcome: {:repo :new-sha :seq :verdict (:accept|:reject) :quorum n :threshold m}
  ts: monotonic tick.
  -> {:merged-cid :lane :effect-id :kind :status :ts} (the ops-runner shape
     its sign-receipt/verify-receipt cover)."
  [{:keys [repo new-sha seq verdict quorum threshold]} ts]
  {:merged-cid (str repo ":" (subs (str new-sha) 0 12))
   :lane :fleet
   :effect-id (str "land|" repo "|seq" seq)
   :kind :fleet/land-back
   :status (if (= :accept verdict) :accepted :rejected)
   :ts ts
   ;; fleet-specific context (outside the signature-covered identity, for audit)
   :fleet/repo repo :fleet/new-sha new-sha :fleet/seq seq
   :fleet/quorum quorum :fleet/threshold threshold})
