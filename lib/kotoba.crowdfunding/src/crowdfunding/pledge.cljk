(ns crowdfunding.pledge
  "Pledge — a backer's commitment, and the state machine that separates
  'promised' from 'paid'.

  The single most consequential fact about rewards crowdfunding is that a
  pledge is an AUTHORIZATION, not a payment. Money is not taken when the
  backer clicks; it is taken (or not) after the deadline. Every field and
  every state here exists to keep those two moments distinguishable:

  - `:authorized` — the backer has committed. Nothing has been charged.
    A campaign's headline 'raised' number is made of these, which is why
    `crowdfunding.funding` and `crowdfunding.collection` report different
    totals and both are correct.
  - `:collected` — money actually arrived.
  - `:failed` → `:retrying` → `:dropped` — the payment did not go through.
    This path is not an edge case: on a large campaign a meaningful
    fraction of authorizations never become collections, and a system with
    no vocabulary for it will report a raise that never landed.
  - `:cancelled` — the backer withdrew, which they may do at any time
    before the funding window closes. That right is not a courtesy; it is
    the counterweight to being charged later for something not yet built.

  A pledge total is `tier minimum-or-more + add-ons + shipping`, all
  integer minor units of the campaign currency. Pure: no clock, no
  network, no randomness."
  (:require [kotoba.lang.text :as str]
            [crowdfunding.campaign :as campaign]
            [crowdfunding.reward :as reward]))

;; ───────────────────────────── lifecycle ─────────────────────────────

(def states
  #{:authorized :collected :failed :retrying :dropped :refunded :cancelled})

(def transitions
  "What is deliberately ABSENT:
  - `:authorized -> :refunded`. There is nothing to refund until money has
    been collected; a refund on an uncollected pledge is a cancellation,
    and calling it a refund would put a payment in the ledger that never
    happened.
  - anything out of `:dropped`. A dropped pledge is a backer the campaign
    lost; recovering them is a NEW pledge with a fresh authorization, not
    a resurrection of an expired one."
  {:authorized #{:collected :failed :cancelled}
   :failed     #{:retrying :dropped}
   :retrying   #{:collected :failed :dropped}
   :collected  #{:refunded}
   :dropped    #{}
   :refunded   #{}
   :cancelled  #{}})

(def counts-toward-funding
  "States whose amount belongs in the campaign's progress toward goal.

  `:authorized` counts (that is what a funding bar means before the
  deadline) and `:collected` counts. `:failed` and `:retrying` also count,
  because the backer's commitment stands while collection is still being
  attempted — dropping them from the total the moment a card bounces would
  make the bar jump around during the collection window. `:dropped`,
  `:cancelled` and `:refunded` do not count."
  #{:authorized :collected :failed :retrying})

;; ───────────────────────────── record ─────────────────────────────

(defn pledge
  "Build a pledge.

  `amount-minor` is the backer's chosen pledge to the TIER — it may exceed
  the tier minimum, which is how over-pledging works. Add-ons and shipping
  are carried separately rather than folded in, so a survey or a refund
  can later reason about them independently."
  [{:keys [id campaign backer amount-minor reward add-ons ship-to
           placed-at late? note]
    :or   {add-ons [] late? false}}]
  {:pledge/id           (str id)
   :pledge/campaign     (str campaign)
   :pledge/backer       (str backer)
   :pledge/amount-minor amount-minor
   :pledge/reward       (when reward (str reward))
   :pledge/add-ons      (vec add-ons)
   :pledge/ship-to      ship-to
   :pledge/placed-at    placed-at
   :pledge/late?        (boolean late?)
   :pledge/note         note
   :pledge/state        :authorized
   :pledge/attempts     0})

(defn add-on-line
  "One add-on on a pledge: which add-on reward, how many."
  [{:keys [reward qty] :or {qty 1}}]
  {:add-on/reward (str reward) :add-on/qty qty})

;; ───────────────────────────── totals ─────────────────────────────

(defn- reward-by-id [rewards id]
  (first (filter #(= (str id) (:reward/id %)) rewards)))

(defn add-ons-minor
  "Extended total of the pledge's add-ons. Returns nil when an add-on
  references a reward that is not in `rewards` — a missing add-on is a
  broken pledge, and silently pricing it at zero would ship a free unit."
  [p rewards]
  (reduce (fn [acc {:add-on/keys [reward qty]}]
            (if-let [r (reward-by-id rewards reward)]
              (when acc (+ acc (* qty (:reward/minimum-minor r 0))))
              nil))
          0
          (:pledge/add-ons p)))

(defn shipping-minor
  "Shipping for the pledge's tier to its destination, or nil when the tier
  cannot ship there. Add-ons ship with the tier, so this is charged once."
  [p rewards]
  (if-let [r (reward-by-id rewards (:pledge/reward p))]
    (reward/shipping-minor-for r (:pledge/ship-to p))
    0))

(defn goods-minor
  "The part of the pledge that counts toward the campaign's GOAL:
  `amount + add-ons`, with shipping excluded.

  Shipping is money that leaves again as postage; counting it toward a
  funding goal would let a campaign hit its target on freight. This mirrors
  `marketplace.settlement`, where conservation is checked against goods and
  the buyer's fixed fee rides on top. Returns nil if an add-on is
  unresolvable."
  [p rewards]
  (let [a (:pledge/amount-minor p) ao (add-ons-minor p rewards)]
    (when (and (integer? a) (integer? ao)) (+ a ao))))

(defn total-minor
  "What the backer will be charged if this pledge is collected:
  `amount + add-ons + shipping`.

  Returns nil if any component is unresolvable. A pledge whose total
  cannot be computed must not be presented to a backer as a number — that
  is the moment a platform invents a price."
  [p rewards]
  (let [a (:pledge/amount-minor p)
        ao (add-ons-minor p rewards)
        sh (shipping-minor p rewards)]
    (when (and (integer? a) (integer? ao) (integer? sh))
      (+ a ao sh))))

;; ───────────────────────────── validation ─────────────────────────────

(defn pledge-errors
  "[] when the pledge may be accepted against `c` and `rewards` at `now`.

  Tier availability is re-derived from the reward record here rather than
  trusted from the request — the 'ground truth, not self-report' rule every
  governor in this fleet applies. A request that says a sold-out tier is
  available is exactly the request this check exists for."
  [p c rewards now]
  (let [r (reward-by-id rewards (:pledge/reward p))]
    (vec
     (concat
      (when (str/blank? (str (:pledge/id p)))
        [{:pledge.error/code :missing-id}])
      (when (str/blank? (str (:pledge/backer p)))
        [{:pledge.error/code :missing-backer}])
      (when-not (= (str (:pledge/campaign p)) (str (:campaign/id c)))
        [{:pledge.error/code :campaign-mismatch}])
      (when-not (and (integer? (:pledge/amount-minor p))
                     (pos? (:pledge/amount-minor p)))
        [{:pledge.error/code :amount-must-be-positive}])
      (when-not (campaign/accepting-pledges? c now)
        [{:pledge.error/code   :campaign-not-accepting-pledges
          :pledge.error/detail (pr-str (:campaign/state c))}])
      (when (and (:pledge/reward p) (nil? r))
        [{:pledge.error/code   :unknown-reward
          :pledge.error/detail (str (:pledge/reward p))}])
      (when (and r (:reward/add-on? r))
        [{:pledge.error/code   :add-on-selected-as-tier
          :pledge.error/detail (:reward/id r)}])
      (when (and r (not (reward/available? r)))
        [{:pledge.error/code :reward-sold-out :pledge.error/detail (:reward/id r)}])
      (when (and r (not (reward/eligible? r (:pledge/amount-minor p))))
        [{:pledge.error/code   :below-reward-minimum
          :pledge.error/detail (str (:pledge/amount-minor p) "<" (:reward/minimum-minor r))}])
      (when (and r (not (reward/ships-to? r (:pledge/ship-to p))))
        [{:pledge.error/code   :not-shippable-to-destination
          :pledge.error/detail (pr-str (:pledge/ship-to p))}])
      (when (nil? (add-ons-minor p rewards))
        [{:pledge.error/code :unknown-add-on}])
      (mapcat (fn [{:add-on/keys [reward qty] :as _line}]
                (let [ar (reward-by-id rewards reward)]
                  (concat
                   (when (and ar (not (:reward/add-on? ar)))
                     [{:pledge.error/code   :tier-selected-as-add-on
                       :pledge.error/detail (:reward/id ar)}])
                   (when-not (and (integer? qty) (pos? qty))
                     [{:pledge.error/code :invalid-add-on-qty}])
                   (when (and ar (integer? (:reward/limit ar))
                              (> qty (reward/remaining ar)))
                     [{:pledge.error/code   :add-on-exceeds-remaining
                       :pledge.error/detail (:reward/id ar)}]))))
              (:pledge/add-ons p))))))

;; ───────────────────────────── backer rights ─────────────────────────────

(defn cancellable?
  "May the backer withdraw at `now`?

  Only while the funding window is open. After the deadline the campaign's
  outcome has been decided using this pledge as part of the total, and the
  creator has begun committing on the strength of it — which is why the
  post-deadline path is a REFUND decision by the creator or platform
  (`crowdfunding.refund` territory), not a unilateral backer cancellation."
  [p c now]
  (boolean (and (= :authorized (:pledge/state p))
                (= :live (:campaign/state c))
                (not (campaign/deadline-passed? c now)))))

(defn changeable?
  "May the backer change tier/amount at `now`? Same window as cancelling —
  a change is a cancel plus a new pledge, and allowing one without the
  other would let a backer escape a window the other respects."
  [p c now]
  (cancellable? p c now))

;; ───────────────────────────── transitions ─────────────────────────────

(defn advance
  "Move a pledge to `to` when the table allows it; nil otherwise."
  [p to]
  (when (contains? (get transitions (:pledge/state p) #{}) to)
    (assoc p :pledge/state to)))

(defn cancel
  "Backer-initiated withdrawal. Refuses (nil) outside the window, so the
  window is enforced by the domain rather than by whichever caller
  remembered to check."
  [p c now]
  (when (cancellable? p c now)
    (assoc p :pledge/state :cancelled :pledge/cancelled-at now)))

(defn counts?
  "Does this pledge belong in the campaign's funding total?"
  [p]
  (contains? counts-toward-funding (:pledge/state p)))
