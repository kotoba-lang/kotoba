(ns game.analytics
  "Provider-neutral analytics and retention reducers for games.

  Hosts own identity proof, durable storage, consent, an authoritative clock and
  payment verification. This namespace only accepts bounded pseudonymous event
  envelopes and produces deterministic projections."
  (:require [kotoba.lang.text :as str]))

(def contract-version 1)
(def inactivity-seconds 1800)
(def max-dimensions 16)
(def max-dimension-length 96)

(def privacy-classes #{:essential :functional :analytics})
(def trust-levels #{:client :server :payment-provider})
(def forbidden-dimensions
  #{:email :phone :ip :ip-address :user-agent :device-fingerprint :name
    :latitude :longitude :address})

(defn utc-day [epoch-seconds]
  (quot epoch-seconds 86400))

(defn- bounded-string? [value limit]
  (and (string? value) (not (str/blank? value)) (<= (count value) limit)))

(defn- scalar? [value]
  (or (string? value) (keyword? value) (boolean? value) (number? value) (nil? value)))

(defn valid-dimensions? [dimensions]
  (and (map? dimensions)
       (<= (count dimensions) max-dimensions)
       (every? (fn [[k value]]
                 (and (keyword? k)
                      (not (contains? forbidden-dimensions k))
                      (scalar? value)
                      (or (not (string? value))
                          (<= (count value) max-dimension-length))))
               dimensions)))

(defn event-error
  "Return a stable error keyword, or nil for a valid event. Revenue events are
  authoritative only when emitted by the server/payment provider."
  [{:event/keys [id player game name occurred-at privacy trust dimensions
                 amount-minor currency]}]
  (cond
    (not (bounded-string? id 128)) :invalid-id
    (not (bounded-string? player 192)) :invalid-player
    (not (bounded-string? game 160)) :invalid-game
    (not (keyword? name)) :invalid-name
    (or (not (integer? occurred-at)) (neg? occurred-at)) :invalid-clock
    (not (contains? privacy-classes privacy)) :invalid-privacy
    (not (contains? trust-levels trust)) :invalid-trust
    (not (valid-dimensions? (or dimensions {}))) :invalid-dimensions
    (and (= privacy :analytics) (not= true (:consent/analytics dimensions))) :consent-required
    (and amount-minor (or (not (integer? amount-minor)) (neg? amount-minor))) :invalid-amount
    (not= (some? amount-minor) (some? currency)) :incomplete-money
    (and currency (not (keyword? currency))) :invalid-currency
    (and amount-minor (= trust :client)) :untrusted-revenue
    :else nil))

(defn ledger [] {:analytics/version contract-version :events {}})

(defn ingest
  "Idempotently append an immutable event. Returns [status ledger], or
  [:error reason ledger]."
  [state event]
  (if-let [reason (event-error event)]
    [:error reason state]
    (let [id (:event/id event)]
      (if (contains? (:events state) id)
        [:duplicate state]
        [:ok (assoc-in state [:events id]
                       (update event :event/dimensions #(or % {})))]))))

(defn ordered-events [state]
  (->> (:events state) vals
       (sort-by (juxt :event/occurred-at :event/id))))

(defn sessions
  "Materialize sessions using an explicit inactivity gap. Session identity is
  deterministic and does not depend on map iteration order."
  ([state] (sessions state inactivity-seconds))
  ([state inactivity]
   (->> (ordered-events state)
        (group-by (juxt :event/player :event/game))
        (mapcat
         (fn [[[player game] events]]
           (let [groups (reduce (fn [acc event]
                                  (let [last-event (some-> acc peek peek)
                                        new? (or (nil? last-event)
                                                 (> (- (:event/occurred-at event)
                                                       (:event/occurred-at last-event))
                                                    inactivity))]
                                    (if new? (conj acc [event])
                                        (update acc (dec (count acc)) conj event))))
                                [] events)]
             (map-indexed
              (fn [index xs]
                {:session/id (str player "|" game "|" (:event/id (first xs)))
                 :session/player player :session/game game :session/index index
                 :session/started-at (:event/occurred-at (first xs))
                 :session/ended-at (:event/occurred-at (last xs))
                 :session/event-count (count xs)})
              groups))))
        (sort-by (juxt :session/started-at :session/id)) vec)))

(defn active-users
  "Distinct active players for [from-day,to-day], inclusive."
  [state from-day to-day]
  (->> (ordered-events state)
       (filter #(<= from-day (utc-day (:event/occurred-at %)) to-day))
       (map :event/player) set count))

(defn retention
  "Cohort retention for offsets such as [1 7 30]. Each player's earliest event
  in the selected game is day zero. Returns exact numerator/denominator data."
  [state game offsets]
  (let [by-player (->> (ordered-events state)
                       (filter #(= game (:event/game %)))
                       (group-by :event/player))
        cohorts (group-by (fn [[_ events]] (utc-day (:event/occurred-at (first events))))
                          by-player)]
    (into (sorted-map)
          (map (fn [[cohort members]]
                 (let [size (count members)]
                   [cohort
                    {:cohort/size size
                     :retention
                     (into (sorted-map)
                           (map (fn [offset]
                                  (let [retained (count
                                                  (filter (fn [[_ events]]
                                                            (some #(= (+ cohort offset)
                                                                      (utc-day (:event/occurred-at %)))
                                                                  events))
                                                          members))]
                                    [offset {:retained retained
                                             :rate (if (zero? size) 0 (/ retained size))}]))
                                offsets))}]))
               cohorts))))

(defn funnel
  "Count players completing ordered event names. A later step only counts when
  it occurs at or after the player's previous step."
  [state game steps]
  (let [players (->> (ordered-events state)
                     (filter #(= game (:event/game %)))
                     (group-by :event/player))
        completed (fn [events]
                    (loop [remaining events wanted steps result []]
                      (if-let [step (first wanted)]
                        (if-let [event (first (drop-while #(not= step (:event/name %)) remaining))]
                          (recur (drop-while #(<= (:event/occurred-at %)
                                                  (:event/occurred-at event)) remaining)
                                 (rest wanted) (conj result step))
                          result)
                        result)))
        counts (mapv (fn [index]
                       (count (filter #(> (count (completed (val %))) index) players)))
                     (range (count steps)))
        entered (or (first counts) 0)]
    (mapv (fn [index step]
            (let [n (nth counts index)]
              {:step step :players n :conversion (if (zero? entered) 0 (/ n entered))
               :dropoff (if (zero? index) 0 (- (nth counts (dec index)) n))}))
          (range) steps)))

(defn revenue
  "Aggregate trusted money events without ever adding different currencies.
  `active-day` makes ARPDAU explicit; amounts remain integer minor units."
  [state game active-day]
  (let [events (filter #(and (= game (:event/game %))
                             (= :purchase-settled (:event/name %))
                             (= active-day (utc-day (:event/occurred-at %)))
                             (:event/amount-minor %))
                       (ordered-events state))
        dau (active-users state active-day active-day)]
    (into (sorted-map)
          (map (fn [[currency xs]]
                 (let [gross (reduce + (map :event/amount-minor xs))
                       payers (count (set (map :event/player xs)))]
                   [currency {:gross-minor gross :payers payers :transactions (count xs)
                              :arpdau-minor (if (zero? dau) 0 (/ gross dau))
                              :arppu-minor (if (zero? payers) 0 (/ gross payers))}]))
               (group-by :event/currency events)))))

