(ns crowdfunding.reward
  "Reward tiers and add-ons — what a backer is actually promised.

  A tier is a scarce, dated promise, and each of those three words is a
  failure mode this namespace has to make impossible to get wrong:

  - **scarce**: a limited tier that oversells is not a pricing mistake, it
    is a promise the creator cannot keep. `claim` is therefore the only
    way to increment `:reward/claimed`, and it REFUSES (nil) rather than
    saturating when the limit is reached. Availability is derived from the
    record, never self-asserted by a pledge.
  - **dated**: `:reward/estimated-delivery` is required. A tier with no
    date is the shape of every fulfilment dispute that follows.
  - **promise**: shipping is part of the promise. A tier that cannot ship
    to the backer's country is not a discount, it is unavailable — so
    `ships-to?` gates claiming, and `shipping-minor-for` is per-destination
    data rather than one global number.

  Amounts are integer minor units of the campaign currency. Pure: no
  clock, no network, no randomness."
  (:require [kotoba.lang.text :as str]))

(def ^:private unlimited nil)

(defn reward
  "Build a reward tier.

  `limit` nil means unlimited. `shipping` is a map of destination →
  shipping cost in minor units; `:rest-of-world` is the fallback key and
  its ABSENCE is meaningful — a tier with no `:rest-of-world` entry ships
  only where it says it ships."
  [{:keys [id title description minimum-minor limit claimed
           estimated-delivery shipping add-on? ships-to]
    :or   {limit unlimited claimed 0 add-on? false shipping {} ships-to #{}}}]
  {:reward/id                 (str id)
   :reward/title              title
   :reward/description        description
   :reward/minimum-minor      minimum-minor
   :reward/limit              limit
   :reward/claimed            claimed
   :reward/estimated-delivery estimated-delivery
   :reward/shipping           shipping
   :reward/ships-to           (set ships-to)
   :reward/add-on?            (boolean add-on?)})

(defn reward-errors
  "[] when the tier may be published."
  [r]
  (vec
   (concat
    (when (str/blank? (str (:reward/id r)))
      [{:reward.error/code :missing-id}])
    (when (str/blank? (str (:reward/title r)))
      [{:reward.error/code :missing-title}])
    (when-not (and (integer? (:reward/minimum-minor r))
                   (pos? (:reward/minimum-minor r)))
      [{:reward.error/code :minimum-must-be-positive}])
    (when-not (or (nil? (:reward/limit r))
                  (and (integer? (:reward/limit r)) (pos? (:reward/limit r))))
      [{:reward.error/code :invalid-limit}])
    (when-not (and (integer? (:reward/claimed r)) (not (neg? (:reward/claimed r))))
      [{:reward.error/code :invalid-claimed}])
    (when (and (integer? (:reward/limit r))
               (> (:reward/claimed r 0) (:reward/limit r)))
      [{:reward.error/code   :oversold
        :reward.error/detail (str (:reward/claimed r) "/" (:reward/limit r))}])
    (when (str/blank? (str (:reward/estimated-delivery r)))
      [{:reward.error/code   :missing-estimated-delivery
        :reward.error/detail "a tier with no date is an undated promise"}])
    (when (and (empty? (:reward/ships-to r))
               (seq (:reward/shipping r)))
      [{:reward.error/code :shipping-priced-but-nowhere-shippable}])
    (mapcat (fn [[dest amount]]
              (when-not (and (integer? amount) (not (neg? amount)))
                [{:reward.error/code   :invalid-shipping-amount
                  :reward.error/detail (pr-str dest)}]))
            (:reward/shipping r)))))

;; ───────────────────────────── availability ─────────────────────────────

(defn remaining
  "How many of this tier are left, or nil when unlimited."
  [r]
  (when-let [l (:reward/limit r)]
    (max 0 (- l (:reward/claimed r 0)))))

(defn available?
  "Is at least one left?"
  [r]
  (let [rem (remaining r)]
    (or (nil? rem) (pos? rem))))

(defn ships-to?
  "May this tier be shipped to `destination`?

  An empty `:reward/ships-to` means the tier is DIGITAL or requires no
  shipping — it is shippable anywhere, because there is nothing to ship.
  A non-empty set is exhaustive: `:rest-of-world` must be listed
  explicitly to be granted."
  [r destination]
  (let [dests (:reward/ships-to r)]
    (or (empty? dests)
        (contains? dests destination)
        (contains? dests :rest-of-world))))

(defn shipping-minor-for
  "Shipping cost to `destination` in minor units, or nil when this tier
  cannot ship there. A nil is a refusal, not a free shipment — callers
  must branch on it."
  [r destination]
  (when (ships-to? r destination)
    (let [table (:reward/shipping r)]
      (or (get table destination)
          (get table :rest-of-world)
          0))))

(defn claim
  "Take one unit of the tier for a backer shipping to `destination`.
  Returns the updated reward, or nil when the tier is unavailable or
  cannot ship there.

  This is the ONLY function that increments `:reward/claimed`. Keeping it
  single-entry is what makes `:oversold` in `reward-errors` an invariant
  violation to assert on rather than a state the system routinely reaches."
  ([r] (claim r nil))
  ([r destination]
   (when (and (available? r)
              (or (nil? destination) (ships-to? r destination)))
     (update r :reward/claimed (fnil inc 0)))))

(defn release
  "Give a claimed unit back — a cancelled or dropped pledge must return
  its scarcity to the pool, otherwise a campaign slowly sells out to
  backers who never paid. Refuses (nil) below zero rather than clamping,
  so an unbalanced claim/release pair surfaces as a bug."
  [r]
  (when (pos? (:reward/claimed r 0))
    (update r :reward/claimed dec)))

;; ───────────────────────────── selection ─────────────────────────────

(defn eligible?
  "Does `amount-minor` reach this tier's minimum?"
  [r amount-minor]
  (and (integer? amount-minor)
       (>= amount-minor (:reward/minimum-minor r 0))))

(defn selectable
  "Every tier a backer pledging `amount-minor` to `destination` could
  actually take, best-value first (highest minimum that the amount still
  reaches), with add-ons excluded — an add-on is bought ALONGSIDE a tier,
  not instead of one.

  Returned in a total order (minimum desc, then id) so two callers with
  the same inputs display the same list. Ties broken by id rather than
  left to hash order, the `marketplace.catalog/buy-box` discipline."
  [rewards amount-minor destination]
  (->> rewards
       (remove :reward/add-on?)
       (filter #(and (available? %)
                     (eligible? % amount-minor)
                     (ships-to? % destination)))
       (sort-by (juxt (comp - :reward/minimum-minor) :reward/id))
       vec))

(defn excluded
  "The mirror of `selectable`: every tier the backer could NOT take, with
  the reason. A backer who cannot see why a tier is unavailable assumes
  the platform is hiding it."
  [rewards amount-minor destination]
  (->> rewards
       (remove :reward/add-on?)
       (keep (fn [r]
               (cond
                 (not (available? r))                {:reward/id (:reward/id r) :reason :sold-out}
                 (not (eligible? r amount-minor))    {:reward/id (:reward/id r) :reason :below-minimum}
                 (not (ships-to? r destination))     {:reward/id (:reward/id r) :reason :not-shippable})))
       (sort-by :reward/id)
       vec))
