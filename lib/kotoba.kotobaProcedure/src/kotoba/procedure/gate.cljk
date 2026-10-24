(ns kotoba.procedure.gate
  "A multi-step external procedure (KYC resubmission, corporate-account
  setup, contract renewal...) as pure state transitions over an
  `IProcedureStore` (see `kotoba.procedure.store`).

  This is a different shape from `kotoba.issue.gate`'s single
  propose->approve/reject/request-changes->merge gate: a procedure has
  several ordered steps, each owned by whoever's turn it is
  (:self/:counterparty/:agent), and a deadline the whole procedure can blow
  past without anyone approving or rejecting anything. `open!` starts one,
  `advance-step!` marks the current step done (auto-completing the
  procedure when every step is), `block!`/`cancel!`/`expire!` are the other
  ways a procedure can stop moving, and `note!` appends context without
  changing state. `next-action`/`expired?` are pure predicates for a runner
  to ask 'what, if anything, needs to happen next' without touching the
  store.

  Prompted by a real gap: tracking a Wise 'log in within 7 days to finish
  corporate account setup or the transfer is refunded' email had nowhere to
  live except a hand-written ledger line -- no type captured the deadline
  or whose turn it was."
  (:require [kotoba.procedure.store :as store]))

(def procedure-states #{:open :blocked :done :cancelled :expired})
(def terminal-states #{:done :cancelled :expired})
(def step-owners #{:self :counterparty :agent})
(def step-statuses #{:pending :done :skipped})

(defn- now [] #?(:clj (java.util.Date.) :cljs (js/Date.)))

(defn audit
  [{:keys [id type procedure source-event]}]
  (cond-> {:kotoba.procedure.audit/id id
           :kotoba.procedure.audit/type type
           :kotoba.procedure.audit/at (now)}
    procedure (assoc :kotoba.procedure.audit/procedure procedure)
    source-event (assoc :kotoba.procedure.audit/source-event source-event)))

;; ---------- construction ----------

(defn step
  [{:keys [key label owner status] :or {status :pending}}]
  (when-not (contains? step-owners owner)
    (throw (ex-info "Unknown step owner" {:owner owner})))
  (when-not (contains? step-statuses status)
    (throw (ex-info "Unknown step status" {:status status})))
  {:kotoba.procedure.step/key key
   :kotoba.procedure.step/label label
   :kotoba.procedure.step/owner owner
   :kotoba.procedure.step/status status})

(defn procedure
  "`steps` is an ordered seq of step maps (see `step`); order is the order
  they're worked in. `deadline`, if given, is any `compare`-able value
  (e.g. an ISO-8601 UTC string, which sorts correctly lexicographically, or
  epoch millis) -- see `expired?`."
  [{:keys [id kind title source source-id steps deadline state]
    :or {state :open}}]
  (when-not (contains? procedure-states state)
    (throw (ex-info "Unknown procedure state" {:state state})))
  (cond-> {:kotoba.procedure/id id
           :kotoba.procedure/kind kind
           :kotoba.procedure/title title
           :kotoba.procedure/state state
           :kotoba.procedure/steps (mapv step steps)}
    source (assoc :kotoba.procedure/source source)
    source-id (assoc :kotoba.procedure/source-id source-id)
    deadline (assoc :kotoba.procedure/deadline deadline)))

(defn open!
  [s procedure-map]
  (let [p (if (:kotoba.procedure/id procedure-map) procedure-map (procedure procedure-map))
        id (:kotoba.procedure/id p)]
    (store/put-entity! s :procedure id p)
    (store/append-audit! s (audit {:id (str "procedure:" id ":opened")
                                    :type :procedure/opened
                                    :procedure id
                                    :source-event (pr-str p)}))
    (store/get-entity s :procedure id)))

;; ---------- transitions ----------

(defn- guard-not-terminal! [s procedure-id]
  (when (contains? terminal-states (:kotoba.procedure/state (store/get-entity s :procedure procedure-id)))
    (throw (ex-info "Procedure is already terminal" {:procedure-id procedure-id}))))

(defn- update-step [steps step-key f]
  (mapv (fn [st] (if (= step-key (:kotoba.procedure.step/key st)) (f st) st)) steps))

(defn advance-step!
  "Mark `step-key` :done. If every step is now :done, the procedure's own
  state becomes :done too (one extra audit record: :procedure/done)."
  [s procedure-id step-key]
  (guard-not-terminal! s procedure-id)
  (let [p (store/get-entity s :procedure procedure-id)
        steps (update-step (:kotoba.procedure/steps p) step-key
                            #(assoc % :kotoba.procedure.step/status :done))
        all-done? (every? #(= :done (:kotoba.procedure.step/status %)) steps)]
    (store/put-entity! s :procedure procedure-id
                        (cond-> {:kotoba.procedure/steps steps}
                          all-done? (assoc :kotoba.procedure/state :done)))
    (store/append-audit! s (audit {:id (str "procedure:" procedure-id ":step:" (name step-key) ":done")
                                    :type :step/advanced
                                    :procedure procedure-id
                                    :source-event (pr-str {:step step-key})}))
    (when all-done?
      (store/append-audit! s (audit {:id (str "procedure:" procedure-id ":done")
                                      :type :procedure/done
                                      :procedure procedure-id})))
    (store/get-entity s :procedure procedure-id)))

(defn block!
  "The procedure can't move right now (e.g. waiting on a document the
  counterparty hasn't sent yet). Not terminal -- `advance-step!` can still
  land after this."
  [s procedure-id reason]
  (guard-not-terminal! s procedure-id)
  (store/put-entity! s :procedure procedure-id {:kotoba.procedure/state :blocked})
  (store/append-audit! s (audit {:id (str "procedure:" procedure-id ":blocked")
                                  :type :procedure/blocked
                                  :procedure procedure-id
                                  :source-event (pr-str {:reason reason})}))
  (store/get-entity s :procedure procedure-id))

(defn cancel!
  [s procedure-id reason]
  (guard-not-terminal! s procedure-id)
  (store/put-entity! s :procedure procedure-id {:kotoba.procedure/state :cancelled})
  (store/append-audit! s (audit {:id (str "procedure:" procedure-id ":cancelled")
                                  :type :procedure/cancelled
                                  :procedure procedure-id
                                  :source-event (pr-str {:reason reason})}))
  (store/get-entity s :procedure procedure-id))

(defn expire!
  "For a runner tick to call once `expired?` (below) turns true -- moves an
  overdue, still-open/blocked procedure to the terminal :expired state."
  [s procedure-id]
  (guard-not-terminal! s procedure-id)
  (store/put-entity! s :procedure procedure-id {:kotoba.procedure/state :expired})
  (store/append-audit! s (audit {:id (str "procedure:" procedure-id ":expired")
                                  :type :procedure/expired
                                  :procedure procedure-id}))
  (store/get-entity s :procedure procedure-id))

(defn note!
  "Append context to the audit trail without changing procedure state --
  e.g. 'counterparty replied, still waiting on the actual document'."
  [s procedure-id text]
  (store/append-audit! s (audit {:id (str "procedure:" procedure-id ":note:" (pr-str text))
                                  :type :procedure/noted
                                  :procedure procedure-id
                                  :source-event text})))

;; ---------- pure predicates (no store access) ----------

(defn expired?
  "True if `proc` has a deadline that is already in the past relative to
  `now-value` (same `compare`-able type as the deadline) and the procedure
  isn't already terminal."
  [proc now-value]
  (boolean (and (:kotoba.procedure/deadline proc)
                (not (contains? terminal-states (:kotoba.procedure/state proc)))
                (pos? (compare now-value (:kotoba.procedure/deadline proc))))))

(defn next-action
  "The first non-:done step in declared order, plus whether the deadline
  has already passed (when `now-value` is given). nil once every step is
  :done or the procedure is already terminal."
  ([proc] (next-action proc nil))
  ([proc now-value]
   (when-not (contains? terminal-states (:kotoba.procedure/state proc))
     (when-let [st (first (remove #(= :done (:kotoba.procedure.step/status %))
                                  (:kotoba.procedure/steps proc)))]
       {:step st
        :overdue? (boolean (and now-value (expired? proc now-value)))}))))
