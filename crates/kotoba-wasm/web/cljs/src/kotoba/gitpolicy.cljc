(ns kotoba.gitpolicy
  "GitOffice merge-policy gate (doc e §5-§6) — pure (.cljc).

   Decides, over the Phase-0 collaboration datoms, whether a PR may merge:
   required approvals, stale-review dismissal, required reviewers (CODEOWNERS-ish),
   branch protection, and required CI checks. Then `land-pr-tx` produces the
   retract/assert ops to advance the base ref to the merge commit, mark the PR merged,
   and close its linked issues. These are the same checks doc e §6 expresses as
   datomicQ — here as plain folds so they are unit-testable without a running kotoba."
  (:require [kotoba.gitoffice :as g]
            [clojure.set :as set]))

;; ---------------------------------------------------------------------------
;; schema (additive): branch-protection policy + CI results
;; ---------------------------------------------------------------------------

(def schema
  {:policy/repo                {:db/valueType :ref     :db/cardinality :one}
   :policy/required-approvals  {:db/valueType :long    :db/cardinality :one}
   :policy/required-reviewer   {:db/valueType :did     :db/cardinality :many}
   :policy/dismiss-stale       {:db/valueType :boolean :db/cardinality :one}
   :policy/require-ci          {:db/valueType :keyword :db/cardinality :many}

   :ci/pr                      {:db/valueType :ref     :db/cardinality :one}
   :ci/check                   {:db/valueType :keyword :db/cardinality :one}
   :ci/state                   {:db/valueType :keyword :db/cardinality :one} ; :ci.state/pass|fail|pending
   :ci/at-commit               {:db/valueType :string  :db/cardinality :one}})

(defn policy->datoms [{:keys [id repo required-approvals required-reviewers
                              dismiss-stale require-ci]}]
  (into (cond-> [[id :policy/repo repo]]
          (some? required-approvals) (conj [id :policy/required-approvals required-approvals])
          (some? dismiss-stale)      (conj [id :policy/dismiss-stale dismiss-stale]))
        (concat (map (fn [d] [id :policy/required-reviewer d]) required-reviewers)
                (map (fn [c] [id :policy/require-ci c]) require-ci))))

(defn ci->datoms [{:keys [id pr check state at-commit]}]
  [[id :ci/pr pr] [id :ci/check check] [id :ci/state state] [id :ci/at-commit at-commit]])

;; ---------------------------------------------------------------------------
;; policy lookup (with GitHub-like defaults when a repo has no protection)
;; ---------------------------------------------------------------------------

(defn policy-for
  "Effective policy map for a repo. No policy entity => unprotected (0 approvals)."
  [datoms repo]
  (let [pid (some (fn [[e a v]] (when (and (= a :policy/repo) (= v repo)) e)) datoms)]
    {:required-approvals (or (and pid (g/v-one datoms pid :policy/required-approvals)) 0)
     :required-reviewers (if pid (g/v-many datoms pid :policy/required-reviewer) #{})
     :dismiss-stale      (if (and pid (some? (g/v-one datoms pid :policy/dismiss-stale)))
                           (g/v-one datoms pid :policy/dismiss-stale)
                           true)                       ; default: dismiss stale approvals
     :require-ci         (if pid (g/v-many datoms pid :policy/require-ci) #{})}))

;; ---------------------------------------------------------------------------
;; effective review state per reviewer (latest-wins-by-rule, stale-aware)
;; ---------------------------------------------------------------------------

(defn effective-states
  "{reviewer-did -> :approved | :changes-requested | :none}.
   When dismiss-stale?, only reviews whose :review/at-commit = head count.
   changes-requested dominates approved for the same reviewer."
  [datoms pr-id head dismiss-stale?]
  (let [rids (->> datoms
                  (keep (fn [[e a v]] (when (and (= a :review/pr) (= v pr-id)) e)))
                  distinct)
        by-rev (group-by #(g/v-one datoms % :review/reviewer) rids)]
    (into {}
          (for [[did rs] by-rev]
            (let [at-head  (filter #(= head (g/v-one datoms % :review/at-commit)) rs)
                  ;; a review AT head always supersedes that reviewer's older reviews
                  ;; (so a fresh approval clears an earlier changes-request). Only when
                  ;; the reviewer has NO review at head does dismiss-stale decide whether
                  ;; their stale reviews still count.
                  relevant (cond
                             (seq at-head)  at-head
                             dismiss-stale? []
                             :else          rs)
                  states (set (map #(g/v-one datoms % :review/state) relevant))]
              [did (cond
                     (states :review.state/changes-requested) :changes-requested
                     (states :review.state/approved)          :approved
                     :else                                    :none)])))))

(defn- ci-states
  "{check -> :ci.state/*} for CI rows at the PR head. Contract: one result row per
   (check, commit) — a re-run retracts+asserts the same entity, so a re-run to green
   clears an earlier failure (last-result-wins, not fail-absorbing)."
  [datoms pr-id head]
  (->> datoms
       (keep (fn [[e a v]] (when (and (= a :ci/pr) (= v pr-id)) e)))
       distinct
       (filter #(= head (g/v-one datoms % :ci/at-commit)))
       (reduce (fn [m c]
                 (assoc m (g/v-one datoms c :ci/check) (g/v-one datoms c :ci/state)))
               {})))

;; ---------------------------------------------------------------------------
;; the merge gate
;; ---------------------------------------------------------------------------

(defn evaluate-merge
  "Decide whether pr-id may merge. -> {:mergeable? :reasons [...] + diagnostics}."
  [datoms pr-id]
  (let [repo  (g/v-one datoms pr-id :pr/repo)
        state (g/v-one datoms pr-id :pr/state)
        head  (g/v-one datoms pr-id :pr/head-commit)
        {:keys [required-approvals required-reviewers dismiss-stale require-ci]} (policy-for datoms repo)
        est   (effective-states datoms pr-id head dismiss-stale)
        approvals (set (keep (fn [[d s]] (when (= s :approved) d)) est))
        changes   (set (keep (fn [[d s]] (when (= s :changes-requested) d)) est))
        missing-app (max 0 (- required-approvals (count approvals)))
        missing-req (set/difference required-reviewers approvals)
        ci    (ci-states datoms pr-id head)
        passing (set (keep (fn [[c s]] (when (= s :ci.state/pass) c)) ci))
        failing (set (keep (fn [[c s]] (when (= s :ci.state/fail) c)) ci))
        missing-ci (set/difference require-ci passing)
        reasons (cond-> []
                  (not= state :pr.state/open) (conj :not-open)
                  (pos? missing-app)          (conj :insufficient-approvals)
                  (seq missing-req)           (conj :missing-required-reviewer)
                  (seq changes)               (conj :changes-requested)
                  (seq failing)               (conj :ci-failing)
                  (seq missing-ci)            (conj :ci-missing))]
    {:mergeable? (empty? reasons)
     :reasons reasons
     :approvals approvals
     :changes-requested changes
     :missing-approvals missing-app
     :missing-required-reviewers missing-req
     :failing-ci failing
     :missing-ci missing-ci}))

;; ---------------------------------------------------------------------------
;; landing a PR (advance base ref, mark merged, close issues) — pure tx ops
;; ---------------------------------------------------------------------------

(defn land-pr-tx
  "Retract/assert ops to land pr-id at merged-commit (the 2-parent merge commit CID).
   -> {:retract [[e a v]...] :assert [[e a v]...]}. Apply only after evaluate-merge passes."
  [datoms pr-id merged-commit]
  (let [base-ref  (g/v-one datoms pr-id :pr/base-ref)
        ref-eid   (some (fn [[e a v]] (when (and (= a :ref/name) (= v base-ref)) e)) datoms)
        old-ref   (and ref-eid (g/v-one datoms ref-eid :ref/commit))
        old-state (g/v-one datoms pr-id :pr/state)
        issues    (g/v-many datoms pr-id :pr/closes-issue)]
    {:retract (cond-> [[pr-id :pr/state old-state]]
                old-ref (conj [ref-eid :ref/commit old-ref])
                true (into (keep (fn [i] (when-let [s (g/v-one datoms i :issue/state)]
                                           [i :issue/state s])) issues)))
     :assert  (cond-> [[pr-id :pr/state :pr.state/merged]
                       [pr-id :pr/merged-commit merged-commit]]
                ref-eid (conj [ref-eid :ref/commit merged-commit])
                true (into (map (fn [i] [i :issue/state :issue.state/closed]) issues)))}))
