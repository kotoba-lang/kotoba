(ns mail-a2a.core
  "Pure validation for the protected MailA2A envelope.

  MIME parsing, mailbox I/O, cryptography, MLS state, and x402 settlement are
  deliberately host effects and are outside this namespace.")

(def binding-version "1.0")

(def operations
  #{:message/send
    :message/stream
    :tasks/get
    :tasks/list
    :tasks/cancel
    :tasks/subscribe
    :push/create
    :push/get
    :push/list
    :push/delete
    :agent-card/get-extended})

(def kinds #{:request :response :event :error})

(def terminal-states
  #{"TASK_STATE_COMPLETED"
    "TASK_STATE_FAILED"
    "TASK_STATE_CANCELED"
    "TASK_STATE_REJECTED"})

(def payment-kinds #{:required :payload :response})

(defn- present-string? [x]
  (and (string? x) (not (empty? x))))

(defn- natural? [x]
  (and (integer? x) (not (neg? x))))

(defn- error [path code]
  {:path path :code code})

(defn- payment-errors [payment]
  (cond
    (nil? payment) []
    (not (map? payment)) [(error [:payment] :must-be-map)]
    :else
    (let [kind (:kind payment)
          x402-version (:x402-version payment)
          object (:object payment)]
      (cond-> []
        (not (contains? payment-kinds kind))
        (conj (error [:payment :kind] :unknown-payment-kind))

        (not= 2 x402-version)
        (conj (error [:payment :x402-version] :must-be-x402-v2))

        (not (map? object))
        (conj (error [:payment :object] :must-be-map))

        (and (contains? #{:required :payload} kind)
             (map? object)
             (not= 2 (:x402Version object)))
        (conj (error [:payment :object :x402Version]
                     :x402-object-version-mismatch))))))

(defn- group-errors [group security]
  (cond
    (nil? group) []
    (not (map? group)) [(error [:group] :must-be-map)]
    :else
    (cond-> []
      (not= :mls (:profile security))
      (conj (error [:security :profile] :group-requires-mls))

      (not (present-string? (:id group)))
      (conj (error [:group :id] :required))

      (not (natural? (:epoch group)))
      (conj (error [:group :epoch] :must-be-natural))

      (not (natural? (:generation group)))
      (conj (error [:group :generation] :must-be-natural)))))

(defn- task-state [payload]
  (or (get-in payload [:task :status :state])
      (get-in payload [:status :state])))

(defn validation-errors
  "Returns stable, data-shaped validation errors for a protected envelope."
  [envelope]
  (if-not (map? envelope)
    [(error [] :must-be-map)]
    (let [{:keys [kind operation message-id correlation-id sequence final?
                  payload payment group security]} envelope
          binding-v (:mail-a2a/version envelope)
          protocol-v (:a2a/version envelope)
          state (task-state payload)]
      (into
       (cond-> []
         (not= binding-version binding-v)
         (conj (error [:mail-a2a/version] :unsupported-binding-version))

         (not (present-string? protocol-v))
         (conj (error [:a2a/version] :required))

         (not (contains? kinds kind))
         (conj (error [:kind] :unknown-kind))

         (not (contains? operations operation))
         (conj (error [:operation] :unknown-operation))

         (not (present-string? message-id))
         (conj (error [:message-id] :required))

         (not (natural? sequence))
         (conj (error [:sequence] :must-be-natural))

         (not (boolean? final?))
         (conj (error [:final?] :must-be-boolean))

         (not (map? payload))
         (conj (error [:payload] :must-be-map))

         (and (= :request kind) (not= 0 sequence))
         (conj (error [:sequence] :request-must-start-at-zero))

         (and (contains? #{:response :event :error} kind)
              (not (present-string? correlation-id)))
         (conj (error [:correlation-id] :required-for-reply))

         (and (= :request kind)
              (contains? #{:message/send :message/stream :tasks/cancel
                           :push/create :push/delete}
                         operation)
              (not (present-string? (:idempotency-key envelope))))
         (conj (error [:idempotency-key] :required-for-effectful-operation))

         (and (contains? terminal-states state) (not= true final?))
         (conj (error [:final?] :terminal-state-must-be-final)))
       (concat (payment-errors payment)
               (group-errors group security))))))

(defn validate-envelope [envelope]
  (let [errors (validation-errors envelope)]
    {:ok? (empty? errors) :errors errors}))

(defn replay-key
  "The minimum authenticated tuple a receiver persists for replay defense."
  [authenticated-sender envelope protected-digest]
  [authenticated-sender
   (:message-id envelope)
   (:idempotency-key envelope)
   (:operation envelope)
   protected-digest])

(defn next-event?
  "True only when `candidate` is the next event in the same exchange.

  Duplicate recognition is separate: the same message-id with the same
  protected digest is ignored before this function is called."
  [previous candidate]
  (and (map? previous)
       (map? candidate)
       (= (:correlation-id previous) (:correlation-id candidate))
       (= (:operation previous) (:operation candidate))
       (= (inc (:sequence previous)) (:sequence candidate))
       (not (true? (:final? previous)))))
