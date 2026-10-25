(ns crowdfunding.collection
  "The collection window — the days after a successful deadline in which
  authorizations are actually charged, and some of them fail.

  This namespace exists because 'the campaign raised X' and 'the creator
  received X' are different numbers, and the gap between them is a real,
  routine, double-digit-percentage phenomenon on large campaigns: cards
  expire between pledging and the deadline, issuers decline a charge that
  is weeks older than the authorization, backers change banks. A design
  that treats collection as a single instantaneous event has no place to
  put any of that, so it reports the first number and lets the creator
  discover the second.

  Two rules give the window its shape:

  1. **Collection is only reachable from a decided outcome.** The plan
     refuses to exist for a campaign that is not `:funding-succeeded` or
     `:collecting`. Under all-or-nothing this is what makes the promise
     literal rather than procedural.
  2. **A retry is bounded in both attempts and time.** A backer whose card
     is failing must eventually be dropped, not pursued forever; a dropped
     backer is a lost sale, and pretending otherwise inflates the total the
     creator plans production against.

  Amounts here are the FULL charge (`pledge/total-minor` — goods plus
  shipping), unlike `crowdfunding.funding`, which reports goods only
  because that is what a goal measures. Pure: no clock, no network."
  (:require [crowdfunding.campaign :as campaign]
            [crowdfunding.pledge :as pledge]))

;; ───────────────────────────── window ─────────────────────────────

(def default-retry-days
  "How long a failing payment is pursued. Long enough for a backer to
  update a card, short enough that a creator can plan production against a
  final number." 7)

(def default-max-attempts
  "Attempts per pledge, including the first. Past this, further tries are
  noise that only annoys the backer's issuer." 4)

(defn window
  "The collection window for a campaign.

  `opened-at` and `closes-at` are supplied by the caller — this library
  has no clock. `closes-at` being explicit rather than derived from
  `retry-days` is deliberate: the two can legitimately differ (a platform
  may extend a window), and deriving it would hide that decision."
  [{:keys [opened-at closes-at retry-days max-attempts]
    :or   {retry-days default-retry-days max-attempts default-max-attempts}}]
  {:window/opened-at    opened-at
   :window/closes-at    closes-at
   :window/retry-days   retry-days
   :window/max-attempts max-attempts})

(defn window-closed? [w now]
  (and (some? (:window/closes-at w))
       (not (neg? (compare (str now) (str (:window/closes-at w)))))))

;; ───────────────────────────── plan ─────────────────────────────

(def collectible-states
  "Campaign states in which charging a backer is legitimate. `:live` is
  absent, which is the whole point of all-or-nothing."
  #{:funding-succeeded :collecting})

(defn charge
  "One intended charge. `:charge/amount-minor` is what the backer sees on
  their statement, so it is the full total including shipping."
  [p amount-minor]
  {:charge/pledge       (:pledge/id p)
   :charge/backer       (:pledge/backer p)
   :charge/amount-minor amount-minor
   :charge/attempt      (inc (:pledge/attempts p 0))})

(defn collection-plan
  "Everything that should be charged for a campaign, or an explicit
  refusal.

  Returns either
    {:plan/refused :not-collectible-state | :not-funded, …}
  or
    {:plan/campaign … :plan/charges [..] :plan/total-minor n
     :plan/unresolved [..]}

  Charges are ordered by pledge id, a total order, so two runs of the same
  plan produce the same sequence — a plan that reorders between runs cannot
  be diffed against what was actually attempted.

  `:plan/unresolved` lists pledges whose total could not be computed
  (a missing add-on reward, an unshippable destination). They are NEVER
  silently charged at a guessed amount and never silently skipped; they
  are named, so a human can fix the data."
  [c pledges rewards]
  (if-not (contains? collectible-states (:campaign/state c))
    {:plan/refused :not-collectible-state
     :plan/detail  (:campaign/state c)}
    (let [pending (->> pledges
                       (filter #(#{:authorized :retrying} (:pledge/state %)))
                       (sort-by :pledge/id))
          priced  (map (fn [p] [p (pledge/total-minor p rewards)]) pending)
          ok      (filter (comp integer? second) priced)
          bad     (remove (comp integer? second) priced)]
      {:plan/campaign    (:campaign/id c)
       :plan/currency    (:campaign/currency c)
       :plan/charges     (mapv (fn [[p amt]] (charge p amt)) ok)
       :plan/total-minor (reduce + 0 (map second ok))
       :plan/unresolved  (mapv (comp :pledge/id first) bad)
       :plan/custodial?  false})))

;; ───────────────────────────── attempts ─────────────────────────────

(def attempt-outcomes
  "`:ok` collected. `:soft-decline` may be retried (insufficient funds,
  expired card the backer can replace). `:hard-decline` may not (closed
  account, stolen card) — retrying it is not persistence, it is a fraud
  signal to the issuer."
  #{:ok :soft-decline :hard-decline})

(defn record-attempt
  "Apply a payment attempt's outcome to a pledge. Returns the updated
  pledge, or nil when the pledge is not in a chargeable state or the
  outcome is unknown — an unrecognised outcome must not be interpreted as
  a decline, and must not be interpreted as a success.

  A `:hard-decline` lands in `:failed` with `:pledge/retryable? false`
  rather than jumping straight to `:dropped`. The extra step keeps the
  state table honest (`:authorized -> :dropped` is not an edge) and leaves
  the drop itself to `expire`, which is where the audit entry belongs."
  [p {:keys [outcome at reason]}]
  (when (and (contains? attempt-outcomes outcome)
             (#{:authorized :retrying} (:pledge/state p)))
    (let [p' (-> p
                 (update :pledge/attempts (fnil inc 0))
                 (assoc :pledge/last-attempt-at at))]
      (case outcome
        :ok           (assoc p' :pledge/state :collected :pledge/collected-at at)
        :soft-decline (assoc p' :pledge/state :failed
                             :pledge/retryable? true
                             :pledge/decline-reason reason)
        :hard-decline (assoc p' :pledge/state :failed
                             :pledge/retryable? false
                             :pledge/decline-reason reason)))))

(defn retryable?
  "May this pledge be charged again inside `w` at `now`?

  All four conditions, not any: the pledge failed softly, attempts remain,
  the window is open, and the pledge has not already been dropped."
  [p w now]
  (boolean (and (= :failed (:pledge/state p))
                (not (false? (:pledge/retryable? p)))
                (< (:pledge/attempts p 0) (:window/max-attempts w default-max-attempts))
                (not (window-closed? w now)))))

(defn retry
  "Move a failed pledge back into `:retrying` so the next plan picks it
  up. Refuses (nil) when `retryable?` is false — the bound lives in the
  domain, not in whichever scheduler happens to call this."
  [p w now]
  (when (retryable? p w now)
    (pledge/advance p :retrying)))

(defn expire
  "Drop a pledge that can no longer be collected. Refuses (nil) for a
  pledge that is still retryable — dropping a backer early is
  indistinguishable, in the final numbers, from a backer who never
  existed."
  [p w now]
  (when (and (#{:failed :retrying} (:pledge/state p))
             (not (retryable? p w now)))
    (some-> (pledge/advance p :dropped)
            (assoc :pledge/dropped-at now
                   :pledge/drop-reason (cond
                                         (false? (:pledge/retryable? p)) :hard-decline
                                         (window-closed? w now)          :window-closed
                                         :else                           :attempts-exhausted)))))

;; ───────────────────────────── finalize ─────────────────────────────

(defn finalize
  "Close the window and state, in one record, what actually happened.

  The three facts a creator needs and platforms routinely separate:
  `:collection/collected-minor` (money in), `:collection/dropped-minor`
  (authorizations that never paid) and `:collection/drop-off-bps` (the
  ratio, in basis points, so it can go in a ledger unrounded).

  `:collection/goal-still-met?` compares COLLECTED goods against the goal.
  It is reported, not acted on: a campaign that hit its goal on
  authorizations and fell short on collections is not retroactively
  unfunded — backers were charged, the creator owes rewards — but a
  creator who plans production from the pledged number and discovers the
  collected one at the factory is the failure this field exists to
  prevent.

  `:collection/proposed-state` is a PROPOSAL for the campaign's next
  state, never applied here. Zero collected means nothing happened and the
  campaign failed; anything collected moves to fulfilment.

  `:collection/unresolved` names every pledge whose total could not be
  priced. Those are excluded from the sums above — necessarily, since
  there is no number to add — so the count travels with the result. A
  drop-off ratio computed over a set that quietly lost members is a ratio
  that reads better than the truth."
  [c pledges rewards]
  (let [collected (filter #(= :collected (:pledge/state %)) pledges)
        dropped   (filter #(= :dropped (:pledge/state %)) pledges)
        pending   (filter #(#{:authorized :failed :retrying} (:pledge/state %)) pledges)
        sum-total (fn [ps] (reduce + 0 (keep #(pledge/total-minor % rewards) ps)))
        sum-goods (fn [ps] (reduce + 0 (keep #(pledge/goods-minor % rewards) ps)))
        got       (sum-total collected)
        lost      (sum-total dropped)
        denom     (+ got lost)
        ;; Same discipline as `funding/tally`: a pledge whose total cannot
        ;; be priced is excluded from the sums, and a caller who does not
        ;; know how many were excluded cannot tell a clean finalisation
        ;; from a lossy one. Naming them is the difference between a
        ;; number and a number you can trust.
        unresolved (->> (concat collected dropped pending)
                        (remove #(pledge/total-minor % rewards))
                        (mapv :pledge/id)
                        sort
                        vec)]
    {:collection/campaign          (:campaign/id c)
     :collection/currency          (:campaign/currency c)
     :collection/collected-minor   got
     :collection/collected-goods-minor (sum-goods collected)
     :collection/dropped-minor     lost
     :collection/pending-count     (count pending)
     :collection/collected-backers (count (distinct (map :pledge/backer collected)))
     :collection/dropped-backers   (count (distinct (map :pledge/backer dropped)))
     :collection/drop-off-bps      (if (pos? denom) (quot (* 10000 lost) denom) 0)
     :collection/goal-minor        (:campaign/goal-minor c)
     :collection/goal-still-met?   (>= (sum-goods collected) (:campaign/goal-minor c 0))
     :collection/shortfall-minor   (max 0 (- (:campaign/goal-minor c 0) (sum-goods collected)))
     :collection/unresolved        unresolved
     :collection/complete?         (zero? (count pending))
     :collection/proposed-state    (if (pos? got) :fulfilling :funding-failed)}))

(defn apply-finalization
  "Advance the campaign to the proposed state. Separate from `finalize`
  so the arithmetic can be computed, audited and approved before it moves
  anything — and so a suspended campaign refuses the move."
  [c f]
  (campaign/advance c (:collection/proposed-state f)))
