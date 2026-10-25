(ns crowdfunding.passthrough
  "Deposit-plus-settlement pricing — the structure a campaign uses when
  its bill of materials is a commodity it has to buy later.

  Fixed-price crowdfunding asks a creator to sell, today, a thing whose
  inputs they will buy in six months. That is an unhedged short on those
  inputs. It is invisible while component prices are flat and it is fatal
  when they are not: ADR-2607268000 declined fixed-price for the Murakumo
  MK-1 after DDR5 rose 448% in twelve months, citing campaigns that
  delivered late, at a loss, or not at all for precisely this reason.

  The alternative this namespace implements moves the risk to the party
  who can see the market, and bounds the backer's exposure:

    charge at deadline  = deposit
    charge at settlement = actual parts cost + fixed margin - deposit
    and never more than  = cap agreed at pledge time

  Three properties make it honest rather than just flexible:

  1. **The cap is agreed up front and enforced here.** A settlement above
     the cap does not silently bill the backer — `settle` marks it
     `:settlement/over-cap?` and computes what the CREATOR absorbs. The
     only way past a cap is `reconsent`, which requires the backer to
     agree to a new one.
  2. **The margin is fixed and stated in the campaign's currency.** It is
     not a percentage of parts cost, because a percentage margin means the
     creator profits from component inflation, which is the incentive that
     makes pass-through pricing untrustworthy.
  3. **Evidence travels with the settlement.** `:settlement/cost-basis`
     names what was bought at what price; a pass-through number with no
     basis is just a higher price with extra steps.

  Amounts are integer minor units of the campaign currency. Pure: no
  clock, no network, no randomness."
  (:require [kotoba.lang.text :as str]))

;; ───────────────────────────── quote ─────────────────────────────

(defn quotation
  "What a backer agrees to at pledge time under this model.

  `deposit-minor` is charged with everyone else's pledge at the deadline.
  `margin-minor` is the creator's fixed take, in currency, not percent.
  `cap-minor` is the most the backer can be charged IN TOTAL — deposit
  included — and is the number that makes this structure a bounded
  commitment rather than an open cheque.

  `estimate-minor` is the creator's honest current parts estimate. It is
  carried so that a settlement can be compared against what the backer was
  shown, which is the comparison that would otherwise never be made."
  [{:keys [deposit-minor margin-minor cap-minor estimate-minor basis-note]}]
  {:quote/deposit-minor  deposit-minor
   :quote/margin-minor   margin-minor
   :quote/cap-minor      cap-minor
   :quote/estimate-minor estimate-minor
   :quote/basis-note     basis-note})

(defn quotation-errors
  "[] when a quote may be shown to a backer."
  [q]
  (let [pos-int? (fn [v] (and (integer? v) (pos? v)))
        nonneg?  (fn [v] (and (integer? v) (not (neg? v))))]
    (vec
     (concat
      (when-not (pos-int? (:quote/deposit-minor q))
        [{:passthrough.error/code :deposit-must-be-positive}])
      (when-not (nonneg? (:quote/margin-minor q))
        [{:passthrough.error/code :invalid-margin}])
      (when-not (pos-int? (:quote/cap-minor q))
        [{:passthrough.error/code :cap-must-be-positive}])
      (when-not (nonneg? (:quote/estimate-minor q))
        [{:passthrough.error/code :invalid-estimate}])
      (when (and (pos-int? (:quote/cap-minor q)) (pos-int? (:quote/deposit-minor q))
                 (< (:quote/cap-minor q) (:quote/deposit-minor q)))
        [{:passthrough.error/code :cap-below-deposit
          :passthrough.error/detail "a cap the deposit already exceeds is not a cap"}])
      (when (and (nonneg? (:quote/estimate-minor q)) (nonneg? (:quote/margin-minor q))
                 (pos-int? (:quote/cap-minor q))
                 (< (:quote/cap-minor q)
                    (+ (:quote/estimate-minor q) (:quote/margin-minor q))))
        [{:passthrough.error/code :cap-below-own-estimate
          :passthrough.error/detail "the creator's own estimate already breaches the cap"}])
      (when (str/blank? (str (:quote/basis-note q)))
        [{:passthrough.error/code :missing-basis-note
          :passthrough.error/detail "a pass-through price with no stated basis is just a price"}])))))

(defn headroom-minor
  "How much component inflation the cap absorbs before the creator starts
  paying for it. The number a creator should be looking at before
  launching, and the one a fixed-price campaign has no way to express."
  [q]
  (- (:quote/cap-minor q) (:quote/estimate-minor q) (:quote/margin-minor q)))

;; ───────────────────────────── cost basis ─────────────────────────────

(defn cost-line
  "One purchased input: what it is, how many, what it actually cost."
  [{:keys [part qty unit-minor source purchased-at]}]
  {:cost/part         (str part)
   :cost/qty          qty
   :cost/unit-minor   unit-minor
   :cost/extended-minor (* qty unit-minor)
   :cost/source       source
   :cost/purchased-at purchased-at})

(defn cost-basis
  "The evidenced parts cost for one unit. Lines are sorted by part so two
  computations of the same basis are byte-identical, which is what makes
  a settlement diffable against the previous one."
  [lines]
  (let [ls (vec (sort-by :cost/part lines))]
    {:basis/lines       ls
     :basis/total-minor (reduce + 0 (map :cost/extended-minor ls))
     :basis/parts       (count ls)}))

(defn basis-errors [b]
  (vec
   (concat
    (when (empty? (:basis/lines b))
      [{:passthrough.error/code :empty-cost-basis}])
    (mapcat (fn [l]
              (concat
               (when (str/blank? (str (:cost/part l)))
                 [{:passthrough.error/code :missing-part}])
               (when-not (and (integer? (:cost/qty l)) (pos? (:cost/qty l)))
                 [{:passthrough.error/code :invalid-qty
                   :passthrough.error/detail (:cost/part l)}])
               (when-not (and (integer? (:cost/unit-minor l)) (not (neg? (:cost/unit-minor l))))
                 [{:passthrough.error/code :invalid-unit-price
                   :passthrough.error/detail (:cost/part l)}])
               (when (str/blank? (str (:cost/source l)))
                 [{:passthrough.error/code :missing-source
                   :passthrough.error/detail (:cost/part l)}])))
            (:basis/lines b)))))

;; ───────────────────────────── settlement ─────────────────────────────

(defn settle
  "Compute the final charge for one backer once the parts are actually
  bought.

  Returns the balance due, and — when the true cost breaches the agreed
  cap — how much of the overage the CREATOR absorbs. The backer is never
  charged past the cap by this function; there is no branch here that can
  produce one, which is the point.

  `:settlement/vs-estimate-minor` is the delta against what the backer was
  shown at pledge time. Positive means components rose. A creator who
  cannot show that number is a creator asking to be trusted rather than
  read."
  [q basis]
  (let [cost     (:basis/total-minor basis 0)
        margin   (:quote/margin-minor q 0)
        deposit  (:quote/deposit-minor q 0)
        cap      (:quote/cap-minor q 0)
        true-total (+ cost margin)
        billable   (min true-total cap)
        over?      (> true-total cap)]
    {:settlement/cost-basis     basis
     :settlement/parts-minor    cost
     :settlement/margin-minor   margin
     :settlement/true-total-minor true-total
     :settlement/cap-minor      cap
     :settlement/billable-total-minor billable
     :settlement/deposit-minor  deposit
     ;; Never negative: a settlement that computed below the deposit is a
     ;; REFUND, reported separately rather than as a negative charge that
     ;; a payment rail would happily execute in the wrong direction.
     :settlement/balance-due-minor (max 0 (- billable deposit))
     :settlement/refund-due-minor  (max 0 (- deposit billable))
     :settlement/over-cap?      over?
     :settlement/creator-absorbs-minor (if over? (- true-total cap) 0)
     :settlement/vs-estimate-minor (- cost (:quote/estimate-minor q 0))
     :settlement/custodial?     false}))

(defn reconsent
  "The ONLY way a backer is charged above a cap: they agree to a new one.

  Requires the backer to be named and the new cap to actually be higher —
  a 'reconsent' that lowers or repeats the cap is either a mistake or a
  record being manufactured. Returns a new quote, so the settlement is
  recomputed from an agreement rather than patched."
  [q {:keys [new-cap-minor agreed-by agreed-at rationale]}]
  (when (and (integer? new-cap-minor)
             (> new-cap-minor (:quote/cap-minor q 0))
             (not (str/blank? (str agreed-by))))
    (assoc q
           :quote/cap-minor new-cap-minor
           :quote/reconsent {:reconsent/prior-cap-minor (:quote/cap-minor q)
                             :reconsent/agreed-by agreed-by
                             :reconsent/agreed-at agreed-at
                             :reconsent/rationale rationale
                             :reconsent/human? true})))

(defn campaign-quote-errors
  "[] when a campaign's pricing model and its pledges' quotes agree.

  Two failures, and both are silent without this check:

  - a `:deposit-plus-settlement` pledge with NO quote has no deposit, no
    margin and — critically — no CAP. It would settle at whatever the
    parts cost, which is the unbounded commitment this whole namespace
    exists to prevent.
  - a `:fixed` pledge WITH a quote is a backer who thinks they agreed to
    a cap on a campaign that will never settle against one.

  `quotes` is a map pledge-id -> quotation. Checked at the campaign level
  because the mismatch is between a campaign-wide setting and a per-pledge
  record; neither one alone can see it."
  [c pledges quotes]
  (let [model    (:campaign/pricing-model c :fixed)
        standing (remove #(contains? #{:cancelled :dropped :refunded} (:pledge/state %))
                         pledges)]
    (vec
     (if (= :deposit-plus-settlement model)
       (mapcat (fn [p]
                 (let [id (:pledge/id p)
                       q  (get quotes id)]
                   (if (nil? q)
                     [{:passthrough.error/code   :missing-quote
                       :passthrough.error/detail id}]
                     (map #(assoc % :passthrough.error/pledge id)
                          (quotation-errors q)))))
               (sort-by :pledge/id standing))
       (keep (fn [p]
               (when (contains? quotes (:pledge/id p))
                 {:passthrough.error/code   :quote-on-fixed-price-campaign
                  :passthrough.error/detail (:pledge/id p)}))
             (sort-by :pledge/id standing))))))

(defn campaign-exposure
  "Aggregate what the creator is absorbing across every backer — the
  number that decides whether a pass-through campaign is still solvent.

  Reported per campaign rather than per backer because absorbing 200 units
  of overage on one order is a rounding error and absorbing it on nine
  hundred is the end of the company, and only the aggregate distinguishes
  them."
  [settlements]
  {:exposure/units             (count settlements)
   :exposure/absorbed-minor    (reduce + 0 (map :settlement/creator-absorbs-minor settlements))
   :exposure/over-cap-units    (count (filter :settlement/over-cap? settlements))
   :exposure/billable-minor    (reduce + 0 (map :settlement/billable-total-minor settlements))
   :exposure/balance-due-minor (reduce + 0 (map :settlement/balance-due-minor settlements))
   :exposure/refund-due-minor  (reduce + 0 (map :settlement/refund-due-minor settlements))})
