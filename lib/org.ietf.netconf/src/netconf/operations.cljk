(ns netconf.operations
  "RFC 6241 §7 — the nine standard NETCONF operations. Each function
  builds a complete <rpc> XML string (via netconf.message/rpc->xml)
  wrapping the operation's element, shaped exactly as the cited RFC 6241
  subsection specifies.

  <filter>/<config> content is opaque, caller-supplied hiccup (already a
  netconf.message/xml.core form, e.g. [:filter {\"type\" \"subtree\"}
  ...]) — this namespace never interprets it. That content is
  YANG-modeled (RFC 7950) per-device data; see the README's YANG-scoping
  note for why that's out of scope here."
  (:require [netconf.message :as msg]))

;; The three configuration datastores base NETCONF defines (RFC 6241 §1.1:
;; <running> always; <candidate>/<startup> only if the device advertises
;; the corresponding capability, §8.3/§8.7 — this codec doesn't know which
;; capabilities a given peer advertised, so it accepts all three
;; everywhere the base spec's operation description doesn't textually
;; forbid one of them, see delete-config below).
(def datastores #{:running :candidate :startup})

(defn- ds-el
  "[:running] / [:candidate] / [:startup] — the child element inside a
  <source>/<target> wrapper. Throws (caller-controlled input) if `ds`
  isn't one this operation's RFC 6241 subsection permits."
  [op-kw ds allowed]
  (when-not (contains? allowed ds)
    (throw (ex-info (str "invalid datastore for " (name op-kw))
                     {:netconf/error (keyword (str (name op-kw) "-invalid-datastore"))
                      :datastore ds :allowed allowed})))
  [ds])

;; ------------------------------------------------------- §7.1 get-config

(defn get-config
  "RFC 6241 §7.1 <get-config>. `source` is :running/:candidate/:startup.
  `filter-el` (optional) is an opaque <filter> hiccup element."
  [message-id source & [filter-el]]
  (msg/rpc->xml message-id
    (into [:get-config [:source (ds-el :get-config source datastores)]]
          (when filter-el [filter-el]))))

;; ------------------------------------------------------- §7.2 edit-config

;; RFC 6241 §7.2 — the three enumerated <default-operation> values, three
;; <test-option> values (the latter only meaningful if the peer
;; advertises :validate:1.1, §8.6 — not checked here, this codec doesn't
;; track capability state), and three <error-option> values.
(def default-operations #{"merge" "replace" "none"})
(def test-options #{"test-then-set" "set" "test-only"})
(def error-options #{"stop-on-error" "continue-on-error" "rollback-on-error"})

(defn edit-config
  "RFC 6241 §7.2 <edit-config>. `target` is :running or :candidate
  (\"Name of the configuration datastore being edited, such as <running/>
  or <candidate/>\" — startup is not a legal edit-config target in base
  NETCONF). `config-el` is the WHOLE opaque `<config>...</config>`
  hiccup element (same convention as `filter-el` elsewhere in this
  namespace: the caller builds the named wrapper itself, including any
  attributes on it — e.g. RFC 6241 §7.2's own delete example puts
  `xmlns:xc=\"...\"` directly on `<config>`, which this function has no
  way to add if it built the `<config>` wrapper itself). Element-level
  `xc:operation=\"merge|replace|create|delete|remove\"` attributes
  inside it are likewise the caller's to have placed — this function
  doesn't inspect <config> content.

  `opts` (all optional, all validated against §7.2's own enumerations
  rather than passed through unchecked): :default-operation :test-option
  :error-option."
  [message-id target config-el & {:keys [default-operation test-option error-option]}]
  (let [tgt (ds-el :edit-config target #{:running :candidate})]
    (when (and default-operation (not (contains? default-operations default-operation)))
      (throw (ex-info "invalid default-operation (RFC 6241 §7.2)"
                       {:netconf/error :edit-config-invalid-default-operation :value default-operation})))
    (when (and test-option (not (contains? test-options test-option)))
      (throw (ex-info "invalid test-option (RFC 6241 §7.2)"
                       {:netconf/error :edit-config-invalid-test-option :value test-option})))
    (when (and error-option (not (contains? error-options error-option)))
      (throw (ex-info "invalid error-option (RFC 6241 §7.2)"
                       {:netconf/error :edit-config-invalid-error-option :value error-option})))
    (msg/rpc->xml message-id
      (into [:edit-config [:target tgt]]
            (remove nil?)
            [(when default-operation [:default-operation default-operation])
             (when test-option [:test-option test-option])
             (when error-option [:error-option error-option])
             config-el]))))

;; ------------------------------------------------------- §7.3 copy-config

(defn- target-or-source-el
  "RFC 6241 §7.3: <target>/<source> hold either a datastore name or (only
  with the :url capability, out of scope for capability tracking here,
  but the shape itself is representable) a <url>/<config> element — so
  this accepts either a datastore keyword or an already-built opaque
  hiccup vector for the latter."
  [tag x allowed-ds op-kw]
  (cond
    (keyword? x) [tag (ds-el op-kw x allowed-ds)]
    (vector? x) [tag x]
    :else (throw (ex-info "target/source must be a datastore keyword or a hiccup element"
                           {:netconf/error :copy-config-invalid-target-or-source :value x}))))

(defn copy-config
  "RFC 6241 §7.3 <copy-config>. `target`/`source` are each either a
  datastore keyword (:running/:candidate/:startup) or an opaque hiccup
  element (a <url> or literal <config>, per §7.3/§8.8)."
  [message-id target source]
  (msg/rpc->xml message-id
    [:copy-config
     (target-or-source-el :target target datastores :copy-config)
     (target-or-source-el :source source datastores :copy-config)]))

;; ----------------------------------------------------- §7.4 delete-config

(defn delete-config
  "RFC 6241 §7.4 <delete-config>. `target` is :candidate or :startup —
  \"The <running> configuration datastore cannot be deleted\" is
  normative text, enforced here rather than left to the wire."
  [message-id target]
  (msg/rpc->xml message-id
    [:delete-config [:target (ds-el :delete-config target #{:candidate :startup})]]))

;; ------------------------------------------------------------- §7.5 lock

(defn lock
  "RFC 6241 §7.5 <lock>. `target` is the datastore to lock."
  [message-id target]
  (msg/rpc->xml message-id [:lock [:target (ds-el :lock target datastores)]]))

;; ----------------------------------------------------------- §7.6 unlock

(defn unlock
  "RFC 6241 §7.6 <unlock>. `target` is the datastore to unlock."
  [message-id target]
  (msg/rpc->xml message-id [:unlock [:target (ds-el :unlock target datastores)]]))

;; --------------------------------------------------------------- §7.7 get

(defn get-op
  "RFC 6241 §7.7 <get>. Named `get-op`, not `get`, so it doesn't shadow
  `clojure.core/get` for anyone who `:refer`s this namespace. `filter-el`
  (optional) is an opaque <filter> hiccup element."
  [message-id & [filter-el]]
  (msg/rpc->xml message-id (into [:get] (when filter-el [filter-el]))))

;; --------------------------------------------------------- §7.8 close-session

(defn close-session
  "RFC 6241 §7.8 <close-session/> — no parameters."
  [message-id]
  (msg/rpc->xml message-id [:close-session]))

;; --------------------------------------------------------- §7.9 kill-session

(defn kill-session
  "RFC 6241 §7.9 <kill-session>. `session-id` is the target session's
  numeric id (\"If this value is equal to the current session ID, an
  'invalid-value' error is returned\" — a runtime check this codec can't
  make, since it doesn't track which session it's building for; only the
  structural constraint, that session-id is a positive integer, is
  enforced here)."
  [message-id session-id]
  (when-not (and (integer? session-id) (pos? session-id))
    (throw (ex-info "session-id must be a positive integer (RFC 6241 §7.9)"
                     {:netconf/error :kill-session-invalid-session-id :session-id session-id})))
  (msg/rpc->xml message-id [:kill-session [:session-id (str session-id)]]))
