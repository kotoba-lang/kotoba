(ns kakeibo.domain
  "Multi-entity accounting domain and immutable journal contract.

  Foundation for Itonami Kaikei: personal and corporate entities, fiscal
  periods, chart of accounts, append-only journals, currencies/crypto with
  valuation provenance, evidence links, and correction entries. Amounts are
  exact minor-unit integers. Balanced postings reuse `kotoba.banking`.

  Pure: no clock, no filesystem, no network, no model. No provider
  credentials and no customer data belong in this namespace or its tests —
  fixtures use invented identifiers only."
  (:require [kotoba.banking :as banking]))

;; ---------------------------------------------------------------------------
;; Shared helpers
;; ---------------------------------------------------------------------------

(def ^:private entity-types #{:personal :corporate})
(def ^:private period-statuses #{:open :closed})
(def ^:private account-types #{:asset :liability :equity :revenue :expense})
(def ^:private normal-sides #{:debit :credit})
(def ^:private journal-statuses #{:proposed :posted :voided})
(def ^:private asset-kinds #{:fiat :crypto})
(def ^:private valuation-sources #{:manual :oracle :exchange :unobserved})

(def account-type->normal-side
  "Default normal balance side for each account type (accounting equation)."
  {:asset     :debit
   :liability :credit
   :equity    :credit
   :revenue   :credit
   :expense   :debit})

(defn- blank-str? [s]
  (or (nil? s) (and (string? s) (empty? (str s)))))

(defn- iso-date? [s]
  (boolean (and (string? s)
                (re-matches #"\d{4}-\d{2}-\d{2}" s))))

(defn- positive-int? [n]
  (and (integer? n) (pos? n)))

(defn- non-neg-int? [n]
  (and (integer? n) (not (neg? n))))

;; ---------------------------------------------------------------------------
;; Entity model
;; ---------------------------------------------------------------------------

(defn entity
  "Construct a personal or corporate accounting entity.

  Returns `{:entity/...}` or `{:kakeibo/problems [...]}`. The base currency
  is the entity's reporting currency; multi-currency and crypto amounts
  convert into it only through explicit valuation records with provenance."
  [id type base-currency & {:keys [name fiscal-year-start]}]
  (let [problems (cond-> []
                   (blank-str? id) (conj :missing-entity-id)
                   (not (contains? entity-types type)) (conj :unsupported-entity-type)
                   (blank-str? base-currency) (conj :missing-base-currency)
                   (and (some? fiscal-year-start)
                        (or (not (map? fiscal-year-start))
                            (not (positive-int? (:month fiscal-year-start)))
                            (not (positive-int? (:day fiscal-year-start)))
                            (> (:month fiscal-year-start) 12)
                            (> (:day fiscal-year-start) 31)))
                   (conj :invalid-fiscal-year-start))]
    (if (seq problems)
      {:kakeibo/problems problems}
      (cond-> {:entity/id             id
               :entity/type           type
               :entity/base-currency  base-currency}
        name (assoc :entity/name name)
        fiscal-year-start (assoc :entity/fiscal-year-start fiscal-year-start)))))

;; ---------------------------------------------------------------------------
;; Fiscal periods
;; ---------------------------------------------------------------------------

(defn fiscal-period
  "Construct a fiscal period for an entity.

  Periods are half-open on the calendar only by convention of their ISO
  bounds; validity of day-of-month is not calendar-checked here (same rule
  as statement date parsing). Status is `:open` until an explicit close."
  [id entity-id start end & {:keys [status]}]
  (let [st (or status :open)
        problems (cond-> []
                   (blank-str? id) (conj :missing-period-id)
                   (blank-str? entity-id) (conj :missing-entity-id)
                   (not (iso-date? start)) (conj :invalid-period-start)
                   (not (iso-date? end)) (conj :invalid-period-end)
                   (and (iso-date? start) (iso-date? end) (pos? (compare start end)))
                   (conj :period-start-after-end)
                   (not (contains? period-statuses st)) (conj :unsupported-period-status))]
    (if (seq problems)
      {:kakeibo/problems problems}
      {:period/id        id
       :period/entity    entity-id
       :period/start     start
       :period/end       end
       :period/status    st})))

(defn close-period
  "Return a closed copy of an open period. Already-closed periods refuse."
  [period]
  (cond
    (nil? period) {:kakeibo/problems [:missing-period]}
    (= :closed (:period/status period))
    {:kakeibo/problems [:period-already-closed] :kakeibo/period period}
    :else (assoc period :period/status :closed)))

(defn date-in-period?
  "True when an ISO date falls within the period inclusive bounds."
  [period iso-date]
  (and (iso-date? iso-date)
       (string? (:period/start period))
       (string? (:period/end period))
       (not (neg? (compare iso-date (:period/start period))))
       (not (pos? (compare iso-date (:period/end period))))))

;; ---------------------------------------------------------------------------
;; Chart of accounts
;; ---------------------------------------------------------------------------

(defn coa-account
  "Construct one chart-of-accounts line for an entity.

  `type` selects the normal side when `:normal-side` is omitted. Parent is an
  optional account id for hierarchies; the domain does not require a tree to
  post — flat COAs are valid."
  [id entity-id code type & {:keys [name normal-side currency parent]}]
  (let [ns (or normal-side (get account-type->normal-side type))
        problems (cond-> []
                   (blank-str? id) (conj :missing-account-id)
                   (blank-str? entity-id) (conj :missing-entity-id)
                   (blank-str? code) (conj :missing-account-code)
                   (not (contains? account-types type)) (conj :unsupported-account-type)
                   (not (contains? normal-sides ns)) (conj :unsupported-normal-side)
                   (and (some? normal-side)
                        (not= normal-side (get account-type->normal-side type)))
                   (conj :normal-side-mismatches-type))]
    (if (seq problems)
      {:kakeibo/problems problems}
      (cond-> {:account/id      id
               :account/entity  entity-id
               :account/code    code
               :account/type    type
               :account/normal-side ns}
        name (assoc :account/name name)
        currency (assoc :account/currency currency)
        parent (assoc :account/parent parent)))))

(defn chart-of-accounts
  "Validate and index a sequence of COA accounts for one entity.

  Returns `{:coa/entity id :coa/accounts {account-id account} :coa/by-code {...}}`
  or problems when ids/codes collide or entities mix."
  [entity-id accounts]
  (let [built (mapv (fn [a]
                      (if (:kakeibo/problems a)
                        a
                        a))
                    accounts)
        problems-from-rows (vec (mapcat :kakeibo/problems built))
        ok (filterv #(and (map? %) (not (:kakeibo/problems %)) (:account/id %)) built)
        ids (mapv :account/id ok)
        codes (mapv :account/code ok)
        foreign (filterv #(not= entity-id (:account/entity %)) ok)
        problems (cond-> problems-from-rows
                   (blank-str? entity-id) (conj :missing-entity-id)
                   (not= (count ids) (count (set ids))) (conj :duplicate-account-id)
                   (not= (count codes) (count (set codes))) (conj :duplicate-account-code)
                   (seq foreign) (conj :mixed-entity-accounts))]
    (if (seq problems)
      {:kakeibo/problems (vec (distinct problems))}
      {:coa/entity   entity-id
       :coa/accounts (into {} (map (juxt :account/id identity)) ok)
       :coa/by-code  (into {} (map (juxt :account/code identity)) ok)})))

;; ---------------------------------------------------------------------------
;; Currency and crypto valuation provenance
;; ---------------------------------------------------------------------------

(defn asset-ref
  "Reference to a fiat currency or crypto asset with its minor-unit scale.

  Fiat JPY uses scale 1; USD scale 100; BTC commonly scale 100_000_000
  (satoshi). Scale must be a supported power of ten for fiat-style subunits,
  or any positive integer for crypto base units the caller declares."
  [kind code scale]
  (let [problems (cond-> []
                   (not (contains? asset-kinds kind)) (conj :unsupported-asset-kind)
                   (blank-str? code) (conj :missing-asset-code)
                   (not (positive-int? scale)) (conj :invalid-asset-scale))]
    (if (seq problems)
      {:kakeibo/problems problems}
      {:asset/kind  kind
       :asset/code  code
       :asset/scale scale})))

(defn valuation
  "Record how an asset quantity was valued into a quote currency.

  All money fields are integers (exact minor units). A missing or
  `:unobserved` source is allowed for draft work but must not be treated as
  a settled rate — callers that post journals should require a concrete
  source. Unknown production market impact is never invented here."
  [{:keys [quantity asset quote-currency quote-minor rate-source as-of]
    :as m}]
  (let [asset* (if (and (map? asset) (not (:kakeibo/problems asset)))
                 asset
                 (when (map? asset) asset))
        problems (cond-> (or (:kakeibo/problems asset) [])
                   (not (integer? quantity)) (conj :missing-quantity)
                   (or (nil? asset*) (:kakeibo/problems asset))
                   (conj :missing-asset)
                   (blank-str? quote-currency) (conj :missing-quote-currency)
                   (not (integer? quote-minor)) (conj :missing-quote-minor)
                   (not (contains? valuation-sources rate-source))
                   (conj :unsupported-rate-source)
                   (not (iso-date? as-of)) (conj :invalid-valuation-as-of))]
    (if (seq problems)
      {:kakeibo/problems (vec (distinct problems))}
      {:valuation/quantity       quantity
       :valuation/asset          asset*
       :valuation/quote-currency quote-currency
       :valuation/quote-minor    quote-minor
       :valuation/rate-source    rate-source
       :valuation/as-of          as-of})))

;; ---------------------------------------------------------------------------
;; Evidence and provenance
;; ---------------------------------------------------------------------------

(defn evidence
  "Link supporting material by content hash only — never by raw payload.

  Kind is free-form but recommended: `:receipt`, `:invoice`, `:statement`,
  `:contract`. Hash should be a stable hex/digest string the host computed."
  [hash kind & {:keys [memo]}]
  (let [problems (cond-> []
                   (blank-str? hash) (conj :missing-evidence-hash)
                   (nil? kind) (conj :missing-evidence-kind))]
    (if (seq problems)
      {:kakeibo/problems problems}
      (cond-> {:evidence/hash hash
               :evidence/kind kind}
        memo (assoc :evidence/memo memo)))))

(defn provenance
  "Audit trail metadata for a journal event.

  `source` is one of `:manual`, `:ingest`, `:correction`, `:closing`.
  `actor` is an opaque operator/agent id — never a credential."
  [source & {:keys [actor note supersedes]}]
  (let [allowed #{:manual :ingest :correction :closing}
        problems (cond-> []
                   (not (contains? allowed source)) (conj :unsupported-provenance-source))]
    (if (seq problems)
      {:kakeibo/problems problems}
      (cond-> {:provenance/source source}
        actor (assoc :provenance/actor actor)
        note (assoc :provenance/note note)
        supersedes (assoc :provenance/supersedes supersedes)))))

;; ---------------------------------------------------------------------------
;; Immutable journal
;; ---------------------------------------------------------------------------

(defn- entry-account-ids [posting]
  (into #{} (map :ledger/account) (:ledger/entries posting)))

(defn- coa-covers-posting? [coa posting]
  (let [accounts (:coa/accounts coa)]
    (every? #(contains? accounts %) (entry-account-ids posting))))

(defn journal-entry
  "Propose one journal entry bound to entity, period, date, and a balanced
  banking posting.

  Does not mutate any store. Returns `{:journal/...}` or problems. Status
  defaults to `:proposed`. Evidence and valuation are optional; corrections
  carry provenance that names the superseded entry id."
  [{:keys [id entity-id period-id date posting memo evidence provenance
           valuation status]
    :as m}]
  (let [st (or status :proposed)
        problems (cond-> []
                   (blank-str? id) (conj :missing-journal-id)
                   (blank-str? entity-id) (conj :missing-entity-id)
                   (blank-str? period-id) (conj :missing-period-id)
                   (not (iso-date? date)) (conj :invalid-journal-date)
                   (nil? posting) (conj :missing-posting)
                   (and (some? posting) (not (:ledger/balanced? posting)))
                   (conj :unbalanced-posting)
                   (and (some? posting) (empty? (:ledger/entries posting)))
                   (conj :empty-posting)
                   (not (contains? journal-statuses st)) (conj :unsupported-journal-status)
                   (and (some? evidence)
                        (not (every? #(and (map? %) (:evidence/hash %)) evidence)))
                   (conj :invalid-evidence)
                   (and (some? provenance) (:kakeibo/problems provenance))
                   (conj :invalid-provenance)
                   (and (some? valuation) (:kakeibo/problems valuation))
                   (conj :invalid-valuation))]
    (if (seq problems)
      {:kakeibo/problems problems}
      (cond-> {:journal/id       id
               :journal/entity   entity-id
               :journal/period   period-id
               :journal/date     date
               :journal/posting  posting
               :journal/status   st}
        memo (assoc :journal/memo memo)
        (seq evidence) (assoc :journal/evidence (vec evidence))
        provenance (assoc :journal/provenance provenance)
        valuation (assoc :journal/valuation valuation)))))

(defn empty-journal
  "Append-only journal log for one entity. The log itself is a vector; the
  only legal writes are `append-entry` and `post-entry` / `void-via-correction`."
  [entity-id]
  (if (blank-str? entity-id)
    {:kakeibo/problems [:missing-entity-id]}
    {:journal-log/entity entity-id
     :journal-log/entries []
     :journal-log/by-id {}}))

(defn- log-ok? [log]
  (and (map? log)
       (not (:kakeibo/problems log))
       (vector? (:journal-log/entries log))
       (map? (:journal-log/by-id log))))

(defn append-entry
  "Append a proposed journal entry to the log.

  Refuses when: entry belongs to another entity, id already exists, period is
  closed, date is outside the period, COA does not cover posting accounts, or
  the entry is not `:proposed`. The previous log vector is never mutated —
  a new log map is returned."
  [log entry period coa]
  (cond
    (not (log-ok? log))
    {:kakeibo/problems [:invalid-journal-log]}

    (:kakeibo/problems entry)
    entry

    (not= (:journal-log/entity log) (:journal/entity entry))
    {:kakeibo/problems [:entity-mismatch] :kakeibo/entry entry}

    (contains? (:journal-log/by-id log) (:journal/id entry))
    {:kakeibo/problems [:duplicate-journal-id] :kakeibo/entry entry}

    (not= :proposed (:journal/status entry))
    {:kakeibo/problems [:append-requires-proposed] :kakeibo/entry entry}

    (nil? period)
    {:kakeibo/problems [:missing-period]}

    (not= (:period/id period) (:journal/period entry))
    {:kakeibo/problems [:period-mismatch] :kakeibo/entry entry}

    (not= (:period/entity period) (:journal/entity entry))
    {:kakeibo/problems [:period-entity-mismatch] :kakeibo/entry entry}

    (= :closed (:period/status period))
    {:kakeibo/problems [:period-closed] :kakeibo/entry entry}

    (not (date-in-period? period (:journal/date entry)))
    {:kakeibo/problems [:date-outside-period] :kakeibo/entry entry}

    (and (some? coa)
         (not= (:coa/entity coa) (:journal/entity entry)))
    {:kakeibo/problems [:coa-entity-mismatch] :kakeibo/entry entry}

    (and (some? coa)
         (not (coa-covers-posting? coa (:journal/posting entry))))
    {:kakeibo/problems [:accounts-not-in-coa] :kakeibo/entry entry}

    :else
    (let [id (:journal/id entry)]
      {:journal-log/entity  (:journal-log/entity log)
       :journal-log/entries (conj (:journal-log/entries log) entry)
       :journal-log/by-id   (assoc (:journal-log/by-id log) id entry)})))

(defn post-entry
  "Transition a proposed entry to `:posted`. Posted entries are immutable:
  subsequent edits are refused; only `void-via-correction` may neutralize."
  [log entry-id]
  (let [entry (get-in log [:journal-log/by-id entry-id])]
    (cond
      (not (log-ok? log)) {:kakeibo/problems [:invalid-journal-log]}
      (nil? entry) {:kakeibo/problems [:unknown-journal-id] :journal/id entry-id}
      (= :posted (:journal/status entry))
      {:kakeibo/problems [:already-posted] :kakeibo/entry entry}
      (= :voided (:journal/status entry))
      {:kakeibo/problems [:already-voided] :kakeibo/entry entry}
      (not= :proposed (:journal/status entry))
      {:kakeibo/problems [:not-proposed] :kakeibo/entry entry}
      :else
      (let [posted (assoc entry :journal/status :posted)
            entries (mapv (fn [e]
                            (if (= entry-id (:journal/id e)) posted e))
                          (:journal-log/entries log))]
        {:journal-log/entity  (:journal-log/entity log)
         :journal-log/entries entries
         :journal-log/by-id   (assoc (:journal-log/by-id log) entry-id posted)}))))

(defn- reverse-entries [entries]
  (mapv (fn [e]
          (assoc e :ledger/side (if (= :debit (:ledger/side e)) :credit :debit)))
        entries))

(defn void-via-correction
  "Neutralize a posted entry by appending a reversing correction.

  The original stays `:posted` with an immutable body; a new `:posted`
  correction entry is appended with provenance `:correction` and
  `:provenance/supersedes` pointing at the original. Direct mutation of the
  original is never performed — that is the immutability contract."
  [log original-id correction-id period coa & {:keys [actor note date]}]
  (let [original (get-in log [:journal-log/by-id original-id])]
    (cond
      (not (log-ok? log)) {:kakeibo/problems [:invalid-journal-log]}
      (nil? original) {:kakeibo/problems [:unknown-journal-id] :journal/id original-id}
      (not= :posted (:journal/status original))
      {:kakeibo/problems [:correction-requires-posted] :kakeibo/entry original}
      (contains? (:journal-log/by-id log) correction-id)
      {:kakeibo/problems [:duplicate-journal-id]}
      :else
      (let [orig-posting (:journal/posting original)
            rev-entries (reverse-entries (:ledger/entries orig-posting))
            rev-posting (banking/posting correction-id rev-entries
                                         :memo (str "correction of " original-id))
            prov (provenance :correction
                             :actor actor
                             :note note
                             :supersedes original-id)
            correction (journal-entry
                        {:id correction-id
                         :entity-id (:journal/entity original)
                         :period-id (:journal/period original)
                         :date (or date (:journal/date original))
                         :posting rev-posting
                         :memo (str "void/correct " original-id)
                         :provenance prov
                         :status :proposed})
            appended (append-entry log correction period coa)]
        (if (:kakeibo/problems appended)
          appended
          (post-entry appended correction-id))))))

;; ---------------------------------------------------------------------------
;; Trial balance / accounting equation (over posted movement)
;; ---------------------------------------------------------------------------

(defn- side-sign [account-type side amount]
  ;; Net asset-like: debit positive; liability/equity/revenue: credit positive
  (let [debit-normal? (contains? #{:asset :expense} account-type)]
    (cond
      debit-normal? (if (= :debit side) amount (- amount))
      :else         (if (= :credit side) amount (- amount)))))

(defn trial-balance
  "Movement trial balance from posted journal entries only.

  Returns `{account-id {:tb/debit n :tb/credit n :tb/net n}}` plus
  `:tb/balanced?` when total debits equal total credits across the set.
  Unobserved accounts are absent — never zero-filled — so \"no postings\"
  does not look like a zero balance."
  [log coa]
  (let [posted (->> (:journal-log/entries log)
                    (filter #(= :posted (:journal/status %))))
        accounts (:coa/accounts coa)
        acc (reduce
             (fn [m entry]
               (reduce
                (fn [m2 le]
                  (let [aid (:ledger/account le)
                        side (:ledger/side le)
                        amt (:ledger/amount le)
                        cur (update-in m2 [aid side] (fnil + 0) amt)]
                    cur))
                m
                (:ledger/entries (:journal/posting entry))))
             {}
             posted)
        rows (into {}
                   (map (fn [[aid sides]]
                          (let [d (long (or (:debit sides) 0))
                                c (long (or (:credit sides) 0))
                                atype (get-in accounts [aid :account/type])]
                            [aid {:tb/debit d
                                  :tb/credit c
                                  :tb/net (- d c)
                                  :tb/account-type atype}])))
                   acc)
        total-d (reduce + 0 (map :tb/debit (vals rows)))
        total-c (reduce + 0 (map :tb/credit (vals rows)))]
    {:tb/rows rows
     :tb/total-debit total-d
     :tb/total-credit total-c
     :tb/balanced? (= total-d total-c)}))

(defn accounting-equation
  "Partition trial-balance nets into the accounting equation groups.

  Uses COA account types. Returns
  `{:eq/assets n :eq/liabilities n :eq/equity n :eq/revenue n :eq/expense n
    :eq/holds? bool}` where holds? is assets == liabilities+equity for the
  *balance-sheet slice* after folding revenue/expense into equity (retained
  earnings style): assets ?= liabilities + equity + revenue - expense.

  All values are movement nets (debit-positive for assets/expenses). Empty
  logs yield unobserved (nil) sides rather than zeros."
  [log coa]
  (let [tb (trial-balance log coa)
        rows (:tb/rows tb)]
    (if (empty? rows)
      {:eq/assets nil :eq/liabilities nil :eq/equity nil
       :eq/revenue nil :eq/expense nil :eq/holds? nil :eq/unobserved true}
      (let [sum-type (fn [t]
                       (reduce + 0
                               (keep (fn [[_ row]]
                                       (when (= t (:tb/account-type row))
                                         ;; debit-normal accounts: debit-credit; credit-normal: credit-debit
                                         (let [d (:tb/debit row)
                                               c (:tb/credit row)]
                                           (if (contains? #{:asset :expense} t)
                                             (- d c)
                                             (- c d)))))
                                     rows)))
            assets (sum-type :asset)
            liab (sum-type :liability)
            equity (sum-type :equity)
            revenue (sum-type :revenue)
            expense (sum-type :expense)
            rhs (+ liab equity revenue (- expense))]
        {:eq/assets assets
         :eq/liabilities liab
         :eq/equity equity
         :eq/revenue revenue
         :eq/expense expense
         :eq/holds? (= assets rhs)
         :eq/unobserved false}))))
