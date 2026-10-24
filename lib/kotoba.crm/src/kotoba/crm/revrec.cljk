(ns kotoba.crm.revrec
  "Straight-line subscription revenue recognition recompute — FASB ASC 606
  / IASB IFRS 15's 5-step model applied to the simplest, most common SaaS
  case: a fixed-fee term subscription with no distinct performance
  obligations, recognized ratably (straight-line) over the service
  period. This is a PURE ground-truth recompute, the same 'recompute one
  side of an equation and compare' family `cloud-itonami-isic-6492` and
  `cloud-itonami-isic-6920` established in this fleet — never trust a
  proposal's claimed recognized-revenue figure without recomputing it.

  Honest scope (R0, see `coverage` below): straight-line recognition
  only. Usage-based/tiered-consumption billing, mid-term contract
  modifications, and multi-element arrangements (ASC 606 step 4,
  allocating price across distinct performance obligations) are NOT
  modeled — a subscription with more than one distinct performance
  obligation must not be recomputed by this namespace alone.")

(defn- round-cents
  "Round a raw cents figure to the nearest integer, portable across clj
  (`Math/round`) and cljs (`js/Math.round`) without leaking a platform
  type into callers — always returns a plain number."
  [cents]
  #?(:clj  (Math/round (double cents))
     :cljs (js/Math.round cents)))

(defn- abs* [x] (if (neg? x) (- x) x))

(def spec-basis
  "The only two standard-setters this recompute cites — real, named,
  never fabricated."
  #{:fasb-asc-606   ; US GAAP, ASC 606: Revenue from Contracts with Customers
    :iasb-ifrs-15})  ; IFRS 15: Revenue from Contracts with Customers

(defn elapsed-months
  "Whole months elapsed between `start-date` and `as-of-date` (both
  `java.time.LocalDate`-compatible maps `{:year Y :month M :day D}` to
  stay platform-neutral), clamped to `[0, term-months]`."
  [{:keys [start-date term-months as-of-date]}]
  (let [{sy :year sm :month} start-date
        {ay :year am :month} as-of-date
        raw (- (+ (* ay 12) am) (+ (* sy 12) sm))]
    (max 0 (min term-months raw))))

(defn recognized-revenue-to-date
  "Straight-line ASC 606 / IFRS 15 recompute: (elapsed-months /
  term-months) × contract-value, rounded to the cent. Returns nil (no
  opinion) if `term-months` is not a positive number — callers must not
  substitute a default in that case, per ADR-2607071351's lesson on
  guarding type-specific recomputes on their own preconditions."
  [{:keys [contract-value-usd term-months] :as subscription}]
  (when (and (number? term-months) (pos? term-months))
    (let [months (elapsed-months subscription)
          cents  (* 100.0 contract-value-usd (/ months (double term-months)))]
      (/ (round-cents cents) 100.0))))

(defn mismatch
  "Compares a PROPOSED booked/recognized amount against the recomputed
  ground truth, within `tolerance-usd` (defaults to 0.01, i.e. rounding
  only). Returns nil when within tolerance, else a diagnostic map — never
  throws, so a governor can always turn this into a SOFT always-escalate
  gate rather than a hard crash."
  ([subscription proposed-amount-usd] (mismatch subscription proposed-amount-usd 0.01))
  ([subscription proposed-amount-usd tolerance-usd]
   (let [truth (recognized-revenue-to-date subscription)]
     (when (and truth (> (abs* (- (double proposed-amount-usd) (double truth)))
                          (double tolerance-usd)))
       {:recomputed-usd truth
        :proposed-usd   proposed-amount-usd
        :delta-usd      (- (double proposed-amount-usd) (double truth))
        :spec-basis     spec-basis}))))

(defn coverage
  "Honest, machine-checkable report of what R0 actually covers."
  []
  {:model :straight-line-only
   :spec-basis spec-basis
   :note (str "R0 scope: single-performance-obligation, fixed-fee, "
              "straight-line term subscriptions only. Usage-based "
              "billing, contract modifications, and multi-element "
              "arrangements (ASC 606 step 4 allocation) are NOT modeled "
              "— extend only by adding a genuinely new, citable "
              "recognition method, never by guessing.")})
