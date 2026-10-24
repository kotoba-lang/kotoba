(ns io.stripe.issuing.state
  "The mapping between kotoba.card.lifecycle's five states and Stripe Issuing's
  three, published rather than absorbed.

  `kotoba.card.actuation/state-mapping-complete?` requires a provider to give
  every lifecycle state a provider-side representation, mapping to nil the ones it
  cannot express. This namespace is that declaration, and the impedance mismatch is
  real:

    lifecycle          Stripe Issuing card.status
    :intake            (nil)      no Stripe object exists yet
    :issued            \"inactive\"  created but not usable
    :active            \"active\"
    :blocked           \"inactive\"  <-- collides with :issued
    :closed            \"canceled\"  terminal, and terminal at Stripe too

  Verified against the live API spec on 2026-07-30 (2026-06-24.preview): a Stripe
  Issuing card's status is one of active / inactive / canceled, and its type is
  virtual / physical.

  THE COLLISION IS THE POINT OF THIS FILE. :issued and :blocked both map to
  \"inactive\", so Stripe alone cannot tell them apart -- and the difference matters:
  one is a card that has never worked, the other is a card that was working and was
  stopped. A provider that read the state back from Stripe would answer :issued for
  a blocked card, and a caller acting on that would \"activate\" a card that a human
  deliberately blocked.

  So this provider does NOT reconstruct the lifecycle state from Stripe. It keeps
  the issuer-side state as the authority and uses Stripe only to effect it. That is
  why `->stripe` is total and `<-stripe` deliberately is not:
  `stripe->candidates` returns the SET of lifecycle states a Stripe status could
  mean, and it is the caller's recorded state that disambiguates."
  (:require [kotoba.card.lifecycle :as lifecycle]))

(def statuses
  "Stripe Issuing card statuses. Verified against the live spec 2026-07-30."
  #{"active" "inactive" "canceled"})

(def card-types
  "Stripe Issuing card types. Verified against the live spec 2026-07-30."
  #{"virtual" "physical"})

(def mapping
  "lifecycle state -> Stripe status, or nil when Stripe cannot represent it.

  Every lifecycle state appears, which is what
  kotoba.card.actuation/state-mapping-complete? checks. :intake maps to nil
  because a cardholder in intake has no Stripe card at all -- that is an absence,
  not a status."
  {:intake  nil
   :issued  "inactive"
   :active  "active"
   :blocked "inactive"
   :closed  "canceled"})

(defn ->stripe
  "The Stripe status for a lifecycle state, or nil when Stripe cannot express it.
  Total over kotoba.card.lifecycle/states."
  [state]
  (get mapping state))

(defn representable?
  "True when Stripe can express this lifecycle state at all."
  [state]
  (some? (->stripe state)))

(defn stripe->candidates
  "The SET of lifecycle states a Stripe status could mean.

  Deliberately a set and not a single value. \"inactive\" is both :issued and
  :blocked, and a provider that guessed one would tell a caller that a
  deliberately-blocked card is merely un-activated. The caller's own recorded
  state is what narrows this."
  [status]
  (into #{} (for [[k v] mapping :when (and (some? v) (= v status))] k)))

(defn ambiguous-statuses
  "The Stripe statuses that map back to more than one lifecycle state. Reported,
  not hidden -- a caller needs to know which reads it cannot trust."
  []
  (into #{} (for [s statuses
                  :let [c (stripe->candidates s)]
                  :when (> (count c) 1)]
              s)))

(def events
  "How a lifecycle event is effected at Stripe.

  :reissue is the interesting one. Stripe has no \"replace\" status transition: a
  replacement is a NEW card object created with replacement_for pointing at the
  old one, which Stripe then cancels. So a reissue is two provider calls, and this
  table says so rather than pretending it is a status change -- matching
  kotoba.card.lifecycle, which already reports :card/mints-successor? true for it."
  {:activate {:stripe/op :update-status :stripe/status "active"}
   :block    {:stripe/op :update-status :stripe/status "inactive"}
   :close    {:stripe/op :update-status :stripe/status "canceled"}
   :reissue  {:stripe/op :replace
              :stripe/detail (str "creates a new card with replacement_for and "
                                  "cancels the original -- two calls, not a status change")}})

(defn event->op
  "What this provider must do to effect a lifecycle event, or nil for an event it
  does not know."
  [event]
  (get events event))

(defn covers-every-event?
  "True when every kotoba.card.lifecycle event has a provider operation. A missing
  one is a gap a caller must be told about, not discovered at runtime."
  []
  (= (set (keys events)) (set (keys lifecycle/events))))
