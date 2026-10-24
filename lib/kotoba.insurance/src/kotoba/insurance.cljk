(ns kotoba.insurance
  "Policies, premiums and claims — pure data contracts.

  A kotoba-lang capability library for the cloud-itonami insurance vertical
  (ISIC 6511/6512/6520/6530/6621/6622/6629): life/non-life insurance,
  reinsurance, pension funding, and the auxiliary activities (risk/damage
  evaluation, agents/brokers, other insurance auxiliary). Models the records
  an insurance operator keeps: policy, premium quote, claim and an
  underwriting-decision record.

  This library carries no real actuarial tables or rate data — an operator
  supplies their own licensed rate table; the pure functions here only
  combine a supplied rate with policy facts (coverage/term), the same way
  kotoba-lang/banking supplies IBAN math but not a real correspondent
  network.

  Amounts are plain numbers in the smallest unit of the account currency.
  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM.")

;; ---------------------------------------------------------------------------
;; Policy
;; ---------------------------------------------------------------------------

(def policy-types #{:life :non-life})

(defn policy
  "Construct a policy record. ptype is :life or :non-life. start/end are
  comparable keys (e.g. date strings or epoch numbers)."
  [id holder ptype coverage-amount start end & {:keys [currency product]}]
  (when (contains? policy-types ptype)
    {:policy/id       id
     :policy/holder   holder
     :policy/type     ptype
     :policy/coverage coverage-amount
     :policy/currency (or currency "USD")
     :policy/start    start
     :policy/end      end
     :policy/product  product}))

(defn policy-active-on?
  "True when as-of falls within [start,end] of the policy term."
  [pol as-of]
  (let [s (:policy/start pol) e (:policy/end pol)]
    (and s e as-of
         (not (or (neg? (compare e s))
                  (pos? (compare as-of e))
                  (neg? (compare as-of s)))))))

;; ---------------------------------------------------------------------------
;; Premium — pure combination of a supplied rate and policy facts
;; ---------------------------------------------------------------------------

(defn premium-quote
  "Combine a per-mille rate (operator-supplied, from their own licensed rate
  table) with a policy's coverage amount to produce a premium-quote record.
  This performs no underwriting judgement -- it is arithmetic only."
  [pol rate-per-mille & {:keys [loading]}]
  (let [base (* (:policy/coverage pol 0) (/ rate-per-mille 1000.0))
        loaded (* base (+ 1 (or loading 0)))]
    {:premium/policy   (:policy/id pol)
     :premium/rate     rate-per-mille
     :premium/loading  (or loading 0)
     :premium/amount   loaded
     :premium/currency (:policy/currency pol)}))

;; ---------------------------------------------------------------------------
;; Claim
;; ---------------------------------------------------------------------------

(def claim-statuses #{:intake :under-review :approved :denied :paid})

(defn claim
  "Construct a claim record against a policy. status defaults to :intake."
  [id policy-id claimant incident-date amount-requested & {:keys [status currency]}]
  {:claim/id              id
   :claim/policy          policy-id
   :claim/claimant        claimant
   :claim/incident-date   incident-date
   :claim/amount-requested amount-requested
   :claim/currency        (or currency "USD")
   :claim/status          (or status :intake)})

(defn claim-in-force?
  "True when a claim's incident-date falls within the referenced policy's
  active term -- i.e. the loss occurred while coverage was in force."
  [claim-rec pol]
  (policy-active-on? pol (:claim/incident-date claim-rec)))

;; ---------------------------------------------------------------------------
;; Underwriting decision
;; ---------------------------------------------------------------------------

(def underwriting-decisions #{:approve :decline :refer})

(defn underwriting-decision
  "Construct an underwriting-decision record. decision is :approve, :decline
  or :refer (refer -> escalate to human underwriter)."
  [policy-id decision & {:keys [risk-score rationale]}]
  (when (contains? underwriting-decisions decision)
    {:underwriting/policy     policy-id
     :underwriting/decision   decision
     :underwriting/risk-score risk-score
     :underwriting/rationale  rationale}))

;; ---------------------------------------------------------------------------
;; Validation
;; ---------------------------------------------------------------------------

(defn validate-policy
  "Return a validation result for a policy record."
  [m]
  (cond
    (not (map? m))                      {:insurance/valid? false :insurance/error :not-a-map}
    (not (:policy/id m))                 {:insurance/valid? false :insurance/error :missing-id}
    (not (contains? policy-types (:policy/type m)))
    {:insurance/valid? false :insurance/error :unknown-type}
    (not (pos? (or (:policy/coverage m) 0)))
    {:insurance/valid? false :insurance/error :non-positive-coverage}
    :else                                {:insurance/valid? true :policy/type (:policy/type m)}))

(defn validate-claim
  "Return a validation result for a claim record."
  [m]
  (cond
    (not (map? m))                      {:insurance/valid? false :insurance/error :not-a-map}
    (not (:claim/id m))                  {:insurance/valid? false :insurance/error :missing-id}
    (not (contains? claim-statuses (:claim/status m)))
    {:insurance/valid? false :insurance/error :unknown-status}
    :else                                {:insurance/valid? true :claim/status (:claim/status m)}))
