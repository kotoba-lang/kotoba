(ns crowdfunding.fulfillment
  "After the money — surveys, delivery, and the accountability record that
  makes a late project distinguishable from an abandoned one.

  Everything in this library up to here happens in weeks. This part
  happens over months or years, and it is where rewards crowdfunding
  actually fails: not usually in fraud, but in a creator who stops posting
  while backers cannot tell whether the project is late or dead. The
  design response is not a penalty. It is to make the DIFFERENCE
  observable — `stale?` is computed from the creator's own update cadence,
  and `accountability` reports obligations as facts rather than opinions,
  so a platform, a backer and the creator all read the same record.

  Two boundaries:

  - **Addresses are collected, not stored here.** A survey response
    carries a reference to where the address lives, never the address.
    This library is pure and gets copied into logs, ledgers and test
    fixtures; a shipping address in a pure domain value ends up in all
    three.
  - **Nothing here adjudicates.** `undeliverable` and `failure-disclosure`
    record what a creator or a named human stated. There is no function
    that decides a project failed.

  Pure: no clock (the caller passes `now`), no network."
  (:require [kotoba.lang.text :as str]))

;; ───────────────────────────── survey ─────────────────────────────

(def ^:private survey-required-fields
  "What a survey must ask before a reward can ship. Reward options come
  from the tier; shipping destination is already known from the pledge, so
  asking again invites a mismatch between what was priced and what ships."
  #{:shipping-address-ref :reward-options :contact-ref})

(defn survey
  "A survey for one backer's pledge. `address-ref` and `contact-ref` are
  OPAQUE references resolved by a system that is allowed to hold personal
  data — this record carries the reference and never the value."
  [{:keys [pledge backer campaign sent-at fields]
    :or   {fields survey-required-fields}}]
  {:survey/pledge   (str pledge)
   :survey/backer   (str backer)
   :survey/campaign (str campaign)
   :survey/sent-at  sent-at
   :survey/fields   (set fields)
   :survey/state    :sent})

(defn survey-response
  "A backer's answers, as references plus reward option selections."
  [{:keys [pledge address-ref contact-ref options responded-at]}]
  {:response/pledge       (str pledge)
   :response/address-ref  address-ref
   :response/contact-ref  contact-ref
   :response/options      (vec (or options []))
   :response/responded-at responded-at})

(defn response-errors
  "[] when a response is complete enough to ship against. A survey that is
  accepted while incomplete becomes an undeliverable parcel three months
  later, with the backer blamed for it."
  [s r]
  (vec
   (concat
    (when-not (= (:survey/pledge s) (:response/pledge r))
      [{:fulfillment.error/code :pledge-mismatch}])
    (when (and (contains? (:survey/fields s) :shipping-address-ref)
               (str/blank? (str (:response/address-ref r))))
      [{:fulfillment.error/code :missing-address-ref}])
    (when (and (contains? (:survey/fields s) :contact-ref)
               (str/blank? (str (:response/contact-ref r))))
      [{:fulfillment.error/code :missing-contact-ref}]))))

;; ───────────────────────────── per-backer state ─────────────────────────────

(def states
  #{:awaiting-survey :survey-received :in-production :shipped :delivered
    :undeliverable :refunded})

(def transitions
  "`:undeliverable` is not terminal — a backer who fixes their address
  returns to `:survey-received`, and a system that could not express that
  would strand them. `:refunded` IS terminal: the obligation ended."
  {:awaiting-survey #{:survey-received :refunded}
   :survey-received #{:in-production :shipped :undeliverable :refunded}
   :in-production   #{:shipped :undeliverable :refunded}
   :shipped         #{:delivered :undeliverable :refunded}
   :delivered       #{:refunded}
   :undeliverable   #{:survey-received :refunded}
   :refunded        #{}})

(defn line
  "One backer's fulfilment state for one pledge."
  [{:keys [pledge backer campaign reward estimated-delivery]}]
  {:fulfillment/pledge   (str pledge)
   :fulfillment/backer   (str backer)
   :fulfillment/campaign (str campaign)
   :fulfillment/reward   (when reward (str reward))
   :fulfillment/estimated-delivery estimated-delivery
   :fulfillment/state    :awaiting-survey})

(defn advance
  "Move a fulfilment line; nil when the table forbids it."
  [l to]
  (when (contains? (get transitions (:fulfillment/state l) #{}) to)
    (assoc l :fulfillment/state to)))

(defn ship
  "Record a shipment. A tracking reference is required — a shipment
  claimed without one cannot be checked by the backer, which makes
  `:shipped` a status the creator can assert unilaterally and the backer
  cannot verify."
  [l {:keys [tracking-ref carrier at]}]
  (when (and (not (str/blank? (str tracking-ref)))
             (contains? (get transitions (:fulfillment/state l) #{}) :shipped))
    (assoc l :fulfillment/state :shipped
           :fulfillment/tracking-ref tracking-ref
           :fulfillment/carrier carrier
           :fulfillment/shipped-at at)))

(defn undeliverable
  "Record a delivery failure with its stated reason. Records, does not
  judge: `:reason` is what the carrier or creator said, and the field is
  named so no reader mistakes it for a finding."
  [l {:keys [reason at]}]
  (some-> (advance l :undeliverable)
          (assoc :fulfillment/undeliverable-reason reason
                 :fulfillment/undeliverable-at at)))

(defn overdue?
  "Is this line past its estimated delivery at `now`? Estimated, not
  promised — the field is called `estimated-delivery` throughout, and
  being overdue is a fact about a date, not a breach."
  [l now]
  (boolean (and (:fulfillment/estimated-delivery l)
                (not (contains? #{:delivered :refunded} (:fulfillment/state l)))
                (pos? (compare (str now) (str (:fulfillment/estimated-delivery l)))))))

;; ───────────────────────────── campaign roll-up ─────────────────────────────

(defn progress
  "Roll fulfilment lines up for a campaign.

  `:fulfillment/complete?` requires every line to be delivered or
  refunded — it is the fact `crowdfunding.payout`'s
  `:on-fulfillment-complete` gate consumes, so it must not be satisfiable
  while any backer is still waiting. `:undeliverable` counts as NOT
  complete: an unreachable backer is an open obligation, not a rounding
  error."
  [lines now]
  (let [by-state (frequencies (map :fulfillment/state lines))
        total    (count lines)
        done     (+ (get by-state :delivered 0) (get by-state :refunded 0))]
    {:fulfillment/total          total
     :fulfillment/by-state       by-state
     :fulfillment/delivered      (get by-state :delivered 0)
     :fulfillment/shipped        (get by-state :shipped 0)
     :fulfillment/awaiting-survey (get by-state :awaiting-survey 0)
     :fulfillment/undeliverable  (get by-state :undeliverable 0)
     :fulfillment/overdue        (count (filter #(overdue? % now) lines))
     :fulfillment/complete?      (and (pos? total) (= total done))
     :fulfillment/first-shipment? (pos? (+ (get by-state :shipped 0)
                                           (get by-state :delivered 0)))
     :fulfillment/completion-bps (if (pos? total) (quot (* 10000 done) total) 0)}))

(defn gate-facts
  "The set of payout gates this campaign's state actually satisfies, for
  `crowdfunding.payout/releasable`.

  Derived here rather than asserted by the payout caller, so a tranche can
  never be released against a gate nobody checked. `:on-production-start`
  is absent unless the creator supplied evidence — production having begun
  is not observable from fulfilment states, and inferring it would invent
  the very fact the holdback exists to require."
  [prog {:keys [collection-closed? production-evidence]}]
  (cond-> #{}
    collection-closed?                  (conj :on-collection)
    (some? production-evidence)         (conj :on-production-start)
    (:fulfillment/first-shipment? prog) (conj :on-first-shipment)
    (:fulfillment/complete? prog)       (conj :on-fulfillment-complete)))

;; ───────────────────────────── accountability ─────────────────────────────

(def ^:private default-update-interval-days
  "How long a creator may go quiet before backers are entitled to read
  that as silence rather than as work. Not a rule about effort — a
  creator who is heads-down building is exactly the case this protects,
  because a single post ends the ambiguity." 90)

(defn accountability
  "The creator's standing obligations, as facts.

  `:accountability/stale?` compares the last update against
  `update-interval-days`. `:accountability/owes-disclosure?` is true when
  the project is overdue AND stale: either alone is ordinary, both
  together is the pattern backers have no way to distinguish from
  abandonment.

  Nothing here concludes that a creator failed. It states what is
  observable, and `failure-disclosure` is the creator's own statement when
  they decide to make one."
  [{:keys [campaign lines last-update-at updates-count now stale-before
           update-interval-days]
    :or   {update-interval-days default-update-interval-days}}]
  (let [prog    (progress lines now)
        overdue (pos? (:fulfillment/overdue prog))
        ;; `stale-before` is `now` minus the interval, computed by the
        ;; caller. This library has no clock and will not do date
        ;; arithmetic on ISO strings — a comparison it could make without
        ;; that input would be a comparison against `now`, which every
        ;; past update loses.
        stale   (when stale-before
                  (or (nil? last-update-at)
                      (neg? (compare (str last-update-at) (str stale-before)))))]
    {:accountability/campaign        campaign
     :accountability/updates-count   (or updates-count 0)
     :accountability/last-update-at  last-update-at
     :accountability/update-interval-days update-interval-days
     :accountability/progress        prog
     :accountability/overdue?        overdue
     ;; nil, not false, when the caller supplied no `stale-before`:
     ;; "we did not measure" and "they are not stale" are different
     ;; statements and only one of them is evidence.
     :accountability/stale?          stale
     :accountability/owes-disclosure? (boolean (and overdue (true? stale)))
     :accountability/adjudicated?    false}))

(defn failure-disclosure
  "A creator's statement that they cannot deliver, with what they propose
  to do about it. Requires a named author and one of a closed set of
  remedies — 'we're working on it' is an update, not a disclosure, and
  letting it be recorded as one would empty the record of meaning."
  [{:keys [campaign stated-by stated-at reason remedy detail]}]
  (when (and (not (str/blank? (str stated-by)))
             (contains? #{:refund :partial-refund :substitute-reward
                          :extended-timeline :no-remedy}
                        remedy))
    {:disclosure/campaign  campaign
     :disclosure/stated-by stated-by
     :disclosure/stated-at stated-at
     :disclosure/reason    reason
     :disclosure/remedy    remedy
     :disclosure/detail    detail
     :disclosure/human?    true}))
