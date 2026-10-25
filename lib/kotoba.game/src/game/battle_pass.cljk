(ns game.battle-pass
  "Provider-neutral season-pass lifecycle with free/premium tracks. Payment
  verification and durable grants remain host responsibilities; XP admission,
  tier unlocks and claim idempotency are shared pure CLJC rules.")

(def contract-version 1)

(defn valid-season?
  [{:season/keys [id starts-at ends-at tiers]}]
  (and (keyword? id) (integer? starts-at) (integer? ends-at) (< starts-at ends-at)
       (vector? tiers) (seq tiers)
       (= (range 1 (inc (count tiers))) (map :tier/level tiers))
       (apply < (map :tier/xp tiers))
       (every? #(and (map? (:tier/free %)) (map? (:tier/premium %))) tiers)))

(defn state [season player]
  {:pass/version contract-version :season/id (:season/id season) :player/id player
   :xp 0 :premium? false :xp-events #{} :claims #{}})

(defn season-status [season now]
  (cond (< now (:season/starts-at season)) :scheduled
        (>= now (:season/ends-at season)) :closed
        :else :active))

(defn add-xp [s season now {:xp/keys [event-id amount verified?]}]
  (cond
    (not= (:season/id season) (:season/id s)) [:error :wrong-season s]
    (not= :active (season-status season now)) [:error :season-not-active s]
    (or (nil? event-id) (not (pos-int? amount))) [:error :invalid-xp s]
    (not verified?) [:error :unverified-xp s]
    (contains? (:xp-events s) event-id) [:duplicate s]
    :else [:ok (-> s (update :xp + amount) (update :xp-events conj event-id))]))

(defn activate-premium [s season now entitlement-id verified?]
  (cond
    (not= :active (season-status season now)) [:error :season-not-active s]
    (or (nil? entitlement-id) (not verified?)) [:error :unverified-entitlement s]
    (:premium? s) [:duplicate s]
    :else [:ok (assoc s :premium? true :premium/entitlement entitlement-id)]))

(defn unlocked-level [s season]
  (->> (:season/tiers season)
       (filter #(<= (:tier/xp %) (:xp s)))
       (map :tier/level) (reduce max 0)))

(defn claim [s season now level track claim-id]
  (let [tier (nth (:season/tiers season) (dec level) nil)
        key [level track]]
    (cond
      (not= :active (season-status season now)) [:error :season-not-active s]
      (nil? tier) [:error :unknown-tier s]
      (not (contains? #{:free :premium} track)) [:error :unknown-track s]
      (> level (unlocked-level s season)) [:error :tier-locked s]
      (and (= track :premium) (not (:premium? s))) [:error :premium-required s]
      (contains? (:claims s) key) [:duplicate s]
      (nil? claim-id) [:error :invalid-claim s]
      :else [:ok (get tier (keyword "tier" (name track)))
             (-> s (update :claims conj key)
                 (assoc-in [:claim-references key] claim-id))])))

