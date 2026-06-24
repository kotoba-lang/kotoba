(ns kotoba.gitpolicy-test
  "Tests for the GitOffice merge-policy gate + land-pr."
  (:require [clojure.test :refer [deftest is testing run-tests]]
            [kotoba.gitoffice :as g]
            [kotoba.gitpolicy :as p]))

;; shared PR fixture (open, head = HEAD2)
(defn- pr-datoms []
  (g/pr->datoms {:id "pr1" :repo "repo1" :number 1 :title "fix"
                 :author "did:key:zAuthor" :base-ref "refs/heads/main"
                 :head-ref "refs/heads/fix" :base-commit "BASE"
                 :head-commit "HEAD2" :state :pr.state/open :closes-issues #{}}))

(defn- review [id reviewer state at]
  (g/review->datoms {:id id :pr "pr1" :reviewer reviewer :state state :at-commit at}))

;; ---------------------------------------------------------------------------
;; unprotected vs required approvals
;; ---------------------------------------------------------------------------

(deftest unprotected-repo-is-mergeable
  (let [ds (pr-datoms)
        r (p/evaluate-merge ds "pr1")]
    (is (:mergeable? r) "no policy => mergeable (unprotected branch)")
    (is (empty? (:reasons r)))))

(deftest required-approvals-gate
  (let [pol (p/policy->datoms {:id "pol" :repo "repo1" :required-approvals 1})
        ds  (into (pr-datoms) pol)]
    (testing "no approval -> blocked"
      (let [r (p/evaluate-merge ds "pr1")]
        (is (not (:mergeable? r)))
        (is (some #{:insufficient-approvals} (:reasons r)))
        (is (= 1 (:missing-approvals r)))))
    (testing "one approval at head -> mergeable"
      (let [ds2 (into ds (review "rv1" "did:key:zR1" :review.state/approved "HEAD2"))
            r (p/evaluate-merge ds2 "pr1")]
        (is (:mergeable? r))
        (is (= #{"did:key:zR1"} (:approvals r)))))))

;; ---------------------------------------------------------------------------
;; stale review dismissal
;; ---------------------------------------------------------------------------

(deftest stale-approval-dismissed
  (let [pol (p/policy->datoms {:id "pol" :repo "repo1" :required-approvals 1
                               :dismiss-stale true})
        ds  (-> (pr-datoms)
                (into pol)
                (into (review "rv1" "did:key:zR1" :review.state/approved "HEAD1")))] ; old head
    (testing "approval at an outdated commit does not count when dismiss-stale"
      (let [r (p/evaluate-merge ds "pr1")]
        (is (not (:mergeable? r)))
        (is (empty? (:approvals r)))))
    (testing "same setup but dismiss-stale=false -> the old approval counts"
      (let [pol2 (p/policy->datoms {:id "pol" :repo "repo1" :required-approvals 1
                                    :dismiss-stale false})
            ds2  (-> (pr-datoms)
                     (into pol2)
                     (into (review "rv1" "did:key:zR1" :review.state/approved "HEAD1")))
            r (p/evaluate-merge ds2 "pr1")]
        (is (:mergeable? r))))))

;; ---------------------------------------------------------------------------
;; changes-requested blocks; required reviewer; CI
;; ---------------------------------------------------------------------------

(deftest fresh-approval-supersedes-stale-changes-request
  (testing "a reviewer's approval AT head clears their earlier changes-request (any dismiss-stale)"
    (doseq [dismiss [true false]]
      (let [pol (p/policy->datoms {:id "pol" :repo "repo1" :required-approvals 1
                                   :dismiss-stale dismiss})
            ds  (-> (pr-datoms) (into pol)
                    (into (review "rv-old" "did:key:zR1" :review.state/changes-requested "HEAD1"))
                    (into (review "rv-new" "did:key:zR1" :review.state/approved "HEAD2")))
            r (p/evaluate-merge ds "pr1")]
        (is (:mergeable? r) (str "dismiss-stale=" dismiss ": head approval wins"))
        (is (= #{"did:key:zR1"} (:approvals r)))
        (is (empty? (:changes-requested r)))))))

(deftest ci-rerun-to-green-clears-failure
  (testing "a failed check re-run to pass at the same head is satisfied (not fail-absorbing)"
    (let [pol (p/policy->datoms {:id "pol" :repo "repo1" :required-approvals 0
                                 :require-ci #{:ci/build}})
          ;; retract+assert contract => only the latest row exists; model the green re-run
          ds  (-> (pr-datoms) (into pol)
                  (into (p/ci->datoms {:id "ci-build" :pr "pr1" :check :ci/build
                                       :state :ci.state/pass :at-commit "HEAD2"})))
          r (p/evaluate-merge ds "pr1")]
      (is (:mergeable? r))
      (is (empty? (:failing-ci r))))))

(deftest changes-requested-blocks
  (let [pol (p/policy->datoms {:id "pol" :repo "repo1" :required-approvals 0})
        ds  (-> (pr-datoms) (into pol)
                (into (review "rv1" "did:key:zR1" :review.state/changes-requested "HEAD2")))
        r (p/evaluate-merge ds "pr1")]
    (is (not (:mergeable? r)))
    (is (some #{:changes-requested} (:reasons r)))))

(deftest required-reviewer-gate
  (let [pol (p/policy->datoms {:id "pol" :repo "repo1" :required-approvals 1
                               :required-reviewers #{"did:key:zOwner"}})]
    (testing "approved by someone else but not the required reviewer -> blocked"
      (let [ds (-> (pr-datoms) (into pol)
                   (into (review "rv1" "did:key:zR1" :review.state/approved "HEAD2")))
            r (p/evaluate-merge ds "pr1")]
        (is (not (:mergeable? r)))
        (is (= #{"did:key:zOwner"} (:missing-required-reviewers r)))))
    (testing "approved by the required reviewer -> mergeable"
      (let [ds (-> (pr-datoms) (into pol)
                   (into (review "rv1" "did:key:zOwner" :review.state/approved "HEAD2")))
            r (p/evaluate-merge ds "pr1")]
        (is (:mergeable? r))))))

(deftest required-ci-gate
  (let [pol (p/policy->datoms {:id "pol" :repo "repo1" :required-approvals 0
                               :require-ci #{:ci/no-refuted :ci/coverage}})]
    (testing "missing a required check -> blocked"
      (let [ds (-> (pr-datoms) (into pol)
                   (into (p/ci->datoms {:id "ci1" :pr "pr1" :check :ci/coverage
                                        :state :ci.state/pass :at-commit "HEAD2"})))
            r (p/evaluate-merge ds "pr1")]
        (is (not (:mergeable? r)))
        (is (= #{:ci/no-refuted} (:missing-ci r)))))
    (testing "a failing check -> blocked even if present"
      (let [ds (-> (pr-datoms) (into pol)
                   (into (p/ci->datoms {:id "ci1" :pr "pr1" :check :ci/coverage
                                        :state :ci.state/pass :at-commit "HEAD2"}))
                   (into (p/ci->datoms {:id "ci2" :pr "pr1" :check :ci/no-refuted
                                        :state :ci.state/fail :at-commit "HEAD2"})))
            r (p/evaluate-merge ds "pr1")]
        (is (some #{:ci-failing} (:reasons r)))
        (is (= #{:ci/no-refuted} (:failing-ci r)))))
    (testing "all required checks pass at head -> mergeable"
      (let [ds (-> (pr-datoms) (into pol)
                   (into (p/ci->datoms {:id "ci1" :pr "pr1" :check :ci/coverage
                                        :state :ci.state/pass :at-commit "HEAD2"}))
                   (into (p/ci->datoms {:id "ci2" :pr "pr1" :check :ci/no-refuted
                                        :state :ci.state/pass :at-commit "HEAD2"})))
            r (p/evaluate-merge ds "pr1")]
        (is (:mergeable? r))))))

(deftest already-merged-not-mergeable
  (let [ds (g/pr->datoms {:id "pr1" :repo "repo1" :number 1 :title "x"
                          :author "did:key:zA" :base-ref "refs/heads/main"
                          :head-ref "refs/heads/y" :base-commit "B" :head-commit "H"
                          :state :pr.state/merged :closes-issues #{}})
        r (p/evaluate-merge ds "pr1")]
    (is (not (:mergeable? r)))
    (is (some #{:not-open} (:reasons r)))))

;; ---------------------------------------------------------------------------
;; landing a PR: advance ref, mark merged, close issues
;; ---------------------------------------------------------------------------

(deftest land-pr-advances-ref-and-closes-issues
  (let [ds (-> []
               (into (g/pr->datoms {:id "pr1" :repo "repo1" :number 1 :title "x"
                                    :author "did:key:zA" :base-ref "refs/heads/main"
                                    :base-commit "BASE" :head-ref "refs/heads/y"
                                    :head-commit "HEAD2" :state :pr.state/open
                                    :closes-issues #{"i1"}}))
               (into [["mainref" :ref/name "refs/heads/main"]
                      ["mainref" :ref/commit "BASE"]])
               (into (g/issue->datoms {:id "i1" :repo "repo1" :number 1 :title "bug"
                                       :author "did:key:zA" :state :issue.state/open
                                       :created-at 0 :labels #{} :anchors #{}})))
        tx (p/land-pr-tx ds "pr1" "MERGEDCID")]
    (testing "ref advances to the merge commit"
      (is (some #{["mainref" :ref/commit "BASE"]} (:retract tx)))
      (is (some #{["mainref" :ref/commit "MERGEDCID"]} (:assert tx))))
    (testing "PR marked merged with the merge commit"
      (is (some #{["pr1" :pr/state :pr.state/merged]} (:assert tx)))
      (is (some #{["pr1" :pr/merged-commit "MERGEDCID"]} (:assert tx))))
    (testing "linked issue is closed"
      (is (some #{["i1" :issue/state :issue.state/open]} (:retract tx)))
      (is (some #{["i1" :issue/state :issue.state/closed]} (:assert tx))))))

(defn -main []
  (let [{:keys [fail error]} (run-tests 'kotoba.gitpolicy-test)]
    (+ (or fail 0) (or error 0))))
