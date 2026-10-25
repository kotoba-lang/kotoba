(ns cloudflare.workers.admission
  "Admission control: the single gate between a planned command and a real
  Cloudflare binding.

  `cloudflare.workers.command` asked *is this a well-formed command?*. This
  namespace asks *is this command authorized, in scope, and within quota,
  right now?* -- and answers with one enumerated reason, never a boolean, so
  a denial is always explicable to an operator.

  Three properties are worth stating because they are the ones that make the
  gate hold rather than merely exist:

  **Batch admission is fail-closed as a whole.** A guest plans a batch as a
  unit -- \"write the order row, then set the session key\". Executing the
  prefix of a plan whose tail was denied leaves storage in a state the guest
  never reasoned about, which is worse than doing nothing. The default is
  therefore `:on-deny :abort`: one denial and *nothing* runs. `:on-deny :skip`
  exists for genuinely independent batches and has to be asked for.

  **The batch envelope is checked before any command is.** `:max-commands`
  applies to the number of commands *submitted*, not the number allowed, so a
  guest cannot spend the host's admission budget by submitting ten thousand
  commands it knows will be denied.

  **D1 capability comes from the registered statement, not the command.** The
  guest names `\"order-by-id\"`; policy says that statement is `:mode :read`;
  the required capability is therefore `:cf/d1-read`. A guest holding only a
  read grant cannot reach a write statement by mislabeling it, because it does
  not get to label anything.

  Pure: no clock, no I/O. `now` is passed in."
  (:require [cloudflare.workers.command :as command]
            [cloudflare.workers.policy :as policy]
            [cloudflare.workers.receipt :as receipt]))

(defn initial-state
  "Fresh per-invocation quota accumulator."
  []
  {:commands 0 :write-bytes 0 :d1-statements 0 :reads 0})

(defn- charge
  [state cmd]
  (-> state
      (update :commands inc)
      (update :write-bytes + (command/payload-byte-count cmd))
      (cond-> (= :cf.d1/exec (:cmd cmd)) (update :d1-statements inc))
      (cond-> (command/read-command? cmd) (update :reads inc))))

(defn- quota-problem
  "First quota ceiling STATE would cross by admitting CMD, or nil."
  [quota state cmd]
  (let [next-state (charge state cmd)]
    (cond
      (> (:commands next-state) (:max-commands quota))
      {:reason :quota-commands-exceeded
       :limit (:max-commands quota) :actual (:commands next-state)}

      (> (:write-bytes next-state) (:max-write-bytes quota))
      {:reason :quota-write-bytes-exceeded
       :limit (:max-write-bytes quota) :actual (:write-bytes next-state)}

      (> (:d1-statements next-state) (:max-d1-statements quota))
      {:reason :quota-d1-statements-exceeded
       :limit (:max-d1-statements quota) :actual (:d1-statements next-state)}

      (> (:reads next-state) (:max-reads quota))
      {:reason :quota-reads-exceeded
       :limit (:max-reads quota) :actual (:reads next-state)}

      :else nil)))

(defn- required-capability
  "Capability kind CMD needs under BINDING-SPEC.

  Returns `{:cap kind}` or `{:reason ... }` when the statement behind a D1
  command is unregistered or its arity does not match the supplied params."
  [binding-spec cmd]
  (let [spec (command/spec-for cmd)]
    (if (not= :statement-mode (:cap spec))
      {:cap (:cap spec)}
      (let [stmt (policy/statement-spec binding-spec (:statement cmd))]
        (cond
          (nil? stmt)
          {:reason :unknown-statement :detail (:statement cmd)}

          (not= (:arity stmt) (count (:params cmd [])))
          {:reason :statement-arity-mismatch
           :limit (:arity stmt) :actual (count (:params cmd []))}

          :else
          (if-let [cap (policy/statement-capability stmt)]
            {:cap cap :statement stmt}
            {:reason :invalid-statement-mode :detail (:mode stmt)}))))))

(defn- value-limit-problem
  [binding-spec cmd]
  (let [bytes (command/payload-byte-count cmd)
        limit (:max-value-bytes binding-spec)]
    (when (and (pos? bytes) (integer? limit) (> bytes limit))
      {:reason :value-too-large :limit limit :actual bytes})))

(defn- ttl-problem
  [binding-spec cmd]
  (when-let [ttl (:ttl cmd)]
    (let [lo (:min-ttl binding-spec)
          hi (:max-ttl binding-spec)]
      (when (or (and (integer? lo) (< ttl lo))
                (and (integer? hi) (> ttl hi)))
        {:reason :ttl-out-of-range :limit [lo hi] :actual ttl}))))

(defn- deny
  [{:keys [cmd at index cap reason detail limit actual]}]
  {:outcome :denied
   :reason reason
   :detail detail
   :limit limit
   :actual actual
   :receipt (receipt/denied {:cap cap
                             :at at
                             :call (:cmd cmd)
                             :binding (:binding cmd)
                             :resource (command/resource cmd)
                             :reason reason
                             :detail detail
                             :index index})})

(defn admit
  "Admit one COMMAND against POLICY and quota STATE at NOW.

  Returns `{:outcome :allowed :command c :cap kind :state s' :receipt r}` or
  `{:outcome :denied :reason kw :receipt r}` (STATE unchanged on denial: a
  denied command consumes no budget, only the batch envelope bounds abuse)."
  ([policy state now command] (admit policy state now command nil))
  ([policy state now command index]
   (let [p (policy/normalize policy)
         base {:cmd command :at now :index index}]
     (if-let [structural (first (command/problems command))]
       (deny (merge base (select-keys structural [:reason :detail])))
       (let [binding-name (:binding command)
             binding-spec (policy/binding-spec p binding-name)
             spec (command/spec-for command)]
         (cond
           (nil? binding-spec)
           (deny (assoc base :reason :unknown-binding :detail binding-name))

           (not= (:kind binding-spec) (:binding-kind spec))
           (deny (assoc base :reason :binding-kind-mismatch
                        :detail {:declared (:kind binding-spec)
                                 :required (:binding-kind spec)}))

           :else
           (let [required (required-capability binding-spec command)]
             (cond
               (:reason required)
               (deny (merge base (select-keys required [:reason :detail :limit :actual])))

               (not (policy/granted? binding-spec (:cap required)))
               (deny (assoc base :reason :capability-not-granted
                            :cap (:cap required)))

               (and (policy/wildcard-scope? binding-spec)
                    (:policy/forbid-wildcard p))
               (deny (assoc base :reason :wildcard-forbidden :cap (:cap required)))

               (and (not= :d1 (:binding-kind spec))
                    (not (policy/key-in-scope? binding-spec (:key command))))
               (deny (assoc base :reason :key-outside-prefix-scope
                            :cap (:cap required)))

               :else
               (if-let [limit-problem (or (value-limit-problem binding-spec command)
                                          (ttl-problem binding-spec command)
                                          (quota-problem (:policy/quota p) state command))]
                 (deny (merge base {:cap (:cap required)} limit-problem))
                 {:outcome :allowed
                  :command command
                  :cap (:cap required)
                  :statement (:statement required)
                  :state (charge state command)
                  :receipt (receipt/granted
                            {:cap (:cap required)
                             :at now
                             :call (:cmd command)
                             :binding binding-name
                             :resource (command/resource command)
                             :index index})})))))))))

(defn admit-batch
  "Admit a whole COMMANDS vector.

  OPTS: `{:now <timestamp> :on-deny :abort|:skip}` (`:abort` is the default).

  Returns
  `{:outcome :allowed :admitted [{:command :cap :statement} ...] :receipts [...] :state s}`
  or, under `:abort`,
  `{:outcome :denied :reason kw :index i :receipts [...]}` with `:admitted`
  absent -- there is deliberately no partial plan for a caller to run by
  mistake. Under `:skip`, the outcome is `:allowed` with the surviving subset
  and every denial still present in `:receipts`."
  [policy commands {:keys [now on-deny] :or {on-deny :abort}}]
  (let [p (policy/normalize policy)
        quota (:policy/quota p)
        n (count commands)]
    (cond
      (not (sequential? commands))
      {:outcome :denied
       :reason :malformed-batch
       :receipts [(receipt/denied {:cap nil :at now :call :batch
                                   :reason :malformed-batch})]}

      (> n (:max-commands quota))
      {:outcome :denied
       :reason :quota-commands-exceeded
       :limit (:max-commands quota)
       :actual n
       :receipts [(receipt/denied {:cap nil :at now :call :batch
                                   :reason :quota-commands-exceeded
                                   :detail {:limit (:max-commands quota)
                                            :submitted n}})]}

      :else
      (loop [[cmd & more] commands
             index 0
             state (initial-state)
             admitted []
             receipts []]
        (if (nil? cmd)
          {:outcome :allowed :admitted admitted :receipts receipts :state state}
          (let [result (admit p state now cmd index)
                receipts' (conj receipts (:receipt result))]
            (cond
              (= :allowed (:outcome result))
              (recur more (inc index) (:state result)
                     (conj admitted (select-keys result [:command :cap :statement]))
                     receipts')

              (= :skip on-deny)
              (recur more (inc index) state admitted receipts')

              :else
              {:outcome :denied
               :reason (:reason result)
               :detail (:detail result)
               :limit (:limit result)
               :actual (:actual result)
               :index index
               :receipts receipts'})))))))
