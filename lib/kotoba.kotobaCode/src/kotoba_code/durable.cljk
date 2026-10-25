(ns kotoba-code.durable
  "Durable outer-loop state as EDN/datoms.

  The langgraph agent remains a bounded inner run. This namespace models the
  host-owned supervisor facts around it: loop, tick, lease, budget, event, and
  governor decisions. It is pure `.cljc`; a Datomic/kotoba backend is injected as
  a langchain.db-compatible `:db-api` map by hosts that persist it.")

(def loop-schema
  {:agent.loop/id       {:db/unique :db.unique/identity}
   :agent.loop/status   {}
   :agent.loop/tick-seq {}
   :agent.loop/budget   {}
   :agent.loop/session  {}})

(def tick-schema
  {:agent.tick/id     {:db/unique :db.unique/identity}
   :agent.tick/loop   {}
   :agent.tick/seq    {}
   :agent.tick/status {}
   :agent.tick/usage  {}
   :agent.tick/at-ms  {}})

(def lease-schema
  {:agent.lease/loop       {:db/unique :db.unique/identity}
   :agent.lease/owner      {}
   :agent.lease/expires-at {}})

(def event-schema
  {:agent.event/id      {:db/unique :db.unique/identity}
   :agent.event/loop    {}
   :agent.event/tick    {}
   :agent.event/type    {}
   :agent.event/payload {}})

(def governor-schema
  {:agent.governor/id       {:db/unique :db.unique/identity}
   :agent.governor/loop     {}
   :agent.governor/tick     {}
   :agent.governor/decision {}
   :agent.governor/reason   {}})

(def schema
  (merge loop-schema tick-schema lease-schema event-schema governor-schema))

(def default-budget
  {:tokens 12000
   :tool-calls 40
   :rounds 1})

(defn new-loop
  ([id] (new-loop id {}))
  ([id {:keys [session budget status]}]
   {:agent.loop/id id
    :agent.loop/session (or session id)
    :agent.loop/status (or status :active)
    :agent.loop/tick-seq 0
    :agent.loop/budget (merge default-budget budget)}))

(defn next-tick [loop-state now-ms]
  (let [seq* (inc (or (:agent.loop/tick-seq loop-state) 0))]
    {:agent.tick/id (str (:agent.loop/id loop-state) "/" seq*)
     :agent.tick/loop (:agent.loop/id loop-state)
     :agent.tick/seq seq*
     :agent.tick/status :running
     :agent.tick/at-ms now-ms}))

(defn acquire-lease [loop-state owner now-ms ttl-ms]
  {:agent.lease/loop (:agent.loop/id loop-state)
   :agent.lease/owner owner
   :agent.lease/expires-at (+ now-ms ttl-ms)})

(defn release-lease [loop-state owner now-ms]
  {:agent.lease/loop (:agent.loop/id loop-state)
   :agent.lease/owner owner
   :agent.lease/expires-at now-ms})

(defn lease-valid? [lease now-ms]
  (boolean (and (:agent.lease/expires-at lease)
                (< now-ms (:agent.lease/expires-at lease)))))

(defn stale-lease? [lease now-ms]
  (not (lease-valid? lease now-ms)))

(defn subtract-budget [budget usage]
  (reduce-kv (fn [m k v]
               (update m k (fnil - 0) v))
             budget
             usage))

(defn apply-tick [loop-state tick usage status]
  (-> loop-state
      (assoc :agent.loop/tick-seq (:agent.tick/seq tick))
      (update :agent.loop/budget subtract-budget usage)
      (assoc :agent.loop/status
             (if (= status :done) :active (:agent.loop/status loop-state)))))

(defn event [loop-state tick type payload]
  {:agent.event/id (str (:agent.loop/id loop-state) "/" (:agent.tick/seq tick) "/" (name type))
   :agent.event/loop (:agent.loop/id loop-state)
   :agent.event/tick (:agent.tick/id tick)
   :agent.event/type type
   :agent.event/payload payload})

(defn governor-decision [loop-state]
  (let [budget (:agent.loop/budget loop-state)]
    (cond
      (= :stopped (:agent.loop/status loop-state))
      {:agent.governor/decision :stop :agent.governor/reason :status-stopped}

      (= :interrupted (:agent.loop/status loop-state))
      {:agent.governor/decision :require-human :agent.governor/reason :interrupted}

      (some (fn [k] (<= (get budget k 0) 0)) [:tokens :tool-calls :rounds])
      {:agent.governor/decision :hold :agent.governor/reason :budget-exhausted}

      :else
      {:agent.governor/decision :continue :agent.governor/reason :ok})))

(defn governor-event [loop-state tick]
  (merge {:agent.governor/id (str (:agent.loop/id loop-state) "/" (:agent.tick/seq tick) "/governor")
          :agent.governor/loop (:agent.loop/id loop-state)
          :agent.governor/tick (:agent.tick/id tick)}
         (governor-decision loop-state)))

(defn tx-data
  "EDN datoms/maps for one durable supervisor tick."
  [{:keys [loop tick lease events governor]}]
  (vec (concat [loop tick]
               (when lease [lease])
               events
               (when governor [governor]))))

(defn persist! [db-api conn tx]
  ((:transact! db-api) conn (tx-data tx)))

(defn supervisor-step
  "Builds durable facts for one host-owned outer-loop tick.

  `run-result` is host-produced EDN:
    {:status :done|:interrupted|:error
     :usage {:tokens n :tool-calls n :rounds n}
     :events [{:type kw :payload edn} ...]}

  Returns {:loop :tick :lease :events :governor :decision :tx-data}."
  [loop-state {:keys [now-ms owner ttl-ms run-result]
               :or {ttl-ms 60000 run-result {}}}]
  (let [tick (next-tick loop-state now-ms)
        lease (release-lease loop-state owner now-ms)
        usage (merge {:tokens 0 :tool-calls 0 :rounds 0} (:usage run-result))
        status (or (:status run-result) :done)
        loop' (cond-> (apply-tick loop-state tick usage status)
                (= status :interrupted) (assoc :agent.loop/status :interrupted)
                (= status :error) (assoc :agent.loop/status :interrupted))
        events (mapv (fn [idx {:keys [type payload]}]
                       (update (event loop' tick (or type :observation) payload)
                               :agent.event/id str "/" idx))
                     (range)
                     (:events run-result))
        tick' (assoc tick :agent.tick/status status :agent.tick/usage usage)
        gov (governor-event loop' tick')
        tx {:loop loop' :tick tick' :lease lease :events events :governor gov}]
    (assoc tx
           :decision (:agent.governor/decision gov)
           :tx-data (tx-data tx))))

(defn lease-claim-step
  "Builds durable facts for a pre-run lease claim.

  This is a zero-usage tick that reserves the loop for `owner` before the host
  starts a model/tool run. It makes multi-worker terminal supervisors converge
  on the latest lease before doing expensive or mutating work."
  [loop-state {:keys [now-ms owner ttl-ms task]
               :or {ttl-ms 60000}}]
  (let [tick (next-tick loop-state now-ms)
        lease (acquire-lease loop-state owner now-ms ttl-ms)
        loop' (assoc loop-state :agent.loop/tick-seq (:agent.tick/seq tick))
        tick' (assoc tick
                     :agent.tick/status :lease-claimed
                     :agent.tick/usage {:tokens 0 :tool-calls 0 :rounds 0})
        events [(update (event loop' tick' :lease
                               {:owner owner
                                :expires-at (:agent.lease/expires-at lease)
                                :task task})
                        :agent.event/id str "/0")]
        gov (governor-event loop' tick')
        tx {:loop loop' :tick tick' :lease lease :events events :governor gov}]
    (assoc tx
           :decision (:agent.governor/decision gov)
           :tx-data (tx-data tx))))

(defn control-step
  "Builds durable facts for an operator control action.

  `action` is one of :interrupt, :resume, :stop. It creates a zero-usage tick and
  a control event so terminal operator actions are auditable in the same log."
  [loop-state {:keys [now-ms owner ttl-ms action reason]
               :or {ttl-ms 60000 action :interrupt}}]
  (let [tick (next-tick loop-state now-ms)
        lease (release-lease loop-state owner now-ms)
        budget-exhausted? (some (fn [k] (<= (get (:agent.loop/budget loop-state) k 0) 0))
                                [:tokens :tool-calls :rounds])
        loop-status (case action
                      :resume :active
                      :stop :stopped
                      :interrupt :interrupted
                      :interrupted)
        tick-status (case action
                      :resume :resumed
                      :stop :stopped
                      :interrupt :interrupted
                      :interrupted)
        loop' (-> loop-state
                  (assoc :agent.loop/tick-seq (:agent.tick/seq tick))
                  (assoc :agent.loop/status loop-status))
        tick' (assoc tick
                     :agent.tick/status tick-status
                     :agent.tick/usage {:tokens 0 :tool-calls 0 :rounds 0})
        effective? (not (and (= action :resume) budget-exhausted?))
        payload (cond-> {:action action :reason reason :effective? effective?}
                  (and (= action :resume) budget-exhausted?)
                  (assoc :blocked-by :budget-exhausted))
        events [(update (event loop' tick' :control payload)
                        :agent.event/id str "/0")]
        gov (governor-event loop' tick')
        tx {:loop loop' :tick tick' :lease lease :events events :governor gov}]
    (assoc tx
           :decision (:agent.governor/decision gov)
           :tx-data (tx-data tx))))

(defn refusal-step
  "Builds durable facts for a task refused by the current supervisor state.

  The loop status is preserved, but the tick sequence advances and a refusal
  event records why no model/tool run was started."
  [loop-state {:keys [now-ms owner ttl-ms reason task]
               :or {ttl-ms 60000 reason :inactive-loop}}]
  (let [tick (next-tick loop-state now-ms)
        lease (release-lease loop-state owner now-ms)
        loop' (assoc loop-state :agent.loop/tick-seq (:agent.tick/seq tick))
        tick' (assoc tick
                     :agent.tick/status :refused
                     :agent.tick/usage {:tokens 0 :tool-calls 0 :rounds 0})
        events [(update (event loop' tick' :refusal
                               {:reason reason
                                :status (:agent.loop/status loop-state)
                                :task task})
                        :agent.event/id str "/0")]
        gov (governor-event loop' tick')
        tx {:loop loop' :tick tick' :lease lease :events events :governor gov}]
    (assoc tx
           :decision (:agent.governor/decision gov)
           :tx-data (tx-data tx))))

(defn reset-budget-step
  "Builds durable facts for an operator budget reset.

  This records an auditable control tick, replaces the durable loop budget, and
  returns the loop to active so work can continue after a governor hold."
  [loop-state {:keys [now-ms owner ttl-ms budget reason]
               :or {ttl-ms 60000 budget default-budget}}]
  (let [tick (next-tick loop-state now-ms)
        lease (release-lease loop-state owner now-ms)
        budget' (merge default-budget budget)
        loop' (-> loop-state
                  (assoc :agent.loop/tick-seq (:agent.tick/seq tick))
                  (assoc :agent.loop/status :active)
                  (assoc :agent.loop/budget budget'))
        tick' (assoc tick
                     :agent.tick/status :reset-budget
                     :agent.tick/usage {:tokens 0 :tool-calls 0 :rounds 0})
        events [(update (event loop' tick' :control {:action :reset-budget
                                                     :reason reason
                                                     :effective? true
                                                     :budget budget'})
                        :agent.event/id str "/0")]
        gov (governor-event loop' tick')
        tx {:loop loop' :tick tick' :lease lease :events events :governor gov}]
    (assoc tx
           :decision (:agent.governor/decision gov)
           :tx-data (tx-data tx))))
