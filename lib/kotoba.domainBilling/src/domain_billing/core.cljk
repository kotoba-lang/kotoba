(ns domain-billing.core
  "Billing for domain registrations: a price book, and a fold from `srs` events
  to ledger entries.

  `srs` returns events rather than performing effects, and this is the first
  consumer of that decision. The dependency points one way — this library reads
  `srs` events; `srs` knows nothing about money.

  ## Refund eligibility is not recomputed here

  The one thing a billing layer is most tempted to do, and the one thing it
  must not. Whether a delete is refundable depends on the RFC 3915 grace
  periods, and those are lifecycle policy: `srs.lifecycle/refundable?` already
  answers it, and the answer travels on the event as `:event/refundable?` and
  `:event/within-grace`. A billing layer that recomputed it from dates would be
  a second implementation of the same rule, free to drift — and the direction it
  drifts decides whether registrants get money back.

  So `charge-for` reads the event and never looks at a date.

  ## Money is integer minor units

  Every amount here is an integer count of the currency's minor unit — cents for
  USD, **whole yen for JPY**, which has none. Floating point cannot represent
  `0.1`, so a price book in dollars accumulates error the moment it is summed,
  and the error shows up as an invoice that is off by a cent for reasons nobody
  can reconstruct. `:currency` travels with every amount because a number
  without one is not a price, and mixing two silently is how a ¥1,000 charge
  becomes a $1,000 charge.

  ## What this library does not do

  No payment. No card, no wallet, no gateway, no stored credential. It produces
  ledger entries and a balance; taking money is a deployment's job, and it is a
  regulated one. Keeping the boundary here means this library holds nothing that
  needs a vault."
  (:require [kotoba.lang.text :as str]))

;; ── money ─────────────────────────────────────────────────────────────────

(def minor-units
  "How many minor units make one major unit. JPY has none — a price book that
  assumes 100 everywhere charges a hundred times too little in yen."
  {"USD" 100 "EUR" 100 "GBP" 100 "JPY" 1 "KRW" 1})

(defn money
  [amount currency]
  {:pre [(integer? amount)]}
  {:money/amount amount :money/currency currency})

(defn- same-currency! [a b]
  (when (and a b (not= (:money/currency a) (:money/currency b)))
    (throw (ex-info "cannot combine amounts in different currencies"
                    {:a (:money/currency a) :b (:money/currency b)}))))

(defn add [a b]
  (same-currency! a b)
  (cond (nil? a) b (nil? b) a
        :else (update a :money/amount + (:money/amount b))))

(defn negate [m] (some-> m (update :money/amount -)))

(defn scale
  "Multiply by a whole number of periods. Deliberately integer-only: a
  fractional multiplier would reintroduce rounding, and there is no such thing
  as two and a half years of registration."
  [m n]
  {:pre [(integer? n)]}
  (update m :money/amount * n))

(defn format-money
  "For an invoice line a human reads. Uses the currency's actual minor-unit
  count, so ¥1000 is `JPY 1000` and not `JPY 10.00`."
  [{:money/keys [amount currency]}]
  (let [u (get minor-units currency 100)]
    (if (= 1 u)
      (str currency " " amount)
      (let [neg? (neg? amount)
            a (abs amount)
            digits (dec (count (str u)))
            frac (str (mod a u))
            frac (str (apply str (repeat (max 0 (- digits (count frac))) "0")) frac)]
        (str (when neg? "-") currency " " (quot a u) "." frac)))))

;; ── price book ────────────────────────────────────────────────────────────

(def billable-actions
  "The `:event/billable` values `srs` emits, and what each one is. Kept as data
  so an unpriced action is a detectable gap rather than a silent zero."
  {:create        "New registration"
   :renew         "Renewal"
   :auto-renew    "Automatic renewal at expiry"
   :transfer      "Inbound transfer"
   :restore       "Restore from redemption"
   :delete-refund "Refund for a deletion inside a grace period"})

(defn price-book
  "`{tld {action money}}` plus optional per-TLD fees.

  `:icann-fee` is charged **per registered year** on create, renew, auto-renew
  and transfer — it is a pass-through the registry owes ICANN regardless of what
  it charges the registrar, and folding it into the base price hides a cost that
  changes independently of your own."
  [m]
  m)

(defn price-of
  [book tld action]
  (get-in book [tld action]))

(defn- tld-of [domain-name]
  (let [ls (str/split (str/lower (str domain-name)) #"\.")]
    (when (> (count ls) 1) (last ls))))

(defn- tld-entry
  "The price entry for a name, falling back to a `:default` TLD. Returns nil
  when neither exists — which `charge-for` reports as `:unpriced` rather than
  charging zero."
  [book domain-name]
  (or (get book (tld-of domain-name)) (get book :default)))

;; ── charging ──────────────────────────────────────────────────────────────

(defn charge-for
  "One `srs` event → a ledger entry, or nil for an event that costs nothing.

  Returns `{:entry/kind :charge|:refund|:unpriced …}`. An action with no price
  produces an explicit `:unpriced` entry rather than a zero charge or a dropped
  event: a registry that silently fails to bill for a TLD it just launched
  discovers it at the end of the month."
  [book {:event/keys [kind domain billable at years refundable? within-grace] :as event}]
  (when billable
    (let [entry (tld-entry book domain)
          base (get entry billable)
          n (or years 1)
          icann (:icann-fee entry)]
      (cond
        (nil? entry)
        {:entry/kind :unpriced :entry/event kind :entry/domain domain :entry/at at
         :entry/reason (str "No price book entry for TLD " (pr-str (tld-of domain)))}

        (and (nil? base) (not= billable :delete-refund))
        {:entry/kind :unpriced :entry/event kind :entry/domain domain :entry/at at
         :entry/reason (str "No price for action " billable
                            " in TLD " (pr-str (tld-of domain)))}

        ;; A delete only produces a refund when the lifecycle said so. The
        ;; grace-period question is srs's to answer and is read off the event —
        ;; recomputing it here would be a second implementation free to drift.
        (= billable :delete-refund)
        (if-not refundable?
          nil
          {:entry/kind :refund
           :entry/event kind :entry/domain domain :entry/at at
           :entry/action billable
           :entry/within-grace within-grace
           ;; Refund the base price of whatever the grace period covers. The
           ;; add grace refunds a create; the auto-renew and renew graces refund
           ;; a renewal. Refunding a create for an auto-renew grace delete would
           ;; hand back a year the registrar never paid for.
           :entry/amount (negate
                          (or (get entry (case within-grace
                                           :add :create
                                           :renew :renew
                                           :auto-renew :auto-renew
                                           :transfer :transfer
                                           nil))
                              (money 0 (:money/currency (or base (money 0 "USD"))))))
           :entry/description (str (get billable-actions billable) " (" (name (or within-grace :unknown)) ")")})

        :else
        (let [amount (add (scale base n) (when icann (scale icann n)))]
          {:entry/kind :charge
           :entry/event kind :entry/domain domain :entry/at at
           :entry/action billable
           :entry/years n
           :entry/amount amount
           :entry/icann-fee (when icann (scale icann n))
           :entry/description (str (get billable-actions billable) " — " domain
                                   (when (> n 1) (str " (" n " years)")))})))))

(defn ledger
  "Fold a sequence of `srs` events into ledger entries, in order.

  Order is preserved and never coalesced. A registrar's month is a sequence of
  billable acts, and collapsing two renewals of the same domain into one line
  loses the fact that there were two — which is exactly what a dispute is about."
  [book events]
  (into [] (keep #(charge-for book %)) events))

(defn total
  "Sum a ledger. Refunds are negative entries, so this is a plain sum rather
  than a charges-minus-refunds subtraction that could be applied twice."
  [entries]
  (reduce (fn [acc e] (add acc (:entry/amount e)))
          nil
          (remove #(= :unpriced (:entry/kind %)) entries)))

(defn unpriced
  "Every entry the price book could not price. Worth calling on any real
  ledger: this is the set of things a registry did and did not bill for."
  [entries]
  (filterv #(= :unpriced (:entry/kind %)) entries))

(defn by-registrar
  "Group entries by registrar. `srs` events do not carry the registrar, so the
  caller supplies `registrar-of` — usually a lookup against the registry as of
  the event, because sponsorship can change mid-month and the registrar who
  owed for a renewal is the one who held the domain then, not the one who holds
  it now."
  [entries registrar-of]
  (group-by registrar-of entries))

(defn invoice
  "A registrar's invoice for a period: its entries, its total, and — separately
  — the ICANN fees inside that total.

  Split out rather than merged because it is a pass-through the registry
  collects and remits: reporting only the gross makes the registry's own margin
  look larger than it is, and makes the remittance impossible to reconcile."
  [entries {:keys [registrar period-start period-end]}]
  (let [priced (remove #(= :unpriced (:entry/kind %)) entries)]
    {:invoice/registrar registrar
     :invoice/period-start period-start
     :invoice/period-end period-end
     :invoice/entries (vec priced)
     :invoice/total (total priced)
     :invoice/icann-fees (reduce (fn [acc e] (add acc (:entry/icann-fee e))) nil priced)
     :invoice/unpriced (unpriced entries)}))
