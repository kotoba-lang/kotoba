(ns crowdfunding.fee
  "The take rate — stated as data, computed as integers, charged only on
  money that actually arrived.

  Three invariants, each of which is a way platforms have historically got
  this wrong:

  1. **Conservation.** `platform + processing + tithe + net = charged`,
     exactly, for every pledge. `net` is computed as the REMAINDER rather
     than as its own percentage, so integer rounding dust flows to the
     creator and the identity holds by construction rather than by luck.
     `pay.core/split-allocations` uses the same dust-to-the-first-party
     convention; it is not used directly here only because a crowdfunding
     fee is bps PLUS a fixed per-pledge amount, which is not a pure
     basis-point split.
  2. **Fees follow collection, not authorization.** `campaign-fees` sums
     over collected pledges only. A failed campaign owes nothing, and a
     campaign whose collections dropped off owes fees on what landed.
     A schedule that billed on the pledged total would charge a creator
     for money they never received.
  3. **The schedule is checkable by the person paying it.** Every
     component is an integer a creator can recompute — the
     `marketplace.settlement/fee-schedule` discipline: 'a marketplace
     whose take rate is not expressible as a number a seller can check is
     a marketplace whose take rate is not accountable.'

  `:fee/tithe-bps` exists because this library absorbed
  `etzhayyim/com-etzhayyim-app-crowdfunding`, whose 10% Public-Fund tithe
  was a constitutional constant of that deployment. It is a schedule
  OPTION here, defaulting to zero: a general crowdfunding protocol must
  not hard-code one operator's covenant, and that operator must not lose
  it. Set `:tithe-bps 1000` to reproduce the original split exactly.

  Amounts are integer minor units. Pure: no clock, no network."
  (:require [crowdfunding.pledge :as pledge]))

(def ^:private bps-total 10000)

;; ───────────────────────────── schedule ─────────────────────────────

(defn fee-schedule
  "Build a fee schedule.

  `micro-*` fields describe the reduced processing fee small pledges get.
  Without them a fixed per-transaction fee eats an unreasonable share of a
  small pledge — a 1-unit fixed fee on a 300-unit pledge is a different
  business than the same fee on a 30,000-unit one, and pretending
  otherwise silently discourages exactly the backers a long tail is made
  of."
  [{:keys [platform-bps processing-bps processing-fixed-minor tithe-bps
           micro-threshold-minor micro-processing-bps micro-processing-fixed-minor]
    :or   {platform-bps 500 processing-bps 300 processing-fixed-minor 0
           tithe-bps 0}}]
  {:fee/platform-bps                 platform-bps
   :fee/processing-bps               processing-bps
   :fee/processing-fixed-minor       processing-fixed-minor
   :fee/tithe-bps                    tithe-bps
   :fee/micro-threshold-minor        micro-threshold-minor
   :fee/micro-processing-bps         micro-processing-bps
   :fee/micro-processing-fixed-minor micro-processing-fixed-minor})

(defn fee-schedule-errors [fs]
  (let [bps? (fn [v] (and (integer? v) (<= 0 v bps-total)))
        nonneg? (fn [v] (and (integer? v) (not (neg? v))))]
    (vec
     (concat
      (when-not (bps? (:fee/platform-bps fs))
        [{:fee.error/code :invalid-platform-bps :fee.error/detail "0..10000"}])
      (when-not (bps? (:fee/processing-bps fs))
        [{:fee.error/code :invalid-processing-bps :fee.error/detail "0..10000"}])
      (when-not (bps? (:fee/tithe-bps fs))
        [{:fee.error/code :invalid-tithe-bps :fee.error/detail "0..10000"}])
      (when-not (nonneg? (:fee/processing-fixed-minor fs))
        [{:fee.error/code :invalid-processing-fixed}])
      (when (and (:fee/micro-threshold-minor fs)
                 (not (nonneg? (:fee/micro-threshold-minor fs))))
        [{:fee.error/code :invalid-micro-threshold}])
      (when (and (:fee/micro-processing-bps fs)
                 (not (bps? (:fee/micro-processing-bps fs))))
        [{:fee.error/code :invalid-micro-processing-bps}])
      (when (> (+ (:fee/platform-bps fs 0) (:fee/processing-bps fs 0)
                  (:fee/tithe-bps fs 0))
               bps-total)
        [{:fee.error/code   :take-rate-exceeds-total
          :fee.error/detail "platform + processing + tithe > 100%"}])))))

(def kickstarter-like
  "A schedule in the shape the reward-crowdfunding market has converged on
  (5% platform, ~3% + fixed processing, reduced fixed fee for micro
  pledges). Provided as a NAMED DEFAULT so a deployment states which
  economics it chose, rather than inheriting numbers from a constant
  buried in code."
  (fee-schedule {:platform-bps                 500
                 :processing-bps               300
                 :processing-fixed-minor       20
                 :micro-threshold-minor        1000
                 :micro-processing-bps         500
                 :micro-processing-fixed-minor 5}))

(def zero
  "The schedule that applies to a campaign that did not fund. Named,
  because 'charge nothing' must be a schedule the code can pass around,
  not a branch someone remembers to write."
  (fee-schedule {:platform-bps 0 :processing-bps 0 :processing-fixed-minor 0}))

;; ───────────────────────────── per pledge ─────────────────────────────

(defn- micro? [fs amount]
  (when-let [t (:fee/micro-threshold-minor fs)]
    (< amount t)))

(defn- processing-terms [fs amount]
  (if (micro? fs amount)
    [(or (:fee/micro-processing-bps fs) (:fee/processing-bps fs))
     (or (:fee/micro-processing-fixed-minor fs) (:fee/processing-fixed-minor fs))]
    [(:fee/processing-bps fs) (:fee/processing-fixed-minor fs 0)]))

(defn- bps-of [amount bps] (quot (* amount bps) bps-total))

(defn pledge-fees
  "Split one collected charge into platform / processing / tithe / net.

  Returns nil for a negative amount rather than producing a negative fee —
  a refund is not a pledge with a minus sign, it has its own path in
  `crowdfunding.payout/refund-plan`.

  `:fee/net-minor` may legitimately be small on a micro pledge, but never
  negative: if fixed fees would exceed the charge, `:fee/underwater?` is
  set and net is clamped at zero with the excess carried in
  `:fee/uncovered-minor`, because a platform silently taking more than the
  backer paid is worse than an obvious, reportable zero."
  [fs amount-minor]
  (when (and (integer? amount-minor) (not (neg? amount-minor)))
    (let [[p-bps p-fixed] (processing-terms fs amount-minor)
          platform   (bps-of amount-minor (:fee/platform-bps fs 0))
          processing (+ (bps-of amount-minor p-bps) p-fixed)
          tithe      (bps-of amount-minor (:fee/tithe-bps fs 0))
          taken      (+ platform processing tithe)
          underwater (> taken amount-minor)
          net        (if underwater 0 (- amount-minor taken))]
      {:fee/charged-minor    amount-minor
       :fee/platform-minor   platform
       :fee/processing-minor processing
       :fee/tithe-minor      tithe
       :fee/net-minor        net
       :fee/micro?           (boolean (micro? fs amount-minor))
       :fee/underwater?      underwater
       :fee/uncovered-minor  (if underwater (- taken amount-minor) 0)
       ;; Computed, not assumed — a future edit that breaks the arithmetic
       ;; fails a test instead of quietly losing money.
       :fee/conserved?       (and (not underwater)
                                  (= amount-minor (+ platform processing tithe net)))})))

;; ───────────────────────────── per campaign ─────────────────────────────

(defn campaign-fees
  "Sum fees across a campaign's COLLECTED pledges.

  Fees are computed per pledge and then summed — never by applying the
  schedule to the campaign total. The two differ whenever a fixed
  per-pledge component exists, and the per-pledge computation is the one
  that matches what each backer was actually charged."
  [fs pledges rewards]
  (let [lines (->> pledges
                   (filter #(= :collected (:pledge/state %)))
                   (sort-by :pledge/id)
                   (keep (fn [p]
                           (when-let [amt (pledge/total-minor p rewards)]
                             (assoc (pledge-fees fs amt) :fee/pledge (:pledge/id p)))))
                   vec)
        sum (fn [k] (reduce + 0 (map k lines)))]
    {:fees/lines            lines
     :fees/charged-minor    (sum :fee/charged-minor)
     :fees/platform-minor   (sum :fee/platform-minor)
     :fees/processing-minor (sum :fee/processing-minor)
     :fees/tithe-minor      (sum :fee/tithe-minor)
     :fees/net-minor        (sum :fee/net-minor)
     :fees/underwater-count (count (filter :fee/underwater? lines))
     :fees/conserved?       (every? :fee/conserved? lines)}))

(defn effective-take-bps
  "What the creator actually paid, in basis points of what backers were
  charged. Headline rates hide fixed fees; this is the number that
  belongs next to them."
  [fees]
  (let [charged (:fees/charged-minor fees 0)]
    (when (pos? charged)
      (quot (* bps-total (- charged (:fees/net-minor fees 0))) charged))))
