(ns game.social
  "Portable social-game platform contracts.

  This namespace is deliberately pure CLJC: applications provide persistence,
  clocks, signatures and payment verification, while this layer owns the data
  invariants shared by browser games, workers and native hosts. IDs and times are
  explicit inputs so replaying the same command is deterministic and idempotent.")

(def currencies #{:free-gem :paid-gem})

(defn player-profile
  [did display-name created-at]
  {:player/did did
   :player/display-name display-name
   :player/created-at created-at
   :player/status :active
   :player/blocked #{}
   :player/muted #{}})

(defn platform-state []
  {:platform/version 1
   :profiles {}
   :achievement-progress {}
   :achievement-unlocks {}
   :activity-events {}
   :notifications {}
   :saves {}
   :wallets {}
   :payment-intents {}
   :refunds {}
   :daily-rewards {}
   :mail {}
   :party-invites {}
   :match-queues {}
   :matches {}
   :match-penalties {}
   :guild-events {}
   :inventories {}
   :receipts {}
   :leaderboards {}
   :chat []
   :friendships #{}
   :friend-requests {}
   :blocks #{}
   :groups {}
   :rooms {}})

(def notification-kinds
  #{:achievement :friend-request :party-invite :group :match :mail
    :purchase :payment :ranking :guild-event :system})

(defn issue-notification
  "Insert one immutable notification envelope. `id` is the delivery
   idempotency key; `source-id` links the originating request, invite, receipt
   or event. Hosts authenticate the producer before calling this reducer."
  [state {:notification/keys [id recipient kind title body source-id action
                              created-at expires-at] :as notification}]
  (cond
    (or (nil? id) (nil? recipient) (not (contains? notification-kinds kind))
        (not (string? title)) (empty? title) (> (count title) 80)
        (not (string? body)) (> (count body) 240)
        (nil? source-id) (not (integer? created-at))
        (and expires-at (or (not (integer? expires-at)) (<= expires-at created-at)))
        (and action (not (map? action))))
    [:error :invalid-notification state]

    (contains? (:notifications state) id) [:duplicate state]

    :else
    [:ok (assoc-in state [:notifications id]
                   (assoc notification :notification/read-at nil
                                       :notification/dismissed-at nil))]))

(defn notification-visible?
  [notification recipient now]
  (and (= recipient (:notification/recipient notification))
       (nil? (:notification/dismissed-at notification))
       (or (nil? (:notification/expires-at notification))
           (> (:notification/expires-at notification) now))))

(defn notification-inbox
  "Visible notifications, unread first then newest, with deterministic id tie
   breaking. `limit` is host-bounded to prevent an unbounded projection."
  [state recipient now limit]
  (if (or (nil? recipient) (not (integer? now)) (not (integer? limit))
          (not (<= 1 limit 100)))
    [:error :invalid-notification-query []]
    [:ok (->> (:notifications state)
              vals
              (filter #(notification-visible? % recipient now))
              (sort-by (fn [notification]
                         [(if (:notification/read-at notification) 1 0)
                          (- (:notification/created-at notification))
                          (str (:notification/id notification))]))
              (take limit)
              vec)]))

(defn unread-notification-count [state recipient now]
  (count (filter #(and (notification-visible? % recipient now)
                       (nil? (:notification/read-at %)))
                 (vals (:notifications state)))))

(defn mark-notification-read [state notification-id recipient read-at]
  (let [notification (get-in state [:notifications notification-id])]
    (cond
      (nil? notification) [:error :notification-not-found state]
      (not= recipient (:notification/recipient notification))
      [:error :not-notification-recipient state]
      (not (integer? read-at)) [:error :invalid-notification-clock state]
      (:notification/read-at notification) [:duplicate state]
      :else [:ok (assoc-in state [:notifications notification-id :notification/read-at]
                           read-at)])))

(defn mark-all-notifications-read [state recipient read-at]
  (if (or (nil? recipient) (not (integer? read-at)))
    [:error :invalid-notification-command state]
    [:ok (update state :notifications
                 (fn [notifications]
                   (into {}
                         (map (fn [[id notification]]
                                [id (if (and (= recipient (:notification/recipient notification))
                                             (nil? (:notification/read-at notification)))
                                      (assoc notification :notification/read-at read-at)
                                      notification)]))
                         notifications)))]))

(defn dismiss-notification [state notification-id recipient dismissed-at]
  (let [notification (get-in state [:notifications notification-id])]
    (cond
      (nil? notification) [:error :notification-not-found state]
      (not= recipient (:notification/recipient notification))
      [:error :not-notification-recipient state]
      (not (integer? dismissed-at)) [:error :invalid-notification-clock state]
      (:notification/dismissed-at notification) [:duplicate state]
      :else [:ok (assoc-in state [:notifications notification-id :notification/dismissed-at]
                           dismissed-at)])))

(def profile-visibilities #{:public :friends :private})

(defn update-player-profile
  "Apply a bounded portable profile patch. Identity ownership and text
   moderation remain host responsibilities; equipped titles must already be
   unlocked by this player's verified achievements."
  [state player {:keys [display-name bio avatar visibility equipped-title] :as patch}]
  (let [unlocked (get-in state [:achievement-unlocks player] {})]
    (cond
      (or (nil? player) (not (string? display-name)) (empty? display-name)
          (> (count display-name) 32) (not (string? bio)) (> (count bio) 160)
          (and avatar (or (not (string? avatar)) (> (count avatar) 512)))
          (not (contains? profile-visibilities visibility)))
      [:error :invalid-profile state]
      (and equipped-title
           (not-any? #(= equipped-title (:achievement/title %)) (vals unlocked)))
      [:error :title-not-unlocked state]
      :else [:ok (assoc-in state [:profiles player]
                           (merge #:player{:did player} patch))])))

(defn achievement
  "Validate a cross-game achievement. Reducer :sum accumulates verified event
   values; :max keeps a personal best."
  [{:achievement/keys [id game metric reducer threshold title title-reward] :as definition}]
  (when (and id game metric (contains? #{:sum :max} reducer)
             (number? threshold) (pos? threshold)
             (string? title) (not (empty? title)) (<= (count title) 48)
             (string? title-reward) (not (empty? title-reward))
             (<= (count title-reward) 48))
    definition))

(defn observe-achievement
  "Consume one host-verified gameplay/economy/social event. Event IDs make
   progress retries idempotent and unlock is immutable once reached."
  [state definition {:event/keys [id player game metric value verified at]}]
  (let [achievement-id (:achievement/id definition)
        path [:achievement-progress player achievement-id]
        progress (get-in state path {:achievement/value 0 :achievement/events #{}})]
    (cond
      (or (nil? id) (nil? player) (not (number? value)) (neg? value))
      [:error :invalid-achievement-event state]
      (not verified) [:error :achievement-event-unverified state]
      (or (not= game (:achievement/game definition))
          (not= metric (:achievement/metric definition)))
      [:error :achievement-event-mismatch state]
      (contains? (:achievement/events progress) id) [:duplicate state]
      :else
      (let [next-value ((if (= :max (:achievement/reducer definition)) max +)
                        (:achievement/value progress) value)
            unlocked? (>= next-value (:achievement/threshold definition))
            progress' {:achievement/value next-value
                       :achievement/events (conj (:achievement/events progress) id)
                       :achievement/updated-at at}
            state' (assoc-in state path progress')]
        [:ok (cond-> state'
               unlocked? (assoc-in [:achievement-unlocks player achievement-id]
                                   #:achievement{:id achievement-id
                                                 :game (:achievement/game definition)
                                                 :title (:achievement/title-reward definition)
                                                 :unlocked-at at}))]))))

(defn record-activity
  "Append an immutable, idempotent activity event with explicit visibility."
  [state {:activity/keys [id player kind visibility at] :as event}]
  (cond
    (or (nil? id) (nil? player) (nil? kind) (not (integer? at))
        (not (contains? profile-visibilities visibility)))
    [:error :invalid-activity state]
    (contains? (:activity-events state) id) [:duplicate state]
    :else [:ok (assoc-in state [:activity-events id] event)]))

(defn visible-activity?
  [viewer friends? {:activity/keys [player visibility]}]
  (or (= viewer player) (= :public visibility)
      (and (= :friends visibility) friends?)))

(defn pair
  "Canonical undirected player pair."
  [a b]
  (when (and a b (not= a b)) (vec (sort [a b]))))

(defn blocked?
  "True when either player has blocked the other."
  [state a b]
  (or (contains? (:blocks state) [a b])
      (contains? (:blocks state) [b a])))

(defn request-friend
  [state {:keys [request-id from to at]}]
  (let [p (pair from to)]
    (cond
      (or (nil? request-id) (nil? p)) [:error :invalid-friend-request state]
      (contains? (:friend-requests state) request-id) [:duplicate state]
      (blocked? state from to) [:error :blocked state]
      (contains? (:friendships state) p) [:error :already-friends state]
      :else [:ok (assoc-in state [:friend-requests request-id]
                           {:request/id request-id :request/from from :request/to to
                            :request/status :pending :request/at at})])))

(defn answer-friend
  [state {:keys [request-id player accept? at]}]
  (let [request (get-in state [:friend-requests request-id])]
    (cond
      (nil? request) [:error :request-not-found state]
      (not= :pending (:request/status request)) [:duplicate state]
      (not= player (:request/to request)) [:error :not-request-recipient state]
      (blocked? state (:request/from request) player) [:error :blocked state]
      :else
      (let [status (if accept? :accepted :declined)
            state' (assoc-in state [:friend-requests request-id]
                             (assoc request :request/status status :request/answered-at at))]
        [:ok (cond-> state' accept?
               (update :friendships conj (pair (:request/from request) player)))]))))

(defn block-player
  "Directional block. Blocking also removes friendship and pending requests
   between the pair, so a stale invitation cannot recreate the relationship."
  [state blocker blocked at]
  (if-let [p (pair blocker blocked)]
    [:ok (-> state
             (update :blocks conj [blocker blocked])
             (update :friendships disj p)
             (update :friend-requests
                     (fn [requests]
                       (into {} (remove (fn [[_ r]]
                                          (and (= :pending (:request/status r))
                                               (= p (pair (:request/from r) (:request/to r))))))
                             requests)))
             (assoc-in [:block-events [blocker blocked]] at))]
    [:error :invalid-block state]))

(defn remove-friend
  "Remove an existing friendship. Pending requests are also removed so both
   players return to a clean unrelated state."
  [state player other]
  (if-let [p (pair player other)]
    (if (contains? (:friendships state) p)
      [:ok (-> state
               (update :friendships disj p)
               (update :friend-requests
                       (fn [requests]
                         (into {} (remove (fn [[_ request]]
                                            (= p (pair (:request/from request)
                                                       (:request/to request)))))
                               requests))))]
      [:duplicate state])
    [:error :invalid-friend state]))

(def group-kinds #{:party :guild})

(defn create-group
  [state {:group/keys [id kind owner capacity] :as group}]
  (cond
    (or (nil? id) (nil? owner) (not (contains? group-kinds kind))
        (not (integer? capacity)) (< capacity 2)) [:error :invalid-group state]
    (contains? (:groups state) id) [:error :group-exists state]
    :else [:ok (assoc-in state [:groups id]
                         (merge group {:group/members {owner :owner}}))]))

(defn join-group
  [state group-id player role]
  (let [group (get-in state [:groups group-id])]
    (cond
      (nil? group) [:error :group-not-found state]
      (contains? (:group/members group) player) [:duplicate state]
      (>= (count (:group/members group)) (:group/capacity group)) [:error :group-full state]
      (some #(blocked? state player %) (keys (:group/members group))) [:error :blocked state]
      :else [:ok (assoc-in state [:groups group-id :group/members player] (or role :member))])))

(def group-roles #{:owner :moderator :member})

(defn leave-group
  "A non-owner may leave freely. A sole owner deletes the empty group; an owner
   with remaining members must transfer ownership first."
  [state group-id player]
  (let [group (get-in state [:groups group-id])
        role (get-in group [:group/members player])]
    (cond
      (nil? group) [:error :group-not-found state]
      (nil? role) [:duplicate state]
      (and (= :owner role) (> (count (:group/members group)) 1))
      [:error :owner-transfer-required state]
      (= :owner role) [:ok (update state :groups dissoc group-id)]
      :else [:ok (update-in state [:groups group-id :group/members] dissoc player)])))

(defn change-group-role
  "Only the owner may promote/demote an existing non-owner member. Ownership
   uses transfer-group-owner so a group can never have zero or two owners."
  [state group-id actor target role]
  (let [group (get-in state [:groups group-id])]
    (cond
      (nil? group) [:error :group-not-found state]
      (not= :owner (get-in group [:group/members actor])) [:error :not-group-owner state]
      (nil? (get-in group [:group/members target])) [:error :member-not-found state]
      (= :owner (get-in group [:group/members target])) [:error :cannot-change-owner-role state]
      (not (contains? #{:moderator :member} role)) [:error :invalid-group-role state]
      (= role (get-in group [:group/members target])) [:duplicate state]
      :else [:ok (assoc-in state [:groups group-id :group/members target] role)])))

(defn transfer-group-owner
  [state group-id actor target]
  (let [group (get-in state [:groups group-id])]
    (cond
      (nil? group) [:error :group-not-found state]
      (not= :owner (get-in group [:group/members actor])) [:error :not-group-owner state]
      (= actor target) [:duplicate state]
      (nil? (get-in group [:group/members target])) [:error :member-not-found state]
      :else [:ok (-> state
                     (assoc-in [:groups group-id :group/owner] target)
                     (assoc-in [:groups group-id :group/members actor] :moderator)
                     (assoc-in [:groups group-id :group/members target] :owner))])))

(defn remove-group-member
  "Owner may remove moderators/members; moderator may remove members only."
  [state group-id actor target]
  (let [group (get-in state [:groups group-id])
        actor-role (get-in group [:group/members actor])
        target-role (get-in group [:group/members target])
        allowed? (or (= :owner actor-role)
                     (and (= :moderator actor-role) (= :member target-role)))]
    (cond
      (nil? group) [:error :group-not-found state]
      (= actor target) [:error :use-leave-group state]
      (nil? target-role) [:duplicate state]
      (= :owner target-role) [:error :cannot-remove-owner state]
      (not allowed?) [:error :insufficient-group-role state]
      :else [:ok (update-in state [:groups group-id :group/members] dissoc target)])))

(defn create-room
  [state {:room/keys [id kind members max-length history-limit] :as room}]
  (cond
    (or (nil? id) (not (contains? #{:direct :party :guild :game} kind))
        (empty? members)) [:error :invalid-room state]
    (contains? (:rooms state) id) [:error :room-exists state]
    :else [:ok (assoc-in state [:rooms id]
                         (merge {:room/max-length 280 :room/history-limit 100
                                 :room/messages []}
                                room {:room/members (set members)}))]))

;; Save data uses optimistic concurrency. A device must write the revision it
;; read, preventing a stale tab from silently overwriting newer progression.
(defn put-save
  [state {:keys [player game expected-rev data updated-at]}]
  (let [path [player game]
        current (get-in state [:saves path])
        rev (or (:save/rev current) 0)]
    (cond
      (not= expected-rev rev) [:error :revision-conflict state]
      (not (map? data)) [:error :invalid-save state]
      :else
      (let [save {:save/player player :save/game game :save/rev (inc rev)
                  :save/data data :save/updated-at updated-at}]
        [:ok save (assoc-in state [:saves path] save)]))))

(defn wallet
  ([] (wallet {}))
  ([balances]
   {:wallet/balances (merge (zipmap currencies (repeat 0)) balances)
    :wallet/transactions []
    :wallet/applied #{}}))

(defn balance [w currency] (get-in w [:wallet/balances currency] 0))

(defn apply-transaction
  "Apply a server-authorized credit/debit once. Returns
   [:ok wallet'] | [:duplicate wallet] | [:error reason wallet]."
  [w {:tx/keys [id currency amount] :as tx}]
  (cond
    (contains? (:wallet/applied w) id) [:duplicate w]
    (not (contains? currencies currency)) [:error :unknown-currency w]
    (not (integer? amount)) [:error :invalid-amount w]
    (zero? amount) [:error :zero-amount w]
    (neg? (+ (balance w currency) amount)) [:error :insufficient-funds w]
    :else [:ok (-> w
                   (update-in [:wallet/balances currency] + amount)
                   (update :wallet/transactions conj tx)
                   (update :wallet/applied conj id))]))

(def default-daily-reward-schedule [10 10 15 15 20 25 50])

(defn daily-reward-schedule
  [schedule]
  (when (and (vector? schedule) (seq schedule)
             (every? #(and (integer? %) (pos? %)) schedule))
    schedule))

(defn claim-daily-reward
  "Claim one host-verified UTC day. Consecutive days advance the streak and
   cycle through the schedule; a missed day restarts at day one."
  [state {:keys [player day schedule verified? claimed-at]
          :or {schedule default-daily-reward-schedule}}]
  (let [reward-state (get-in state [:daily-rewards player]
                             {:reward/last-day nil :reward/streak 0 :reward/claims {}})
        last-day (:reward/last-day reward-state)]
    (cond
      (or (nil? player) (not (integer? day)) (nil? (daily-reward-schedule schedule)))
      [:error :invalid-daily-reward state]
      (not verified?) [:error :daily-reward-unverified state]
      (contains? (:reward/claims reward-state) day)
      [:duplicate (get-in reward-state [:reward/claims day]) state]
      (and last-day (< day last-day)) [:error :stale-reward-day state]
      :else
      (let [streak (if (= last-day (dec day)) (inc (:reward/streak reward-state)) 1)
            amount (nth schedule (mod (dec streak) (count schedule)))
            claim #:reward{:day day :streak streak :currency :free-gem
                           :amount amount :claimed-at claimed-at}
            tx #:tx{:id (str "daily/" player "/" day) :currency :free-gem
                    :amount amount :kind :daily-reward :at claimed-at :ref (str day)}
            [status wallet] (apply-transaction (get-in state [:wallets player] (wallet)) tx)]
        (if (not= :ok status)
          [:error :daily-reward-credit-failed state]
          [:ok claim (-> state
                         (assoc-in [:wallets player] wallet)
                         (assoc-in [:daily-rewards player :reward/last-day] day)
                         (assoc-in [:daily-rewards player :reward/streak] streak)
                         (assoc-in [:daily-rewards player :reward/claims day] claim))])))))

(defn inventory [] {:inventory/items {} :inventory/entitlements #{}})

(defn grant-item
  [inv {:item/keys [id quantity]}]
  (if (and id (integer? quantity) (pos? quantity))
    [:ok (update-in inv [:inventory/items id] (fnil + 0) quantity)]
    [:error :invalid-item-grant inv]))

(defn grant-entitlement [inv entitlement]
  (update inv :inventory/entitlements conj entitlement))

(defn owned? [inv item-id]
  (or (pos? (get-in inv [:inventory/items item-id] 0))
      (contains? (:inventory/entitlements inv) item-id)))

(defn mail-attachment
  [{:keys [currency amount item quantity] :as attachment}]
  (cond
    (and (= currency :free-gem) (integer? amount) (pos? amount)) attachment
    (and item (integer? quantity) (pos? quantity)) attachment
    :else nil))

(defn issue-mail
  "Create host-verified system mail. Attachments are free gems or stack items;
   paid gems and entitlements are deliberately not transferable here."
  [state {:keys [id recipient sender kind subject attachments created-at expires-at verified?]}]
  (cond
    (contains? (:mail state) id) [:duplicate (get-in state [:mail id]) state]
    (or (nil? id) (nil? recipient) (not verified?) (not (seq attachments))
        (not (every? mail-attachment attachments))
        (and expires-at (<= expires-at created-at)))
    [:error :invalid-mail state]
    :else
    (let [message #:mail{:id id :recipient recipient :sender sender
                         :kind (or kind :system) :subject (or subject "Reward")
                         :attachments (vec attachments) :status :pending
                         :created-at created-at :expires-at expires-at}]
      [:ok message (assoc-in state [:mail id] message)])))

(defn send-free-gem-gift
  "Escrow free gems from a verified friend relationship at send time."
  [state {:keys [id sender recipient amount created-at expires-at friendship-verified?]}]
  (cond
    (contains? (:mail state) id) [:duplicate (get-in state [:mail id]) state]
    (or (nil? id) (nil? sender) (nil? recipient) (= sender recipient)
        (not friendship-verified?) (not (integer? amount)) (not (<= 1 amount 100))
        (not (integer? expires-at)) (<= expires-at created-at))
    [:error :invalid-gift state]
    :else
    (let [debit #:tx{:id (str "gift-escrow/" id) :currency :free-gem
                     :amount (- amount) :kind :gift-escrow :at created-at :ref recipient}
          [status wallet] (apply-transaction (get-in state [:wallets sender] (wallet)) debit)]
      (if (not= :ok status)
        [:error status state]
        (let [[mail-status message next-state]
              (issue-mail (assoc-in state [:wallets sender] wallet)
                          {:id id :recipient recipient :sender sender :kind :gift
                           :subject "Friend gift" :attachments [{:currency :free-gem :amount amount}]
                           :created-at created-at :expires-at expires-at :verified? true})]
          (if (= :ok mail-status) [:ok message next-state]
              [:error :gift-mail-failed state]))))))

(defn claim-mail
  [state {:keys [mail-id player now]}]
  (let [message (get-in state [:mail mail-id])]
    (cond
      (nil? message) [:error :mail-not-found state]
      (not= player (:mail/recipient message)) [:error :not-mail-recipient state]
      (= :claimed (:mail/status message)) [:duplicate message state]
      (not= :pending (:mail/status message)) [:error :mail-not-pending state]
      (and (:mail/expires-at message) (>= now (:mail/expires-at message)))
      [:error :mail-expired state]
      :else
      (let [[wallet inventory]
            (reduce (fn [[w inv] [index attachment]]
                      (if-let [currency (:currency attachment)]
                        [(second (apply-transaction
                                  w #:tx{:id (str "mail/" mail-id "/" index)
                                         :currency currency :amount (:amount attachment)
                                         :kind :mail-claim :at now :ref mail-id})) inv]
                        [w (second (grant-item inv #:item{:id (:item attachment)
                                                        :quantity (:quantity attachment)}))]))
                    [(get-in state [:wallets player] (wallet))
                     (get-in state [:inventories player] (inventory))]
                    (map-indexed vector (:mail/attachments message)))
            claimed (assoc message :mail/status :claimed :mail/claimed-at now)]
        [:ok claimed (-> state
                         (assoc-in [:wallets player] wallet)
                         (assoc-in [:inventories player] inventory)
                         (assoc-in [:mail mail-id] claimed))]))))

(defn expire-mail
  "Expire pending mail. Gift escrow is returned exactly once to its sender."
  [state mail-id now]
  (let [message (get-in state [:mail mail-id])]
    (cond
      (nil? message) [:error :mail-not-found state]
      (not= :pending (:mail/status message)) [:duplicate message state]
      (or (nil? (:mail/expires-at message)) (< now (:mail/expires-at message)))
      [:error :mail-not-expired state]
      :else
      (let [expired (assoc message :mail/status :expired :mail/expired-at now)
            state (assoc-in state [:mail mail-id] expired)]
        (if (= :gift (:mail/kind message))
          (let [amount (get-in message [:mail/attachments 0 :amount])
                [_ wallet] (apply-transaction
                            (get-in state [:wallets (:mail/sender message)] (wallet))
                            #:tx{:id (str "gift-refund/" mail-id) :currency :free-gem
                                 :amount amount :kind :gift-refund :at now :ref mail-id})]
            [:ok expired (assoc-in state [:wallets (:mail/sender message)] wallet)])
          [:ok expired state])))))

(def queue-statuses #{:queued :matched :active :cancelled})
(def match-statuses #{:ready :active :declined :expired :complete})

(def party-invite-statuses #{:pending :accepted :declined :expired})

(defn invite-party
  "Create an expiring invitation. Party owners and moderators may invite;
   identity proof and delivery are host responsibilities."
  [state {:invite/keys [id party from to created-at expires-at] :as invite}]
  (let [group (get-in state [:groups party])
        role (get-in group [:group/members from])]
    (cond
      (contains? (:party-invites state) id)
      [:duplicate (get-in state [:party-invites id]) state]
      (or (nil? id) (nil? to) (not= :party (:group/kind group))
          (not (contains? #{:owner :moderator} role))
          (not (integer? created-at)) (not (integer? expires-at))
          (<= expires-at created-at)) [:error :invalid-party-invite state]
      (contains? (:group/members group) to) [:error :already-party-member state]
      (>= (count (:group/members group)) (:group/capacity group)) [:error :group-full state]
      (some #(blocked? state to %) (keys (:group/members group))) [:error :blocked state]
      :else (let [invite (assoc invite :invite/status :pending)]
              [:ok invite (assoc-in state [:party-invites id] invite)]))))

(defn answer-party-invite
  [state {:keys [invite-id player accept? at]}]
  (let [invite (get-in state [:party-invites invite-id])]
    (cond
      (nil? invite) [:error :invite-not-found state]
      (not= player (:invite/to invite)) [:error :not-invite-recipient state]
      (not= :pending (:invite/status invite)) [:duplicate invite state]
      (>= at (:invite/expires-at invite))
      (let [expired (assoc invite :invite/status :expired :invite/answered-at at)]
        [:error :invite-expired (assoc-in state [:party-invites invite-id] expired)])
      (not accept?)
      (let [declined (assoc invite :invite/status :declined :invite/answered-at at)]
        [:ok declined (assoc-in state [:party-invites invite-id] declined)])
      :else
      (let [[status reason-or-state joined-state]
            (join-group state (:invite/party invite) player :member)]
        (if (= :ok status)
          (let [accepted (assoc invite :invite/status :accepted :invite/answered-at at)]
            [:ok accepted (assoc-in reason-or-state [:party-invites invite-id] accepted)])
          [:error reason-or-state (or joined-state state)])))))

(defn match-penalty-active?
  [state player now]
  (> (get-in state [:match-penalties player :penalty/until] 0) now))

(defn- queue-players [entry]
  (vec (or (:queue/players entry) [(:queue/player entry)])))

(defn enqueue-match
  [state {:queue/keys [id player game mode region rating joined-at] :as entry}]
  (let [players (queue-players entry)
        existing (some #(when (and (some (set players) (queue-players %))
                                   (contains? #{:queued :matched} (:queue/status %))) %)
                       (vals (:match-queues state)))]
    (cond
      (contains? (:match-queues state) id) [:duplicate (get-in state [:match-queues id]) state]
      existing [:error :already-queued state]
      (some #(match-penalty-active? state % joined-at) players) [:error :match-penalty-active state]
      (or (nil? id) (nil? player) (nil? game) (nil? mode) (nil? region)
          (not (integer? rating)) (neg? rating) (not (integer? joined-at))
          (empty? players) (some nil? players) (not= (count players) (count (set players))))
      [:error :invalid-queue-entry state]
      :else
      (let [queued (assoc entry :queue/players players :queue/status :queued)]
        [:ok queued (assoc-in state [:match-queues id] queued)]))))

(defn enqueue-party-match
  "Snapshot a party into one queue unit. Only its owner can queue the party."
  [state {:queue/keys [party player] :as entry}]
  (let [group (get-in state [:groups party])]
    (cond
      (not= :party (:group/kind group)) [:error :party-not-found state]
      (not= :owner (get-in group [:group/members player])) [:error :not-party-leader state]
      :else (enqueue-match state (assoc entry :queue/players
                                        (vec (sort (keys (:group/members group)))))))))

(defn cancel-match-queue
  [state player cancelled-at]
  (if-let [entry (some #(when (and (= player (:queue/player %))
                                   (= :queued (:queue/status %))) %)
                       (vals (:match-queues state)))]
    (let [cancelled (assoc entry :queue/status :cancelled :queue/cancelled-at cancelled-at)]
      [:ok cancelled (assoc-in state [:match-queues (:queue/id entry)] cancelled)])
    [:duplicate state]))

(defn- compatible-queue? [a b rating-window]
  (and (= (:queue/game a) (:queue/game b))
       (= (:queue/mode a) (:queue/mode b))
       (= (:queue/region a) (:queue/region b))
       (<= (#?(:clj Math/abs :cljs js/Math.abs)
            (- (:queue/rating a) (:queue/rating b))) rating-window)))

(defn form-match
  "Pair the oldest queued player with the oldest compatible player. IDs,
   clocks and rating window are authoritative host inputs."
  [state {:keys [match-id now ready-until rating-window]
          :or {rating-window 200}}]
  (let [queued (->> (:match-queues state) vals
                    (filter #(= :queued (:queue/status %)))
                    (sort-by (juxt :queue/joined-at :queue/player)) vec)
        pair (some (fn [a]
                     (when-let [b (first (filter #(and (not= (:queue/id a) (:queue/id %))
                                                       (compatible-queue? a % rating-window))
                                                queued))]
                       [a b]))
                   queued)]
    (cond
      (contains? (:matches state) match-id) [:duplicate (get-in state [:matches match-id]) state]
      (or (nil? match-id) (not (integer? now)) (not (integer? ready-until))
          (<= ready-until now) (not (integer? rating-window)) (neg? rating-window))
      [:error :invalid-match state]
      (nil? pair) [:waiting state]
      :else
      (let [[a b] pair
            players (vec (concat (queue-players a) (queue-players b)))
            match #:match{:id match-id :game (:queue/game a) :mode (:queue/mode a)
                          :region (:queue/region a) :players players
                          :queues [(:queue/id a) (:queue/id b)] :accepted #{}
                          :status :ready :created-at now :ready-until ready-until}
            state (reduce (fn [s queue-id]
                            (assoc-in s [:match-queues queue-id :queue/status] :matched))
                          state (:match/queues match))]
        [:ok match (assoc-in state [:matches match-id] match)]))))

(defn answer-match
  [state {:keys [match-id player accept? at]}]
  (let [match (get-in state [:matches match-id])]
    (cond
      (nil? match) [:error :match-not-found state]
      (not= :ready (:match/status match)) [:duplicate match state]
      (not (some #{player} (:match/players match))) [:error :not-match-player state]
      (>= at (:match/ready-until match)) [:error :match-ready-expired state]
      (contains? (:match/accepted match) player) [:duplicate match state]
      (not accept?)
      (let [match (assoc match :match/status :declined :match/declined-by player
                         :match/resolved-at at)
            state (reduce (fn [s queue-id]
                            (let [entry (get-in s [:match-queues queue-id])]
                              (assoc-in s [:match-queues queue-id]
                                        (assoc entry :queue/status
                                               (if (some #{player} (queue-players entry)) :cancelled :queued)
                                               :queue/joined-at at))))
                          state (:match/queues match))]
        [:ok match (assoc-in state [:matches match-id] match)])
      :else
      (let [accepted (conj (:match/accepted match) player)
            active? (= (set (:match/players match)) accepted)
            match (cond-> (assoc match :match/accepted accepted)
                    active? (assoc :match/status :active :match/started-at at
                                   :match/connections (zipmap (:match/players match)
                                                              (repeat {:connection/status :connected}))))
            state (if active?
                    (reduce #(assoc-in %1 [:match-queues %2 :queue/status] :active)
                            state (:match/queues match))
                    state)]
        [:ok match (assoc-in state [:matches match-id] match)]))))

(defn expire-match
  [state match-id now]
  (let [match (get-in state [:matches match-id])]
    (cond
      (nil? match) [:error :match-not-found state]
      (not= :ready (:match/status match)) [:duplicate match state]
      (< now (:match/ready-until match)) [:error :match-not-expired state]
      :else
      (let [accepted (:match/accepted match)
            match (assoc match :match/status :expired :match/resolved-at now)
            state (reduce (fn [s queue-id]
                            (let [entry (get-in s [:match-queues queue-id])]
                              (assoc-in s [:match-queues queue-id]
                                        (assoc entry :queue/status
                                               (if (every? accepted (queue-players entry))
                                                 :queued :cancelled)
                                               :queue/joined-at now))))
                          state (:match/queues match))]
        [:ok match (assoc-in state [:matches match-id] match)]))))

(defn disconnect-match-player
  [state {:keys [match-id player at reconnect-until]}]
  (let [match (get-in state [:matches match-id])]
    (cond
      (not= :active (:match/status match)) [:error :match-not-active state]
      (not (some #{player} (:match/players match))) [:error :not-match-player state]
      (or (not (integer? at)) (not (integer? reconnect-until)) (<= reconnect-until at))
      [:error :invalid-reconnect-window state]
      (= :disconnected (get-in match [:match/connections player :connection/status]))
      [:duplicate match state]
      :else (let [match (assoc-in match [:match/connections player]
                                  {:connection/status :disconnected
                                   :connection/disconnected-at at
                                   :connection/reconnect-until reconnect-until})]
              [:ok match (assoc-in state [:matches match-id] match)]))))

(defn reconnect-match-player
  [state {:keys [match-id player at]}]
  (let [match (get-in state [:matches match-id])
        connection (get-in match [:match/connections player])]
    (cond
      (not= :active (:match/status match)) [:error :match-not-active state]
      (not= :disconnected (:connection/status connection)) [:duplicate match state]
      (>= at (:connection/reconnect-until connection)) [:error :reconnect-expired state]
      :else (let [match (assoc-in match [:match/connections player]
                                  {:connection/status :connected :connection/reconnected-at at})]
              [:ok match (assoc-in state [:matches match-id] match)]))))

(defn abandon-match-player
  "Resolve an expired disconnect or verified early leave and apply a bounded
   per-player queue cooldown. Replays are idempotent."
  [state {:keys [match-id player at penalty-until reason]}]
  (let [match (get-in state [:matches match-id])
        connection (get-in match [:match/connections player])]
    (cond
      (not= :active (:match/status match)) [:error :match-not-active state]
      (not (some #{player} (:match/players match))) [:error :not-match-player state]
      (= :abandoned (:connection/status connection)) [:duplicate match state]
      (or (not (integer? at)) (not (integer? penalty-until)) (<= penalty-until at))
      [:error :invalid-match-penalty state]
      (and (= reason :disconnect-timeout)
           (< at (:connection/reconnect-until connection))) [:error :reconnect-window-active state]
      :else (let [penalty #:penalty{:player player :match match-id :reason reason
                                    :at at :until penalty-until}
                  match (-> match
                            (assoc-in [:match/connections player]
                                      {:connection/status :abandoned :connection/abandoned-at at})
                            (update :match/abandoned (fnil conj #{}) player))]
              [:ok penalty (-> state
                               (assoc-in [:matches match-id] match)
                               (assoc-in [:match-penalties player] penalty))]))))

(defn product
  [{:product/keys [id currency price grants] :as p}]
  (when (and id (contains? currencies currency) (integer? price) (pos? price)
             (seq grants))
    p))

(def fiat-currencies #{:jpy :usd :eur})

(defn gem-pack
  "Validate a provider-neutral paid-gem pack. Fiat amounts use minor units;
   provider product/price IDs stay in the host adapter."
  [{:pack/keys [id gems fiat-currency fiat-amount] :as pack}]
  (when (and id (integer? gems) (pos? gems)
             (contains? fiat-currencies fiat-currency)
             (integer? fiat-amount) (pos? fiat-amount))
    pack))

(defn create-payment-intent
  "Reserve one immutable player/pack purchase. Creating the same intent ID is
   idempotent; payment-provider checkout creation remains a host concern."
  [state {:keys [intent-id player pack created-at]}]
  (cond
    (contains? (:payment-intents state) intent-id)
    [:duplicate (get-in state [:payment-intents intent-id]) state]
    (or (nil? intent-id) (nil? player) (nil? (gem-pack pack)))
    [:error :invalid-payment-intent state]
    :else
    (let [intent #:payment{:id intent-id :player player :pack pack
                           :status :pending :created-at created-at}]
      [:ok intent (assoc-in state [:payment-intents intent-id] intent)])))

(defn settle-payment
  "Credit paid gems exactly once after the host verifies provider authenticity,
   amount, currency, pack mapping, and successful state."
  [state {:keys [intent-id provider-ref verified? settled-at]}]
  (let [intent (get-in state [:payment-intents intent-id])]
    (cond
      (nil? intent) [:error :payment-intent-not-found state]
      (= :settled (:payment/status intent)) [:duplicate intent state]
      (not= :pending (:payment/status intent)) [:error :payment-not-pending state]
      (or (not verified?) (nil? provider-ref)) [:error :payment-unverified state]
      :else
      (let [player (:payment/player intent)
            gems (get-in intent [:payment/pack :pack/gems])
            tx #:tx{:id (str "payment/" intent-id) :currency :paid-gem
                    :amount gems :kind :payment :at settled-at :ref provider-ref}
            [status wallet] (apply-transaction (get-in state [:wallets player] (wallet)) tx)]
        (if (not= :ok status)
          [:error :payment-credit-failed state]
          (let [settled (assoc intent :payment/status :settled
                               :payment/provider-ref provider-ref
                               :payment/settled-at settled-at)]
            [:ok settled (-> state
                             (assoc-in [:wallets player] wallet)
                             (assoc-in [:payment-intents intent-id] settled))]))))))

(defn refund-payment
  "Reverse a settled paid-gem pack once after a verified provider refund. If
   gems were already spent, automatic refund is refused for host review."
  [state {:keys [refund-id intent-id provider-ref verified? refunded-at]}]
  (let [intent (get-in state [:payment-intents intent-id])]
    (cond
      (contains? (:refunds state) refund-id)
      [:duplicate (get-in state [:refunds refund-id]) state]
      (or (nil? refund-id) (nil? intent)) [:error :payment-intent-not-found state]
      (not= :settled (:payment/status intent)) [:error :payment-not-settled state]
      (or (not verified?) (nil? provider-ref)) [:error :refund-unverified state]
      :else
      (let [player (:payment/player intent)
            gems (get-in intent [:payment/pack :pack/gems])
            tx #:tx{:id (str "refund/" refund-id) :currency :paid-gem
                    :amount (- gems) :kind :payment-refund :at refunded-at :ref provider-ref}
            [status x] (apply-transaction (get-in state [:wallets player] (wallet)) tx)]
        (if (= status :error)
          [:error :refund-balance-spent state]
          (let [refund #:refund{:id refund-id :payment intent-id :player player
                                :gems gems :provider-ref provider-ref :at refunded-at}
                refunded (assoc intent :payment/status :refunded
                                 :payment/refunded-at refunded-at)]
            [:ok refund (-> state
                            (assoc-in [:wallets player] x)
                            (assoc-in [:payment-intents intent-id] refunded)
                            (assoc-in [:refunds refund-id] refund))]))))))

(defn purchase
  "Atomically debit a wallet and grant a catalog product. receipt-id is the
   idempotency key; payment providers remain outside this pure contract."
  [state {:keys [player receipt-id product purchased-at]}]
  (cond
    (contains? (:receipts state) receipt-id) [:duplicate (get-in state [:receipts receipt-id]) state]
    (nil? (game.social/product product)) [:error :invalid-product state]
    :else
    (let [w (get-in state [:wallets player] (wallet))
          inv (get-in state [:inventories player] (inventory))
          debit #:tx{:id receipt-id :currency (:product/currency product)
                     :amount (- (:product/price product)) :kind :purchase
                     :at purchased-at :product (:product/id product)}
          [status x & _] (apply-transaction w debit)]
      (if (not= status :ok)
        [:error x state]
        (let [inv' (reduce (fn [acc grant]
                             (if-let [e (:entitlement/id grant)]
                               (grant-entitlement acc e)
                               (second (grant-item acc grant))))
                           inv (:product/grants product))
              receipt {:receipt/id receipt-id :receipt/player player
                       :receipt/product (:product/id product)
                       :receipt/at purchased-at}
              state' (-> state
                         (assoc-in [:wallets player] x)
                         (assoc-in [:inventories player] inv')
                         (assoc-in [:receipts receipt-id] receipt))]
          [:ok receipt state'])))))

(defn royalties
  "Credits by lineage distance, dropping rounded-to-zero awards."
  ([amount ancestors] (royalties amount ancestors {:rate 0.1 :decay 0.5}))
  ([amount ancestors {:keys [rate decay] :or {rate 0.1 decay 0.5}}]
   (->> ancestors
        (map-indexed (fn [i ancestor]
                       [ancestor (long (#?(:clj Math/floor :cljs js/Math.floor)
                                         (* amount rate
                                            (#?(:clj Math/pow :cljs js/Math.pow) decay i))))]))
        (filterv (fn [[_ credit]] (pos? credit))))))

(defn leaderboard
  [{:board/keys [id game season order] :or {order :desc}}]
  {:board/id id :board/game game :board/season season :board/order order
   :board/entries {} :board/submissions #{}})

(defn submit-score
  "Idempotent best-score submission. Verification is an explicit prerequisite
   supplied by the authoritative game-specific verifier."
  [board {:score/keys [submission player value verified] :as score}]
  (cond
    (contains? (:board/submissions board) submission) [:duplicate board]
    (not verified) [:error :unverified board]
    (not (number? value)) [:error :invalid-score board]
    :else
    (let [old (get-in board [:board/entries player])
          better? (or (nil? old)
                      ((if (= :asc (:board/order board)) < >) value (:score/value old)))
          board' (cond-> (update board :board/submissions conj submission)
                   better? (assoc-in [:board/entries player] score))]
      [:ok board'])))

(defn standings [board]
  (let [cmp (if (= :asc (:board/order board)) identity -)]
    (->> (:board/entries board) vals (sort-by (comp cmp :score/value)) vec)))

(defn season
  "Create a portable season definition. Reward tiers are ordered inclusive
   rank ceilings, e.g. [{:through 1 :reward {:free-gem 100}} ...]."
  [{:season/keys [id starts-at ends-at reward-tiers] :as config}]
  (when (and id (integer? starts-at) (integer? ends-at) (< starts-at ends-at)
             (vector? reward-tiers)
             (every? (fn [{:keys [through reward]}]
                       (and (integer? through) (pos? through) (map? reward)))
                     reward-tiers)
             (apply < 0 (map :through reward-tiers)))
    config))

(defn season-status [season now]
  (cond (< now (:season/starts-at season)) :scheduled
        (< now (:season/ends-at season)) :active
        :else :closed))

(defn submit-season-score
  "Season-aware form of submit-score. The authoritative host supplies `now`;
   scheduled/closed seasons reject writes before the normal verified-score
   and best-score invariants run."
  [board season now score]
  (if (= :active (season-status season now))
    (submit-score board score)
    [:error :season-not-active board]))

(defn ranked-standings
  "Deterministic competition ranking. Equal values share rank; the next rank
   skips accordingly. at then player provide stable display order without
   changing tie rank."
  [board]
  (let [direction (if (= :asc (:board/order board)) identity -)
        sorted (sort-by (juxt (comp direction :score/value)
                              #(or (:score/at %) 0) :score/player)
                        (vals (:board/entries board)))]
    (loop [remaining sorted, index 1, previous ::none, previous-rank 0, out []]
      (if-let [entry (first remaining)]
        (let [value (:score/value entry)
              rank (if (= value previous) previous-rank index)]
          (recur (next remaining) (inc index) value rank
                 (conj out (assoc entry :score/rank rank))))
        out))))

(defn reward-for-rank [season rank]
  (some (fn [{:keys [through reward]}] (when (<= rank through) reward))
        (:season/reward-tiers season)))

(defn close-season
  "Freeze deterministic standings and reward assignments after the end time.
   The returned snapshot is pure data; hosts own durable payout idempotency."
  [board season now]
  (if (not= :closed (season-status season now))
    [:error :season-not-closed]
    (let [ranked (ranked-standings board)]
      [:ok {:season/id (:season/id season)
            :season/closed-at now
            :season/standings ranked
            :season/rewards (into {}
                                  (keep (fn [entry]
                                          (when-let [reward (reward-for-rank season (:score/rank entry))]
                                            [(:score/player entry) reward])))
                                  ranked)}])))

;; ── guild events and guild competition ─────────────────────────────────────

(defn guild-event
  "Validate a portable cooperative guild event. Reward tiers are inclusive
   competition-rank ceilings and reward verified contributors, not players who
   merely join a guild immediately before closure."
  [{:event/keys [id game starts-at ends-at target reward-tiers] :as config}]
  (when (and id game (integer? starts-at) (integer? ends-at) (< starts-at ends-at)
             (integer? target) (pos? target) (vector? reward-tiers)
             (every? (fn [{:keys [through free-gem-per-contributor]}]
                       (and (integer? through) (pos? through)
                            (integer? free-gem-per-contributor)
                            (not (neg? free-gem-per-contributor))))
                     reward-tiers)
             (apply < 0 (map :through reward-tiers)))
    config))

(defn guild-event-status [event now]
  (cond (< now (:event/starts-at event)) :scheduled
        (< now (:event/ends-at event)) :active
        :else :closed))

(defn guild-event-state [event]
  {:event/id (:event/id event)
   :event/game (:event/game event)
   :event/contributions {}
   :event/submissions #{}})

(defn contribute-guild-event
  "Record one verified positive contribution. The host verifies gameplay and
   current guild membership; submission IDs make retries idempotent."
  [state event now {:contribution/keys [submission guild player amount
                                        verified member-verified at]}]
  (cond
    (not= :active (guild-event-status event now)) [:error :guild-event-not-active state]
    (or (nil? submission) (nil? guild) (nil? player)
        (not (integer? amount)) (not (pos? amount))) [:error :invalid-contribution state]
    (not verified) [:error :contribution-unverified state]
    (not member-verified) [:error :guild-membership-unverified state]
    (contains? (:event/submissions state) submission) [:duplicate state]
    :else
    [:ok (-> state
             (update :event/submissions conj submission)
             (update-in [:event/contributions guild :guild/total] (fnil + 0) amount)
             (assoc-in [:event/contributions guild :guild/id] guild)
             (update-in [:event/contributions guild :guild/players player :player/total]
                        (fnil + 0) amount)
             (assoc-in [:event/contributions guild :guild/players player :player/last-at]
                       (or at now)))]))

(defn guild-event-standings
  "Competition ranking by total contribution, with guild ID as deterministic
   display tie-break without changing tied ranks."
  [state]
  (let [sorted (sort-by (juxt (comp - :guild/total) :guild/id)
                        (vals (:event/contributions state)))]
    (loop [remaining sorted, index 1, previous ::none, previous-rank 0, out []]
      (if-let [entry (first remaining)]
        (let [value (:guild/total entry)
              rank (if (= value previous) previous-rank index)]
          (recur (next remaining) (inc index) value rank
                 (conj out (assoc entry :guild/rank rank))))
        out))))

(defn- guild-reward-for-rank [event rank]
  (some #(when (<= rank (:through %)) %) (:event/reward-tiers event)))

(defn close-guild-event
  "Freeze standings and deterministic contributor rewards after event end.
   The host durably pays returned player rewards using event+player IDs."
  [state event now]
  (if (not= :closed (guild-event-status event now))
    [:error :guild-event-not-closed]
    (let [standings (guild-event-standings state)
          rewards (into {}
                        (mapcat (fn [{:guild/keys [id rank players]}]
                                  (let [amount (:free-gem-per-contributor
                                                (guild-reward-for-rank event rank))]
                                    (when (pos? (or amount 0))
                                      (map (fn [player]
                                             [player {:free-gem amount :guild id :rank rank}])
                                           (keys players)))))
                                standings))]
      [:ok {:event/id (:event/id event)
            :event/closed-at now
            :event/standings standings
            :event/rewards rewards}])))

;; ── portable platform HUD projection ────────────────────────────────────────

(defn- currency-key [currency]
  (cond (keyword? currency) currency
        (string? currency) (keyword currency)
        :else currency))

(defn platform-hud-model
  "Project a host snapshot into one stable, portable HUD model. Hosts may use
   D1/HTTP, native storage, or an in-memory state; renderers consume this shape
   instead of learning a provider's wire rows. Unknown fields are ignored so
   old clients can read newer snapshots."
  [{:keys [did profile achievements activity balances transactions inventory receipts products
           gem-packs payments daily-reward server-day
           economy-debts economy-holds
           saves missions battle-pass battle-pass-tiers battle-pass-claims
           subscription-plans subscriptions
           mail notifications match-queue matches guild-events guild-standings
           friend-requests friendships blocks groups group-members
           party-invites match-penalty match-connections]
    :as _snapshot}]
  (let [wallet-balances (reduce (fn [m {:keys [currency balance]}]
                                  (assoc m (currency-key currency) (or balance 0)))
                                (zipmap currencies (repeat 0)) balances)
        owned-items (->> inventory
                         (map #(update % :entitlement
                                       (fn [value] (or (true? value) (= 1 value)))))
                         (filter #(or (pos? (or (:quantity %) 0))
                                      (true? (:entitlement %))))
                         (sort-by :item) vec)
        friend-ids (->> friendships
                        (keep (fn [{:keys [a b]}]
                                (cond (= did a) b (= did b) a)))
                        distinct sort vec)
        pending-in (->> friend-requests
                        (filter #(and (= did (:recipient %)) (= "pending" (:status %))))
                        (sort-by :created_at) vec)
        pending-out (->> friend-requests
                         (filter #(and (= did (:sender %)) (= "pending" (:status %))))
                         (sort-by :created_at) vec)
        inbox (->> mail
                   (filter #(= "pending" (:status %)))
                   (sort-by :created_at >) vec)
        notification-inbox (->> notifications
                                (remove :dismissed_at)
                                (sort-by (fn [notification]
                                           [(if (:read_at notification) 1 0)
                                            (- (or (:created_at notification) 0))
                                            (str (:id notification))]))
                                vec)
        product-models (->> products
                            (map (fn [{:keys [currency price] :as p}]
                                   (let [currency (currency-key currency)]
                                     (assoc p :currency currency
                                            :affordable? (>= (get wallet-balances currency 0)
                                                             (or price 0))))))
                            (sort-by :id) vec)]
    {:hud/version 1
     :player/did did
     :profile/data profile
     :profile/achievements (vec (sort-by #(or (:unlocked_at %) (:achievement/unlocked-at %) 0)
                                         > achievements))
     :profile/activity (vec (sort-by :at > activity))
     :wallet/balances wallet-balances
     :wallet/transactions (vec transactions)
     :wallet/daily-reward daily-reward
     :wallet/server-day server-day
     :wallet/daily-claimable? (not= server-day (:day daily-reward))
     :wallet/debts (vec economy-debts)
     :wallet/holds (vec economy-holds)
     :wallet/restricted? (boolean (seq economy-holds))
     :inventory/items owned-items
     :store/products product-models
     :store/receipts (vec receipts)
     :store/gem-packs (vec gem-packs)
     :store/payments (vec payments)
     :saves/items (vec (sort-by :game saves))
     :missions/items (vec (sort-by (juxt :starts_at :id) missions))
     :battle-pass/data battle-pass
     :battle-pass/tiers (vec (sort-by :level battle-pass-tiers))
     :battle-pass/claims (set (map (juxt :level :track) battle-pass-claims))
     :subscription/plans (vec (sort-by :id subscription-plans))
     :subscription/items (vec (sort-by (juxt :plan :started_at) subscriptions))
     :mail/inbox inbox
     :notifications/items notification-inbox
     :notifications/unread (count (remove :read_at notification-inbox))
     :matchmaking/queue match-queue
     :matchmaking/matches (vec matches)
     :matchmaking/penalty match-penalty
     :matchmaking/connections (vec match-connections)
     :guild-events/items (vec guild-events)
     :guild-events/standings (->> guild-standings
                                  (group-by :event_id)
                                  (reduce-kv (fn [m event-id rows]
                                               (assoc m event-id (vec (sort-by :rank rows))))
                                             {}))
     :social/friends friend-ids
     :social/pending-in pending-in
     :social/pending-out pending-out
     :social/blocks (vec blocks)
     :social/groups (vec groups)
     :social/party-invites (vec party-invites)
     :social/group-members (->> group-members
                                (group-by :group_id)
                                (reduce-kv (fn [m group-id members]
                                             (assoc m group-id
                                                    (vec (sort-by :joined_at members))))
                                           {}))
     :hud/tabs [{:tab/id :notifications
                 :tab/count (count (remove :read_at notification-inbox))}
                {:tab/id :profile
                 :tab/count (count (filter #(or (:unlocked_at %)
                                                (:achievement/unlocked-at %)) achievements))}
                {:tab/id :wallet :tab/count (count transactions)}
                {:tab/id :inventory :tab/count (count owned-items)}
                {:tab/id :store :tab/count (+ (count product-models) (count gem-packs))}
                {:tab/id :saves :tab/count (count saves)}
                {:tab/id :missions :tab/count (count (remove :claimed_at missions))}
                {:tab/id :battle-pass :tab/count (if battle-pass 1 0)}
                {:tab/id :membership :tab/count (count subscriptions)}
                {:tab/id :mail :tab/count (count inbox)}
                {:tab/id :match :tab/count (+ (if match-queue 1 0) (count matches)
                                              (count (filter #(= "pending" (:status %))
                                                             party-invites)))}
                {:tab/id :guild-events :tab/count (count guild-events)}
                {:tab/id :friends :tab/count (+ (count friend-ids) (count pending-in))}
                {:tab/id :groups :tab/count (count groups)}]}))

(defn admit-chat
  "Validate one player message against room policy and recipient controls.
   Content classification/moderation supplies :message/moderation externally."
  [state {:message/keys [id from to text moderation] :as message}
          {:room/keys [max-length] :or {max-length 280}}]
  (let [recipient (get-in state [:profiles to])]
    (cond
      (or (nil? id) (nil? from) (not (string? text)) (empty? text)) [:error :invalid-message state]
      (> (count text) max-length) [:error :message-too-long state]
      (contains? (:player/blocked recipient) from) [:error :blocked state]
      (= moderation :rejected) [:error :moderation-rejected state]
      :else [:ok message (update state :chat conj message)])))

(defn admit-room-message
  "Room-aware chat admission. The host supplies moderation classification,
   persistence and rate-limit decisions; this transition owns membership,
   block, length, duplicate and bounded-history invariants."
  [state {:message/keys [id room from text moderation] :as message}]
  (let [r (get-in state [:rooms room])
        members (:room/members r)]
    (cond
      (or (nil? id) (nil? r) (nil? from) (not (string? text)) (empty? text))
      [:error :invalid-message state]
      (not (contains? members from)) [:error :not-room-member state]
      (some #(blocked? state from %) (disj members from)) [:error :blocked state]
      (> (count text) (:room/max-length r)) [:error :message-too-long state]
      (= moderation :rejected) [:error :moderation-rejected state]
      (some #(= id (:message/id %)) (:room/messages r)) [:duplicate state]
      :else
      (let [messages (->> (conj (:room/messages r) message)
                          (take-last (:room/history-limit r)) vec)]
        [:ok message (assoc-in state [:rooms room :room/messages] messages)]))))
