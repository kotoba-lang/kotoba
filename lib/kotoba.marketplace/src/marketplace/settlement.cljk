(ns marketplace.settlement
  "Multi-seller settlement — how one buyer payment becomes N seller
  payouts plus the operator's commission, without the operator ever
  taking custody.

  A marketplace basket differs from a shop basket in exactly one way
  that matters to money: its lines belong to DIFFERENT sellers. A
  single-store order (`kotoba.okaimono`) settles to one party; a
  marketplace order must split, and every split is a place where money
  can silently go missing. This namespace's central invariant is
  therefore CONSERVATION: for every plan, the sum of all allocations
  equals the amount the buyer paid, exactly, with no rounding leak.

  ## No custody (ADR-2607264000 D1 invariant 2)

  Nothing here moves money. A `settlement-plan` is a COMPUTATION — an
  auditable statement of who should receive what. Executing it is the
  settlement actor's separately human-approved step, and that actor's
  governor treats 'having moved funds' as a permanent scope exclusion.
  This mirrors `kotoba-lang/pay`'s own stated boundary ('zero network
  I/O, zero key custody'), whose `split-allocations` does the integer
  allocation arithmetic here.

  ## Units

  Amounts are INTEGER minor units of `:plan/currency` (yen, cents,
  paisa) — never floats, the `kotoba.reji` discipline. `pay.core/
  split-allocations` is unit-agnostic integer math, so passing minor
  units through it is sound; the `->pay-micros` bridge is provided
  separately for the USDC rail, where `pay`'s own unit is 6-decimal
  micros and conflating the two would be a real bug.

  Pure: no clock, no network, no randomness."
  (:require [kotoba.lang.text :as str]
            [pay.core :as pay]))

;; ───────────────────────────── fee schedule ─────────────────────────────

(def ^:private bps-total 10000)

(defn fee-schedule
  "The operator's commission, in basis points, plus an optional
  per-order fixed fee in minor units.

  Stated as data so it is auditable and reproducible by a seller. A
  marketplace whose take rate is not expressible as a number a seller
  can check is a marketplace whose take rate is not accountable."
  [{:keys [commission-bps fixed-minor payout-hold-days]
    :or   {fixed-minor 0 payout-hold-days 0}}]
  {:fee/commission-bps   commission-bps
   :fee/fixed-minor      fixed-minor
   :fee/payout-hold-days payout-hold-days})

(defn fee-schedule-errors [fs]
  (vec
   (concat
    (when-not (and (integer? (:fee/commission-bps fs))
                   (<= 0 (:fee/commission-bps fs) bps-total))
      [{:settlement.error/code :invalid-commission-bps
        :settlement.error/detail "0..10000 の整数"}])
    (when-not (and (integer? (:fee/fixed-minor fs)) (not (neg? (:fee/fixed-minor fs))))
      [{:settlement.error/code :invalid-fixed-fee}])
    (when-not (and (integer? (:fee/payout-hold-days fs))
                   (not (neg? (:fee/payout-hold-days fs))))
      [{:settlement.error/code :invalid-hold-days}]))))

;; ───────────────────────────── payout destination ─────────────────────────────

(def payout-rails
  "Settlement rails this protocol can describe. `:x402` is the on-chain
  USDC rail cloud-itonami already runs in production via
  `gftdcojp/nexus-x402`; `:stripe` is the card rail `cloud-itonami.
  billing` uses. Adding a rail is a data change, not a redesign."
  #{:x402 :stripe :bank-transfer})

(defn payout-destination
  "Where one seller's money should go. `:verified?` is NEVER self-
  asserted by a proposal — the settlement actor's governor re-derives it
  from the seller's own record, the 'ground truth, not self-report'
  discipline every governor in this fleet uses."
  [{:keys [seller rail address verified?] :or {verified? false}}]
  {:payout/seller    (str seller)
   :payout/rail      rail
   :payout/address   address
   :payout/verified? (boolean verified?)})

(defn payout-destination-errors [d]
  (vec
   (concat
    (when (str/blank? (str (:payout/seller d)))
      [{:settlement.error/code :missing-payout-seller}])
    (when-not (contains? payout-rails (:payout/rail d))
      [{:settlement.error/code :unknown-rail :settlement.error/detail (pr-str (:payout/rail d))}])
    (when (str/blank? (str (:payout/address d)))
      [{:settlement.error/code :missing-payout-address}])
    (when-not (true? (:payout/verified? d))
      [{:settlement.error/code :payout-destination-unverified}]))))

;; ───────────────────────────── basket ─────────────────────────────

(defn basket-line
  "One line of a multi-seller basket. `amount-minor` is the extended
  amount for this line (qty × unit price), already computed by the
  caller — this namespace does not re-derive prices, the catalog owns
  them."
  [{:keys [seller offer amount-minor qty]}]
  {:line/seller       (str seller)
   :line/offer        (str offer)
   :line/amount-minor amount-minor
   :line/qty          qty})

(defn basket-total
  "Sum of every line's extended amount."
  [lines]
  (reduce + 0 (map :line/amount-minor lines)))

(defn by-seller
  "Group basket lines into per-seller subtotals, seller-sorted for
  determinism."
  [lines]
  (->> lines
       (group-by :line/seller)
       (map (fn [[s ls]] {:seller s
                          :lines (vec ls)
                          :subtotal-minor (basket-total ls)}))
       (sort-by :seller)
       vec))

;; ───────────────────────────── plan ─────────────────────────────

(defn- seller-allocation
  "Split ONE seller's subtotal into (seller payout, operator commission)
  via `pay.core/split-allocations`.

  The seller is deliberately FIRST in the split vector, because
  `split-allocations` routes rounding dust to the first entry — dust
  goes to the seller, never to the operator. On a marketplace with
  many small orders that choice is worth real money, and defaulting it
  toward the operator would be a quiet, compounding extraction."
  [{:keys [seller subtotal-minor]} fs operator]
  (let [commission-bps (:fee/commission-bps fs)
        seller-bps     (- bps-total commission-bps)
        alloc          (pay/split-allocations
                        subtotal-minor
                        [{:to seller   :bps seller-bps}
                         {:to operator :bps commission-bps}])
        [s-alloc o-alloc] alloc]
    {:alloc/seller             seller
     :alloc/subtotal-minor     subtotal-minor
     :alloc/seller-payout-minor (:amount-micros s-alloc)
     :alloc/commission-minor    (:amount-micros o-alloc)
     :alloc/commission-bps      commission-bps}))

(defn settlement-plan
  "Compute the full settlement for one multi-seller basket.

  Returns
    {:plan/currency ..
     :plan/gross-minor ..          what the buyer pays for goods
     :plan/fixed-fee-minor ..      operator per-order fixed fee
     :plan/allocations [..]        per-seller payout + commission
     :plan/seller-payout-total-minor ..
     :plan/operator-total-minor ..
     :plan/conserved? bool}

  `:plan/conserved?` is the audit invariant made explicit and carried
  on the plan itself: seller payouts + operator total must equal gross.
  It is computed, not assumed, so a future edit that breaks the
  arithmetic fails a test rather than quietly losing money."
  [{:keys [lines currency fee-schedule operator]}]
  (let [groups (by-seller lines)
        gross  (basket-total lines)
        fs     fee-schedule
        allocs (mapv #(seller-allocation % fs operator) groups)
        payouts (reduce + 0 (map :alloc/seller-payout-minor allocs))
        commissions (reduce + 0 (map :alloc/commission-minor allocs))
        fixed (:fee/fixed-minor fs 0)
        operator-total (+ commissions fixed)]
    {:plan/currency        currency
     :plan/gross-minor     gross
     :plan/fixed-fee-minor fixed
     :plan/operator        operator
     :plan/allocations     allocs
     :plan/seller-payout-total-minor payouts
     :plan/commission-total-minor    commissions
     :plan/operator-total-minor      operator-total
     ;; The fixed fee is charged to the BUYER on top of goods, so
     ;; conservation is checked against gross (goods) alone; the buyer's
     ;; total charge is `buyer-charge-minor`.
     :plan/conserved?      (= gross (+ payouts commissions))
     :plan/buyer-charge-minor (+ gross fixed)
     :plan/non-adjudicating true
     :plan/custodial? false}))

(defn plan-errors
  "Everything that must be true before a plan may be presented for
  human approval.

  `destinations` is a map seller-id → payout destination; every seller
  in the plan must have a VERIFIED one. A plan for a seller whose
  payout destination is unverified is refused here rather than
  discovered at execution time, which is the same failure mode ISIC
  4791 guards with its `:payment-processor-linked?` gate."
  [plan destinations]
  (let [sellers (map :alloc/seller (:plan/allocations plan))]
    (vec
     (concat
      (when-not (:plan/conserved? plan)
        [{:settlement.error/code :not-conserved
          :settlement.error/detail (str "gross=" (:plan/gross-minor plan)
                                        " payouts+commission="
                                        (+ (:plan/seller-payout-total-minor plan)
                                           (:plan/commission-total-minor plan)))}])
      (when-not (and (string? (:plan/currency plan))
                     (re-matches #"^[A-Z]{3}$" (str (:plan/currency plan))))
        [{:settlement.error/code :invalid-currency}])
      (when (neg? (:plan/gross-minor plan 0))
        [{:settlement.error/code :negative-gross}])
      (when (empty? (:plan/allocations plan))
        [{:settlement.error/code :empty-basket}])
      (when (str/blank? (str (:plan/operator plan)))
        [{:settlement.error/code :missing-operator}])
      (mapcat (fn [s]
                (if-let [d (get destinations s)]
                  (payout-destination-errors d)
                  [{:settlement.error/code :missing-payout-destination
                    :settlement.error/detail s}]))
              sellers)))))

;; ───────────────────────────── escrow ─────────────────────────────

(def escrow-states
  "Escrow lifecycle. `:disputed` has NO automatic exit — only a human
  decision moves it, because resolving a payment dispute is a permanent
  scope exclusion for every actor in this fleet (ISIC 4791 established
  this; ADR-2607264000 D5 keeps it)."
  #{:held :released :refunded :disputed})

(def escrow-transitions
  "Allowed escrow transitions, in the same explicit-table style as
  `kotoba.okaimono/transitions`. Note what is ABSENT: there is no
  `:disputed -> :released` or `:disputed -> :refunded` edge reachable
  by anything automatic — `resolve-dispute` takes an explicit human
  decision and is the only way across that boundary."
  {:held     #{:released :refunded :disputed}
   :released #{}
   :refunded #{}
   :disputed #{}})

(defn escrow
  "Open an escrow record over a settlement plan. `opened-at` comes from
  the caller — no clock here.

  `:basket` names the order this escrow covers. It belongs on the record
  rather than being tracked separately by the caller, because
  `releasable?` needs a delivery confirmation and a delivery
  confirmation is about an ORDER — an escrow that cannot say which order
  it belongs to cannot be released safely."
  [{:keys [id plan basket opened-at release-after]}]
  {:escrow/id            id
   :escrow/plan          plan
   :escrow/basket        basket
   :escrow/state         :held
   :escrow/opened-at     opened-at
   :escrow/release-after release-after
   :escrow/custodial?    false})

(defn advance-escrow
  "Move an escrow to `to` when the transition table allows it; nil
  otherwise (an illegal transition is a refusal, not an exception —
  `kotoba.okaimono/advance`'s convention)."
  [e to]
  (when (contains? (get escrow-transitions (:escrow/state e) #{}) to)
    (assoc e :escrow/state to)))

(defn releasable?
  "May this escrow be released at `now`? Requires the hold window to
  have elapsed AND delivery to be confirmed. Both, not either — a hold
  window that expires on an undelivered order must not auto-release."
  [e now delivered?]
  (and (= :held (:escrow/state e))
       (true? delivered?)
       (or (nil? (:escrow/release-after e))
           (not (neg? (compare (str now) (str (:escrow/release-after e))))))))

(defn resolve-dispute
  "The ONLY path out of `:disputed`, and it requires an explicit human
  decision record.

  `decision` must be `:release` or `:refund`, and `decided-by` must
  name a human. This function does not decide anything — it records
  that a human did, and refuses (nil) if handed a decision with no
  human attached. The distinction matters: an actor calling this with
  a synthesized `decided-by` would be fabricating a human sign-off,
  which is precisely what the fleet's audit ledgers exist to make
  impossible."
  [e {:keys [decision decided-by decided-at rationale]}]
  (when (and (= :disputed (:escrow/state e))
             (contains? #{:release :refund} decision)
             (not (str/blank? (str decided-by))))
    (assoc e
           :escrow/state (case decision :release :released :refund :refunded)
           :escrow/resolution {:resolution/decision  decision
                               :resolution/decided-by decided-by
                               :resolution/decided-at decided-at
                               :resolution/rationale rationale
                               :resolution/human? true})))

;; ───────────────────────────── pay bridge ─────────────────────────────

(defn ->pay-micros
  "Bridge a minor-unit amount to `pay`'s 6-decimal micros for the USDC
  rail.

  Explicit and separate on purpose: `pay`'s unit is micros (1 USDC =
  1,000,000) while this namespace's unit is the currency's minor unit
  (1 USD = 100 cents). Silently passing cents where micros are expected
  would under-pay by 10,000×. `minor-per-unit` must be stated by the
  caller (100 for USD, 1 for JPY) — this library will not guess a
  currency's exponent."
  [amount-minor minor-per-unit]
  (when (and (integer? amount-minor) (integer? minor-per-unit) (pos? minor-per-unit))
    (quot (* amount-minor pay/micros-per-usdc) minor-per-unit)))
