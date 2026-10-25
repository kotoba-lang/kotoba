(ns chobo.invoice
  "Invoice + settlement (pure). An Invoice is {:id :tenant :lines :status
  :totals :issued-at :due-at}. Lines are {:description :amount :currency}.
  Status: :draft → :issued → :paid | :overdue | :cancelled; dunning (滞留) =
  issued past due. IInvoiceStore is an injected port (mock). Portable .cljc.

  This is the billing counterpart to mise.pricing: mise computes cart totals
  at checkout; chobo.invoice persists the billed document and tracks payment."
  (:require [chobo.ledger :as ledger]))

(defrecord Invoice [id tenant lines status totals issued-at due-at])
(defrecord Line [description amount currency])

(defn line
  ([description amount]
   (line description amount "JPY"))
  ([description amount currency]
   (->Line description amount currency)))

(def statuses #{:draft :issued :paid :overdue :cancelled})
(def transitions
  {:draft   #{:issued :cancelled}
   :issued  #{:paid :overdue :cancelled}
   :paid    #{}
   :overdue #{:paid :cancelled}
   :cancelled #{}})

(defn invoice
  ([tenant]
   (invoice tenant {}))
  ([tenant {:keys [id lines issued-at due-at]}]
   (->Invoice (or id (str "inv_" (hash [tenant lines])))
              tenant (vec lines) :draft nil issued-at due-at)))

(defn add-line [inv l] (update inv :lines conj l))

(defn totals
  "Sum line amounts (per currency; v1 assumes single currency)."
  [inv]
  (let [cur (get-in inv [:lines 0 :currency] "JPY")
        amt (reduce + 0 (map :amount (:lines inv)))]
    {:amount amt :currency cur}))

(defn line-with-tax
  "Given a Line and a tax rate (0.08 = 8%), return the line with :tax and
  :total-with-tax computed. :tax = round(amount * rate); :total-with-tax =
  amount + tax."
  [line rate]
  (let [amt (:amount line 0)
        tax #?(:clj (Math/round (double (* amt rate)))
               :cljs (js/Math.round (* amt rate)))]
    (assoc line :tax tax :total-with-tax (+ amt tax))))

(defn apply-tax
  "Apply a tax rate to all lines, returning an invoice with :lines updated
  (each line gets :tax/:total-with-tax) and :tax-summary set."
  [inv rate]
  (let [lines-with-tax (mapv #(line-with-tax % rate) (:lines inv))
        subtotal (reduce + 0 (map :amount lines-with-tax))
        tax-total (reduce + 0 (map :tax lines-with-tax))
        grand-total (+ subtotal tax-total)
        cur (get-in inv [:lines 0 :currency] "JPY")]
    (assoc inv
           :lines lines-with-tax
           :tax-summary {:subtotal subtotal
                         :tax tax-total
                         :total grand-total
                         :currency cur
                         :rate rate})))

(defn tax-summary
  "Get the :tax-summary map (computed by apply-tax), or fall back to plain
  totals if no tax was applied."
  [inv]
  (or (:tax-summary inv)
      (let [t (totals inv)]
        {:subtotal (:amount t 0)
         :tax 0
         :total (:amount t 0)
         :currency (:currency t "JPY")
         :rate 0})))

(defn can-transition? [from to] (contains? (get transitions from #{}) to))

(defn transition [inv to]
  (when (can-transition? (:status inv :draft) to)
    (assoc inv :status to)))

(defn mark-issued [inv] (transition inv :issued))
(defn mark-paid [inv] (transition inv :paid))
(defn cancel [inv] (transition inv :cancelled))
(defn mark-overdue [inv] (transition inv :overdue))

(defn dunning?
  "True if issued and past due (due-at < now) — caller passes `now` for purity."
  [inv now]
  (and (= (:status inv) :issued)
       (:due-at inv)
       (pos? (compare (str now) (str (:due-at inv))))))

;; ---------------------------------------------------------------------------
;; partial payments + credit balance
;; ---------------------------------------------------------------------------

(defrecord Payment [id amount currency at method ref])

(defn payment [m] (merge {:currency "JPY"} m))

(defn outstanding
  "Remaining amount on an invoice: total - sum(paid payments). Returns a Price.
  Uses :tax-summary total if present, else plain totals."
  [inv]
  (let [summary (tax-summary inv)
        total-amt (:amount (or (:total summary) summary) (:total summary 0))
        cur (:currency summary "JPY")
        paid-amt (reduce + 0 (map :amount (:payments inv [])))]
    {:amount (max 0 (- total-amt paid-amt)) :currency cur}))

(defn amount-paid
  "Sum of all payment amounts on the invoice."
  [inv]
  (reduce + 0 (map :amount (:payments inv []))))

(defn fully-paid?
  "True if payments cover the invoice total."
  [inv]
  (<= (:amount (outstanding inv) 0) 0))

(defn apply-payment
  "Record a partial (or full) payment on an invoice. If it fully covers the
  total, mark the invoice :paid. Returns the updated invoice."
  [inv pmt]
  (let [p (payment pmt)
        inv' (update inv :payments (fnil conj []) p)]
    (if (fully-paid? inv')
      (or (mark-paid inv') inv')                ; mark-paid returns nil if not :issued
      inv')))

(defn credit-balance
  "Compute a tenant's credit balance: total overpayments across invoices
  (payments exceeding invoice totals). v1: sums max(0, paid - total) per invoice."
  [invoices]
  (reduce + 0
          (map (fn [inv]
                 (let [summary (tax-summary inv)
                       total (:amount (or (:total summary) summary) (:total summary 0))
                       paid (amount-paid inv)]
                   (max 0 (- paid total))))
               invoices)))

(defn billing-activity
  "Build a ledger activity for an invoice (lane :billing, kind :invoice). Caller
  appends to the audit ledger."
  [inv opts]
  (ledger/activity
   (merge {:lane :billing :kind :invoice
           :title (str "Invoice " (:id inv))
           :tenant (:tenant inv)
           :source :billing
           :props {:invoice-id (:id inv) :status (:status inv)
                   :total (totals inv)}} opts)))

;; ---------------------------------------------------------------------------
;; IInvoiceStore port (injected)
;; ---------------------------------------------------------------------------

(defprotocol IInvoiceStore
  (put-invoice! [this inv])
  (get-invoice [this id])
  (list-invoices [this])
  (overdue-invoices [this now]))

(defrecord MockInvoiceStore [state]
  IInvoiceStore
  (put-invoice! [_ inv]
    (let [inv (if (:id inv) inv (assoc inv :id (str "inv_" (hash inv))))]
      (swap! state assoc (:id inv) inv)
      inv))
  (get-invoice [_ id] (get @state id))
  (list-invoices [_] (vals @state))
  (overdue-invoices [s now] (filterv #(dunning? % now) (vals @state))))

(defn mock-invoice-store [] (->MockInvoiceStore (atom {})))

;; ---------------------------------------------------------------------------
;; dunning escalation tiers (reminder → urgent → final → collection)
;; ---------------------------------------------------------------------------

(def dunning-tiers
  "Ordered escalation tiers for overdue invoices. Each tier has a label and
  a days-overdue threshold (how many days past the due-date)."
  [{:tier :reminder   :days-overdue 1   :label "Payment reminder"}
   {:tier :urgent     :days-overdue 7   :label "Urgent: payment overdue"}
   {:tier :final      :days-overdue 30  :label "Final notice before collection"}
   {:tier :collection :days-overdue 60  :label "Sent to collections"}])

(defn- civil-day-number
  "Proleptic-Gregorian day number (days since 1970-01-01) for calendar
  y/m/d. Howard Hinnant's days_from_civil algorithm (public domain) -- pure
  integer arithmetic, correct across month/year/leap-year boundaries, no
  host date library needed (portable .cljc)."
  [y m d]
  (let [y   (if (<= m 2) (dec y) y)
        era (quot (if (>= y 0) y (- y 399)) 400)
        yoe (- y (* era 400))
        doy (+ (quot (+ (* 153 (+ m (if (> m 2) -3 9))) 2) 5) (dec d))
        doe (+ (* yoe 365) (quot yoe 4) (- (quot yoe 100)) doy)]
    (+ (* era 146097) doe -719468)))

(defn days-overdue
  "Compute how many calendar days an invoice is past due (0 if not overdue
  or no due-at). Parses the YYYY-MM-DD prefix of both dates and diffs their
  civil-day-numbers, so it stays correct across month/year boundaries.
  (v1 was a day-of-month-only subtraction that silently went negative ->
  clamped to 0 whenever `now`'s day-of-month was <= due-at's, e.g. ANY
  overdue span crossing a month boundary -- even though dunning? had
  already confirmed, via a separate full lexicographic ISO-date comparison,
  that the invoice really is overdue. That silently suppressed dunning-tier
  escalation for such invoices.)"
  [inv now]
  (if (dunning? inv now)
    (let [parse-int #?(:clj (fn [s] (Integer/parseInt s))
                       :cljs (fn [s] (let [n (js/parseInt s 10)]
                                       (if (js/isNaN n) (throw (js/Error. "NaN")) n))))
          parse-ymd (fn [s] (let [s (str s)]
                              [(parse-int (subs s 0 4))
                               (parse-int (subs s 5 7))
                               (parse-int (subs s 8 10))]))]
      (try
        (let [[dy dm dd] (parse-ymd (:due-at inv))
              [ny nm nd] (parse-ymd now)]
          (max 0 (- (civil-day-number ny nm nd) (civil-day-number dy dm dd))))
        (catch #?(:clj Exception :cljs js/Error) _ 1)))
    0))

(defn dunning-tier
  "Determine the dunning tier for an invoice given `now`. Returns the tier map
  (the highest whose days-overdue threshold is met), or nil if not overdue."
  [inv now]
  (when (dunning? inv now)
    (let [dd (days-overdue inv now)]
      (some (fn [tier]
              (when (>= dd (:days-overdue tier)) tier))
            (reverse dunning-tiers)))))

(defn dunning-tier-activity
  "Build a ledger activity for a dunning escalation (kind :dunning-escalation)."
  [inv tier opts]
  (ledger/activity
   (merge {:lane :billing :kind :dunning-escalation
           :title (:label tier "dunning")
           :tenant (:tenant inv)
           :props {:invoice-id (:id inv)
                   :tier (:tier tier)
                   :days-overdue (:days-overdue tier)}}
          opts)))
