(ns kotoba.shohyo.ifrs
  "IAS 1 *Presentation of Financial Statements* — the line items a statement
  of financial position and a statement of profit or loss must present, read
  from the standard rather than from a textbook.

  `kotoba.shohyo` classifies into five account types and checks the
  accounting equation. `kotoba.shohyo.jp` says what a Japanese statement
  looks like under 会社計算規則. This says what an IFRS one looks like, and
  it is chosen by the caller: **the core stays jurisdiction-neutral and knows
  about neither module.**

  ## What was read, and from where

  Both, in full, on 2026-08-18:

  - the IFRS Foundation's own PDF of IAS 1 (issued 2021, Part A) —
    HTTP 200, 246 388 bytes, `application/pdf`, no DRM
  - the text adopted into Union law by Commission Regulation (EC)
    No 1126/2008, consolidated at 2023-01-01 — CELEX `02008R1126-20230101`,
    HTTP 200, 11 362 077 bytes, from the CELLAR endpoint

  They agree word for word on every paragraph quoted here, which is why the
  quotes are marked `:read-from-source` rather than merely reachable. The
  discipline is `kotoba-lang/taxlaw`'s and it is not decorative: **a
  provision nobody read may not make a statement conformant.** See
  `catalog-verification`, and `requirable?`, which enforces it in code rather
  than in prose.

  ## The rule a naive implementation gets wrong

  IAS 1.54 lists twenty items and IAS 1.82 thirteen live ones, so the obvious
  implementation is a checklist: any statement missing one of the twenty is
  non-conformant. That is not what the standard says, twice over.

      57  This Standard does not prescribe the order or format in which an
          entity presents items. Paragraph 54 simply lists items that are
          sufficiently different in nature or function to warrant separate
          presentation …

      31  … An entity need not provide a specific disclosure required by an
          IFRS if the information resulting from that disclosure is not
          material. This is the case even if the IFRS contains a list of
          specific requirements or describes them as minimum requirements.

  A checklist would report every entity on earth non-conformant for having no
  biological assets. So **materiality is the entity's judgement, not this
  library's**: an item is required of a statement when the chart declares an
  account for it, and missing when no line in that currency's statement
  carries it. This library never invents a requirement the caller did not
  declare — the same refusal to guess that the core is built on.

  ## The second rule a naive implementation gets wrong

  IAS 1.60 lets an entity present in order of liquidity instead of
  current/non-current. The obvious reading is that choosing liquidity turns
  the whole current/non-current section off. IAS 1.61 opens by saying it does
  not:

      61  **Whichever method of presentation is adopted**, an entity shall
          disclose the amount expected to be recovered or settled after more
          than twelve months for each asset and liability line item that
          combines amounts …

  So the twelve-month disclosure is checked under both methods, and only the
  per-line current/non-current classification is switched off by the
  exception.

  ## What a chart declares

      {\"inventory\" {:type :asset
                    :ias1/item :inventories
                    :ias1/classification :current}}

  `:ias1/classification` is `:current` or `:non-current`. An account whose
  line combines both periods declares `:ias1/combines-both-periods? true`
  and the amount `:ias1/beyond-twelve-months`, per IAS 1.61.

  The core forwards the whole chart entry onto each line as `:declared`
  without knowing what any of these keys mean."
  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------------------
;; provenance — what was read, from where, and what was not
;; ---------------------------------------------------------------------------

(def sources
  "The two texts of IAS 1 that were fetched, with what the fetch returned.

  A citation whose retrieval nobody recorded cannot be told apart from one
  nobody attempted."
  {:ifrs/ias-1-pdf
   {:source/title "IAS 1 Presentation of Financial Statements (issued 2021, Part A)"
    :source/authority "IFRS Foundation"
    :source/kind :standard
    :source/url (str "https://www.ifrs.org/content/dam/ifrs/publications/"
                     "pdf-standards/english/2021/issued/part-a/"
                     "ias-1-presentation-of-financial-statements.pdf")
    :source/http-status 200
    :source/bytes 246388
    :source/content-type "application/pdf"
    :source/retrieved-at "2026-08-18"}

   :eu/ias-1-as-adopted
   {:source/title (str "Commission Regulation (EC) No 1126/2008, consolidated "
                       "text of 2023-01-01, Annex — IAS 1")
    :source/authority "European Union (Publications Office, CELLAR)"
    :source/kind :adopted-standard
    :source/celex "02008R1126-20230101"
    :source/url "http://publications.europa.eu/resource/celex/02008R1126-20230101"
    :source/request-headers {"Accept" "application/xhtml+xml" "Accept-Language" "eng"}
    :source/http-status 200
    :source/bytes 11362077
    :source/retrieved-at "2026-08-18"}})

(def catalog-verification
  "What was verified, what was not, and what was read but backs no check.

  Three distinct claims. Collapsing them is how a citation list becomes
  decoration — `kotoba-lang/taxlaw` draws the same line for the same reason."
  {:catalog/corroborated?
   true

   :catalog/corroboration
   (str "Every paragraph quoted here was read in BOTH sources and the wording "
        "is identical. The IFRS Foundation PDF is the standard; the CELLAR "
        "text is that standard as adopted into Union law, which is what makes "
        "it publicly retrievable at all.")

   :catalog/content-verified
   [{:claim :sofp-line-items         :provision "IAS 1.54"}
    {:claim :profit-or-loss-line-items :provision "IAS 1.82"}
    {:claim :current-non-current-distinction :provision "IAS 1.60"}
    {:claim :twelve-month-disclosure :provision "IAS 1.61"}
    {:claim :deferred-tax-is-never-current :provision "IAS 1.56"}
    {:claim :offsetting                :provision "IAS 1.32"}
    {:claim :materiality-overrides-a-minimum-list :provision "IAS 1.31"}
    {:claim :paragraph-54-is-not-a-format :provision "IAS 1.57"}]

   ;; Read, quoted, and enforcing nothing. Saying so is the point: a cited
   ;; article that silently backs no check reads exactly like one that does.
   :catalog/read-but-not-enforced
   [{:provision "IAS 1.32"
     :why (str "Offsetting happens upstream of a trial balance. By the time "
               "balances reach this library the netting, if any, has already "
               "been done and left no trace in the data. Checking it here "
               "would be theatre. It is quoted so a reader can see it was "
               "considered and see why it is not answered.")}]

   ;; Cited BY IAS 1.54 and 1.82 to fix the scope of particular items. Not
   ;; read. `requirable?` refuses to let any of them make a statement
   ;; conformant, which is the only thing that makes this record load-bearing.
   :catalog/not-verified
   [{:standard "IFRS 17" :provision-cited "paragraph 78"
     :scopes ["IAS 1.54(da)" "IAS 1.54(ma)" "IAS 1.82(a)(ii)"
              "IAS 1.82(ab)" "IAS 1.82(ac)" "IAS 1.82(bb)" "IAS 1.82(bc)"]
     :review :reachable-not-read}
    {:standard "IFRS 9" :provision-cited "Section 5.5"
     :scopes ["IAS 1.82(ba)" "IAS 1.82(ca)"]
     :review :reachable-not-read}
    {:standard "IFRS 5" :provision-cited nil
     :scopes ["IAS 1.54(j)" "IAS 1.54(p)" "IAS 1.82(ea)"]
     :review :reachable-not-read}
    {:standard "IAS 12" :provision-cited nil
     :scopes ["IAS 1.54(n)" "IAS 1.54(o)"]
     :review :reachable-not-read}
    {:standard "IAS 41" :provision-cited nil
     :scopes ["IAS 1.54(f)"]
     :review :reachable-not-read}
    {:standard "IAS 1" :provision-cited "paragraphs 66–76"
     :scopes ["the criteria that decide whether an asset or liability IS current"]
     :review :reachable-not-read
     :why (str "IAS 1.60 defers to them. This library takes the caller's "
               "declared classification at face value and does not re-derive "
               "it, so the criteria are not read and no check depends on them.")}]

   :catalog/rejected
   [{:url "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02008R1126-20230101"
     :http-status 202
     :bytes 0
     :why (str "HTTP 202 with an empty body, twice. The human-facing EUR-Lex "
               "URL is an async renderer; 202 here means `not this way`, not "
               "`unavailable` — the CELLAR resource URL served the same act in "
               "full. Recorded so nobody reads a 202 as an absent text.")}
    {:url "http://publications.europa.eu/resource/celex/02008R1126-20240101"
     :http-status 404
     :why "no consolidated version at that date; 2023-01-01 is the one that exists"}
    {:url "http://publications.europa.eu/resource/celex/32008R1126"
     :http-status 200
     :why (str "Fetched and read (6 596 496 bytes), then NOT used. It carries "
               "IAS 1 as revised in 2003, whose paragraph 54 is a sentence "
               "about financial institutions and whose balance-sheet list is "
               "paragraph 68. Citing IAS 1.54 from it would have quoted the "
               "wrong text under the right number — the amending regulation "
               "(EC) No 1274/2008 replaced it, and the consolidation carries "
               "the replacement.")}]})

(def provisions
  "The paragraphs implemented here, quoted verbatim from the sources above.

  taxlaw's standing rule applies: a claim that is ENFORCED must be read."
  {:standard "IAS 1"
   :standard-title "Presentation of Financial Statements"
   :retrieved-at "2026-08-18"
   :sources (vec (keys sources))
   :paragraphs
   [{:paragraph "IAS 1.31" :on :materiality :review :read-from-source
     :quote (str "Some IFRSs specify information that is required to be included "
                 "in the financial statements, which include the notes. An entity "
                 "need not provide a specific disclosure required by an IFRS if the "
                 "information resulting from that disclosure is not material. This "
                 "is the case even if the IFRS contains a list of specific "
                 "requirements or describes them as minimum requirements.")}
    {:paragraph "IAS 1.32" :on :offsetting :review :read-from-source
     :enforced? false
     :quote (str "An entity shall not offset assets and liabilities or income and "
                 "expenses, unless required or permitted by an IFRS.")}
    {:paragraph "IAS 1.54" :on :sofp-line-items :review :read-from-source
     :quote (str "The statement of financial position shall include line items that "
                 "present the following amounts:")
     :quote-is-partial? true
     :quote-omits (str "the twenty lettered items (a)–(r), including (da) and (ma), "
                       "are carried individually in `sofp-items` with their own "
                       "letter and wording rather than repeated here.")}
    {:paragraph "IAS 1.56" :on :deferred-tax-is-never-current :review :read-from-source
     :quote (str "When an entity presents current and non-current assets, and current "
                 "and non-current liabilities, as separate classifications in its "
                 "statement of financial position, it shall not classify deferred tax "
                 "assets (liabilities) as current assets (liabilities).")}
    {:paragraph "IAS 1.57" :on :not-a-format :review :read-from-source
     :quote (str "This Standard does not prescribe the order or format in which an "
                 "entity presents items. Paragraph 54 simply lists items that are "
                 "sufficiently different in nature or function to warrant separate "
                 "presentation in the statement of financial position.")}
    {:paragraph "IAS 1.60" :on :current-non-current :review :read-from-source
     :quote (str "An entity shall present current and non-current assets, and current "
                 "and non-current liabilities, as separate classifications in its "
                 "statement of financial position in accordance with paragraphs 66–76 "
                 "except when a presentation based on liquidity provides information "
                 "that is reliable and more relevant. When that exception applies, an "
                 "entity shall present all assets and liabilities in order of liquidity.")}
    {:paragraph "IAS 1.61" :on :twelve-month-disclosure :review :read-from-source
     :quote (str "Whichever method of presentation is adopted, an entity shall disclose "
                 "the amount expected to be recovered or settled after more than twelve "
                 "months for each asset and liability line item that combines amounts "
                 "expected to be recovered or settled: (a) no more than twelve months "
                 "after the reporting period, and (b) more than twelve months after the "
                 "reporting period.")}
    {:paragraph "IAS 1.82" :on :profit-or-loss-line-items :review :read-from-source
     :quote (str "In addition to items required by other IFRSs, the profit or loss "
                 "section or the statement of profit or loss shall include line items "
                 "that present the following amounts for the period:")
     :quote-is-partial? true
     :quote-omits (str "the lettered items are carried individually in `pl-items`, "
                       "including (e) and (f)–(i), which the current text marks "
                       "[deleted] and which are recorded as deleted rather than "
                       "dropped.")}]})

;; ---------------------------------------------------------------------------
;; IAS 1.54 — the statement of financial position
;; ---------------------------------------------------------------------------

(def sofp-items
  "The twenty line items of IAS 1.54, each with the article's own wording.

  `:type` is the core account type the item must land on, and is **nil where
  the article itself names both sides** — 54(n) and 54(o) say \"liabilities
  and assets\". Forcing a side there would contradict the text.

  `:scope-review :reachable-not-read` marks an item whose scope is fixed by a
  standard that was not read. Those items are still recognised — dropping
  them silently is the bug this library exists to refuse — but
  `requirable?` will not let one make a statement conformant."
  {:property-plant-and-equipment
   {:provision "IAS 1.54(a)" :label "property, plant and equipment"
    :type :asset :review :read-from-source}
   :investment-property
   {:provision "IAS 1.54(b)" :label "investment property"
    :type :asset :review :read-from-source}
   :intangible-assets
   {:provision "IAS 1.54(c)" :label "intangible assets"
    :type :asset :review :read-from-source}
   :financial-assets
   {:provision "IAS 1.54(d)"
    :label "financial assets (excluding amounts shown under (e), (h) and (i))"
    :type :asset :review :read-from-source}
   :ifrs17-contract-assets
   {:provision "IAS 1.54(da)"
    :label "portfolios of contracts within the scope of IFRS 17 that are assets"
    :type :asset :review :read-from-source
    :scope-source "IFRS 17 paragraph 78" :scope-review :reachable-not-read}
   :equity-method-investments
   {:provision "IAS 1.54(e)" :label "investments accounted for using the equity method"
    :type :asset :review :read-from-source}
   :biological-assets
   {:provision "IAS 1.54(f)" :label "biological assets within the scope of IAS 41 Agriculture"
    :type :asset :review :read-from-source
    :scope-source "IAS 41" :scope-review :reachable-not-read}
   :inventories
   {:provision "IAS 1.54(g)" :label "inventories"
    :type :asset :review :read-from-source}
   :trade-and-other-receivables
   {:provision "IAS 1.54(h)" :label "trade and other receivables"
    :type :asset :review :read-from-source}
   :cash-and-cash-equivalents
   {:provision "IAS 1.54(i)" :label "cash and cash equivalents"
    :type :asset :review :read-from-source}
   :held-for-sale-assets
   {:provision "IAS 1.54(j)"
    :label (str "the total of assets classified as held for sale and assets included "
                "in disposal groups classified as held for sale in accordance with IFRS 5")
    :type :asset :review :read-from-source
    :scope-source "IFRS 5" :scope-review :reachable-not-read}
   :trade-and-other-payables
   {:provision "IAS 1.54(k)" :label "trade and other payables"
    :type :liability :review :read-from-source}
   :provisions
   {:provision "IAS 1.54(l)" :label "provisions"
    :type :liability :review :read-from-source}
   :financial-liabilities
   {:provision "IAS 1.54(m)"
    :label "financial liabilities (excluding amounts shown under (k) and (l))"
    :type :liability :review :read-from-source}
   :ifrs17-contract-liabilities
   {:provision "IAS 1.54(ma)"
    :label "portfolios of contracts within the scope of IFRS 17 that are liabilities"
    :type :liability :review :read-from-source
    :scope-source "IFRS 17 paragraph 78" :scope-review :reachable-not-read}
   :current-tax
   {:provision "IAS 1.54(n)"
    :label "liabilities and assets for current tax, as defined in IAS 12 Income Taxes"
    ;; the article names both sides — see the docstring
    :type nil :review :read-from-source
    :scope-source "IAS 12" :scope-review :reachable-not-read}
   :deferred-tax
   {:provision "IAS 1.54(o)"
    :label "deferred tax liabilities and deferred tax assets, as defined in IAS 12"
    :type nil :review :read-from-source
    :scope-source "IAS 12" :scope-review :reachable-not-read
    ;; IAS 1.56, read and quoted in `provisions`.
    :never-current? true}
   :held-for-sale-liabilities
   {:provision "IAS 1.54(p)"
    :label (str "liabilities included in disposal groups classified as held for sale "
                "in accordance with IFRS 5")
    :type :liability :review :read-from-source
    :scope-source "IFRS 5" :scope-review :reachable-not-read}
   :non-controlling-interests
   {:provision "IAS 1.54(q)" :label "non-controlling interests, presented within equity"
    :type :equity :review :read-from-source}
   :issued-capital-and-reserves
   {:provision "IAS 1.54(r)" :label "issued capital and reserves attributable to owners of the parent"
    :type :equity :review :read-from-source}})

;; ---------------------------------------------------------------------------
;; IAS 1.82 — the statement of profit or loss
;; ---------------------------------------------------------------------------

(def pl-items
  "The line items of IAS 1.82.

  `:status :deleted` records (e) and (f)–(i), which the current text marks
  `[deleted]`. They are kept rather than omitted: *the standard deleted this*
  and *we never implemented this* are different facts, and a list that drops
  them cannot tell a reader which happened.

  `:type` is nil wherever the article names an amount that may fall either
  way — \"gains and losses\", \"including reversals\", \"income or expenses\",
  \"a single amount\". Pinning those to one side would be this library
  guessing, which is precisely what it refuses to do."
  {:revenue
   {:provision "IAS 1.82(a)" :label "revenue"
    :type :revenue :review :read-from-source}
   :interest-revenue-effective-interest
   {:provision "IAS 1.82(a)(i)"
    :label "interest revenue calculated using the effective interest method"
    :type :revenue :review :read-from-source}
   :insurance-revenue
   {:provision "IAS 1.82(a)(ii)" :label "insurance revenue (see IFRS 17)"
    :type :revenue :review :read-from-source
    :scope-source "IFRS 17" :scope-review :reachable-not-read}
   :amortised-cost-derecognition-result
   {:provision "IAS 1.82(aa)"
    :label (str "gains and losses arising from the derecognition of financial assets "
                "measured at amortised cost")
    :type nil :review :read-from-source}
   :insurance-service-expenses
   {:provision "IAS 1.82(ab)"
    :label "insurance service expenses from contracts issued within the scope of IFRS 17"
    :type :expense :review :read-from-source
    :scope-source "IFRS 17" :scope-review :reachable-not-read}
   :reinsurance-held-result
   {:provision "IAS 1.82(ac)" :label "income or expenses from reinsurance contracts held"
    :type nil :review :read-from-source
    :scope-source "IFRS 17" :scope-review :reachable-not-read}
   :finance-costs
   {:provision "IAS 1.82(b)" :label "finance costs"
    :type :expense :review :read-from-source}
   :impairment-losses
   {:provision "IAS 1.82(ba)"
    :label (str "impairment losses (including reversals of impairment losses or "
                "impairment gains) determined in accordance with Section 5.5 of IFRS 9")
    :type nil :review :read-from-source
    :scope-source "IFRS 9 Section 5.5" :scope-review :reachable-not-read}
   :insurance-finance-result
   {:provision "IAS 1.82(bb)"
    :label "insurance finance income or expenses from contracts issued within the scope of IFRS 17"
    :type nil :review :read-from-source
    :scope-source "IFRS 17" :scope-review :reachable-not-read}
   :reinsurance-finance-result
   {:provision "IAS 1.82(bc)" :label "finance income or expenses from reinsurance contracts held"
    :type nil :review :read-from-source
    :scope-source "IFRS 17" :scope-review :reachable-not-read}
   :equity-method-share-of-result
   {:provision "IAS 1.82(c)"
    :label (str "share of the profit or loss of associates and joint ventures accounted "
                "for using the equity method")
    :type nil :review :read-from-source}
   :reclassified-amortised-cost-to-fvtpl
   {:provision "IAS 1.82(ca)"
    :label (str "gain or loss on a financial asset reclassified out of amortised cost "
                "to fair value through profit or loss")
    :type nil :review :read-from-source
    :scope-source "IFRS 9" :scope-review :reachable-not-read}
   :reclassified-fvoci-to-fvtpl
   {:provision "IAS 1.82(cb)"
    :label (str "cumulative gain or loss reclassified to profit or loss on a financial "
                "asset reclassified out of fair value through other comprehensive income")
    :type nil :review :read-from-source}
   :tax-expense
   {:provision "IAS 1.82(d)" :label "tax expense"
    :type :expense :review :read-from-source}
   :deleted-82e
   {:provision "IAS 1.82(e)" :label "[deleted]" :status :deleted
    :type nil :review :read-from-source}
   :discontinued-operations
   {:provision "IAS 1.82(ea)" :label "a single amount for the total of discontinued operations"
    :type nil :review :read-from-source
    :scope-source "IFRS 5" :scope-review :reachable-not-read}
   :deleted-82f-i
   {:provision "IAS 1.82(f)–(i)" :label "[deleted]" :status :deleted
    :type nil :review :read-from-source}})

;; ---------------------------------------------------------------------------
;; the discipline, in code
;; ---------------------------------------------------------------------------

(defn item-of
  "The IAS 1 item named by `k`, from either statement. nil when unknown."
  [k]
  (or (sofp-items k) (pl-items k)))

(defn known-item? [k] (some? (item-of k)))

(defn requirable?
  "May this item be used to call a statement short — or whole?

  No, when the standard deleted it, and no when its scope is fixed by a
  standard nobody read. That second clause is the whole point of
  `catalog-verification`: taxlaw's rule is that an unverified rule must not
  back a check, and a rule enforced only in prose is not enforced. Here the
  filter is the code path, so a citation downgraded to `:reachable-not-read`
  stops being requirable in the same edit."
  [k]
  (let [{:keys [status review scope-review]} (item-of k)]
    (boolean
     (and (some? (item-of k))
          (not= :deleted status)
          (= :read-from-source review)
          (not= :reachable-not-read scope-review)))))

(defn unverifiable?
  "Is this a real IAS 1 item whose scope was never read?

  Distinct from `(not (requirable? k))`, which is also true of an unknown
  keyword and of a deleted paragraph. These three are named separately
  because a caller must be able to tell *you invented this*, *the Board
  removed this* and *nobody checked what this covers* apart."
  [k]
  (= :reachable-not-read (:scope-review (item-of k))))

(defn statement-of
  "`:bs` or `:pl` for an item — which statement IAS 1 puts it on."
  [k]
  (cond (contains? sofp-items k) :bs
        (contains? pl-items k) :pl))

;; ---------------------------------------------------------------------------
;; the chart
;; ---------------------------------------------------------------------------

(defn item-problems
  "Ways a chart's IAS 1 declarations are wrong, before any statement is folded.

  An item the standard does not name, an item the standard deleted, and an
  item whose account type contradicts the article — tagging a payable as
  `:inventories` would put it in the wrong half of the statement of financial
  position and every total would still add up."
  [chart]
  (vec
   (mapcat
    (fn [[account entry]]
      (let [k (:ias1/item entry)
            cls (:ias1/classification entry)
            declared-type (:type entry)
            {:keys [type status provision never-current?]} (item-of k)]
        (cond-> []
          (and (some? k) (not (known-item? k)))
          (conj {:account account :problem :unknown-item :item k})

          (= :deleted status)
          (conj {:account account :problem :deleted-item :item k
                 :detail (str provision " is marked [deleted] in the current text")})

          (and (some? k) (known-item? k) (some? type) (some? declared-type)
               (not= type declared-type))
          (conj {:account account :problem :item-type-conflict :item k
                 :detail (str (name k) " is " (name type) " under " provision
                              ", not " (name declared-type))})

          (and (some? cls) (not (contains? #{:current :non-current} cls)))
          (conj {:account account :problem :unknown-classification
                 :detail (str (pr-str cls) " is neither :current nor :non-current")})

          ;; IAS 1.56, quoted in `provisions`.
          (and never-current? (= :current cls))
          (conj {:account account :problem :deferred-tax-classified-current :item k
                 :detail "IAS 1.56 forbids classifying deferred tax as current"}))))
    chart)))

;; ---------------------------------------------------------------------------
;; the statement
;; ---------------------------------------------------------------------------

(defn- lines-of [cur-result]
  (concat (:bs cur-result) (:pl cur-result)))

(defn- declared-item [line] (get-in line [:declared :ias1/item]))

(defn- twelve-month-gaps
  "IAS 1.61 — accounts whose line combines both periods without stating the
  amount beyond twelve months.

  Run under BOTH presentation methods. `Whichever method of presentation is
  adopted` is the article's first clause, and switching this off with the
  current/non-current classification is the mistake the docstring names."
  [lines]
  (vec
   (sort
    (keep (fn [{:keys [account declared]}]
            (when (and (:ias1/combines-both-periods? declared)
                       (not (number? (:ias1/beyond-twelve-months declared))))
              account))
          lines))))

(defn- classification-gaps
  "IAS 1.60 — asset and liability lines with no current/non-current
  classification.

  Equity is not asked for: the article says `current and non-current assets,
  and current and non-current liabilities`, and nothing about equity."
  [lines]
  (vec
   (sort
    (keep (fn [{:keys [account type declared]}]
            (when (and (contains? #{:asset :liability} type)
                       (not (contains? #{:current :non-current}
                                       (:ias1/classification declared))))
              account))
          lines))))

(defn- current-non-current
  [method lines]
  (let [gaps-61 (twelve-month-gaps lines)]
    (case method
      :current-non-current
      (let [gaps-60 (classification-gaps lines)]
        {:answered? true :method method
         :unclassified-accounts gaps-60
         :undisclosed-twelve-month-accounts gaps-61
         :holds? (and (empty? gaps-60) (empty? gaps-61))
         :provisions ["IAS 1.60" "IAS 1.61"]})

      :liquidity
      {:answered? true :method method
       ;; IAS 1.60's own exception. 1.61 survives it.
       :unclassified-accounts []
       :undisclosed-twelve-month-accounts gaps-61
       :holds? (empty? gaps-61)
       :provisions ["IAS 1.60" "IAS 1.61"]}

      {:answered? false :method method
       :why :presentation-method-not-declared
       :detail (str "IAS 1.60 offers two methods and this statement declares "
                    "neither; which one applies is the entity's choice, not "
                    "this library's guess")
       :holds? false})))

(defn- currency-verdict
  [method required unverifiable cur-result]
  (let [lines (lines-of cur-result)
        by-item (group-by declared-item lines)
        present (set (keys by-item))
        missing (vec (sort-by #(:provision (item-of %))
                              (remove present required)))
        misplaced (vec (sort-by #(:provision (item-of %))
                                (keep (fn [k]
                                        (let [want (statement-of k)
                                              got (set (map :statement (by-item k)))]
                                          (when (and (seq got) (not (contains? got want)))
                                            k)))
                                      (filter present required))))
        cnc (current-non-current method lines)
        reasons (cond-> []
                  (seq missing) (conj :required-items-absent)
                  (seq misplaced) (conj :item-on-the-wrong-statement)
                  (seq unverifiable) (conj :scope-not-read)
                  (not (:holds? cnc)) (conj (or (:why cnc) :current-non-current-not-satisfied)))]
    {:conformant? (empty? reasons)
     ;; named, never counted — the core's own rule for an unclassified account
     :missing (vec (map (fn [k] {:item k
                                 :provision (:provision (item-of k))
                                 :label (:label (item-of k))})
                        missing))
     :misplaced (vec (map (fn [k] {:item k
                                   :provision (:provision (item-of k))
                                   :expected-statement (statement-of k)})
                          misplaced))
     :unverifiable unverifiable
     :current-non-current cnc
     :reasons (vec (sort-by name reasons))}))

(defn presentation
  "Does `r` — a result from `kotoba.shohyo/statements` — present the line
  items IAS 1 requires of it, and which required items are absent?

  `opts` may carry `:presentation-method`, `:current-non-current` or
  `:liquidity`, being the choice IAS 1.60 leaves to the entity. Absent, the
  current/non-current question is answered `:presentation-method-not-declared`
  and the statement is not conformant — a library that picked one would be
  making the entity's choice for it, and picking `:liquidity` would switch
  off a check by default, which is how a silent pass gets built.

  Returns, three-valued at the top and never a bare boolean:

      {:shohyo.ifrs/coverage :unread}        nothing in the catalogue was read
      {:shohyo.ifrs/coverage :not-declared}  no account declares an IAS 1 item
      {:shohyo.ifrs/coverage :checked ...}   answered, per currency

  **Only the third can be a pass, and it still need not be.** `:unread` and
  `:not-declared` are both `no` in the sense that matters — nothing was
  demonstrated — and they are kept apart because the fix differs: one is a
  citation to go and read, the other is a chart to go and tag.

  Required items are the ones the CHART DECLARES, not all twenty of IAS 1.54.
  IAS 1.31 and IAS 1.57 say a minimum list is not a checklist, and materiality
  is the entity's judgement. So this reports what the entity said it has and
  the statement does not show — and never invents a requirement.

  Missing items are named with their paragraph letter, never counted."
  ([r] (presentation r {}))
  ([r opts]
   (let [by-cur (:shohyo/by-currency r)
         all-lines (mapcat lines-of (vals by-cur))
         declared (into #{} (keep declared-item) all-lines)
         requirable (into #{} (filter requirable?) declared)
         unverifiable (vec (sort (filter unverifiable? declared)))
         ;; If nothing in the catalogue is read-from-source there is nothing
         ;; this module is entitled to assert. Derived, not asserted: a
         ;; provision downgraded to :reachable-not-read drops out here.
         any-read? (boolean (seq (filter #(= :read-from-source (:review %))
                                         (:paragraphs provisions))))]
     (cond
       (not any-read?)
       {:shohyo.ifrs/coverage :unread
        :shohyo.ifrs/why (str "no paragraph of IAS 1 is marked :read-from-source; "
                              "an unread standard cannot make a statement conformant")}

       (empty? declared)
       {:shohyo.ifrs/coverage :not-declared
        :shohyo.ifrs/why (str "no account in this statement declares an :ias1/item; "
                              "a framework nobody claimed is not a framework this "
                              "statement was checked against")}

       :else
       (let [method (:presentation-method opts)
             verdicts (into {}
                            (map (fn [[cur cr]]
                                   [cur (currency-verdict method requirable
                                                          unverifiable cr)]))
                            by-cur)
             ;; A statement short by whole accounts cannot be IAS 1 conformant,
             ;; whatever its line items say. The core already knows this and
             ;; there is no reason for the module to reach a cheerier answer.
             core-ok? (= :complete (:shohyo/coverage r))]
         {:shohyo.ifrs/coverage :checked
          :shohyo.ifrs/declared-items (vec (sort declared))
          :shohyo.ifrs/unverifiable-items unverifiable
          :shohyo.ifrs/core-coverage (:shohyo/coverage r)
          :shohyo.ifrs/by-currency verdicts
          ;; `verdicts` cannot be empty here: coverage is `:checked` only when
          ;; some line declared an item, and lines exist only inside
          ;; `:shohyo/by-currency`. An `(seq verdicts)` guard stood here and a
          ;; mutation proved it unreachable, so it is gone rather than left as
          ;; a check nothing can exercise.
          :shohyo.ifrs/conformant?
          (boolean (and core-ok? (every? :conformant? (vals verdicts))))
          :shohyo.ifrs/reasons
          (vec (sort-by name
                        (cond-> (into #{} (mapcat :reasons) (vals verdicts))
                          (not core-ok?) (conj :core-statement-incomplete))))})))))

(defn presented?
  "Convenience boolean over `presentation`, conservative like the rest.

  Deliberately not `(:shohyo.ifrs/conformant? ...)` alone: `:unread` and
  `:not-declared` carry no such key, so a caller reaching for the convenient
  boolean gets false there too. `shohyo/complete?`, `taxlaw/supported?` and
  `worklaw/compliant?` all make the same choice for the same reason — the
  convenient answer must be the conservative one, not the flattering one."
  ([r] (presented? r {}))
  ([r opts] (true? (:shohyo.ifrs/conformant? (presentation r opts)))))

(defn missing-items
  "Every required item absent from any currency's statement, named.

  `presented?` answers whether to worry; this answers what is short, the way
  `shohyo/out-of-balance` answers where. Keyed by currency, because a chart
  is one chart and a statement is one per currency: an item declared once can
  be absent from the USD statement and present in the JPY one."
  ([r] (missing-items r {}))
  ([r opts]
   (into {}
         (keep (fn [[cur v]]
                 (when (seq (:missing v))
                   [cur (mapv :provision (:missing v))])))
         (:shohyo.ifrs/by-currency (presentation r opts)))))

(defn unread-provisions
  "The paragraphs and standards this module cites without having read them.

  Exposed rather than buried in `catalog-verification` so a caller can print
  it. A reader who cannot see what was unread has to take the conformant
  answer entirely on trust — and `str/join` here rather than a count, for the
  same reason missing items are named."
  []
  (mapv (fn [{:keys [standard provision-cited scopes]}]
          {:standard standard
           :provision provision-cited
           :affects (str/join ", " scopes)})
        (:catalog/not-verified catalog-verification)))
