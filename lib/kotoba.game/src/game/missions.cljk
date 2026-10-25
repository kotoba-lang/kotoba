(ns game.missions
  "Portable mission and quest-chain reducers. Hosts authenticate gameplay
  events and supply clocks; this namespace owns deterministic progress,
  prerequisites, expiry and idempotent reward claims.")

(def contract-version 1)

(defn- valid-rewards? [rewards]
  (and (map? rewards)
       (every? (fn [[k value]] (or (= k :items) (pos-int? value))) rewards)
       (or (nil? (:items rewards))
           (and (vector? (:items rewards))
                (every? #(and (string? (:item %)) (seq (:item %))
                              (or (nil? (:quantity %)) (pos-int? (:quantity %)))
                              (or (nil? (:entitlement %)) (boolean? (:entitlement %))))
                        (:items rewards))))
       (or (some (fn [[k value]] (and (not= k :items) (pos-int? value))) rewards)
           (seq (:items rewards)))))

(defn valid-definition?
  [{:mission/keys [id event target starts-at ends-at prerequisites rewards]}]
  (and (keyword? id) (keyword? event) (integer? target) (pos? target)
       (integer? starts-at) (integer? ends-at) (< starts-at ends-at)
       (set? prerequisites) (every? keyword? prerequisites)
       (valid-rewards? rewards)))

(defn catalog [definitions]
  (let [by-id (into {} (map (juxt :mission/id identity)) definitions)]
    (when (and (= (count by-id) (count definitions))
               (every? valid-definition? definitions)
               (every? #(contains? by-id %)
                       (mapcat :mission/prerequisites definitions)))
      by-id)))

(defn state [] {:mission/version contract-version :progress {} :events #{} :claims #{}})

(defn status [s definition now]
  (let [id (:mission/id definition)
        progress (get-in s [:progress id] 0)]
    (cond
      (< now (:mission/starts-at definition)) :scheduled
      (>= now (:mission/ends-at definition)) :expired
      (some #(not (contains? (:claims s) %)) (:mission/prerequisites definition)) :locked
      (>= progress (:mission/target definition))
      (if (contains? (:claims s) id) :claimed :complete)
      :else :active)))

(defn apply-event
  "Apply one host-verified event to all matching active missions. Event IDs
  deduplicate retries across every mission."
  [s definitions now {:event/keys [id kind amount verified?]}]
  (cond
    (or (nil? id) (not (keyword? kind)) (not (pos-int? amount))) [:error :invalid-event s]
    (not verified?) [:error :unverified-event s]
    (contains? (:events s) id) [:duplicate s]
    :else
    [:ok (reduce (fn [next definition]
                   (if (and (= kind (:mission/event definition))
                            (= :active (status next definition now)))
                     (update-in next [:progress (:mission/id definition)]
                                (fnil #(min (:mission/target definition) (+ % amount)) 0))
                     next))
                 (update s :events conj id) definitions)]))

(defn claim [s definition player now claim-id]
  (let [id (:mission/id definition)]
    (cond
      (or (nil? player) (nil? claim-id)) [:error :invalid-claim s]
      (contains? (:claims s) id) [:duplicate s]
      (not= :complete (status s definition now)) [:error :mission-not-complete s]
      :else [:ok (:mission/rewards definition)
             (-> s (update :claims conj id)
                 (assoc-in [:claim-references id] {:claim/id claim-id :player player :at now}))])))
