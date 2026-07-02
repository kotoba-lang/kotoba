(ns kotoba.host-providers
  "Capability-guarded host provider dispatch for the CLJ runtime slice
  (issue #263).

  Every host-import op from the kotoba core capability contract
  (clipboard_read, http_fetch, fs_read, ...) maps to a
  kotoba.lang.capability-values capability kind (:host/clipboard-read,
  :host/http, :host/fs-read, ...). At run time the launcher builds
  CACAO-style grants and a local policy from its existing policy EDN and
  dispatches each provider invocation through
  kotoba.lang.capability-host/guard-call, so:

  - a denied call NEVER reaches the provider handler (fail closed), and
  - every call — grant, denial, or handler error — leaves a receipt in the
    run's audit journal (surfaced as :kotoba.host/receipts in the launcher
    result).

  Legacy behavior is preserved: a `run` without `--policy` installs no guard
  and host-import ops remain statically rejected as :capability-not-granted,
  exactly as before. Enforcement happens only when a capability policy is
  supplied.

  Policy EDN vocabulary (superset of the existing wasm/provider policy):

  {:kotoba.policy/capabilities #{:clipboard/text :http/fetch ...}
   ;; optional per-capability resource scope (default :any)
   :kotoba.policy/capability-resources {:clipboard/text #{\"clipboard:system\"}}
   ;; optional per-capability grant expiry, enforced at call time
   :kotoba.policy/capability-expires {:clipboard/text \"2027-01-01\"}}

  The default handlers are deterministic Rust-free stubs (the interpreter
  slice has no real memory ABI); concrete native providers (pbcopy/pbpaste,
  an HTTP client, ...) plug in by passing a :handlers map to `host-call`."
  (:require [kotoba.core.contracts :as core-contracts]
            [kotoba.lang.capability-host :as capability-host]
            [kotoba.lang.capability-values :as capability-values]
            [kotoba.runtime :as runtime]))

(def op->kind
  "Host-import op (capability contract symbol) -> capability kind understood
  by kotoba.lang.capability-values/effect-for-kind."
  {'notify-show :host/notify
   'clipboard-read :host/clipboard-read
   'clipboard-write :host/clipboard-write
   'clipboard-write-str :host/clipboard-write
   'http-fetch :host/http
   'keychain-read :host/keychain-read
   'keychain-write :host/keychain-write
   'fs-read :host/fs-read
   'fs-write :host/fs-write
   'host-i64-roundtrip :host/ledger-append})

(defn op-capability
  "Contract capability name (e.g. \"clipboard/text\") for a host-import op."
  [op]
  (get-in runtime/host-imports [op :capability]))

(defn- named-lookup
  "Look up CAP-NAME in a policy map keyed by capability keyword or string."
  [m cap-name]
  (some (fn [[k v]]
          (when (= cap-name (core-contracts/capability-name k))
            v))
        m))

(defn- resource-scope
  "Grant resource set for CAP-NAME under POLICY; defaults to the universe."
  [policy cap-name]
  (let [resources (named-lookup (:kotoba.policy/capability-resources policy)
                                cap-name)]
    (cond
      (nil? resources) #{:any}
      (= :any resources) #{:any}
      :else (set resources))))

(defn- grant-expiry
  [policy cap-name]
  (named-lookup (:kotoba.policy/capability-expires policy) cap-name))

(defn- granted-kinds
  "Seq of [kind cap-name] for every guarded kind whose contract capability
  appears in the policy's :kotoba.policy/capabilities."
  [policy]
  (let [caps (core-contracts/policy-capabilities policy)]
    (distinct
     (keep (fn [[op kind]]
             (let [cap-name (op-capability op)]
               (when (and cap-name (contains? caps cap-name))
                 [kind cap-name])))
           op->kind))))

(defn policy-grants
  "CACAO-style grants derived from the launcher policy EDN: one grant per
  guarded host kind enabled by :kotoba.policy/capabilities, scoped by
  :kotoba.policy/capability-resources and expiring per
  :kotoba.policy/capability-expires."
  [policy]
  (vec (for [[kind cap-name] (granted-kinds policy)]
         {:grant/kind kind
          :grant/resources (resource-scope policy cap-name)
          :grant/expires (grant-expiry policy cap-name)
          :grant/id (str "policy:" cap-name)})))

(defn local-policy
  "kotoba.lang.capability-values local policy derived from the launcher
  policy EDN."
  [policy]
  {:policy/allow
   (into {} (for [[kind cap-name] (granted-kinds policy)]
              [kind (resource-scope policy cap-name)]))})

(def default-handlers
  "Deterministic Rust-free provider stubs, keyed by host-import op. Each
  handler is (fn [concrete-cap args] result). host-i64-roundtrip echoes its
  argument (matching the interpreter builtin); the pointer-ABI providers
  return 0 (the success status of the provider result ABI). Real native
  providers replace these via the :handlers option of `host-call`."
  {'notify-show (fn [_cap _args] 0)
   'clipboard-read (fn [_cap _args] 0)
   'clipboard-write (fn [_cap _args] 0)
   'clipboard-write-str (fn [_cap _args] 0)
   'http-fetch (fn [_cap _args] 0)
   'keychain-read (fn [_cap _args] 0)
   'keychain-write (fn [_cap _args] 0)
   'fs-read (fn [_cap _args] 0)
   'fs-write (fn [_cap _args] 0)
   'host-i64-roundtrip (fn [_cap args] (first args))})

(defn journal
  "Append-only receipt recorder ({:record! fn :entries fn}) for a guarded run."
  []
  (capability-host/journal))

(defn capability-query-fn
  "Interpreter binding for `has-capability?`: a policy lookup, not a host
  effect, so it is not receipted."
  [policy]
  (let [caps (core-contracts/policy-capabilities policy)]
    (fn [cap]
      (contains? caps (core-contracts/capability-name cap)))))

(defn host-call
  "Build the guarded host-call fn handed to kotoba.runtime/run:
  (fn [op args] result). Every invocation goes through
  kotoba.lang.capability-host/guard-call with grants/policy derived from the
  launcher policy EDN; receipts flow to :record! (see `journal`). A denial
  throws ex-info carrying :kotoba.host/denied, :kotoba.host/call, and the
  denial :kotoba.host/receipt — the provider handler is never invoked."
  ([policy] (host-call policy nil))
  ([policy {:keys [record! now handlers]}]
   (let [grants (policy-grants policy)
         allow (local-policy policy)
         now (or now (str (java.time.LocalDate/now)))
         handlers (or handlers default-handlers)]
     (fn guarded-host-call [op args]
       (let [kind (get op->kind op)
             handler (get handlers op)]
         (when-not (and kind handler)
           (throw (ex-info "host op has no capability guard"
                           {:kotoba.host/op op})))
         (let [outcome (capability-host/guard-call
                        {:call (keyword "kotoba.host" (str op))
                         :requested (capability-values/make-cap kind :any)
                         :cacao-grants grants
                         :local-policy allow
                         :now now
                         :record! record!
                         :handler (fn [concrete] (handler concrete (vec args)))})]
           (if (:kotoba.host/ok? outcome)
             (:kotoba.host/result outcome)
             (throw (ex-info "host call denied by capability guard"
                             {:kotoba.host/denied (:kotoba.host/denied outcome)
                              :kotoba.host/call op
                              :kotoba.host/receipt (:kotoba.host/receipt outcome)})))))))))
