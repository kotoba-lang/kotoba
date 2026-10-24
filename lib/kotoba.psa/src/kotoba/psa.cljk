(ns kotoba.psa
  "Professional services: staffing, rates, margin, utilization, invoices —
  pure data contracts.

  A kotoba-lang capability library for the PSA layer the fleet had only a
  legal-vertical slice of (the Kantata / BigTime / Certinia / NetSuite
  OpenAir / Deltek Vantagepoint category). It sits between two siblings
  and depends on neither:

    kotoba.activity — how much time was OBSERVED and what it was for
    kotoba.psa      — what that time is WORTH, who is committed to what,
                      and what may be invoiced   ← here
    kotoba.labor    — what the worker is PAID

  Timesheet entries are read in the `:ts/*` shape all three share
  (`:ts/worker :ts/date :ts/hours :ts/project`), so the libraries compose
  without any of them depending on the others.

  Amounts are plain numbers in the smallest unit of the account currency
  (e.g. cents), per hour for rates — the same convention as
  `kotoba.labor`, no BigDecimal assumption.

  Three invariants, each with a test that fails if it stops holding.
  Every one of them is a place where PSA tools conventionally produce a
  confident number instead of admitting a gap:

    1. No rate, no line. Time whose [project role] has no rate card is
       reported as unpriced. It is never billed at zero and never at a
       'default rate'.
    2. Margin needs both sides. With a bill rate but no cost rate the
       margin is :unknown, not equal to revenue. Fake profit is the
       classic PSA lie and it comes from exactly this substitution.
    3. Utilization needs a denominator. With no declared capacity,
       utilization is :unknown, not 1.0.

  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM."
  (:require [kotoba.lang.text :as str]))

(def ^:private ms-per-hour 3600000)

;; ---------------------------------------------------------------------------
;; Rate card
;; ---------------------------------------------------------------------------

(defn rate-card
  "Construct a rate card entry: what an hour of `role` on `project` is
  billed at, and what it costs. `cost` may be omitted — margin then
  reports :unknown rather than pretending the work was free.

  `:tax-category` is which tax-RATE category an hour of this work falls
  in. It is an OPAQUE keyword here: this library does not know that
  `:standard` means 10% anywhere, and it must not, because it prices US,
  EU and Japanese engagements out of the same function and a rate is a
  jurisdiction's fact with a date on it. What belongs here is the
  grouping — which category a line falls in — because that is a fact
  about the engagement, it is the one thing the taxing rule cannot infer,
  and this is where the lines are. See `invoice`.

  Omitted, it is nil, and every invoice drawing on this card refuses to
  state per-category subtotals at all rather than state some of them.

  ## Should there be a project-level default?

  Argued both ways, because the answer is not obvious.

  FOR: taxability is usually a property of the supply, not of the role.
  A firm whose whole engagement is standard-rated would otherwise repeat
  `:tax-category :standard` on every card, and a repeated declaration is
  a declaration that will eventually be forgotten on one card — which is
  precisely the state this refuses to bill through.

  AGAINST, and this is the choice made: a default is what invariant 1
  already refuses for rates. A project-level category that leaked PAST an
  exact-role card would put the rate and the category on two different
  cards, so a reader asking `why is this line standard-rated` would have
  to know which of two cards won for which field. Worse, the case a
  default gets wrong is exactly the case that matters — the one role on
  the engagement that is rated differently, which is the reason a
  category exists at all.

  So there is no separate project-level mechanism, and none is needed:
  `rate-for` already has one. A role-less card is the project-wide
  fallback for the rate AND for the category together, so a project may
  declare its category once. It simply does not survive being overridden
  by an exact-role card — the card that priced the line is the card that
  categorises it, and there is exactly one place to look."
  [project role billable & {:keys [cost currency tax-category]}]
  {:rate/project      project
   :rate/role         role
   :rate/billable     billable
   :rate/cost         cost
   :rate/currency     (or currency "USD")
   :rate/tax-category tax-category})

(defn card-key
  "Identity of a rate card: `[project role]`. Content-derived like
  `entry-key`, so a card named in `:invoice/uncategorised` can be found
  again in the caller's card list without a generated id. A project-wide
  fallback card's role is nil and its key says nil, rather than naming a
  role the card never claimed."
  [c]
  [(:rate/project c) (:rate/role c)])

(defn rate-for
  "Look up the rate card for [project role]. A role-less card
  (`:rate/role nil`) is the project-wide fallback; an exact role match
  wins over it. Returns nil when neither exists — callers must treat
  that as unpriced, not as free."
  [cards project role]
  (let [in-project (filter #(= project (:rate/project %)) cards)]
    (or (first (filter #(= role (:rate/role %)) in-project))
        (first (filter #(nil? (:rate/role %)) in-project)))))

;; ---------------------------------------------------------------------------
;; Staffing — assignments against capacity
;; ---------------------------------------------------------------------------

(defn assignment
  "Commit `hours` of `person` to `project` over `[from to]` (epoch ms)."
  [id person project role from to hours]
  {:assign/id      id
   :assign/person  person
   :assign/project project
   :assign/role    role
   :assign/from    from
   :assign/to      to
   :assign/hours   hours})

(defn capacity
  "Declare that `person` has `hours` available over `[from to]`."
  [person from to hours]
  {:capacity/person person
   :capacity/from   from
   :capacity/to     to
   :capacity/hours  hours})

(defn- overlap-ms [[a-from a-to] [b-from b-to]]
  (max 0 (- (min a-to b-to) (max a-from b-from))))

(defn hours-in-window
  "The part of an assignment that falls inside `[from to]`, prorated by
  overlap. This assumes the committed hours are spread evenly across the
  assignment's span — a real assumption, stated here rather than buried:
  an assignment front-loaded into its first week reads as under-allocated
  in that week and over-allocated later."
  [a [from to]]
  (let [span (- (:assign/to a) (:assign/from a))]
    (if (pos? span)
      (* (:assign/hours a) (/ (double (overlap-ms [(:assign/from a) (:assign/to a)] [from to])) span))
      0.0)))

(defn allocation
  "How `person` is committed over `[from to]`: total prorated hours, the
  declared capacity, and whether the commitments exceed it.

  `:allocation/capacity-hours` is nil when no capacity covering the
  window was declared, and `:allocation/over?` is then false — an
  undeclared capacity is not an infinite one, but neither is it a
  violation to report. `:allocation/capacity-known?` says which case
  you are in."
  [assignments capacities person [from to]]
  (let [mine (filter #(= person (:assign/person %)) assignments)
        committed (reduce + 0.0 (map #(hours-in-window % [from to]) mine))
        cap (first (filter #(and (= person (:capacity/person %))
                                 (<= (:capacity/from %) from)
                                 (>= (:capacity/to %) to))
                           capacities))]
    {:allocation/person          person
     :allocation/window          [from to]
     :allocation/committed-hours committed
     :allocation/capacity-hours  (:capacity/hours cap)
     :allocation/capacity-known? (some? cap)
     :allocation/over?           (boolean (and cap (> committed (:capacity/hours cap))))
     :allocation/assignments     (mapv :assign/id mine)}))

;; ---------------------------------------------------------------------------
;; Value, cost, margin
;; ---------------------------------------------------------------------------

(defn- entry-role [entry] (:ts/role entry))

(defn price-entry
  "Price one `:ts/*` timesheet entry against the rate cards. Returns
  `{:priced/entry :priced/rate :priced/billable :priced/cost :priced/unpriced? }`.
  With no card, `:priced/unpriced?` is true and both amounts are nil —
  not zero. Zero is a price; nil is the absence of one, and the
  difference is the whole point."
  [cards entry]
  (let [card (rate-for cards (:ts/project entry) (entry-role entry))
        h (:ts/hours entry)]
    {:priced/entry     entry
     :priced/rate      card
     :priced/billable  (when card (* (:rate/billable card) h))
     :priced/cost      (when (and card (:rate/cost card)) (* (:rate/cost card) h))
     :priced/unpriced? (nil? card)}))

(defn margin
  "Revenue, cost and margin across priced entries.

  `:margin/amount` is `:unknown` unless EVERY contributing entry has both
  a bill rate and a cost rate. A partially costed set produces a margin
  that looks like profit and is really missing data, so this refuses to
  produce one and names how many entries were missing a cost."
  [priced]
  (let [billable (filter :priced/billable priced)
        revenue (reduce + 0 (map :priced/billable billable))
        missing-cost (remove :priced/cost billable)
        ;; keep, not map: a nil cost is exactly the case this function
        ;; exists to refuse, and summing it would throw before we got the
        ;; chance to say :unknown.
        cost (reduce + 0 (keep :priced/cost billable))
        complete? (and (seq billable) (empty? missing-cost))]
    {:margin/revenue        revenue
     :margin/cost           (if complete? cost :unknown)
     :margin/amount         (if complete? (- revenue cost) :unknown)
     :margin/ratio          (if (and complete? (pos? revenue))
                              (double (/ (- revenue cost) revenue))
                              :unknown)
     :margin/unpriced-count (count (filter :priced/unpriced? priced))
     :margin/uncosted-count (count missing-cost)}))

(defn utilization
  "Billable hours over declared capacity for `person` in `[from to]`.

  `:utilization/ratio` is `:unknown` when no capacity covering the window
  was declared. A utilization figure with an invented denominator is the
  number people are managed by, so it does not get invented here."
  [entries capacities person [from to] date->ms]
  (let [mine (filter #(= person (:ts/worker %)) entries)
        in-window (filter #(let [ms (date->ms (:ts/date %))]
                             (and ms (<= from ms) (< ms to)))
                          mine)
        billable (reduce + 0.0 (map :ts/hours in-window))
        cap (first (filter #(and (= person (:capacity/person %))
                                 (<= (:capacity/from %) from)
                                 (>= (:capacity/to %) to))
                           capacities))]
    {:utilization/person         person
     :utilization/window         [from to]
     :utilization/billable-hours billable
     :utilization/capacity-hours (:capacity/hours cap)
     :utilization/ratio          (if (and cap (pos? (:capacity/hours cap)))
                                   (double (/ billable (:capacity/hours cap)))
                                   :unknown)}))

;; ---------------------------------------------------------------------------
;; Invoicing
;; ---------------------------------------------------------------------------

(defn entry-key
  "Identity of a timesheet entry for double-billing purposes. Deliberately
  content-derived rather than a generated id: two systems that emit the
  same day's work for the same worker, project and role produce the same
  key, so re-importing a timesheet cannot bill it twice."
  [e]
  [(:ts/worker e) (:ts/date e) (:ts/project e) (:ts/role e)])

(defn- tax-subtotals
  "Per-tax-category subtotals over `lines`, or a refusal.

  `cards-used` are the rate cards that actually priced a billable line —
  not the caller's whole card list, which may hold cards for other
  projects that contribute nothing here.

  Two things stop a subtotal map from being produced, and in both cases
  what comes back is `:unknown` rather than a map with some of the
  categories in it. A partial map does not read as partial: it reads as
  a smaller invoice, and it understates the tax by exactly the lines it
  omitted.

    :uncategorised-cards  some contributing card declared no category
    :mixed-currency       the contributing cards do not agree on one,
                          so the subtotals would add two units together"
  [lines cards-used]
  (let [uncategorised (->> cards-used
                           (filter #(nil? (:rate/tax-category %)))
                           (map card-key)
                           (sort-by str)
                           vec)
        currencies (vec (distinct (map :rate/currency cards-used)))
        mixed? (> (count currencies) 1)
        gaps (cond-> #{}
               (seq uncategorised) (conj :uncategorised-cards)
               mixed?              (conj :mixed-currency))
        complete? (empty? gaps)]
    {:invoice/subtotals-by-tax-category
     (if complete?
       (reduce (fn [acc l]
                 (update acc (:line/tax-category l) (fnil + 0) (:line/amount l)))
               {} lines)
       :unknown)
     :invoice/subtotals-complete? complete?
     :invoice/subtotals-gaps      gaps
     :invoice/uncategorised       uncategorised
     :invoice/subtotals-currency  (if mixed? :unknown (first currencies))}))

(defn invoice
  "Draft an invoice for `project` from `:ts/*` entries.

  `billed` is the set of `entry-key`s already on a committed invoice;
  those are excluded and reported, never silently re-billed. Entries with
  no rate card are excluded and reported too — the invoice total covers
  exactly what could be priced, and `:invoice/unpriced` says what could
  not.

  Lines are grouped by role, so a project billed at two rates shows two
  lines rather than one blended figure nobody can check.

  ## Per-tax-category subtotals

  A taxing rule does not want lines. 消費税法施行令 第七十条の十 computes
  the tax on 「税率の異なるごとに区分して合計した金額」 — the per-rate
  subtotal — multiplied once and rounded once. Taxing each line and
  summing the results is a third method the article does not offer, and
  it differs by up to ¥1 per rate on every invoice. So the caller must
  hand its tax library per-category subtotals, and this is where the
  lines are.

  What this library supplies is the GROUPING and never the rate. It does
  not know that `:standard` means 10% anywhere; the category is an opaque
  keyword it carries from `rate-card` to here. A 10% constant in a
  jurisdiction-neutral library would be wrong for two of the three
  continents it bills on, and wrong for the third the day a rate changes.

      :invoice/subtotals-by-tax-category  {category amount}, or :unknown
      :invoice/subtotals-complete?        boolean
      :invoice/subtotals-gaps             set of reasons, #{} when none
      :invoice/uncategorised              [[project role] ...] card-keys
      :invoice/subtotals-currency         the one currency, or :unknown
      :line/tax-category                  on each line, for 区分記載

  `{}` with `:invoice/subtotals-complete? true` is a real answer: an
  invoice with no billable lines owes no tax, and the subtotals sum to
  its total, which is zero. The subtotals partition the LINES, not the
  entries — what never became a line is `:invoice/unpriced`'s business
  and does not make the subtotals incomplete.

  ## The refusal

  If any contributing card declares no category, the subtotals are not
  merely missing an entry, they are WRONG: they sum to less than
  `:invoice/total` while looking like a complete map, and a tax library
  handed them would round the shortfall into a legal figure. So there is
  no partial map to misread — `:invoice/subtotals-by-tax-category` is the
  keyword `:unknown`, `:invoice/subtotals-complete?` is false, and
  `:invoice/uncategorised` names the cards, the way `:invoice/unpriced`
  names the entries that could not be priced. None of those three
  requires counting lines to interpret.

  ## Currency

  Checked, not assumed: one invoice is NOT one currency by construction.
  `:invoice/currency` is `(:rate/currency (first cards))` — the first card
  the CALLER passed, which need not be a card this invoice used, and
  nothing anywhere requires the cards of one project to agree. That key is
  left exactly as it was, because consumers read it. The subtotals do not
  inherit its assumption: they are refused when the contributing cards
  disagree, and `:invoice/subtotals-currency` states the unit they are in
  when they do agree. It is nil when there were no lines, because nothing
  declared one and an empty subtotal set needs no unit.

  **`:invoice/total` still has the assumption the subtotals refuse.** It sums
  `:line/amount` across every line, so on a mixed-currency invoice it adds
  ¥100,000 and $500 and reports 100500. That is not new — it predates the
  subtotals — but it is now visible: `:invoice/currencies` lists what was
  actually used, and `:invoice/total-is-one-currency?` is false. Both keys
  are additive; `:invoice/total` and `:invoice/currency` are unchanged,
  because consumers read them and silently redefining a key is worse than a
  wrong number somebody can now detect. A caller needing a correct total on
  a mixed invoice must sum `:invoice/lines` itself, per currency.

  `:invoice/total-is-one-currency?` is **true** for an invoice with no
  billable lines: nothing was added, so nothing was added wrongly. That is
  deliberately NOT the reading `bookkeeping.trial-balance/balanced?` takes
  of an empty set — that function asserts the books balance, and this one
  only says no unlike things were summed."
  ([id project entries cards] (invoice id project entries cards #{}))
  ([id project entries cards billed]
   (let [mine (filter #(= project (:ts/project %)) entries)
         {dupes true fresh false} (group-by #(contains? billed (entry-key %)) mine)
         priced (map #(price-entry cards %) fresh)
         {unpriced true billable false} (group-by :priced/unpriced? priced)
         cards-used (vec (distinct (map :priced/rate billable)))
         lines (->> billable
                    (group-by #(get-in % [:priced/rate :rate/role]))
                    (map (fn [[role items]]
                           {:line/role   role
                            :line/hours  (reduce + 0.0 (map (comp :ts/hours :priced/entry) items))
                            :line/rate   (get-in (first items) [:priced/rate :rate/billable])
                            :line/amount (reduce + 0 (map :priced/billable items))
                            :line/tax-category (get-in (first items)
                                                       [:priced/rate :rate/tax-category])}))
                    (sort-by #(str (:line/role %)))
                    vec)]
     (merge
      {:invoice/id       id
       :invoice/project  project
       :invoice/lines    lines
       ;; ⚠ `:invoice/total` sums `:line/amount` across every line, and the
       ;; lines of one invoice are NOT guaranteed to be in one currency (see
       ;; the Currency section above). Measured 2026-08-18: an invoice drawing
       ;; on a ¥10,000/h card and a $100/h card reports a total of 100500,
       ;; which is ¥100,000 and $500 added together. It is wrong, it looks
       ;; right, and nothing about the number says which — the same shape of
       ;; defect this workspace already fixed at the journal-entry level
       ;; (`bookkeeping.posting`) and in the trial balance (keyed
       ;; `[account currency]`).
       ;;
       ;; It is left as it is because consumers read it, and changing its
       ;; meaning is a breaking change that is not this function's to make.
       ;; What IS added is the marker, so the number can no longer be read as
       ;; a single-currency figure without checking.
       :invoice/total    (reduce + 0 (map :line/amount lines))
       :invoice/currency (or (:rate/currency (first cards)) "USD")
       :invoice/currencies (vec (sort (distinct (keep :rate/currency cards-used))))
       :invoice/total-is-one-currency?
       (<= (count (distinct (keep :rate/currency cards-used))) 1)
       :invoice/entries  (mapv entry-key (map :priced/entry billable))
       :invoice/unpriced (mapv (comp entry-key :priced/entry) unpriced)
       :invoice/excluded-already-billed (mapv entry-key dupes)}
      (tax-subtotals lines cards-used)))))

(defn billable?
  "Would `entry` produce a line on an invoice? Useful as a pre-check so a
  caller can surface unpriced work before drafting rather than after."
  [cards entry]
  (some? (rate-for cards (:ts/project entry) (entry-role entry))))

(defn describe-gap
  "One-line human summary of what an invoice draft could not bill. Empty
  string when nothing was left out — so a caller can append it
  unconditionally without printing a reassuring 'no problems' line that
  is really 'nothing was checked'."
  [inv]
  (let [u (count (:invoice/unpriced inv))
        d (count (:invoice/excluded-already-billed inv))]
    (str/join "; "
              (cond-> []
                (pos? u) (conj (str u " entries had no rate card and were not billed"))
                (pos? d) (conj (str d " entries were already billed and were excluded"))))))

(defn describe-tax-gap
  "One-line human summary of why an invoice's per-category subtotals are
  `:unknown`. Empty string when they are complete — the same discipline as
  `describe-gap`: absence of text is the signal, and there is no
  reassuring `all categorised` line that would print just as happily when
  nothing was checked.

  Deliberately NOT folded into `describe-gap`. That function reports what
  could not be BILLED; an uncategorised line is billed, is on the invoice,
  and is in the total. What it cannot be is taxed. One sentence answering
  both questions would make each of them harder to read, and would change
  the meaning of a string consumers already print."
  [inv]
  (let [gaps (:invoice/subtotals-gaps inv)
        u (count (:invoice/uncategorised inv))]
    (str/join "; "
              (cond-> []
                (contains? gaps :uncategorised-cards)
                (conj (str u " rate cards declared no tax category, so no"
                           " per-category subtotals were stated"))
                (contains? gaps :mixed-currency)
                (conj (str "the rate cards used declare more than one currency,"
                           " so per-category subtotals would add two units"))))))

(defn hours->ms [h] (* h ms-per-hour))
(defn ms->hours [ms] (/ (double ms) ms-per-hour))

;; ---------------------------------------------------------------------------
;; Currency
;;
;; A fourth invariant, and the same shape as the other three: an amount
;; whose rate to the target currency is unknown is NOT converted at 1:1,
;; not dropped, and not silently summed with amounts in another currency.
;; It is reported. Every conversion carries the rate and the date it was
;; taken from, because an invoice total that cannot say which rate it used
;; is an invoice total nobody can check.
;; ---------------------------------------------------------------------------

(defn fx-rate
  "One directed rate: `n` units of `to` per unit of `from`, `as-of` a date
  string. Rates are directional and are NOT inverted automatically — a
  buy rate is not a sell rate, and inferring one from the other would
  invent a spread."
  [from to rate as-of]
  {:fx/from from :fx/to to :fx/rate rate :fx/as-of as-of})

(defn convert
  "Convert `amount` from `from` to `to` using `rates`.

  Returns `{:money/amount n :money/currency to :money/rate r :money/as-of d}`,
  or `{:money/unconvertible? true :money/currency from}` when no rate is
  declared. Same currency converts at 1 with no rate lookup."
  [rates amount from to]
  (if (= from to)
    {:money/amount amount :money/currency to :money/rate 1 :money/as-of nil}
    (if-let [r (first (filter #(and (= from (:fx/from %)) (= to (:fx/to %))) rates))]
      {:money/amount (* amount (:fx/rate r))
       :money/currency to :money/rate (:fx/rate r) :money/as-of (:fx/as-of r)}
      {:money/unconvertible? true :money/currency from :money/amount amount})))

(defn total-in
  "Sum `{:amount :currency}` items into `currency`.

  `:total/unconvertible` lists what could not be converted, and those
  amounts are NOT in `:total/amount`. A total that quietly absorbed a
  currency it could not price would be wrong by an unknown factor; one
  that silently dropped it would be wrong by a known one. Neither is
  reported as complete: `:total/complete?` says which you have."
  [rates items currency]
  (let [converted (map #(assoc (convert rates (:amount %) (:currency %) currency) :item %) items)
        {bad true good false} (group-by #(boolean (:money/unconvertible? %)) converted)]
    {:total/amount        (reduce + 0 (map :money/amount good))
     :total/currency      currency
     ;; Only rates an actual lookup produced. A same-currency item
     ;; converts at 1 without consulting anything, and listing that as a
     ;; "rate used" would pad the audit trail with a fact nobody supplied.
     :total/rates-used    (vec (distinct (keep #(when (:money/as-of %)
                                                  (select-keys % [:money/rate :money/as-of]))
                                               good)))
     :total/unconvertible (mapv :item bad)
     :total/complete?     (empty? bad)}))

;; ---------------------------------------------------------------------------
;; Expenses
;; ---------------------------------------------------------------------------

(defn expense
  "A cost incurred on a project. `:billable?` decides whether it reaches
  an invoice; `:markup` (e.g. 0.1 for 10%) is applied only to billable
  expenses and defaults to none.

  A non-billable expense still counts against margin. Absorbing a cost is
  a decision about who pays, not a reason to stop counting it."
  [id project amount currency & {:keys [billable? markup category date incurred-by]}]
  {:expense/id          id
   :expense/project     project
   :expense/amount      amount
   :expense/currency    currency
   :expense/billable?   (boolean billable?)
   :expense/markup      (or markup 0)
   :expense/category    category
   :expense/date        date
   :expense/incurred-by incurred-by})

(defn expense-billable-amount
  "What a billable expense adds to an invoice: cost plus markup. Zero for
  a non-billable one."
  [e]
  (if (:expense/billable? e)
    (* (:expense/amount e) (+ 1 (:expense/markup e)))
    0))

;; ---------------------------------------------------------------------------
;; Subcontractors
;; ---------------------------------------------------------------------------

(defn subcontract
  "A subcontractor's hours on a project: what they are paid (`cost-rate`)
  and what the client is billed (`bill-rate`).

  Both rates are explicit rather than derived from the project's rate
  card, because a subcontractor's cost is a separate negotiation and
  inheriting the internal cost rate would report someone else's payroll
  as this firm's."
  [id project vendor role hours cost-rate bill-rate currency]
  {:sub/id id :sub/project project :sub/vendor vendor :sub/role role
   :sub/hours hours :sub/cost-rate cost-rate :sub/bill-rate bill-rate
   :sub/currency currency})

(defn subcontract-margin [s]
  {:sub/billable (* (:sub/hours s) (:sub/bill-rate s))
   :sub/cost     (* (:sub/hours s) (:sub/cost-rate s))
   :sub/amount   (* (:sub/hours s) (- (:sub/bill-rate s) (:sub/cost-rate s)))})

(defn project-margin
  "Margin across everything a project actually costs: labour, billable and
  non-billable expenses, and subcontractors.

  Inherits invariant 2 unchanged — one uncosted labour entry and the
  whole figure is `:unknown`. Expenses and subcontractors always carry
  both sides, so they cannot be the reason it is unknown, but they are
  reported separately so a reader can see WHERE the money went rather
  than only how much is left."
  [priced expenses subs]
  (let [labour (margin priced)
        exp-billable (reduce + 0 (map expense-billable-amount expenses))
        exp-cost (reduce + 0 (map :expense/amount expenses))
        sub-m (map subcontract-margin subs)
        sub-billable (reduce + 0 (map :sub/billable sub-m))
        sub-cost (reduce + 0 (map :sub/cost sub-m))
        revenue (+ (:margin/revenue labour) exp-billable sub-billable)
        known? (not= :unknown (:margin/cost labour))
        cost (when known? (+ (:margin/cost labour) exp-cost sub-cost))]
    {:margin/revenue          revenue
     :margin/cost             (if known? cost :unknown)
     :margin/amount           (if known? (- revenue cost) :unknown)
     :margin/ratio            (if (and known? (pos? revenue))
                                (double (/ (- revenue cost) revenue))
                                :unknown)
     :margin/labour           labour
     :margin/expense-revenue  exp-billable
     :margin/expense-cost     exp-cost
     :margin/subcontract-revenue sub-billable
     :margin/subcontract-cost    sub-cost
     :margin/unpriced-count   (:margin/unpriced-count labour)
     :margin/uncosted-count   (:margin/uncosted-count labour)}))

;; ---------------------------------------------------------------------------
;; Revenue recognition
;; ---------------------------------------------------------------------------

(def recognition-methods
  "How revenue is recognised over a project's life.

    :as-delivered      recognise what has been delivered — time-and-
                       materials, where each hour is its own performance
                       obligation
    :percent-complete  recognise a fixed fee in proportion to progress
    :on-completion     recognise nothing until the project is complete"
  #{:as-delivered :percent-complete :on-completion})

(defn contract
  "A revenue contract for a project. `:fee` is the fixed fee for
  `:percent-complete` / `:on-completion`; it is ignored (and may be nil)
  for `:as-delivered`. `:budget-hours` is the denominator for progress
  and is required for `:percent-complete`."
  [project method & {:keys [fee currency budget-hours]}]
  (when (contains? recognition-methods method)
    {:contract/project      project
     :contract/method       method
     :contract/fee          fee
     :contract/currency     (or currency "USD")
     :contract/budget-hours budget-hours}))

(defn recognize
  "Revenue recognised so far under `contract-record`.

  Returns `{:revenue/amount n :revenue/method m :revenue/progress p}`, or
  `:unknown` for `:amount` when the inputs the method needs are absent —
  percent-complete with no budget cannot produce a percentage, and a
  project 'about 80% done' is an estimate, not a measurement. This
  refuses to supply the estimate.

  Progress is capped at 1.0: an over-budget project has delivered its
  scope, not 130% of the contract's value. The overrun shows up in
  margin, which is where it belongs."
  [contract-record priced complete?]
  (let [{:contract/keys [method fee budget-hours]} contract-record
        delivered (reduce + 0 (map (comp :ts/hours :priced/entry) priced))]
    (case method
      :as-delivered
      {:revenue/method method
       :revenue/amount (reduce + 0 (keep :priced/billable priced))
       :revenue/progress nil
       :revenue/unpriced-count (count (filter :priced/unpriced? priced))}

      :percent-complete
      (if (and budget-hours (pos? budget-hours) fee)
        (let [p (min 1.0 (/ (double delivered) budget-hours))]
          {:revenue/method method :revenue/amount (* fee p) :revenue/progress p
           :revenue/delivered-hours delivered :revenue/budget-hours budget-hours})
        {:revenue/method method :revenue/amount :unknown :revenue/progress :unknown
         :revenue/reason (if fee :no-budget-hours :no-fee)})

      :on-completion
      {:revenue/method method
       :revenue/amount (if complete? fee 0)
       :revenue/progress (if complete? 1.0 0.0)
       :revenue/complete? (boolean complete?)}

      {:revenue/method method :revenue/amount :unknown :revenue/reason :unknown-method})))
