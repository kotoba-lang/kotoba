(ns cloudflare.workers.provider
  "The `kotoba/host` provider: the only code in this repo that touches a real
  Cloudflare binding.

  It is deliberately the *last* link in the chain and it does not trust the
  link before it. `execute!` re-runs admission itself rather than accepting an
  already-admitted list from a caller, so there is no code path -- including a
  future refactor, including a mistaken direct call -- that reaches `env.DB`
  without passing the gate. Defence in depth costs one pure function call per
  command here and removes a whole class of \"someone called the inner
  function\" bug.

  No ambient fallback. If policy names a binding the Worker was not deployed
  with, that is a denial (`:binding-absent`), not a silent skip and not an
  in-memory stand-in. A stand-in would let a Worker deployed without its D1
  database appear to work in production while writing nothing.

  Binding *kind* is verified by shape before use. `KVNamespace`, `D1Database`
  and `R2Bucket` are structurally distinguishable (`getWithMetadata`,
  `prepare`, `head` respectively), so a policy that says `:kind :kv` for what
  is actually an R2 bucket is caught here rather than throwing halfway through
  a batch."
  (:require [cloudflare.workers.admission :as admission]
            [cloudflare.workers.command :as command]
            [cloudflare.workers.policy :as policy]
            [cloudflare.workers.receipt :as receipt]))

;; ---------------------------------------------------------------------------
;; Binding resolution
;; ---------------------------------------------------------------------------

(def ^:private required-members
  "Members that must be present for a binding to be accepted as its declared
  kind. Each list contains at least one member unique to that kind."
  {:kv ["get" "put" "delete" "getWithMetadata"]
   :d1 ["prepare" "batch"]
   :r2 ["get" "put" "delete" "head"]})

(defn- fn-member?
  [obj member]
  (fn? (unchecked-get obj member)))

(defn resolve-binding
  "Look BINDING-NAME up in ENV and verify it looks like KIND.

  Returns `{:ok? true :binding obj}` or `{:reason ...}`."
  [env binding-name kind]
  (let [obj (when (some? env) (unchecked-get env binding-name))]
    (cond
      (nil? obj)
      {:reason :binding-absent :detail binding-name}

      (not (every? (partial fn-member? obj) (get required-members kind)))
      {:reason :binding-shape-mismatch
       :detail {:binding binding-name :expected kind}}

      :else {:ok? true :binding obj})))

;; ---------------------------------------------------------------------------
;; Payload encoding
;; ---------------------------------------------------------------------------

(defn- b64->bytes
  [s]
  (let [bin (js/atob s)
        n (.-length bin)
        out (js/Uint8Array. n)]
    (dotimes [i n]
      (aset out i (.charCodeAt bin i)))
    out))

(defn- bytes->b64
  "Base64 of an ArrayBuffer, chunked so a large object cannot blow the stack
  through `String.fromCharCode.apply`."
  [array-buffer]
  (let [bytes (js/Uint8Array. array-buffer)
        n (.-length bytes)
        chunk 8192]
    (loop [i 0 acc ""]
      (if (>= i n)
        (js/btoa acc)
        (let [end (min n (+ i chunk))
              slice (.subarray bytes i end)]
          (recur end (str acc (.apply js/String.fromCharCode nil slice))))))))

(defn- payload->js
  "Command payload (`\"text\"` or `{:b64 \"...\"}`) to what a binding accepts."
  [payload]
  (if (map? payload)
    (b64->bytes (:b64 payload))
    payload))

;; ---------------------------------------------------------------------------
;; Per-command execution
;; ---------------------------------------------------------------------------

(defn- kv-execute
  [kv {:keys [cmd key value ttl binding]}]
  (case cmd
    :cf.kv/get
    (-> (.get kv key)
        (.then (fn [v]
                 {:event :cf.kv/value :binding binding :key key
                  :found (some? v) :value v})))

    :cf.kv/put
    (-> (.put kv key (payload->js value)
              (if ttl #js {:expirationTtl ttl} #js {}))
        (.then (fn [_] {:event :cf.kv/written :binding binding :key key})))

    :cf.kv/delete
    (-> (.delete kv key)
        (.then (fn [_] {:event :cf.kv/deleted :binding binding :key key})))))

(defn- d1-execute
  [db {:keys [binding statement params]} statement-spec]
  (let [prepared (.prepare db (:sql statement-spec))
        bound (if (seq params)
                (.apply (.-bind prepared) prepared (to-array params))
                prepared)]
    (if (= :read (:mode statement-spec))
      (-> (.all bound)
          (.then (fn [res]
                   {:event :cf.d1/rows :binding binding :statement statement
                    :rows (js->clj (.-results res) :keywordize-keys true)
                    :meta (js->clj (.-meta res) :keywordize-keys true)})))
      (-> (.run bound)
          (.then (fn [res]
                   {:event :cf.d1/applied :binding binding :statement statement
                    :meta (js->clj (.-meta res) :keywordize-keys true)}))))))

(defn- r2-execute
  [bucket {:keys [cmd binding key body content-type]}]
  (case cmd
    :cf.r2/get
    (-> (.get bucket key)
        (.then (fn [obj]
                 (if (nil? obj)
                   (js/Promise.resolve
                    {:event :cf.r2/object :binding binding :key key
                     :found false :body nil})
                   (-> (.arrayBuffer obj)
                       (.then (fn [ab]
                                {:event :cf.r2/object :binding binding :key key
                                 :found true
                                 ;; Always base64: lossless for binary, and one
                                 ;; shape for callers to handle.
                                 :body {:b64 (bytes->b64 ab)}
                                 :size (.-size obj)
                                 :content-type (some-> (.-httpMetadata obj)
                                                       (.-contentType))})))))))

    :cf.r2/put
    (-> (.put bucket key (payload->js body)
              (if content-type
                #js {:httpMetadata #js {:contentType content-type}}
                #js {}))
        (.then (fn [_] {:event :cf.r2/written :binding binding :key key})))

    :cf.r2/delete
    (-> (.delete bucket key)
        (.then (fn [_] {:event :cf.r2/deleted :binding binding :key key})))))

(defn- execute-one
  [env {:keys [command statement]}]
  (let [kind (:binding-kind (command/spec-for command))
        resolved (resolve-binding env (:binding command) kind)]
    (if-not (:ok? resolved)
      (js/Promise.resolve {::resolution-failure resolved})
      (let [obj (:binding resolved)]
        (case kind
          :kv (kv-execute obj command)
          :d1 (d1-execute obj command statement)
          :r2 (r2-execute obj command))))))

;; ---------------------------------------------------------------------------
;; Batch execution
;; ---------------------------------------------------------------------------

(defn- error-message
  [e]
  (cond
    (nil? e) "unknown error"
    (instance? js/Error e) (.-message e)
    :else (str e)))

(defn execute!
  "Admit COMMANDS against POLICY, then run the survivors against ENV bindings.

  OPTS: `{:env <Workers env> :policy <policy map> :commands [...]
          :now <timestamp string> :on-deny :abort|:skip}`

  Returns a Promise of:

  - `{:outcome :allowed :events [...] :receipts [...]}` -- every admitted
    command ran
  - `{:outcome :denied :reason kw :index i :receipts [...] :events []}` --
    admission refused the batch; **nothing ran**
  - `{:outcome :failed :reason kw :index i :events [...] :receipts [...]}` --
    admission passed but a binding was absent, mis-shaped, or errored. Commands
    before the failure did run; execution stops there rather than pressing on
    through a plan whose premises no longer hold.

  `now` is required and is passed straight to receipts. In a Worker, use the
  request time."
  [{:keys [env policy commands now on-deny] :or {on-deny :abort}}]
  (let [p (policy/normalize policy)
        admission (admission/admit-batch p commands {:now now :on-deny on-deny})]
    (if (= :denied (:outcome admission))
      (js/Promise.resolve (assoc admission :events []))
      (let [admitted (:admitted admission)]
        (reduce
         (fn [promise [index entry]]
           (.then
            promise
            (fn [acc]
              (if (:halted acc)
                acc
                (-> (execute-one env entry)
                    (.then
                     (fn [result]
                       (if-let [failure (::resolution-failure result)]
                         (assoc acc
                                :halted true
                                :outcome :failed
                                :reason (:reason failure)
                                :detail (:detail failure)
                                :index index
                                :receipts (conj (:receipts acc)
                                                (receipt/failed
                                                 {:cap (:cap entry)
                                                  :at now
                                                  :call (:cmd (:command entry))
                                                  :binding (:binding (:command entry))
                                                  :resource (command/resource (:command entry))
                                                  :reason (:reason failure)
                                                  :index index})))
                         (update acc :events conj (assoc result :index index)))))
                    (.catch
                     (fn [e]
                       (assoc acc
                              :halted true
                              :outcome :failed
                              :reason :provider-error
                              :detail (error-message e)
                              :index index
                              :receipts (conj (:receipts acc)
                                              (receipt/failed
                                               {:cap (:cap entry)
                                                :at now
                                                :call (:cmd (:command entry))
                                                :binding (:binding (:command entry))
                                                :resource (command/resource (:command entry))
                                                :reason :provider-error
                                                :index index}))))))))))
         (js/Promise.resolve {:outcome :allowed
                              :events []
                              :receipts (:receipts admission)
                              :halted false})
         (map-indexed vector admitted))))))

(defn preflight
  "Check ENV and POLICY agree *before* serving traffic.

  Returns a vector of problems: policy problems from
  `cloudflare.workers.policy/problems` plus one entry per binding that policy
  names but the deployment does not actually provide, or provides as the wrong
  kind. Call this from a Worker's startup path or a `/healthz` route so a
  misconfigured deploy is loud at deploy time instead of at the first write."
  [env policy]
  (let [p (policy/normalize policy)]
    (into (vec (policy/problems p))
          (keep (fn [[binding-name spec]]
                  (let [resolved (resolve-binding env binding-name (:kind spec))]
                    (when-not (:ok? resolved)
                      {:problem (:reason resolved)
                       :binding binding-name
                       :kind (:kind spec)})))
                (:policy/bindings p)))))
