(ns crowdfunding.campaign
  "Campaign — the funded thing itself, and the state table that decides
  when money is allowed to move.

  A rewards crowdfunding campaign is not a store listing. The difference
  that matters is TIME: a backer commits to something that does not exist
  yet, at a price fixed today, redeemable at a date the creator estimates.
  Every rule in this library follows from that gap, and the two rules that
  follow from it here are:

  1. **All-or-nothing is a property of the campaign, not of a payment.**
     Under `:all-or-nothing`, no backer is charged unless the goal is met
     at the deadline. That is why `:live -> :collecting` is not an edge in
     this table: a campaign must pass through `:funding-succeeded` (a
     decided outcome) before anything is collectible. Collection cannot be
     reached by accident.
  2. **A suspended campaign has no automatic exit.** `:suspended` is where
     trust-and-safety puts a campaign it believes is misrepresenting
     itself, and the only way out is `reinstate`, which requires a named
     human. An actor that could un-suspend a campaign on its own would
     make suspension worthless.

  Amounts are INTEGER minor units of `:campaign/currency` (yen, cents) —
  never floats, the `kotoba.reji` discipline that `marketplace.settlement`
  also keeps.

  Timestamps are ISO-8601 UTC strings, so lexicographic compare IS
  chronological compare. Pure: no clock, no network, no randomness."
  (:require [kotoba.lang.text :as str]))

;; ───────────────────────────── funding model ─────────────────────────────

(def funding-models
  "`:all-or-nothing` — nothing is collected unless the goal is met by the
  deadline; the backer's risk is bounded by the creator's own target.
  `:flexible` — the creator keeps whatever was pledged. Both exist in the
  wild; this library refuses to let a campaign be ambiguous about which one
  a backer agreed to, because that ambiguity is the single most common
  crowdfunding dispute."
  #{:all-or-nothing :flexible})

(def pricing-models
  "How the backer's final price is determined.

  `:fixed` — the price is set at pledge time. This is what the category
  means by 'crowdfunding', and it is also, for anything with a bill of
  materials, an unhedged short on the components: the creator fixes a
  price today and buys parts months later. ADR-2607268000 declined it for
  exactly that reason after DDR5 rose 448% in twelve months.

  `:deposit-plus-settlement` — the backer commits a deposit for a build
  slot and a stated margin; the parts cost passes through at settlement,
  bounded by a cap the backer agreed to at pledge time. The commodity risk
  sits with the party that can see the market, and the backer's exposure
  is bounded and stated rather than absorbed by a creator who may not
  survive absorbing it.

  Supporting only `:fixed` would be a platform that cannot express the
  structure this workspace's own hardware campaign chose."
  #{:fixed :deposit-plus-settlement})

(def ^:private min-duration-days 1)

(def max-duration-days
  "Upper bound on a funding period. A long campaign is not a bigger
  campaign — it is a longer window in which the estimated delivery date
  ages while nothing is collected. 60 days is the industry ceiling and
  this library keeps it as a hard validation rather than advice."
  60)

;; ───────────────────────────── lifecycle ─────────────────────────────

(def states
  "Campaign lifecycle. Note that funding OUTCOME (`:funding-succeeded` /
  `:funding-failed`) is separate from COLLECTION (`:collecting`): the
  outcome is decided by arithmetic at the deadline, collection is a
  multi-day process that can itself partially fail. Conflating them is
  how a platform ends up reporting a raise it never actually received."
  #{:draft :in-review :live
    :funding-succeeded :funding-failed
    :collecting :fulfilling :completed
    :cancelled :suspended})

(def transitions
  "Allowed transitions, as an explicit table in the style of
  `kotoba.okaimono/transitions`.

  What is deliberately ABSENT:
  - `:live -> :collecting` — see the all-or-nothing note above.
  - anything out of `:suspended` — only `reinstate` crosses that line.
  - anything out of `:funding-failed`, `:cancelled`, `:completed` — a
    campaign that failed is not re-openable; a new campaign is a new
    campaign, with a new set of consents from its backers.
  - `:collecting -> :funding-failed` IS present, because a campaign whose
    collections all drop off has not, in fact, been funded."
  {:draft             #{:in-review :cancelled}
   :in-review         #{:live :draft :cancelled}
   :live              #{:funding-succeeded :funding-failed :cancelled :suspended}
   :funding-succeeded #{:collecting :suspended}
   :funding-failed    #{}
   :collecting        #{:fulfilling :funding-failed :suspended}
   :fulfilling        #{:completed :suspended}
   :completed         #{}
   :cancelled         #{}
   :suspended         #{}})

;; ───────────────────────────── record ─────────────────────────────

(defn campaign
  "Build a campaign record.

  `risks` is required by `campaign-errors`, not optional-with-a-default.
  A campaign page that does not state what could go wrong is the exact
  artifact this domain exists to prevent, and defaulting it to an empty
  string would let one through."
  [{:keys [id creator title currency goal-minor funding-model category
           duration-days launched-at deadline story risks
           late-pledges? ships-to pricing-model]
    :or   {funding-model :all-or-nothing
           pricing-model :fixed
           late-pledges? false
           ships-to      #{}}}]
  {:campaign/pricing-model pricing-model
   :campaign/id            (str id)
   :campaign/creator       (str creator)
   :campaign/title         title
   :campaign/currency      currency
   :campaign/goal-minor    goal-minor
   :campaign/funding-model funding-model
   :campaign/category      category
   :campaign/duration-days duration-days
   :campaign/launched-at   launched-at
   :campaign/deadline      deadline
   :campaign/story         story
   :campaign/risks         risks
   :campaign/late-pledges? (boolean late-pledges?)
   :campaign/ships-to      (set ships-to)
   :campaign/state         :draft})

(defn campaign-errors
  "Everything that must be true before a campaign may be submitted for
  review. Returns [] when valid — errors are DATA, so a governor can quote
  them back to a creator verbatim rather than paraphrasing a thrown
  exception."
  [c]
  (vec
   (concat
    (when (str/blank? (str (:campaign/id c)))
      [{:campaign.error/code :missing-id}])
    (when (str/blank? (str (:campaign/creator c)))
      [{:campaign.error/code :missing-creator}])
    (when (str/blank? (str (:campaign/title c)))
      [{:campaign.error/code :missing-title}])
    (when-not (and (integer? (:campaign/goal-minor c))
                   (pos? (:campaign/goal-minor c)))
      [{:campaign.error/code :goal-must-be-positive}])
    (when-not (re-matches #"^[A-Z]{3}$" (str (:campaign/currency c)))
      [{:campaign.error/code :invalid-currency}])
    (when-not (contains? funding-models (:campaign/funding-model c))
      [{:campaign.error/code   :unknown-funding-model
        :campaign.error/detail (pr-str (:campaign/funding-model c))}])
    (when-not (contains? pricing-models (:campaign/pricing-model c))
      [{:campaign.error/code   :unknown-pricing-model
        :campaign.error/detail (pr-str (:campaign/pricing-model c))}])
    (when-not (and (integer? (:campaign/duration-days c))
                   (<= min-duration-days (:campaign/duration-days c) max-duration-days))
      [{:campaign.error/code   :invalid-duration
        :campaign.error/detail (str min-duration-days ".." max-duration-days " days")}])
    (when (str/blank? (str (:campaign/risks c)))
      [{:campaign.error/code   :missing-risks-disclosure
        :campaign.error/detail "backers must be told what could go wrong"}])
    (when (str/blank? (str (:campaign/story c)))
      [{:campaign.error/code :missing-story}])
    (when (and (:campaign/launched-at c) (:campaign/deadline c)
               (not (neg? (compare (str (:campaign/launched-at c))
                                   (str (:campaign/deadline c))))))
      [{:campaign.error/code :deadline-not-after-launch}]))))

;; ───────────────────────────── transitions ─────────────────────────────

(defn advance
  "Move a campaign to `to` when the table allows it; nil otherwise.

  An illegal transition is a REFUSAL, not an exception — `kotoba.okaimono/
  advance`'s convention, kept so a caller can branch on nil instead of
  wrapping every state change in a try."
  [c to]
  (when (contains? (get transitions (:campaign/state c) #{}) to)
    (assoc c :campaign/state to)))

(defn suspend
  "Suspend a campaign. Records who suspended it and why, because a
  suspension that cannot be attributed cannot be appealed."
  [c {:keys [by at reason]}]
  (when (and (contains? (get transitions (:campaign/state c) #{}) :suspended)
             (not (str/blank? (str by))))
    (assoc c
           :campaign/state :suspended
           :campaign/suspension {:suspension/prior-state (:campaign/state c)
                                 :suspension/by     by
                                 :suspension/at     at
                                 :suspension/reason reason})))

(defn reinstate
  "The ONLY path out of `:suspended`, and it requires a named human and a
  rationale — the same shape as `marketplace.settlement/resolve-dispute`.

  This function does not decide whether a campaign should come back. It
  records that a human decided, and refuses (nil) if handed a decision
  with no human attached. An actor synthesizing `decided-by` here would be
  fabricating a sign-off, which is what the audit ledger exists to make
  impossible."
  [c {:keys [decided-by decided-at rationale to]}]
  (let [target (or to (get-in c [:campaign/suspension :suspension/prior-state]))]
    (when (and (= :suspended (:campaign/state c))
               (contains? states target)
               (not= :suspended target)
               (not (str/blank? (str decided-by))))
      (-> c
          (assoc :campaign/state target)
          (assoc :campaign/reinstatement {:reinstatement/decided-by decided-by
                                          :reinstatement/decided-at decided-at
                                          :reinstatement/rationale  rationale
                                          :reinstatement/human?     true})))))

;; ───────────────────────────── time predicates ─────────────────────────────

(defn deadline-passed?
  "Has the funding window closed at `now`? ISO-8601 UTC strings compare
  lexicographically, so no clock and no date library is needed here."
  [c now]
  (and (some? (:campaign/deadline c))
       (not (neg? (compare (str now) (str (:campaign/deadline c)))))))

(defn accepting-pledges?
  "May a NEW pledge be taken at `now`?

  Two disjoint windows: the live funding window, and — only if the creator
  opted in — the late-pledge window after a successful outcome. Late
  pledges are off by default because they change what a backer is buying:
  the goal is already decided, so a late pledge is a pre-order, not a vote
  on whether the project happens."
  [c now]
  (boolean
   (or (and (= :live (:campaign/state c)) (not (deadline-passed? c now)))
       (and (:campaign/late-pledges? c)
            (contains? #{:funding-succeeded :collecting} (:campaign/state c))))))

(defn late-pledge?
  "Is a pledge taken at `now` a late pledge (post-outcome) rather than a
  funding-window pledge? Collection treats the two differently, so the
  distinction is carried on the pledge rather than re-derived later."
  [c now]
  (boolean (and (accepting-pledges? c now)
                (not= :live (:campaign/state c))
                (deadline-passed? c now))))
