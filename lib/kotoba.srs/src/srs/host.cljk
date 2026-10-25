(ns srs.host
  "Host objects (RFC 5732) — nameservers as first-class registry objects rather
  than strings on a domain.

  `srs.core` stored nameservers as plain names, which works right up to the
  point where the registry has to answer two questions it cannot:

  - **Is this nameserver still in use?** A host referenced by any domain cannot
    be deleted, and a registry that keeps only strings has no way to know. RFC
    5732 §3.2.2 calls this an association, and deleting an associated host
    breaks every domain that delegates to it.
  - **Where does the glue live?** A nameserver *inside* the zone it serves —
    `ns1.example.com` serving `example.com` — is unreachable without an address
    record in the parent, because resolving it requires already knowing it.
    That is the whole reason glue exists, and whether a host needs it is a
    property of the host, not of any one domain that points at it.

  ## In-zone versus out-of-zone is the load-bearing distinction

  `ns1.example.com` for `example.com` is **in-zone** and MUST carry addresses.
  `ns1.example.net` for `example.com` is **out-of-zone** and MUST NOT — the
  registry is not authoritative for `example.net` and any address it published
  would be a second, stale copy of someone else's data. RFC 5732 §1.1 states
  both directions, and implementations routinely get the second one wrong:
  storing an address for an out-of-zone host looks helpful and quietly makes
  the registry an unreliable authority for a name it does not own.

  Everything here is pure: hosts go in a map, `now` is an argument, and no
  storage or clock is imported."
  (:require [kotoba.lang.text :as str]
            [srs.status :as status]))

(defn normalize [nm]
  (some-> nm str/trim (str/replace #"\.$" "") str/lower))

(defn in-zone?
  "Is `host` inside `zone`? `ns1.example.com` is in-zone for `example.com`;
  `example.com` itself and `ns1.example.net` are not."
  [host zone]
  (let [h (normalize host) z (normalize zone)]
    (boolean (and h z (not= h z) (str/ends-with? h (str "." z))))))

(defn- ipv4? [s]
  (boolean (and (string? s)
                (re-matches #"(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})" s)
                (every? #(<= 0 (#?(:clj Integer/parseInt :cljs js/parseInt) %) 255)
                        (str/split s #"\.")))))

(defn- ipv6? [s]
  (boolean (and (string? s) (str/includes? s ":")
                (re-matches #"[0-9a-fA-F:]+" s))))

(def codes
  {:object-exists 2302 :object-does-not-exist 2303 :status-prohibits 2304
   :object-association-prohibits 2305 :parameter-value-policy 2306
   :parameter-value-syntax 2005})

(defn- fail [code message & [data]]
  {:ok? false :error (merge {:error/code code :error/message message} data)})

(defn- ok [host events] {:ok? true :host host :events (vec events)})

;; ── validation ────────────────────────────────────────────────────────────

(defn check-addresses
  "The rule RFC 5732 §1.1 states in both directions, and which is usually only
  half-implemented. Returns nil when the host is well formed."
  [name zone addresses]
  (let [in? (in-zone? name zone)
        addrs (vec addresses)]
    (cond
      (and in? (empty? addrs))
      {:error/code (codes :parameter-value-policy)
       :error/message (str name " is inside " zone
                           " and must have at least one address; without glue it cannot be resolved, because resolving it would require already knowing it")}

      (and (not in?) (seq addrs))
      {:error/code (codes :parameter-value-policy)
       :error/message (str name " is outside " zone
                           " and must not carry addresses; this registry is not authoritative for it, and publishing one would be a second, stale copy of someone else's data")}

      (some #(not (or (ipv4? %) (ipv6? %))) addrs)
      {:error/code (codes :parameter-value-syntax)
       :error/message (str "not an IPv4 or IPv6 address: "
                           (first (remove #(or (ipv4? %) (ipv6? %)) addrs)))})))

;; ── transforms ────────────────────────────────────────────────────────────

(defn create
  [existing {:keys [name zone registrar addresses]} now]
  (let [nm (normalize name)]
    (cond
      existing (fail (codes :object-exists) (str "Object exists: " nm))
      (nil? nm) (fail (codes :parameter-value-syntax) "host name is required")
      :else
      (if-let [e (check-addresses nm zone addresses)]
        {:ok? false :error e}
        (let [h {:host/name nm
                 :host/zone (normalize zone)
                 :host/registrar registrar
                 :host/addresses (vec addresses)
                 :host/statuses #{}
                 :host/linked #{}
                 :host/created-at now
                 :host/updated-at now}]
          (ok h [{:event/kind :host/created :event/host nm :event/at now
                  :event/in-zone? (in-zone? nm zone)}]))))))

(defn link
  "Record that `domain` delegates to this host. The association RFC 5732 §3.2.2
  protects — kept as a set of domain names rather than a count, because a count
  cannot survive the same domain being linked twice and would eventually let a
  host in use be deleted."
  [host domain now]
  (ok (-> host
          (update :host/linked (fnil conj #{}) (normalize domain))
          (assoc :host/updated-at now))
      [{:event/kind :host/linked :event/host (:host/name host)
        :event/domain (normalize domain) :event/at now}]))

(defn unlink
  [host domain now]
  (ok (-> host
          (update :host/linked (fnil disj #{}) (normalize domain))
          (assoc :host/updated-at now))
      [{:event/kind :host/unlinked :event/host (:host/name host)
        :event/domain (normalize domain) :event/at now}]))

(defn delete
  "Delete a host.

  Refused with **2305** — object association prohibits operation — while any
  domain still delegates to it. That is the code's actual meaning, and it is
  more useful than a generic failure: a registrar seeing 2305 knows to look for
  the associations rather than for a lock."
  [host now]
  (cond
    (seq (:host/linked host))
    (fail (codes :object-association-prohibits)
          (str (:host/name host) " is still used by "
               (count (:host/linked host)) " domain(s)")
          {:error/linked (vec (sort (:host/linked host)))})

    (seq (status/blocking (:host/statuses host) :delete))
    (fail (codes :status-prohibits) "Object status prohibits operation"
          {:error/statuses (vec (status/blocking (:host/statuses host) :delete))})

    :else
    (ok (assoc host :host/deleted-at now)
        [{:event/kind :host/deleted :event/host (:host/name host) :event/at now}])))

(defn update-addresses
  "Replace a host's addresses, re-checking the in-zone rule.

  Re-checked rather than assumed: a host can become in-zone or out-of-zone
  relative to a *renamed* zone, and an update that skipped the check would let
  a registry end up publishing addresses for a name it does not own."
  [host addresses now]
  (if-let [e (check-addresses (:host/name host) (:host/zone host) addresses)]
    {:ok? false :error e}
    (ok (assoc host :host/addresses (vec addresses) :host/updated-at now)
        [{:event/kind :host/updated :event/host (:host/name host) :event/at now}])))

(defn effective-statuses
  "`linked` is a *derived* status (RFC 5732 §2.3): a host is linked when at
  least one domain uses it. Storing it would let it disagree with the
  associations it is supposed to summarize."
  [host]
  (let [st (set (:host/statuses host))
        st (if (seq (:host/linked host)) (conj st :linked) st)]
    (if (empty? st) #{:ok} st)))

(defn info
  "The public view of a host — what EPP `<host:info>` and RDAP's nameserver
  object both render from, so the two cannot disagree."
  [host]
  (-> host
      (assoc :host/statuses (effective-statuses host))
      (assoc :host/linked-count (count (:host/linked host)))
      (dissoc :host/linked)))
