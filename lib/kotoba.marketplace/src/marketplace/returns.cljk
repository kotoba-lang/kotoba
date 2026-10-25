(ns marketplace.returns
  "Returns and RMAs — the path to the `:refunded` escrow state that
  existed with no way to reach it.

  ## An RMA is not a dispute

  This distinction is the whole design. A DISPUTE is a contested claim:
  the buyer says one thing, the seller another, and somebody has to
  decide — which is why `marketplace.crossborder` refuses to, and why
  no actor in this fleet adjudicates.

  A RETURN is the seller's OWN PUBLISHED POLICY being applied to facts
  nobody disagrees about: the parcel was delivered on the 3rd, the
  window is 14 days, it is now the 9th, the category is returnable.
  Nothing there is contested, so `eligibility` can answer it
  mechanically — and refusing to, on the grounds that all decisions need
  humans, would make returns unusable while protecting nobody.

  What is NOT mechanical is the RESOLUTION. Whether a returned item was
  actually unopened, whether damage is the courier's or the buyer's, and
  whether money moves are judgements with money attached, so
  `resolve-return` requires a named human exactly as
  `marketplace.settlement/resolve-dispute` does.

  A DECLINED return is the bridge back: `->dispute-reason` maps it to
  the dispute vocabulary, because a buyer told 'policy says no' who
  disagrees now has a genuinely contested claim, and that is precisely
  what the dispute path is for.

  Pure: no clock, no network, no randomness — `now` and the delivery
  date are the caller's."
  (:require [kotoba.lang.text :as str]))

;; ───────────────────────────── policy ─────────────────────────────

(def return-reasons
  "Why the buyer wants to return. A closed set, and deliberately
  distinct from `marketplace.crossborder/dispute-reasons`: 'changed my
  mind' is a perfectly ordinary return and not a dispute at all."
  #{:changed-mind :not-as-described :damaged :wrong-item
    :missing-parts :arrived-late :defective})

(def ^:private buyer-fault-reasons
  "Reasons where, if the policy says so, the buyer bears return
  shipping. Kept separate from the rest so `who-pays-return-shipping`
  never has to guess."
  #{:changed-mind})

(defn return-policy
  "A seller's published return policy.

  `:window-days` counts from DELIVERY, not from order placement — a
  parcel that took three weeks to arrive has not used up the buyer's
  window while it was in transit.

  `:non-returnable` is a set of categories (perishables, personalised
  goods, opened hygiene items). It is operator/seller data, not a
  built-in list, for the same reason
  `marketplace.listing/restricted-baseline` is only a floor: what may
  lawfully be refused differs by jurisdiction."
  [{:keys [window-days restocking-fee-bps non-returnable
           seller-pays-shipping-on free-window-days]
    :or   {window-days 14 restocking-fee-bps 0 non-returnable #{}
           seller-pays-shipping-on #{:damaged :wrong-item :defective :not-as-described}}}]
  {:policy/window-days      window-days
   :policy/free-window-days free-window-days
   :policy/restocking-fee-bps restocking-fee-bps
   :policy/non-returnable   (set non-returnable)
   :policy/seller-pays-shipping-on (set seller-pays-shipping-on)})

(defn policy-errors [p]
  (vec
   (concat
    (when-not (and (integer? (:policy/window-days p)) (not (neg? (:policy/window-days p))))
      [{:returns.error/code :invalid-window}])
    (when-not (and (integer? (:policy/restocking-fee-bps p))
                   (<= 0 (:policy/restocking-fee-bps p) 10000))
      [{:returns.error/code :invalid-restocking-fee :returns.error/detail "0..10000"}])
    (when-not (set? (:policy/non-returnable p))
      [{:returns.error/code :invalid-non-returnable}]))))

;; ───────────────────────── eligibility (mechanical) ─────────────────────────

(defn- parse-int*
  "Portable decimal parse — `Integer/parseInt` is JVM-only and
  `js/parseInt` is ClojureScript-only, so neither can appear unguarded
  in a `.cljc` file."
  [s]
  #?(:clj (Integer/parseInt s) :cljs (js/parseInt s 10)))

(defn- ->jdn
  "Julian Day Number for an ISO-8601 date. Calendar-correct across month
  and year boundaries, which a naive day-of-month subtraction is not —
  a delivery on 31 Jan and a request on 2 Feb is 2 days, not -29."
  [s]
  (let [[y m dd] (map parse-int* (str/split (subs (str s) 0 10) #"-"))
        a  (quot (- 14 m) 12)
        y' (+ y 4800 (- a))
        m' (+ m (* 12 a) -3)]
    (+ dd (quot (+ (* 153 m') 2) 5) (* 365 y')
       (quot y' 4) (- (quot y' 100)) (quot y' 400) -32045)))

(defn- days-between
  "Whole days from `from` to `to`, both ISO-8601 date or datetime
  strings. Compares the DATE part only, so a delivery at 23:00 and a
  request at 01:00 the next day counts as one day, not zero — a buyer
  should never lose a day of their window to a clock time."
  [from to]
  (- (->jdn to) (->jdn from)))

(defn eligibility
  "Is this return within the seller's own published policy?

  Mechanical on purpose — see the namespace docstring. Returns
  `{:eligible? bool :reasons [kw ..] :days-since-delivery n}`.

  `:outside-window` and `:non-returnable-category` are the two policy
  facts. A `nil` delivery date yields `:not-yet-delivered`: a parcel
  that has not arrived cannot be returned, and the buyer wants the
  dispute path (`:not-received`) instead."
  [{:keys [policy category delivered-at now]}]
  (let [days (when (and delivered-at now) (days-between delivered-at now))
        reasons (vec
                 (concat
                  (when (nil? delivered-at) [:not-yet-delivered])
                  (when (and days (neg? days)) [:delivery-date-in-the-future])
                  (when (and days (> days (:policy/window-days policy))) [:outside-window])
                  (when (contains? (:policy/non-returnable policy) category)
                    [:non-returnable-category])))]
    {:eligible? (empty? reasons)
     :reasons   reasons
     :days-since-delivery days}))

(defn who-pays-return-shipping
  "Which side bears return postage under the policy. `:seller` for
  fault-shaped reasons the policy lists, `:buyer` otherwise.

  A buyer-fault reason (`:changed-mind`) can still be seller-paid if the
  seller chose to offer that — the policy wins over the default."
  [policy reason]
  (cond
    (contains? (:policy/seller-pays-shipping-on policy) reason) :seller
    (contains? buyer-fault-reasons reason) :buyer
    :else :buyer))

(defn restocking-fee-minor
  "The fee the policy allows to be withheld, in minor units.

  Zero for fault-shaped reasons regardless of what the policy says: a
  seller may not charge a restocking fee for having sent the wrong item.
  That is not a jurisdiction question, it is arithmetic about who caused
  the return."
  [policy reason amount-minor]
  (if (contains? #{:damaged :wrong-item :defective :not-as-described :missing-parts} reason)
    0
    (quot (* amount-minor (:policy/restocking-fee-bps policy 0)) 10000)))

;; ───────────────────────────── the RMA ─────────────────────────────

(def rma-states
  #{:requested :authorized :declined :in-transit :received :inspected :resolved :cancelled})

(def rma-transitions
  "Explicit table. Note `:declined` and `:resolved` are terminal, and
  `:inspected -> :resolved` is the ONLY way into `:resolved` — an RMA
  cannot be resolved before somebody has looked at what came back."
  {:requested  #{:authorized :declined :cancelled}
   :authorized #{:in-transit :cancelled}
   :in-transit #{:received}
   :received   #{:inspected}
   :inspected  #{:resolved}
   :declined   #{}
   :resolved   #{}
   :cancelled  #{}})

(defn rma
  "Open a return request. INTAKE — this records that a buyer asked,
  nothing more."
  [{:keys [id order seller buyer reason category lines
           amount-minor currency delivered-at requested-at]}]
  {:rma/id           id
   :rma/order        order
   :rma/seller       seller
   :rma/buyer        buyer
   :rma/reason       reason
   :rma/category     category
   :rma/lines        (vec lines)
   :rma/amount-minor amount-minor
   :rma/currency     currency
   :rma/delivered-at delivered-at
   :rma/requested-at requested-at
   :rma/state        :requested
   :rma/adjudicated-by-actor? false})

(defn rma-errors [r]
  (vec
   (concat
    (when (str/blank? (str (:rma/id r)))    [{:returns.error/code :missing-id}])
    (when (str/blank? (str (:rma/order r))) [{:returns.error/code :missing-order}])
    (when (str/blank? (str (:rma/seller r))) [{:returns.error/code :missing-seller}])
    (when-not (contains? return-reasons (:rma/reason r))
      [{:returns.error/code :unknown-return-reason
        :returns.error/detail (pr-str (:rma/reason r))}])
    (when-not (contains? rma-states (:rma/state r))
      [{:returns.error/code :invalid-state}])
    (when (empty? (:rma/lines r)) [{:returns.error/code :empty-return}])
    (when-not (and (integer? (:rma/amount-minor r)) (not (neg? (:rma/amount-minor r))))
      [{:returns.error/code :invalid-amount}])
    (when (true? (:rma/adjudicated-by-actor? r))
      [{:returns.error/code :actor-adjudicated-return
        :returns.error/detail "actor が返品の可否を裁定したと主張するレコードは禁止"}]))))

(defn advance
  "Move an RMA along when the table allows it; nil otherwise."
  [r to]
  (when (contains? (get rma-transitions (:rma/state r) #{}) to)
    (assoc r :rma/state to)))

(defn authorize
  "Authorize a return, recording the eligibility that justified it.

  Returns nil when the RMA is not `:requested` or the eligibility says
  no — an ineligible return must go through `decline`, which records a
  reason the buyer can act on, rather than being quietly authorized
  anyway."
  [r elig {:keys [authorized-at return-label carrier]}]
  (when (and (= :requested (:rma/state r)) (:eligible? elig))
    (assoc r :rma/state :authorized
           :rma/eligibility elig
           :rma/authorized-at authorized-at
           :rma/return-label return-label
           :rma/carrier carrier)))

(defn decline
  "Decline a return under the policy, recording WHY.

  The reasons come from `eligibility`, so a decline is always traceable
  to a published rule rather than to someone's mood — and
  `->dispute-reason` gives the buyer somewhere to go if they disagree."
  [r elig {:keys [declined-at note]}]
  (when (= :requested (:rma/state r))
    (assoc r :rma/state :declined
           :rma/eligibility elig
           :rma/declined-at declined-at
           :rma/decline-note note)))

(defn record-inspection
  "Record what was found when the returned goods were opened.

  `condition` is an observation (`:as-described` / `:used` / `:damaged`
  / `:not-the-item` / `:missing-parts`), not a verdict about who is at
  fault. Requires the RMA to be `:received`."
  [r {:keys [condition inspected-by inspected-at note]}]
  (when (and (= :received (:rma/state r))
             (contains? #{:as-described :used :damaged :not-the-item :missing-parts}
                        condition)
             (not (str/blank? (str inspected-by))))
    (-> (advance r :inspected)
        (assoc :rma/inspection {:inspection/condition condition
                                :inspection/by inspected-by
                                :inspection/at inspected-at
                                :inspection/note note
                                :inspection/observation-only true}))))

;; ───────────────────────── resolution (human) ─────────────────────────

(def resolutions #{:refund-full :refund-partial :replace :deny})

(defn resolve-return
  "Record that a HUMAN resolved the return.

  Requires `:inspected` state, a known outcome and a named human. Like
  `marketplace.settlement/resolve-dispute` there is deliberately no
  counterpart that computes an outcome from the inspection — condition
  `:used` does not mechanically mean `:deny`, and encoding that it does
  would quietly turn an observation into a verdict."
  [r {:keys [outcome refund-minor decided-by decided-at rationale]}]
  (when (and (= :inspected (:rma/state r))
             (contains? resolutions outcome)
             (not (str/blank? (str decided-by))))
    (assoc r :rma/state :resolved
           :rma/resolution {:resolution/outcome outcome
                            :resolution/refund-minor (or refund-minor 0)
                            :resolution/decided-by decided-by
                            :resolution/decided-at decided-at
                            :resolution/rationale rationale
                            :resolution/human? true})))

(defn refund-instruction
  "What a resolved refund means for the escrow, as a record — never an
  execution.

  Returns nil unless the RMA resolved to a refund with a named human.
  The amount is the human's decided figure, capped at what was actually
  paid: a refund larger than the order is always a mistake, and catching
  it here is cheaper than catching it on a bank statement."
  [r]
  (let [res (:rma/resolution r)]
    (when (and (= :resolved (:rma/state r))
               (contains? #{:refund-full :refund-partial} (:resolution/outcome res))
               (true? (:resolution/human? res)))
      (let [want (if (= :refund-full (:resolution/outcome res))
                   (:rma/amount-minor r)
                   (:resolution/refund-minor res))]
        {:refund/rma        (:rma/id r)
         :refund/order      (:rma/order r)
         :refund/seller     (:rma/seller r)
         :refund/buyer      (:rma/buyer r)
         :refund/amount-minor (min want (:rma/amount-minor r))
         :refund/capped?    (> want (:rma/amount-minor r))
         :refund/currency   (:rma/currency r)
         :refund/authorised-by (:resolution/decided-by res)
         :refund/executed?  false}))))

;; ───────────────────────── the bridge to disputes ─────────────────────────

(def ^:private reason->dispute
  {:not-as-described :not-as-described
   :damaged          :damaged
   :wrong-item       :not-as-described
   :missing-parts    :not-as-described
   :defective        :not-as-described
   :arrived-late     :not-as-described
   ;; `:changed-mind` has no dispute counterpart on purpose: a buyer who
   ;; changed their mind outside the window has no contested claim, and
   ;; manufacturing one would let the dispute path be used to reopen
   ;; every policy decision.
   :changed-mind     nil})

(defn ->dispute-reason
  "The `marketplace.crossborder/dispute-reasons` value a DECLINED return
  maps to, or nil when the buyer has no contested claim.

  This is the escalation path: a buyer told 'policy says no' who
  disagrees now has a genuinely contested question, which is exactly
  what the dispute machinery is for. A return declined for
  `:changed-mind` is not that."
  [r]
  (when (= :declined (:rma/state r))
    (get reason->dispute (:rma/reason r))))

(defn escalatable?
  "True when a declined return can become a dispute."
  [r]
  (some? (->dispute-reason r)))
