(ns marketplace.fulfillment
  "Warehouse fulfillment — pick, pack, hand over — and the first place in
  this stack where a ROBOT does the physical work.

  ## What `kotoba.robotics` is, and what it is not

  The fleet declares `:robotics true` on hundreds of blueprints, but the
  library itself is explicit: *policy, not control — it does not drive
  motors.* It models a mission, an action with a safety class, a
  safety-stop and a telemetry proof, and gives a governor the records it
  needs to refuse unsafe actuation **before it reaches hardware**.

  This namespace is the warehouse-side composition of that contract. It
  turns an order's sub-order into concrete pick/pack/handover tasks,
  proposes the robot actions each task needs, and answers the two
  questions a warehouse governor must ask:

    1. Is this action even about something in the order?
    2. Is this action's safety class dispatchable without a human?

  Nothing here talks to a robot. `dispatchable-actions` returns the
  actions a driver *may* be handed; handing them over is the operator's
  integration, deliberately outside this library — the same boundary
  `marketplace.settlement` draws around moving money.

  Pure: no clock, no network, no randomness."
  (:require [kotoba.lang.text :as str]
            [kotoba.okaimono :as ok]
            [kotoba.robotics :as robo]))

;; ───────────────────────────── tasks ─────────────────────────────

(def task-kinds
  "The three physical steps between a confirmed sub-order and a courier.
  Deliberately not more: anything finer is a robot's internal motion
  planning, which this contract does not model."
  #{:pick :pack :handover})

(def task-statuses
  #{:planned :in-progress :done :halted})

(def task-transitions
  "Explicit table, same style as `kotoba.okaimono/transitions`. A halted
  task is terminal here — recovering from a safety stop means planning a
  NEW task, not silently resuming the one a robot was halted mid-way
  through, because the physical state after a stop is unknown."
  {:planned     #{:in-progress :halted}
   :in-progress #{:done :halted}
   :done        #{}
   :halted      #{}})

(defn task-id [order-id seller kind]
  (str "ff." order-id "." seller "." (name kind)))

(defn task
  "Build a fulfillment task for one seller's sub-order."
  [{:keys [order-id seller kind lines station robot]}]
  (when (contains? task-kinds kind)
    {:task/id      (task-id order-id seller kind)
     :task/order   order-id
     :task/seller  seller
     :task/kind    kind
     :task/lines   (vec lines)
     :task/station station
     :task/robot   robot
     :task/status  :planned}))

(defn plan-tasks
  "Plan the full pick -> pack -> handover sequence for ONE seller's
  sub-order. Lines come from the `okaimono` sub-order itself, so a task
  can never reference an item the buyer did not order."
  [order-id sub-order & {:keys [station robot]}]
  (let [seller (:okaimono/store sub-order)
        lines  (:okaimono/lines sub-order)]
    (mapv #(task {:order-id order-id :seller seller :kind %
                  :lines lines :station station :robot robot})
          [:pick :pack :handover])))

(defn advance-task
  "Advance a task when the transition table allows it; nil otherwise."
  [t to]
  (when (contains? (get task-transitions (:task/status t) #{}) to)
    (assoc t :task/status to)))

;; ───────────────────────── the over-pick guard ─────────────────────────

(defn- ordered-qty
  "How many of `sku` the sub-order actually contains."
  [sub-order sku]
  (->> (:okaimono/lines sub-order)
       (filter #(= sku (:line/sku %)))
       (map :line/qty)
       (reduce + 0)))

(defn pick-errors
  "Errors in a proposed pick against the sub-order it claims to fulfil.

  This is the characteristic warehouse failure, and it is a QUANTITY
  question, not a robotics one: picking an SKU the buyer never ordered,
  or picking more of one than they ordered. A robot that is mechanically
  perfect will still ship the wrong box if nothing checks this, so it is
  checked here — against the order — rather than being left to the
  robot's own confidence in its barcode read.

  `picks` is `[{:sku .. :qty ..} ..]`.

  Quantities are AGGREGATED per SKU before comparison. Checking each
  entry on its own would let two passes of 2 and 1 against an order for
  2 both pass individually while three units leave the shelf — and a
  second pick pass is the normal way a short pick gets topped up, so
  that is not a hypothetical."
  [sub-order picks]
  (let [totals (reduce (fn [m {:keys [sku qty]}]
                         (update m sku (fnil + 0) (if (number? qty) qty 0)))
                       {} picks)]
    (vec
     (concat
      (for [[sku _] (sort totals)
            :when (zero? (ordered-qty sub-order sku))]
        {:fulfillment.error/code :sku-not-in-order
         :fulfillment.error/detail (str sku " は注文に含まれていない")})
      (for [[sku got] (sort totals)
            :let [want (ordered-qty sub-order sku)]
            :when (and (pos? want) (> got want))]
        {:fulfillment.error/code :over-pick
         :fulfillment.error/detail (str sku " 注文 " want " に対し合計 " got " をピックしようとしている")})
      (for [{:keys [sku qty]} picks
            :when (not (and (integer? qty) (pos? qty)))]
        {:fulfillment.error/code :invalid-pick-qty
         :fulfillment.error/detail (str sku)})))))

(defn short-picks
  "SKUs picked in fewer units than ordered. NOT an error — a short pick
  is a real, ordinary warehouse state (stock discrepancy) that a human
  must see rather than a rule the system should refuse. Reported so the
  actor can escalate it instead of silently shipping an incomplete
  parcel."
  [sub-order picks]
  (let [by-sku (reduce (fn [m {:keys [sku qty]}] (update m sku (fnil + 0) qty)) {} picks)]
    (vec
     (for [l (:okaimono/lines sub-order)
           :let [want (:line/qty l)
                 got  (get by-sku (:line/sku l) 0)]
           :when (< got want)]
       {:sku (:line/sku l) :ordered want :picked got}))))

;; ───────────────────────── robot actions ─────────────────────────

(def ^:private kind->action
  "Which robot action kind each fulfillment step needs, and how
  dangerous it is by default.

  `:handover` is `:high` because it is the step where a robot moves a
  parcel into a space a human courier occupies. Everything a human
  shares floor space with is a sign-off class in
  `kotoba.robotics/human-sign-off-classes`, which is what makes that
  choice load-bearing rather than decorative."
  {:pick     {:kind :grasp :safety :medium}
   :pack     {:kind :actuate :safety :low}
   :handover {:kind :move :safety :high}})

(defn mission-for
  "One bounded robot mission per task. `kotoba.robotics/mission` states
  the rule this follows: 1 mission = 1 bounded operation, and a durable
  outer loop repeats missions rather than a mission looping internally."
  [t]
  (robo/mission (str "m." (:task/id t))
                (:task/robot t)
                (str (name (:task/kind t)) " for " (:task/seller t))
                :boundaries (:task/station t)
                :max-steps (max 1 (count (:task/lines t)))))

(defn actions-for
  "The robot actions a task needs, as `kotoba.robotics` records.

  Every action carries the payload the operator's driver would need
  (`:params`), but this function does not dispatch anything — see the
  namespace docstring."
  [t]
  (let [{:keys [kind safety]} (get kind->action (:task/kind t))
        mid (str "m." (:task/id t))]
    (mapv (fn [i l]
            (robo/action (str (:task/id t) ".a" i) mid kind safety
                         :params {:sku (:line/sku l)
                                  :qty (:line/qty l)
                                  :station (:task/station t)}))
          (range)
          (:task/lines t))))

(defn gate-actions
  "Gate every action of a task against the safety classes this operator
  permits, delegating wholly to `kotoba.robotics/gate`.

  Returns `{:permitted [..] :needs-sign-off [..] :denied [..]}`.

  Note `:needs-sign-off` is kept SEPARATE from `:permitted`.
  `kotoba.robotics/action-permitted?` is explicit that a sign-off-class
  action is not permitted outright, and collapsing the two here would
  quietly undo that — a `:handover` would go to a driver with no human
  ever having looked."
  [t allowed-safety-classes]
  (reduce (fn [acc a]
            (let [d (robo/gate a allowed-safety-classes)]
              (case (:gate/decision d)
                :permit          (update acc :permitted conj a)
                :require-sign-off (update acc :needs-sign-off conj a)
                (update acc :denied conj (assoc a :gate/reason (:gate/reason d))))))
          {:permitted [] :needs-sign-off [] :denied []}
          (actions-for t)))

(defn dispatchable-actions
  "The actions an operator's driver may be handed right now: gated
  `:permit` only. A task with any denied action yields NOTHING — a
  partially-executed physical task is worse than an unstarted one,
  because the warehouse then does not know where the goods are."
  [t allowed-safety-classes]
  (let [{:keys [permitted denied]} (gate-actions t allowed-safety-classes)]
    (when (empty? denied) permitted)))

(defn halt
  "A safety stop for a task's mission. Delegates the reason vocabulary to
  `kotoba.robotics/safety-stop`, which returns nil for an unknown
  reason — so an unrecognised stop cause cannot be recorded as if it
  were understood."
  [t reason & {:keys [source detail]}]
  (when-let [s (robo/safety-stop (str "m." (:task/id t)) reason
                                 :source source :detail detail)]
    {:halt/task (:task/id t)
     :halt/stop s
     :halt/task-after (advance-task t :halted)}))

(defn proof
  "A telemetry proof linking a robot sensor reading to the audit ledger."
  [t sensor reading & {:keys [timestamp provenance]}]
  (robo/telemetry-proof (str "m." (:task/id t)) sensor reading
                        :timestamp timestamp :provenance provenance))

;; ───────────────────────── readiness ─────────────────────────

(defn ready-for-handover?
  "Can this seller's parcel go to a courier? Requires the pack task done
  AND the sub-order in `kotoba.okaimono`'s own `:packed` state.

  Two sources must agree. The warehouse's view (`:pack` task done) and
  the order's view (`okaimono` says `:packed`) are maintained by
  different actors, and shipping on either one alone is how a parcel
  leaves before it was actually packed."
  [tasks sub-order]
  (boolean
   (and (some #(and (= :pack (:task/kind %)) (= :done (:task/status %))) tasks)
        (ok/dispatchable? sub-order))))

(defn task-errors [t]
  (vec
   (concat
    (when-not (contains? task-kinds (:task/kind t))
      [{:fulfillment.error/code :invalid-task-kind}])
    (when-not (contains? task-statuses (:task/status t))
      [{:fulfillment.error/code :invalid-task-status}])
    (when (empty? (:task/lines t))
      [{:fulfillment.error/code :empty-task}])
    (when (str/blank? (str (:task/seller t)))
      [{:fulfillment.error/code :missing-seller}])
    (when (str/blank? (str (:task/robot t)))
      [{:fulfillment.error/code :missing-robot
        :fulfillment.error/detail "作業を行うロボットが特定できないタスクは計画できない"}]))))
