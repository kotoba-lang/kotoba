(ns srs.core
  "The registry as a value: a map of name → domain, and one `execute` that
  takes a command and returns the next registry plus the events it produced.

  `srs.lifecycle` knows what happens to *a* domain. This namespace is the
  Shared Registry System proper — the thing that owns the whole namespace of
  names, decides that `example.com` is one object rather than two, and gives
  EPP a single door to push commands through.

  It holds no storage and no clock. A registry value goes in, a registry value
  comes out, and persistence is the caller's problem — which is what lets the
  same code run against an in-memory map in a test, a Datomic database in
  production, and a `kgraph` assertion log in a Kotoba host, without the
  lifecycle rules knowing which.

      (-> (empty-registry \"com\")
          (execute {:command/kind :domain/create :command/name \"example.com\" …} now)
          :registry)

  ## Why events are returned rather than applied

  A create is not only a state change: it is a line on an invoice, a delegation
  to publish into the zone, and an RDAP record that changes. If `execute`
  performed those, `srs` would have to know about billing, DNS and HTTP, and
  every one of them would be untestable without the others. Returning them as
  data keeps the direction of dependency pointing one way — `domain-billing`
  and the zone publisher read `srs` events; `srs` reads nothing."
  (:require [kotoba.lang.text :as str]
            [srs.lifecycle :as lc]
            [srs.status :as status]))

;; ── the registry value ────────────────────────────────────────────────────

(defn empty-registry
  "A registry for one or more TLDs. `tlds` is the set of suffixes this registry
  is authoritative for — checked on create, because a registry that accepts a
  name outside its own namespace has allocated something it cannot serve."
  ([tld] (empty-registry [tld] {}))
  ([tlds policy]
   {:registry/tlds (into #{} (map #(str/lower (str/replace % #"^\.|\.$" ""))) tlds)
    :registry/policy (merge lc/default-policy policy)
    :registry/domains {}}))

(defn normalize-name
  "Registry names are case-insensitive (RFC 1035 §2.3.3) and stored without a
  trailing dot. Normalizing on the way in rather than at every comparison is
  what keeps `EXAMPLE.com` and `example.com.` from becoming two objects — the
  same class of defect that ADR-2607262100 recorded in `cloud-itonami` when
  FQDN and zone-relative forms were compared unnormalized."
  [name]
  (some-> name str/trim (str/replace #"\.$" "") str/lower))

(defn domain [registry dname]
  (get-in registry [:registry/domains (normalize-name dname)]))

(defn in-namespace?
  "Is `dname` a direct child of one of this registry's TLDs?

  A registry for `com` serves `example.com` and not `sub.example.com` — the
  latter is inside the registrant's own zone, and accepting it would let a
  registrar allocate a name the registry does not hold.

  Written against the registry's own TLD set rather than by counting labels,
  because a multi-label suffix is ordinary: a registry for `co.jp` serves
  `example.co.jp`, which has three labels and is still a direct child. Counting
  to two would have quietly refused every ccTLD second-level registry."
  [registry dname]
  (let [n (normalize-name dname)]
    (boolean
     (some (fn [tld]
             (let [suffix (str "." tld)]
               (and (str/ends-with? n suffix)
                    (let [label (subs n 0 (- (count n) (count suffix)))]
                      (and (seq label) (not (str/includes? label ".")))))))
           (:registry/tlds registry)))))

(defn available?
  [registry dname]
  (and (in-namespace? registry dname) (lc/available? (domain registry dname))))

;; ── command dispatch ──────────────────────────────────────────────────────

(def command-kinds
  "Every command the registry accepts, and the operation each one is gated on.
  Kept as data so `org-ietf-epp` can check a parsed command is dispatchable
  before it reaches the lifecycle, and so this list cannot silently disagree
  with the dispatch table below."
  {:domain/create           :create
   :domain/renew            :renew
   :domain/delete           :delete
   :domain/restore          :restore
   :domain/restore-report   :restore
   :domain/transfer-request :transfer
   :domain/transfer-approve :transfer
   :domain/transfer-reject  :transfer
   :domain/transfer-cancel  :transfer
   :domain/update           :update})

(defn- sponsored-by?
  "Is `registrar` the sponsoring registrar for this domain?"
  [d registrar]
  (or (nil? registrar) (= registrar (:domain/registrar d))))

(defn- authorize
  "RFC 5730 §2.9.1.1: a transform on an object is the sponsoring registrar's to
  make. The exceptions are the transfer commands, where by construction one
  side is *not* the sponsor — a gaining registrar requests and cancels, the
  losing registrar approves and rejects. Getting this backwards is how a
  registry lets anyone cancel anyone's transfer."
  [d kind registrar]
  (let [xfer (:domain/transfer d)
        gaining (:transfer/gaining-registrar xfer)
        losing (:transfer/losing-registrar xfer)]
    (case kind
      :domain/transfer-request nil                       ; any registrar may ask
      :domain/transfer-cancel
      (when-not (or (nil? registrar) (= registrar gaining))
        {:error/code 2201 :error/message "Only the gaining registrar may cancel a transfer"})
      (:domain/transfer-approve :domain/transfer-reject)
      (when-not (or (nil? registrar) (= registrar losing))
        {:error/code 2201 :error/message "Only the losing registrar may approve or reject a transfer"})
      (when-not (sponsored-by? d registrar)
        {:error/code 2201 :error/message "Registrar does not sponsor this object"}))))

(defn execute
  "Run one command against the registry.

  Returns `{:ok? true :registry r :domain d :events [...]}` or
  `{:ok? false :error {:error/code n :error/message s}}`. The registry is never
  partially updated: a failed command returns the error and nothing else, so a
  caller cannot accidentally commit half of one.

  `:command/registrar` is the authenticated registrar making the request. It is
  optional so a registry operator can drive the machine directly (a court-
  ordered transfer, a bulk migration), and that hole is deliberate and narrow —
  passing nil means \"the registry itself is acting\", which is a different
  thing from \"nobody checked\"."
  [registry {:keys [command/kind command/name command/registrar] :as command} now]
  (let [policy (:registry/policy registry)
        ;; The lifecycle takes an unqualified payload; the envelope is
        ;; namespaced. Translating here — once — is what keeps every lifecycle
        ;; function free of the transport's key shape.
        payload (fn [& kvs] (apply assoc command :name (normalize-name name) kvs))
        nm (normalize-name name)
        d (domain registry nm)
        commit (fn [{:keys [ok? domain events error]}]
                 (if ok?
                   {:ok? true
                    :registry (assoc-in registry [:registry/domains nm] domain)
                    :domain domain
                    :events (vec events)}
                   {:ok? false :error error}))]
    (cond
      (not (contains? command-kinds kind))
      {:ok? false :error {:error/code 2000 :error/message (str "Unknown command: " kind)}}

      (nil? nm)
      {:ok? false :error {:error/code 2005 :error/message "Missing domain name"}}

      (= kind :domain/create)
      (if-not (in-namespace? registry nm)
        {:ok? false
         :error {:error/code 2306
                 :error/message (str "Not a name this registry is authoritative for: " nm)}}
        (commit (lc/create d policy (payload :registrar registrar) now)))

      (nil? d)
      {:ok? false :error {:error/code 2303 :error/message (str "Object does not exist: " nm)}}

      (= :purged (:domain/phase d))
      {:ok? false :error {:error/code 2303 :error/message (str "Object does not exist: " nm)}}

      :else
      (if-let [err (authorize d kind registrar)]
        {:ok? false :error err}
        (commit
         (case kind
           :domain/renew  (lc/renew d policy (payload) now)
           :domain/delete (lc/delete d policy now)
           :domain/restore (lc/restore d policy now)
           :domain/restore-report (lc/restore-report d policy now)
           ;; The requesting registrar *is* the gaining registrar unless the
           ;; caller names one explicitly — a registry operator moving a domain
           ;; on a registrant's behalf is the only case where they differ.
           :domain/transfer-request
           (lc/transfer-request d policy
                                (merge {:gaining-registrar registrar} (payload)) now)
           :domain/transfer-approve (lc/transfer-approve d policy now)
           :domain/transfer-reject  (lc/transfer-reject d policy now)
           :domain/transfer-cancel  (lc/transfer-cancel d policy now)
           :domain/update (lc/update-domain d policy (payload) now)))))))

(defn execute-all
  "Fold a sequence of commands, stopping at the first failure. Returns the
  registry as of the last success plus the accumulated events and, if one
  occurred, the error and the index of the command that produced it —
  a partial application a caller can inspect rather than a thrown stack."
  [registry commands now]
  (reduce
   (fn [{:keys [registry events] :as acc} [i cmd]]
     (let [r (execute registry cmd now)]
       (if (:ok? r)
         (assoc acc :registry (:registry r) :events (into events (:events r)))
         (reduced (assoc acc :ok? false :error (:error r) :failed-at i)))))
   {:ok? true :registry registry :events []}
   (map-indexed vector commands)))

;; ── the sweep ─────────────────────────────────────────────────────────────

(defn advance
  "Apply every due time-driven transition across the whole registry.

  This is the daily batch, as a pure function of the registry and an instant.
  Running it twice with the same `now` is a no-op the second time, because
  every transition is keyed on a date rather than on having-been-run — which is
  what makes it safe to retry after a partial failure."
  [registry now]
  (reduce
   (fn [acc [nm d]]
     (let [r (lc/advance d (get-in acc [:registry :registry/policy]) now)]
       (-> acc
           (assoc-in [:registry :registry/domains nm] (:domain r))
           (update :events into (:events r)))))
   {:registry registry :events []}
   (:registry/domains registry)))

;; ── projection ────────────────────────────────────────────────────────────

(defn info
  "The registry's answer to an EPP `<domain:info>` / RDAP domain lookup:
  everything public about a name at `now`, with statuses already projected.
  One function so EPP and RDAP cannot disagree about what a domain looks like."
  [registry dname now]
  (when-let [d (domain registry dname)]
    (-> d
        (assoc :domain/statuses (lc/effective-statuses d now))
        (assoc :domain/grace (lc/active-grace d now))
        (dissoc :domain/auth-info))))

(defn zone-records
  "The names this registry currently publishes delegations for, as
  `{:name … :nameservers […]}`. A domain under a hold status or in redemption
  is absent — that is what `:publish` prohibition means, and computing it here
  rather than in the zone builder keeps one definition of \"resolves\".

  Feeds `zone.model` directly; `srs` does not depend on `zone` to say it."
  [registry now]
  (into []
        (comp (map val)
              (filter #(status/allows? (lc/effective-statuses % now) :publish))
              (filter #(seq (:domain/nameservers %)))
              (map (fn [d] {:name (:domain/name d)
                            :nameservers (:domain/nameservers d)})))
        (:registry/domains registry)))
