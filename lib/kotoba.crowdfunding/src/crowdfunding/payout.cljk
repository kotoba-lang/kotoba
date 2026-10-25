(ns crowdfunding.payout
  "Creator payout — computing who is owed what, and holding some of it
  back until the promise is kept.

  Crowdfunding's payout problem is not the marketplace's. A marketplace
  seller ships and then is paid; a crowdfunding creator is paid and then
  ships, months later, using the money to do it. Paying 100% on collection
  maximises the creator's ability to build and maximises the backer's
  exposure; paying nothing until delivery makes the campaign pointless.
  So this namespace does not pick a side — it makes the choice EXPLICIT
  and auditable as a tranche schedule that a backer can read before
  pledging.

  Invariants:

  - **No custody.** A payout plan is a COMPUTATION. Nothing here moves
    money, holds a key, or touches the network. Executing a tranche is the
    payout actor's separately human-approved step, and 'having moved
    funds' is a permanent scope exclusion for that actor. Same boundary as
    `marketplace.settlement`, kept all the way up from `kotoba-lang/pay`.
  - **Conservation.** Tranches plus holdback equal the creator's net,
    exactly; net plus fees equal what backers were charged. Both are
    computed on the plan, not asserted in a comment.
  - **No adjudication.** There is no function here that decides a dispute.
    `resolve-hold` records what a NAMED HUMAN decided, and refuses without
    one — the `marketplace.settlement/resolve-dispute` shape.

  Amounts are integer minor units. Pure: no clock, no network."
  (:require [kotoba.lang.text :as str]
            [crowdfunding.fee :as fee]
            [marketplace.settlement :as settle]
            [pay.core :as pay]))

(def ^:private bps-total 10000)

;; ───────────────────────────── destination ─────────────────────────────

(def payout-rails
  "Rails a payout can be described on. Delegated in spirit to
  `marketplace.settlement/payout-rails` — same set, re-exported so a
  consumer of this library does not have to know that marketplace exists."
  settle/payout-rails)

(defn payout-destination
  "Where a creator's money should go. `:verified?` is NEVER self-asserted
  by a proposal: the payout actor's governor re-derives it from the
  creator's own record."
  [{:keys [creator rail address verified?] :or {verified? false}}]
  (settle/payout-destination {:seller creator :rail rail
                              :address address :verified? verified?}))

;; ───────────────────────────── tranches ─────────────────────────────

(defn tranche
  "One scheduled release. `:tranche/gate` is what must be true before it
  may be released, and it is data rather than code so a backer can read
  the release conditions on the campaign page."
  [{:keys [id bps gate note]}]
  {:tranche/id   (str id)
   :tranche/bps  bps
   :tranche/gate gate
   :tranche/note note})

(def gates
  "Release gates a tranche may name.
  `:on-collection` — funds have landed.
  `:on-production-start` — creator evidenced production beginning.
  `:on-first-shipment` — the first backer received something.
  `:on-fulfillment-complete` — every surveyed backer is delivered or
  refunded. A gate that no external fact can satisfy is worse than no
  holdback at all, so this set is closed and each member maps to a fact
  `crowdfunding.fulfillment` can actually report."
  #{:on-collection :on-production-start :on-first-shipment :on-fulfillment-complete})

(def immediate
  "Pay everything on collection. Maximum creator liquidity, zero backer
  protection — legitimate for a small, low-risk campaign, and named so
  that choosing it is visible rather than being the shape you get by
  writing no schedule at all."
  [(tranche {:id "full" :bps 10000 :gate :on-collection
             :note "entire net released once collection closes"})])

(def staged
  "A middle schedule: most on collection so the creator can build, a
  holdback that only clears once backers have actually been served."
  [(tranche {:id "build"    :bps 7000 :gate :on-collection})
   (tranche {:id "ship"     :bps 2000 :gate :on-first-shipment})
   (tranche {:id "complete" :bps 1000 :gate :on-fulfillment-complete})])

(defn schedule-errors
  "A schedule must allocate exactly 100% and name only real gates. Bps
  that sum to less than 10000 would strand creator money with no release
  path — the silent kind of holdback."
  [tranches]
  (vec
   (concat
    (when (empty? tranches)
      [{:payout.error/code :empty-schedule}])
    (let [total (reduce + 0 (map :tranche/bps tranches))]
      (when (not= bps-total total)
        [{:payout.error/code   :tranche-bps-not-total
          :payout.error/detail (str total "/" bps-total)}]))
    (mapcat (fn [t]
              (concat
               (when-not (contains? gates (:tranche/gate t))
                 [{:payout.error/code   :unknown-gate
                   :payout.error/detail (pr-str (:tranche/gate t))}])
               (when-not (and (integer? (:tranche/bps t)) (pos? (:tranche/bps t)))
                 [{:payout.error/code   :invalid-tranche-bps
                   :payout.error/detail (:tranche/id t)}])))
            tranches)
    (let [ids (map :tranche/id tranches)]
      (when (not= (count ids) (count (distinct ids)))
        [{:payout.error/code :duplicate-tranche-id}])))))

;; ───────────────────────────── plan ─────────────────────────────

(defn payout-plan
  "Compute the full payout for one finalized campaign.

  Inputs are the collection result (`crowdfunding.collection/finalize`),
  the fee schedule, the creator, the tranche schedule and the platform's
  own identity. Returns the fee breakdown, the creator's net, each
  tranche's amount, and the conservation checks.

  The tranche split goes through `pay.core/split-allocations`, so rounding
  dust lands in the FIRST tranche. That is deliberate and it matters here
  in the opposite direction from a marketplace: the first tranche is the
  earliest one, so dust reaches the creator soonest rather than sitting in
  a holdback nobody remembers to release."
  [{:keys [collection pledges rewards fee-schedule creator tranches platform]
    :or   {tranches immediate}}]
  (let [fees   (fee/campaign-fees fee-schedule pledges rewards)
        net    (:fees/net-minor fees 0)
        allocs (when (pos? net)
                 (pay/split-allocations
                  net
                  (mapv (fn [t] {:to (:tranche/id t) :bps (:tranche/bps t)}) tranches)))
        lines  (mapv (fn [t a]
                       (assoc t :tranche/amount-minor (:amount-micros a)
                              :tranche/state :pending))
                     tranches
                     (or allocs (repeat (count tranches) {:amount-micros 0})))
        sum    (reduce + 0 (map :tranche/amount-minor lines))]
    {:payout/campaign        (:collection/campaign collection)
     :payout/currency        (:collection/currency collection)
     :payout/creator         (str creator)
     :payout/platform        (str platform)
     :payout/charged-minor   (:fees/charged-minor fees 0)
     :payout/fees            fees
     :payout/platform-minor  (+ (:fees/platform-minor fees 0)
                                (:fees/processing-minor fees 0))
     :payout/tithe-minor     (:fees/tithe-minor fees 0)
     :payout/creator-net-minor net
     :payout/tranches        lines
     ;; Both conservation checks, computed:
     :payout/tranches-conserved? (= net sum)
     :payout/fees-conserved?     (and (:fees/conserved? fees)
                                      (= (:fees/charged-minor fees 0)
                                         (+ (:fees/platform-minor fees 0)
                                            (:fees/processing-minor fees 0)
                                            (:fees/tithe-minor fees 0)
                                            net)))
     :payout/non-adjudicating true
     :payout/custodial?       false}))

(defn plan-errors
  "Everything that must be true before a payout plan may be presented for
  human approval.

  A verified destination is required here rather than discovered at
  execution — the same gate `marketplace.settlement/plan-errors` applies,
  for the same reason: an unverified destination found at release time is
  a payment already in flight."
  [plan destination]
  (vec
   (concat
    (when-not (:payout/tranches-conserved? plan)
      [{:payout.error/code   :tranches-not-conserved
        :payout.error/detail (str "net=" (:payout/creator-net-minor plan))}])
    (when-not (:payout/fees-conserved? plan)
      [{:payout.error/code :fees-not-conserved}])
    (when (neg? (:payout/creator-net-minor plan 0))
      [{:payout.error/code :negative-net}])
    (when (str/blank? (str (:payout/creator plan)))
      [{:payout.error/code :missing-creator}])
    (when-not (re-matches #"^[A-Z]{3}$" (str (:payout/currency plan)))
      [{:payout.error/code :invalid-currency}])
    (if destination
      (settle/payout-destination-errors destination)
      [{:payout.error/code :missing-payout-destination}]))))

;; ───────────────────────────── release ─────────────────────────────

(defn gate-satisfied?
  "Is a tranche's gate met, given the facts the caller has established?

  `facts` is a set of satisfied gate keywords, supplied by the caller from
  `crowdfunding.fulfillment` and the collection result. This function does
  not go and look — a domain function that fetched its own evidence would
  be deciding what counts as evidence."
  [t facts]
  (contains? (set facts) (:tranche/gate t)))

(defn releasable
  "Which tranches may be released now, in schedule order.

  Ordered by schedule position, and a tranche whose gate is unmet BLOCKS
  the ones after it. A later tranche clearing before an earlier one would
  mean the holdback ordering the backer read on the campaign page was
  decorative."
  [plan facts]
  (->> (:payout/tranches plan)
       (reduce (fn [{:keys [out blocked?]} t]
                 (if (or blocked?
                         (not= :pending (:tranche/state t))
                         (not (gate-satisfied? t facts)))
                   {:out out :blocked? true}
                   {:out (conj out t) :blocked? false}))
               {:out [] :blocked? false})
       :out
       vec))

(defn hold
  "Put a tranche on hold — an unresolved backer complaint, a fraud signal,
  a fulfilment that stopped. Requires a named human and a reason, because
  a hold nobody can be asked about is indistinguishable from a bug."
  [t {:keys [by at reason]}]
  (when (and (= :pending (:tranche/state t)) (not (str/blank? (str by))))
    (assoc t :tranche/state :held
           :tranche/hold {:hold/by by :hold/at at :hold/reason reason})))

(defn resolve-hold
  "The only path out of `:held`, and it records a human decision rather
  than making one. `decision` is `:release` or `:refund-backers`;
  `decided-by` must name a human. Refuses (nil) otherwise — an actor
  synthesizing a sign-off here is exactly what the ledger exists to make
  impossible."
  [t {:keys [decision decided-by decided-at rationale]}]
  (when (and (= :held (:tranche/state t))
             (contains? #{:release :refund-backers} decision)
             (not (str/blank? (str decided-by))))
    (assoc t :tranche/state (case decision :release :pending :refund-backers :cancelled)
           :tranche/resolution {:resolution/decision   decision
                                :resolution/decided-by decided-by
                                :resolution/decided-at decided-at
                                :resolution/rationale  rationale
                                :resolution/human?     true})))

;; ───────────────────────────── refunds ─────────────────────────────

(defn refund-plan
  "What returning money to backers costs and who bears it.

  Processing fees are generally NOT returned by the processor when a
  charge is refunded. Stating that on the plan rather than discovering it
  at execution is the difference between a creator who refunds knowingly
  and one who ends up personally short. `:refund/creator-owes-minor` is
  what the creator must find beyond the funds they still hold."
  [{:keys [pledges rewards fee-schedule reason requested-by requested-at]}]
  (let [fees (fee/campaign-fees fee-schedule pledges rewards)
        gross (:fees/charged-minor fees 0)
        unrecoverable (:fees/processing-minor fees 0)
        net-held (:fees/net-minor fees 0)]
    {:refund/gross-minor          gross
     :refund/unrecoverable-fees-minor unrecoverable
     :refund/creator-held-minor   net-held
     :refund/creator-owes-minor   (max 0 (- gross net-held))
     :refund/reason               reason
     :refund/requested-by         requested-by
     :refund/requested-at         requested-at
     :refund/lines                (mapv (fn [l]
                                          {:refund/pledge (:fee/pledge l)
                                           :refund/amount-minor (:fee/charged-minor l)})
                                        (:fees/lines fees))
     :refund/non-adjudicating     true
     :refund/custodial?           false}))
