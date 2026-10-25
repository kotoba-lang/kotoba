(ns ichiran.policy
  "Pure checks over ichiran's published facts (sensitive-cite redaction
  requirements, artifact tenancy) — no I/O, no store: shared by TallyGovernor
  and the mock tally-LLM so both reason over the same facts without coupling
  the censor to the proposer (the ichiran analog of teian.policy /
  kekkai.acl / tayori.policy).")

(def sensitive-categories #{:financial :legal :personnel})

(defn sensitive-cite? [cite] (contains? sensitive-categories cite))

(defn missing-redactions
  "Sensitive cites the proposal did not list in :redactions."
  [cites redactions]
  (vec (remove (set redactions) (filter sensitive-cite? cites))))

(defn tenant-mismatch?
  "Does the proposal's declared `tenant` diverge from the artifact's own
  registered :repo? No implicit allow — drafting a tally for a tenant other
  than the artifact's own itonami-activity repo is a cross-tenant leak."
  [artifact tenant]
  (not= tenant (:repo artifact)))
