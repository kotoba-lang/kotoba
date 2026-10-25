(ns kakeibo.accounting
  "Pure contracts for multi-entity accounting and immutable journals."
  (:require [kotoba.banking :as banking]))

(def entity-kinds #{:person :corporation})
(def account-types #{:asset :liability :equity :revenue :expense})

(defn problems
  "Return deterministic validation problems for an accounting aggregate."
  [{:accounting/keys [entities periods accounts journals]}]
  (let [entity-ids (set (map :entity/id entities))
        period-ids (set (map :period/id periods))
        account-ids (set (map :account/id accounts))]
    (vec
     (concat
      (for [{:entity/keys [id kind]} entities
            :when (or (nil? id) (not (contains? entity-kinds kind)))]
        {:problem/type :invalid-entity :problem/id id})
      (for [{:period/keys [id entity start end]} periods
            :when (or (nil? id) (not (contains? entity-ids entity))
                      (nil? start) (nil? end) (pos? (compare start end)))]
        {:problem/type :invalid-period :problem/id id})
      (for [{:account/keys [id entity type currency]} accounts
            :when (or (nil? id) (not (contains? entity-ids entity))
                      (not (contains? account-types type)) (nil? currency))]
        {:problem/type :invalid-account :problem/id id})
      (for [{:journal/keys [id entity period posting provenance]} journals
            :let [entries (:ledger/entries posting)]
            :when (or (nil? id) (not (contains? entity-ids entity))
                      (not (contains? period-ids period))
                      (not (true? (:ledger/balanced? posting)))
                      (empty? entries)
                      (some #(not (contains? account-ids (:ledger/account %))) entries)
                      (nil? (:provenance/recorded-at provenance))
                      (nil? (:provenance/actor provenance)))]
        {:problem/type :invalid-journal :problem/id id})))))

(defn valid? [accounting]
  (empty? (problems accounting)))

(defn journal
  "Create an immutable journal value around a banking balanced posting."
  [{:keys [id entity period date entries memo provenance evidence valuation corrects]}]
  (cond
    (or (nil? id) (nil? entity) (nil? period) (nil? date))
    {:accounting/problem :missing-journal-identity}

    (or (empty? entries)
        (some #(not (integer? (:ledger/amount %))) entries))
    {:accounting/problem :invalid-minor-units}

    (or (nil? (:provenance/recorded-at provenance))
        (nil? (:provenance/actor provenance)))
    {:accounting/problem :missing-provenance}

    (and valuation
         (or (nil? (:valuation/source valuation))
             (nil? (:valuation/observed-at valuation))
             (nil? (:valuation/quote-currency valuation))))
    {:accounting/problem :incomplete-valuation-provenance}

    :else
    (let [posting (banking/posting id entries :memo memo)]
      (if-not (:ledger/balanced? posting)
        {:accounting/problem :unbalanced-journal}
        {:accounting/journal
         (cond-> {:journal/id id
                  :journal/entity entity
                  :journal/period period
                  :journal/date date
                  :journal/posting posting
                  :journal/provenance provenance
                  :journal/evidence (vec (or evidence []))}
           corrects (assoc :journal/corrects corrects)
           valuation (assoc :journal/valuation valuation))}))))

(defn append-journal
  "Append without rewriting history; reject duplicate ids and closed periods."
  [accounting journal]
  (let [journals (:accounting/journals accounting)
        journal-ids (set (map :journal/id journals))
        period (some #(when (= (:period/id %) (:journal/period journal)) %)
                     (:accounting/periods accounting))]
    (cond
      (contains? journal-ids (:journal/id journal))
      {:accounting/problem :duplicate-journal-id}

      (= :closed (:period/status period))
      {:accounting/problem :period-closed}

      (and (:journal/corrects journal)
           (not (contains? journal-ids (:journal/corrects journal))))
      {:accounting/problem :unknown-corrected-journal}

      :else
      {:accounting/value
       (update accounting :accounting/journals (fnil conj []) journal)})))
