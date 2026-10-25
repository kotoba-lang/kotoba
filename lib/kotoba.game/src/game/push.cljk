(ns game.push
  "Portable push-delivery policy. Hosts own Web Push/APNs/FCM credentials,
  encrypted endpoint storage, clocks and actual network delivery. This namespace
  decides eligibility and retries without ever seeing a raw push endpoint.")

(def contract-version 1)
(def max-topics 32)
(def max-attempts 6)
(def retry-seconds [60 300 1800 7200 21600 86400])
(def terminal-statuses #{:delivered :expired :cancelled :permanent-failure})

(defn state [] {:push/version contract-version :subscriptions {} :deliveries {}})
(defn- minute-of-day [epoch-seconds offset-minutes]
  (mod (+ (quot epoch-seconds 60) offset-minutes) 1440))
(defn quiet? [{:subscription/keys [quiet-start quiet-end timezone-offset]} now]
  (let [minute (minute-of-day now timezone-offset)]
    (cond
      (= quiet-start quiet-end) false
      (< quiet-start quiet-end) (<= quiet-start minute (dec quiet-end))
      :else (or (<= quiet-start minute 1439) (< minute quiet-end)))))

(defn subscribe
  [s {:subscription/keys [id player endpoint-ref locale timezone-offset quiet-start
                          quiet-end topics expires-at] :as subscription} now]
  (cond
    (or (not (string? id)) (empty? id) (> (count id) 128)
        (not (string? player)) (empty? player)
        (not (string? endpoint-ref)) (empty? endpoint-ref) (> (count endpoint-ref) 256)
        (not (string? locale)) (> (count locale) 16)
        (not (integer? timezone-offset)) (not (<= -840 timezone-offset 840))
        (not (integer? quiet-start)) (not (<= 0 quiet-start 1439))
        (not (integer? quiet-end)) (not (<= 0 quiet-end 1439))
        (not (set? topics)) (> (count topics) max-topics) (not-every? keyword? topics)
        (and expires-at (or (not (integer? expires-at)) (<= expires-at now))))
    [:error :invalid-subscription s]
    :else
    [:ok (assoc-in s [:subscriptions id]
                   (assoc subscription :subscription/status :active
                                       :subscription/created-at now
                                       :subscription/updated-at now))]))

(defn unsubscribe [s id player now]
  (let [subscription (get-in s [:subscriptions id])]
    (cond (nil? subscription) [:error :subscription-not-found s]
          (not= player (:subscription/player subscription)) [:error :not-subscription-owner s]
          (= :inactive (:subscription/status subscription)) [:duplicate s]
          :else [:ok (-> s
                         (assoc-in [:subscriptions id :subscription/status] :inactive)
                         (assoc-in [:subscriptions id :subscription/updated-at] now))])))

(defn eligible?
  [subscription topic now]
  (and (= :active (:subscription/status subscription))
       (or (nil? (:subscription/expires-at subscription))
           (> (:subscription/expires-at subscription) now))
       (contains? (:subscription/topics subscription) topic)
       (not (quiet? subscription now))))

(defn enqueue
  "Create one delivery per eligible subscription. `notification-id +
  subscription-id` is the deterministic idempotency key."
  [s {:notification/keys [id recipient topic expires-at] :as notification} now]
  (if (or (not (string? id)) (not (string? recipient)) (not (keyword? topic))
          (not (integer? expires-at)) (<= expires-at now))
    [:error :invalid-push-notification s]
    (let [subscriptions (filter #(and (= recipient (:subscription/player %))
                                      (eligible? % topic now))
                                (vals (:subscriptions s)))
          deliveries (map (fn [subscription]
                            (let [delivery-id (str id "|" (:subscription/id subscription))]
                              [delivery-id #:delivery{:id delivery-id :notification-id id
                                :subscription-id (:subscription/id subscription)
                                :player recipient :topic topic :status :pending :attempts 0
                                :next-at now :expires-at expires-at :created-at now}]))
                          subscriptions)
          fresh (remove #(contains? (:deliveries s) (first %)) deliveries)]
      [(if (seq fresh) :ok :duplicate)
       (update s :deliveries into fresh)])))

(defn due [s now limit]
  (if (or (not (integer? limit)) (not (<= 1 limit 500))) []
      (->> (:deliveries s) vals
           (filter #(and (not (contains? terminal-statuses (:delivery/status %)))
                         (<= (:delivery/next-at %) now)
                         (> (:delivery/expires-at %) now)))
           (sort-by (juxt :delivery/next-at :delivery/id)) (take limit) vec)))

(defn record-attempt
  "`result` is :delivered, :transient-failure or :permanent-failure. HTTP
  404/410 adapters map to permanent failure and deactivate the subscription."
  [s delivery-id result now]
  (let [delivery (get-in s [:deliveries delivery-id]) attempts (inc (or (:delivery/attempts delivery) 0))]
    (cond
      (nil? delivery) [:error :delivery-not-found s]
      (contains? terminal-statuses (:delivery/status delivery)) [:duplicate s]
      (not (contains? #{:delivered :transient-failure :permanent-failure} result))
      [:error :invalid-delivery-result s]
      :else
      (let [terminal? (or (= result :delivered) (= result :permanent-failure)
                          (>= attempts max-attempts) (<= (:delivery/expires-at delivery) now))
            status (cond (= result :delivered) :delivered
                         (= result :permanent-failure) :permanent-failure
                         (<= (:delivery/expires-at delivery) now) :expired
                         (>= attempts max-attempts) :permanent-failure
                         :else :retrying)
            next-at (when-not terminal? (+ now (nth retry-seconds (dec attempts))))
            subscription-id (:delivery/subscription-id delivery)
            s' (-> s (assoc-in [:deliveries delivery-id]
                               (cond-> (assoc delivery :delivery/status status
                                                      :delivery/attempts attempts
                                                      :delivery/last-at now)
                                 next-at (assoc :delivery/next-at next-at))))
            s' (if (= status :permanent-failure)
                 (assoc-in s' [:subscriptions subscription-id :subscription/status] :inactive) s')]
        [:ok s']))))
