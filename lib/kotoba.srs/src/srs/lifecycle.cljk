(ns srs.lifecycle
  "The domain lifecycle state machine — allocation, renewal, transfer, and the
  Registry Grace Periods of RFC 3915 — as a pure function of state, command,
  policy and time.

  This is the part of a registry that is *not* a protocol. EPP (RFC 5730-5734)
  is how a command arrives and RDAP (RFC 9083) is how the result is published,
  but neither says what a domain does between them: when it auto-renews, how
  long redemption lasts, whether a delete on day 4 is a refund and a delete on
  day 6 is not. Registries encode that in stored procedures and cron jobs, and
  it becomes untestable — the interesting transitions are 30 to 45 days apart,
  so nobody runs them.

  Three commitments make it testable instead:

  **No clock.** Every function takes `now` in epoch milliseconds. A 10-year
  lifecycle is an ordinary `reduce` over a vector of instants, not a fixture
  that has to sleep.

  **No implicit transitions.** Time-driven changes — auto-renew at expiry,
  redemption ending, a transfer auto-approving on day 5 — happen in `advance`
  and nowhere else. A command never silently sweeps the calendar on its way
  past. If a domain has been untouched for two years, `advance` applies every
  due transition in order and reports each one; it does not jump to the end
  state and lose the events in between, because those events are what billing
  and the zone publisher consume.

  **Failure is a value.** Every transform returns `{:ok? false :error {…}}`
  with an EPP result code (RFC 5730 §3), never an exception. `org-ietf-epp`
  maps the code straight onto the wire, so the reason a registrar's command
  was refused is the reason they are told.

  ## The phases

      available ──create──▶ active ──delete──▶ redemption ──▶ pendingDelete ──▶ purged
                              ▲                    │                              │
                              └────restore─────────┘                              ▼
                                                                              available

  `active` is the only phase with a public presence; everything after `delete`
  is a countdown. `purged` is terminal and means the name is allocatable again
  — kept as an explicit phase rather than deleting the record, because the
  registry still owes RDAP an answer about a name that existed yesterday, and
  because a name that went through redemption is a different thing from a name
  that never existed.

  Grace periods overlay `active` rather than replacing it (RFC 3915 §3.1): a
  domain in `addPeriod` is an ordinary active domain that happens to be
  refundable. Modeling them as phases — as the naive reading of the RFC's
  status list invites — makes them mutually exclusive, and they are not: a
  domain can sit in `renewPeriod` and `transferPeriod` at once."
  (:require [kotoba.lang.text :as str]
            [srs.status :as status]
            [srs.time :as t]))

;; ── policy ────────────────────────────────────────────────────────────────

(def default-policy
  "gTLD-standard windows. Every one of these is policy, not protocol — ccTLDs
  differ widely and a registry operator is expected to override. They are
  collected here rather than inlined so that `srs` never contains a bare
  number whose provenance is a guess."
  {;; RFC 3915 §3.1 grace periods.
   :policy/add-grace-days         5   ; AGP — delete here is a full refund
   :policy/renew-grace-days       5
   :policy/auto-renew-grace-days  45
   :policy/transfer-grace-days    5
   ;; RFC 3915 §3.2 — the redemption sequence.
   :policy/redemption-days        30
   :policy/pending-delete-days    5
   :policy/restore-report-days    7   ; RFC 3915 §4.2, restore report deadline
   ;; RFC 5731 §3.2.4 — transfer.
   :policy/transfer-auto-approve-days 5
   ;; ICANN Transfer Policy: a domain may not be transferred within 60 days of
   ;; creation or of a previous transfer.
   :policy/lock-after-create-days   60
   :policy/lock-after-transfer-days 60
   ;; ICANN maximum registration period.
   :policy/max-term-years         10
   :policy/auto-renew?            true})

(defn- days [policy k] (get policy k (get default-policy k)))

;; ── results ───────────────────────────────────────────────────────────────

(defn- ok [domain events] {:ok? true :domain domain :events (vec events)})

(defn- fail
  "EPP result codes (RFC 5730 §3). Carrying the numeric code here rather than
  in the protocol layer means the reason survives to any front end — RDAP and
  a CLI get the same discrimination EPP does."
  [code message & [data]]
  {:ok? false
   :error (cond-> {:error/code code :error/message message}
            data (merge data))})

(def ^:private codes
  {:object-exists            2302
   :object-does-not-exist    2303
   :status-prohibits         2304
   :authorization-error      2201
   :parameter-value-policy   2306
   :parameter-value-range    2004
   ;; RFC 5730 §3 has transfer-specific codes, and using them rather than a
   ;; generic "not eligible" is the difference between a registrar's client
   ;; retrying and giving up. 2300 means one is already in flight; 2301 means
   ;; there is nothing to approve, reject or cancel.
   :object-pending-transfer  2300
   :object-not-pending-transfer 2301})

(defn- event [kind domain at extra]
  (merge {:event/kind kind :event/domain (:domain/name domain) :event/at at} extra))

;; ── grace periods ─────────────────────────────────────────────────────────

(defn- add-grace [domain kind at ends-at]
  (update domain :domain/grace (fnil conj [])
          {:grace/kind kind :grace/started-at at :grace/ends-at ends-at}))

(defn active-grace
  "Grace windows still open at `now`. Kept as a query rather than pruned in
  place so that `advance` is the only thing that mutates, and so a caller can
  ask about a past instant."
  [domain now]
  (filterv #(> (:grace/ends-at %) now) (:domain/grace domain)))

(defn in-grace?
  [domain kind now]
  (boolean (some #(= kind (:grace/kind %)) (active-grace domain now))))

(defn refundable?
  "Is a delete right now refundable, and under which grace period?

  This is the single question billing asks of the lifecycle, and it is
  deliberately answered here rather than in `domain-billing`: the windows are
  lifecycle policy, and a billing layer that recomputed them from dates would
  be a second implementation of the same rule, free to drift."
  [domain now]
  (let [kinds (into #{} (map :grace/kind) (active-grace domain now))]
    (some kinds [:add :renew :auto-renew :transfer])))

;; ── status projection ─────────────────────────────────────────────────────

(defn effective-statuses
  "The status set as EPP should report it: stored prohibitions, plus the RGP
  statuses implied by the current phase and open grace windows, plus the
  derived `ok`/`inactive` (RFC 5731 §2.3).

  Derived rather than stored because a stored RGP status is a status that can
  disagree with the dates — and when it does, the dates are right and the
  status is what the registrar sees."
  [domain now]
  (let [phase (:domain/phase domain)
        grace-status {:add :addPeriod :renew :renewPeriod
                      :auto-renew :autoRenewPeriod :transfer :transferPeriod}
        from-grace (into #{} (keep (comp grace-status :grace/kind))
                         (active-grace domain now))
        from-phase (case phase
                     :redemption     #{:redemptionPeriod :pendingDelete}
                     :pending-restore #{:pendingRestore :pendingDelete}
                     :pending-delete #{:pendingDelete}
                     #{})
        from-transfer (when (:domain/transfer domain) #{:pendingTransfer})]
    (status/normalize
     (into (set (:domain/statuses domain)) (concat from-grace from-phase from-transfer))
     {:nameservers (:domain/nameservers domain)})))

(defn- guard
  "Refuse `op` if the effective status set prohibits it, naming the statuses
  that did it."
  [domain op now]
  (let [st (effective-statuses domain now)
        blockers (status/blocking st op)]
    (when (seq blockers)
      (fail (codes :status-prohibits)
            (str "Object status prohibits operation: "
                 (str/join ", " (map name blockers)))
            {:error/statuses (vec blockers)}))))

;; ── create ────────────────────────────────────────────────────────────────

(defn create
  "Allocate a name. `existing` is the current record for this name or nil —
  passing it in rather than consulting a store keeps this function pure and
  lets the caller decide what \"exists\" means (a purged record does not).

  A name in `redemption`, `pending-restore` or `pending-delete` is *not*
  available: that is the entire point of those phases, and a registry that
  allows a create there has reintroduced the drop-catching hole RGP closed."
  [existing policy {:keys [name registrar registrant years nameservers auth-info]} now]
  (let [years (or years 1)
        max-y (days policy :policy/max-term-years)]
    (cond
      (and existing (not= :purged (:domain/phase existing)))
      (fail (codes :object-exists) (str "Object exists: " name))

      (or (not (pos-int? years)) (> years max-y))
      (fail (codes :parameter-value-range)
            (str "Registration period must be 1-" max-y " years"))

      (or (nil? registrar) (nil? name))
      (fail (codes :parameter-value-policy) "name and registrar are required")

      :else
      (let [expires (t/plus-years now years)
            d {:domain/name name
               :domain/phase :active
               :domain/registrar registrar
               :domain/registrant registrant
               :domain/statuses #{}
               :domain/nameservers (vec nameservers)
               :domain/auth-info auth-info
               :domain/created-at now
               :domain/updated-at now
               :domain/expires-at expires
               :domain/phase-entered-at now
               :domain/transferred-at nil
               :domain/transfer nil
               :domain/grace []}
            d (add-grace d :add now (t/plus-days now (days policy :policy/add-grace-days)))]
        (ok d [(event :domain/created d now {:event/years years
                                             :event/expires-at expires
                                             :event/billable :create})])))))

;; ── renew ─────────────────────────────────────────────────────────────────

(defn renew
  "Extend the registration.

  `current-expires-at` is RFC 5731 §3.2.3's `curExpDate`, and it is required
  rather than optional. The RFC makes it mandatory for a reason that reads as
  pedantry until it happens: a registrar retrying a renew it never saw
  acknowledged, against a registry that already applied it, renews twice and
  bills the registrant twice. Matching the caller's view of the expiry against
  the registry's turns that retry into a no-op error instead of a second year.
  Passing `nil` skips the check, which is a choice a caller has to make
  explicitly.

  The comparison is at **day** granularity, because `curExpDate` is an
  `xs:date` on the wire (RFC 5731 §3.2.3) and carries no time of day. Comparing
  epoch milliseconds would reject every well-formed renew whose registry expiry
  happens to fall at 12:00 rather than midnight — the check would then be
  rejecting valid commands rather than duplicate ones, which is worse than not
  having it."
  [domain policy {:keys [years current-expires-at]} now]
  (let [years (or years 1)
        max-y (days policy :policy/max-term-years)]
    (or
     (guard domain :renew now)
     (cond
       (not (pos-int? years))
       (fail (codes :parameter-value-range) "Renewal period must be a positive number of years")

       (and current-expires-at
            (not= (t/same-day? current-expires-at (:domain/expires-at domain)) true))
       (fail (codes :parameter-value-policy)
             (str "curExpDate does not match registry expiry ("
                  (t/iso8601 (:domain/expires-at domain)) ")")
             {:error/expected (:domain/expires-at domain)})

       :else
       (let [expires (t/plus-years (:domain/expires-at domain) years)]
         (if (> expires (t/plus-years now max-y))
           (fail (codes :parameter-value-policy)
                 (str "Renewal would exceed the maximum " max-y "-year term"))
           (let [d (-> domain
                       (assoc :domain/expires-at expires :domain/updated-at now)
                       (add-grace :renew now (t/plus-days now (days policy :policy/renew-grace-days))))]
             (ok d [(event :domain/renewed d now {:event/years years
                                                  :event/expires-at expires
                                                  :event/billable :renew})]))))))))

;; ── delete / restore ──────────────────────────────────────────────────────

(defn delete
  "Request deletion.

  Inside the add grace period the name is purged immediately and the create is
  refunded — that is what AGP is (RFC 3915 §3.1.1). Outside it, the name enters
  redemption and stays reachable-but-dark for 30 days so the registrant can get
  it back. Collapsing the two would either make every mistaken registration
  unrefundable or make every deletion instantly droppable."
  [domain policy now]
  (or
   (guard domain :delete now)
   (if (in-grace? domain :add now)
     (let [d (assoc domain :domain/phase :purged :domain/phase-entered-at now
                    :domain/updated-at now :domain/grace [])]
       (ok d [(event :domain/deleted d now {:event/within-grace :add
                                            :event/refundable? true
                                            :event/billable :delete-refund})
              (event :domain/purged d now {:event/reason :add-grace-delete})]))
     (let [refund (refundable? domain now)
           d (assoc domain :domain/phase :redemption :domain/phase-entered-at now
                    :domain/updated-at now :domain/transfer nil)]
       (ok d [(event :domain/deleted d now
                     (cond-> {:event/refundable? (boolean refund)
                              :event/redemption-ends-at
                              (t/plus-days now (days policy :policy/redemption-days))}
                       refund (assoc :event/within-grace refund
                                     :event/billable :delete-refund)))])))))

(defn restore
  "Request restoration out of redemption (RFC 3915 §4.1). The domain moves to
  `pendingRestore` and stays dark until the restore *report* arrives — the
  report is what makes RGP restoration an accountable act rather than an undo
  button, so the two steps stay separate here."
  [domain policy now]
  (cond
    (not= :redemption (:domain/phase domain))
    (fail (codes :status-prohibits)
          (str "Only a domain in redemptionPeriod may be restored (phase: "
               (name (:domain/phase domain)) ")"))
    :else
    (let [d (assoc domain :domain/phase :pending-restore :domain/phase-entered-at now
                   :domain/updated-at now)]
      (ok d [(event :domain/restore-requested d now
                    {:event/report-due-at (t/plus-days now (days policy :policy/restore-report-days))
                     :event/billable :restore})]))))

(defn restore-report
  "File the RFC 3915 §4.2 restore report. This is the step that actually brings
  the name back."
  [domain _policy now]
  (cond
    (not= :pending-restore (:domain/phase domain))
    (fail (codes :status-prohibits) "No restore is pending for this domain")
    :else
    (let [d (assoc domain :domain/phase :active :domain/phase-entered-at now
                   :domain/updated-at now)]
      (ok d [(event :domain/restored d now {})]))))

;; ── transfer ──────────────────────────────────────────────────────────────

(defn- transfer-locked-until
  "The instant after which a transfer is permitted, per the ICANN Transfer
  Policy's two 60-day windows. Returns nil when unlocked."
  [domain policy]
  (let [after-create (t/plus-days (:domain/created-at domain)
                                  (days policy :policy/lock-after-create-days))
        after-xfer (some-> (:domain/transferred-at domain)
                           (t/plus-days (days policy :policy/lock-after-transfer-days)))]
    (apply max (keep identity [after-create after-xfer]))))

(defn transfer-request
  "A gaining registrar requests the transfer. `auth-info` must match the
  domain's — that shared secret is the registrant's consent, and checking it
  here rather than at the protocol edge means no front end can skip it."
  [domain policy {:keys [gaining-registrar auth-info years]} now]
  (or
   (guard domain :transfer now)
   (let [unlock (transfer-locked-until domain policy)]
     (cond
       (:domain/transfer domain)
       (fail (codes :object-pending-transfer) "A transfer is already pending for this domain")

       (= gaining-registrar (:domain/registrar domain))
       (fail (codes :parameter-value-policy)
             "Gaining registrar is already the sponsoring registrar")

       (not= auth-info (:domain/auth-info domain))
       (fail (codes :authorization-error) "Authorization information does not match")

       (and unlock (< now unlock))
       (fail (codes :status-prohibits)
             (str "Transfer is locked until " (t/iso8601 unlock))
             {:error/unlocks-at unlock})

       :else
       (let [auto-at (t/plus-days now (days policy :policy/transfer-auto-approve-days))
             d (assoc domain :domain/updated-at now
                      :domain/transfer {:transfer/gaining-registrar gaining-registrar
                                        :transfer/losing-registrar (:domain/registrar domain)
                                        :transfer/requested-at now
                                        :transfer/auto-approve-at auto-at
                                        :transfer/years (or years 1)})]
         (ok d [(event :domain/transfer-requested d now
                       {:event/gaining-registrar gaining-registrar
                        :event/auto-approve-at auto-at})]))))))

(defn- complete-transfer [domain policy now how]
  (let [{:transfer/keys [gaining-registrar years]} (:domain/transfer domain)
        expires (t/plus-years (:domain/expires-at domain) (or years 1))
        d (-> domain
              (assoc :domain/registrar gaining-registrar
                     :domain/expires-at expires
                     :domain/transferred-at now
                     :domain/updated-at now
                     :domain/transfer nil)
              (add-grace :transfer now
                         (t/plus-days now (days policy :policy/transfer-grace-days))))]
    (ok d [(event :domain/transferred d now
                  {:event/gaining-registrar gaining-registrar
                   :event/how how
                   :event/expires-at expires
                   :event/billable :transfer})])))

(defn transfer-approve
  "The losing registrar approves (RFC 5731 §3.2.4). A transfer adds a year to
  the term — that is protocol, not policy, and it is why `expires-at` moves
  here as well as in `renew`."
  [domain policy now]
  (if-not (:domain/transfer domain)
    (fail (codes :object-not-pending-transfer) "No transfer is pending for this domain")
    (complete-transfer domain policy now :approved)))

(defn transfer-reject
  "The losing registrar rejects. The domain stays where it is; the 60-day locks
  are untouched, because nothing transferred."
  [domain _policy now]
  (if-not (:domain/transfer domain)
    (fail (codes :object-not-pending-transfer) "No transfer is pending for this domain")
    (let [gaining (get-in domain [:domain/transfer :transfer/gaining-registrar])
          d (assoc domain :domain/transfer nil :domain/updated-at now)]
      (ok d [(event :domain/transfer-rejected d now {:event/gaining-registrar gaining})]))))

(defn transfer-cancel
  "The gaining registrar withdraws its own request."
  [domain _policy now]
  (if-not (:domain/transfer domain)
    (fail (codes :object-not-pending-transfer) "No transfer is pending for this domain")
    (let [gaining (get-in domain [:domain/transfer :transfer/gaining-registrar])
          d (assoc domain :domain/transfer nil :domain/updated-at now)]
      (ok d [(event :domain/transfer-cancelled d now {:event/gaining-registrar gaining})]))))

;; ── update ────────────────────────────────────────────────────────────────

(defn update-domain
  "Apply an EPP update (RFC 5731 §3.2.5): add/remove statuses and nameservers,
  change the registrant or authInfo.

  Only `client*` statuses may be added or removed through this door.
  `server*` statuses are the registry's, and a registrar that could clear
  `serverTransferProhibited` would be able to unlock a domain the registry
  locked — which is the one thing that lock exists to prevent."
  [domain _policy {:keys [add-statuses remove-statuses nameservers registrant auth-info]} now]
  (or
   (guard domain :update now)
   (let [bad (remove status/client-settable? (concat add-statuses remove-statuses))]
     (if (seq bad)
       (fail (codes :authorization-error)
             (str "Only client-settable statuses may be changed by the registrar: "
                  (str/join ", " (map name bad))))
       (let [d (cond-> domain
                 true (update :domain/statuses
                              #(-> (set %) (into add-statuses)
                                   (as-> s (apply disj s remove-statuses))))
                 (some? nameservers) (assoc :domain/nameservers (vec nameservers))
                 (some? registrant)  (assoc :domain/registrant registrant)
                 (some? auth-info)   (assoc :domain/auth-info auth-info)
                 true (assoc :domain/updated-at now))]
         (ok d [(event :domain/updated d now {})]))))))

;; ── time-driven transitions ───────────────────────────────────────────────

(defn- next-transition
  "The single earliest transition due at or before `now`, or nil. Returning one
  at a time is what lets `advance` emit every intermediate event for a domain
  nobody touched for two years, instead of collapsing to the final state."
  [domain policy now]
  (let [phase (:domain/phase domain)
        entered (:domain/phase-entered-at domain)]
    (cond
      (and (:domain/transfer domain)
           (<= (get-in domain [:domain/transfer :transfer/auto-approve-at]) now))
      [:transfer-auto-approve (get-in domain [:domain/transfer :transfer/auto-approve-at])]

      (and (= phase :active)
           (get policy :policy/auto-renew? (:policy/auto-renew? default-policy))
           (<= (:domain/expires-at domain) now))
      [:auto-renew (:domain/expires-at domain)]

      (and (= phase :redemption)
           (<= (t/plus-days entered (days policy :policy/redemption-days)) now))
      [:redemption-expired (t/plus-days entered (days policy :policy/redemption-days))]

      (and (= phase :pending-restore)
           (<= (t/plus-days entered (days policy :policy/restore-report-days)) now))
      [:restore-report-missed (t/plus-days entered (days policy :policy/restore-report-days))]

      (and (= phase :pending-delete)
           (<= (t/plus-days entered (days policy :policy/pending-delete-days)) now))
      [:purge (t/plus-days entered (days policy :policy/pending-delete-days))]

      :else nil)))

(defn- apply-transition [domain policy [kind at]]
  (case kind
    :transfer-auto-approve
    (complete-transfer domain policy at :auto-approved)

    :auto-renew
    (let [expires (t/plus-years (:domain/expires-at domain) 1)
          d (-> domain
                (assoc :domain/expires-at expires)
                (add-grace :auto-renew at
                           (t/plus-days at (days policy :policy/auto-renew-grace-days))))]
      (ok d [(event :domain/auto-renewed d at {:event/years 1
                                               :event/expires-at expires
                                               :event/billable :auto-renew})]))

    :redemption-expired
    (let [d (assoc domain :domain/phase :pending-delete :domain/phase-entered-at at)]
      (ok d [(event :domain/pending-delete d at {})]))

    ;; A restore was requested but the report never came. RFC 3915 §4.2 puts
    ;; the domain back where it was — it does not grant the restore, and it
    ;; does not accelerate the delete. The remaining redemption clock restarts,
    ;; which is the lenient reading; a registry wanting the strict one should
    ;; override this rather than have it be silent either way.
    :restore-report-missed
    (let [d (assoc domain :domain/phase :redemption :domain/phase-entered-at at)]
      (ok d [(event :domain/restore-expired d at {})]))

    :purge
    (let [d (assoc domain :domain/phase :purged :domain/phase-entered-at at
                   :domain/grace [])]
      (ok d [(event :domain/purged d at {:event/reason :pending-delete-elapsed})]))))

(defn advance
  "Apply every transition due at or before `now`, in chronological order,
  accumulating the events.

  This is the registry's cron job, made a pure function. `max-steps` is a
  runaway guard, not a policy — a transition that failed to move the clock
  forward would otherwise spin, and a silent infinite loop in the thing that
  deletes domains is not an acceptable failure mode."
  ([domain policy now] (advance domain policy now 64))
  ([domain policy now max-steps]
   (loop [d domain, evs [], n 0]
     (if-let [tr (and (< n max-steps) (next-transition d policy now))]
       (let [{:keys [domain events]} (apply-transition d policy tr)]
         (recur domain (into evs events) (inc n)))
       {:ok? true :domain d :events evs}))))

(defn available?
  "May this name be allocated at `now`? `nil` (never registered) and `:purged`
  are the only two answers that mean yes."
  [domain]
  (or (nil? domain) (= :purged (:domain/phase domain))))
