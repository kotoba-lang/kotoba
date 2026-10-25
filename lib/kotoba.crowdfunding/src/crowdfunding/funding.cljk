(ns crowdfunding.funding
  "Funding progress and the deadline outcome — the arithmetic that decides
  whether anyone gets charged.

  This namespace reports THREE different totals and refuses to collapse
  them, because a platform that reports one number as 'raised' is always
  overstating at least one of them:

  - `:funding/pledged-minor`  — goods committed by pledges that still stand.
    This is the funding bar. It is a promise, not money.
  - `:funding/collected-minor` — goods on pledges that actually paid.
  - `:funding/at-risk-minor`   — goods on pledges whose payment is failing
    but still being retried. Included in pledged, absent from collected;
    the gap between the two is the number a creator most needs and is most
    often not shown.

  Shipping is excluded from all three (see `pledge/goods-minor`): a goal is
  a goal for the project, not for postage.

  `outcome` is the only function here that decides anything, and what it
  decides is arithmetic — did the total reach the goal by the deadline. It
  does not decide whether a campaign SHOULD be funded; suspension and
  trust-and-safety live in `crowdfunding.trust` and end at a human.

  Pure: no clock, no network, no randomness."
  (:require [crowdfunding.campaign :as campaign]
            [crowdfunding.pledge :as pledge]))

;; ───────────────────────────── tally ─────────────────────────────

(defn tally
  "Reduce a campaign's pledges into the three totals plus backer counts.

  Backers are counted DISTINCTLY by `:pledge/backer`, so one backer with a
  tier and a late pledge is one backer. Counting pledges and calling them
  backers is the oldest inflation in this domain."
  [pledges rewards]
  (let [standing   (filter pledge/counts? pledges)
        collected  (filter #(= :collected (:pledge/state %)) pledges)
        at-risk    (filter #(#{:failed :retrying} (:pledge/state %)) pledges)
        sum        (fn [ps] (reduce + 0 (keep #(pledge/goods-minor % rewards) ps)))
        unresolved (count (remove #(pledge/goods-minor % rewards) standing))]
    {:funding/pledged-minor   (sum standing)
     :funding/collected-minor (sum collected)
     :funding/at-risk-minor   (sum at-risk)
     :funding/backers         (count (distinct (map :pledge/backer standing)))
     :funding/collected-backers (count (distinct (map :pledge/backer collected)))
     :funding/pledge-count    (count standing)
     ;; Carried, not hidden: a pledge whose total cannot be computed is
     ;; excluded from the sums, and a caller that does not know how many
     ;; were excluded cannot tell a small campaign from a broken one.
     :funding/unresolved      unresolved}))

(defn percent-funded
  "Progress toward goal in basis points of the goal, using PLEDGED. Basis
  points rather than a float — this number ends up in a UI and in a
  ledger, and the two must agree exactly."
  [c t]
  (let [goal (:campaign/goal-minor c 0)]
    (when (pos? goal)
      (quot (* 10000 (:funding/pledged-minor t 0)) goal))))

(defn goal-met?
  "Has PLEDGED reached the goal? Note the deliberate asymmetry with
  `crowdfunding.collection/finalize`, which asks the same question of
  COLLECTED. Both are legitimate questions; answering the first and
  reporting it as the second is how a campaign is announced as funded and
  then quietly is not."
  [c t]
  (>= (:funding/pledged-minor t 0) (:campaign/goal-minor c 0)))

;; ───────────────────────────── stretch goals ─────────────────────────────

(defn stretch-goal
  "A commitment that unlocks at a threshold above the goal. It is a
  PROMISE with a `:stretch/scope` note, because every stretch goal adds
  work to a delivery date that was estimated before it existed."
  [{:keys [id threshold-minor title scope]}]
  {:stretch/id              (str id)
   :stretch/threshold-minor threshold-minor
   :stretch/title           title
   :stretch/scope           scope})

(defn unlocked
  "Which stretch goals the pledged total has reached, ascending. Ordered
  by threshold then id so the list is stable."
  [stretch-goals t]
  (->> stretch-goals
       (filter #(>= (:funding/pledged-minor t 0) (:stretch/threshold-minor % 0)))
       (sort-by (juxt :stretch/threshold-minor :stretch/id))
       vec))

(defn next-stretch
  "The nearest unreached stretch goal and the gap to it, or nil."
  [stretch-goals t]
  (when-let [g (->> stretch-goals
                    (remove #(>= (:funding/pledged-minor t 0) (:stretch/threshold-minor % 0)))
                    (sort-by (juxt :stretch/threshold-minor :stretch/id))
                    first)]
    (assoc g :stretch/gap-minor (- (:stretch/threshold-minor g)
                                   (:funding/pledged-minor t 0)))))

;; ───────────────────────────── outcome ─────────────────────────────

(defn outcome
  "The funding outcome at `now`, or nil while the window is still open.

  Under `:all-or-nothing` the goal must be met. Under `:flexible` any
  positive total succeeds — but a flexible campaign that raised NOTHING
  still fails, because there is no such thing as collecting zero and
  calling it a success.

  Returns a decision record rather than a bare keyword: the basis
  (`goal`, `pledged`, `model`) travels with it so an audit ledger entry
  can be reproduced without re-reading the campaign as it was that day."
  [c t now]
  (when (and (= :live (:campaign/state c)) (campaign/deadline-passed? c now))
    (let [pledged (:funding/pledged-minor t 0)
          goal    (:campaign/goal-minor c 0)
          model   (:campaign/funding-model c)
          success (case model
                    :all-or-nothing (>= pledged goal)
                    :flexible       (pos? pledged)
                    false)]
      {:outcome/state         (if success :funding-succeeded :funding-failed)
       :outcome/funding-model model
       :outcome/goal-minor    goal
       :outcome/pledged-minor pledged
       :outcome/backers       (:funding/backers t 0)
       :outcome/decided-at    now
       ;; Arithmetic, not judgement. Suspension is a separate path that
       ;; ends at a named human (`campaign/suspend`).
       :outcome/basis         :arithmetic})))

(defn apply-outcome
  "Move the campaign into its decided outcome state. Returns nil if the
  transition is not allowed — a suspended campaign does not silently
  resume its way to `:funding-succeeded` because a deadline passed."
  [c o]
  (when o (campaign/advance c (:outcome/state o))))
