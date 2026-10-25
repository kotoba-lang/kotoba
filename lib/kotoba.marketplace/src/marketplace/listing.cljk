(ns marketplace.listing
  "Listing admission and the buyer-facing search projection — the layer
  that decides whether an offer may become publicly visible, and how a
  buyer finds it.

  A LISTING is the public face of an OFFER: title, description, images,
  category, plus the compliance attestations the operator requires. An
  offer can exist in the catalog while its listing is refused (a seller
  can price an item the operator will not display).

  ## Restricted goods: a policy table, not a claim to know the law

  There is no honest way for a library to enumerate what every
  jurisdiction prohibits. This namespace therefore ships a small
  BASELINE of categories that essentially every consumer marketplace
  restricts, and otherwise takes the operator's own policy table as
  input. The baseline is deliberately a floor, not a legal opinion, and
  `restricted-baseline` says so in its own docstring. An operator
  running in a specific jurisdiction supplies `:policy` with their real
  list; this library never pretends to have derived one.

  Consistent with the fleet's non-adjudication discipline, a restricted
  category here produces a REFUSAL TO DISPLAY, never a finding that the
  seller did something unlawful. The listing actor's governor treats
  'finalizing a legality determination' as a permanent scope exclusion,
  exactly as ISIC 4791 does for fraud determinations.

  ## Search

  Projection targets `kotoba-lang/search` (`search.model`) rather than a
  bespoke index. KNOWN LIMITATION, stated rather than hidden: that
  library's `tokenize` matches runs of `[a-z0-9]` and CJK ranges, so a
  Japanese phrase like \"ワイヤレスイヤホン\" becomes ONE token and a
  query for \"イヤホン\" will not match it. There is no morphological
  segmentation upstream. The mitigation here is `:listing/keywords` —
  explicit seller/operator-supplied terms that land in `:search/tags`,
  which the buyer surface can also render as facets. Do not read the
  presence of a search projection as a claim of good Japanese recall.

  Pure: no clock, no network, no randomness."
  (:require [kotoba.lang.text :as str]
            [marketplace.catalog :as catalog]
            [search.model :as search]))

;; ───────────────────────────── vocabulary ─────────────────────────────

(def statuses
  "Listing lifecycle. Only `:live` is publicly visible."
  #{:draft :live :suppressed :withdrawn})

(def restricted-baseline
  "A FLOOR, not a legal opinion and not exhaustive.

  These are categories that essentially every consumer marketplace
  restricts regardless of jurisdiction, so refusing them by default is
  safer than defaulting open. An operator MUST supply their own
  jurisdiction policy on top of this — see `admission`'s `:policy`
  option. Nothing here should be read as advice about what is lawful
  in any particular country."
  #{:weapons-firearms
    :explosives
    :controlled-substances
    :prescription-pharmaceuticals
    :human-remains-organs
    :endangered-species
    :counterfeit-goods
    :stolen-goods
    :csam
    :covert-surveillance-devices
    :government-identity-documents})

(def attestations
  "Attestations a seller may be required to make. Which of these are
  REQUIRED is an operator policy input, never assumed here."
  #{:authentic-goods :right-to-sell :accurate-condition
    :export-eligible :age-restricted-handled})

;; ───────────────────────────── listing ─────────────────────────────

(defn listing
  "Build a listing over an existing offer id. Does not validate."
  [{:keys [id offer product seller title description category keywords
           images status attested condition-note]
    :or   {status :draft images [] keywords [] attested #{}}}]
  {:listing/id          (or id (str "listing." offer))
   :listing/offer       (str offer)
   :listing/product     (str product)
   :listing/seller      (str seller)
   :listing/title       title
   :listing/description (or description "")
   :listing/category    category
   :listing/keywords    (vec keywords)
   :listing/images      (vec images)
   :listing/status      status
   :listing/attested    (set attested)
   :listing/condition-note condition-note})

;; ───────────────────────────── admission ─────────────────────────────

(defn- content-errors [l]
  (vec
   (concat
    (when (str/blank? (str (:listing/title l)))
      [{:listing.error/code :missing-title}])
    (when (and (:listing/title l) (> (count (str (:listing/title l))) 200))
      [{:listing.error/code :title-too-long :listing.error/detail "200 文字以内"}])
    (when-not (contains? statuses (:listing/status l))
      [{:listing.error/code :invalid-status :listing.error/detail (pr-str (:listing/status l))}])
    (when (empty? (:listing/images l))
      [{:listing.error/code :no-images}])
    (when-not (keyword? (:listing/category l))
      [{:listing.error/code :missing-category}]))))

(defn admission
  "Decide whether a listing may go live.

  `opts`:
    `:policy`        extra restricted categories for this operator's
                     jurisdiction (unioned with `restricted-baseline`)
    `:require`       set of attestations this operator requires
    `:seller-ok?`    truthy when the seller is `sellable?` — the caller
                     passes `marketplace.seller/sellable?`, because
                     identity is that namespace's business, not this one's
    `:counterfeit-signal` truthy when an independent verification service
                     (e.g. cloud-itonami-gtin-verification) flagged the
                     item; a REFUSAL to display, never a finding of
                     counterfeiting

  Returns {:admission/outcome :admissible|:review|:refused
           :admission/reasons [kw ..]}.

  `:refused` reasons are structural — the listing actor's governor
  treats them as HARD blocks that no human approval overrides at the
  library level. `:review` means a human must look before it displays."
  ([l] (admission l {}))
  ([l {:keys [policy require seller-ok? counterfeit-signal]
       :or   {policy #{} require #{}}}]
   (let [restricted (into restricted-baseline policy)
         attested   (:listing/attested l)
         missing-attestations (remove attested require)
         reasons
         (vec
          (concat
           (map :listing.error/code (content-errors l))
           (when (contains? restricted (:listing/category l)) [:restricted-category])
           (when counterfeit-signal [:counterfeit-signal])
           (when-not seller-ok? [:seller-not-sellable])
           (when (seq missing-attestations) [:missing-attestation])
           (when (= :withdrawn (:listing/status l)) [:withdrawn])
           (when (= :suppressed (:listing/status l)) [:suppressed])
           (when (= :draft (:listing/status l)) [:not-yet-live])))
         refusing #{:restricted-category :counterfeit-signal :seller-not-sellable
                    :missing-title :title-too-long :invalid-status :no-images
                    :missing-category :withdrawn}
         reviewing #{:missing-attestation :suppressed :not-yet-live}]
     {:admission/outcome (cond
                           (some refusing reasons)  :refused
                           (some reviewing reasons) :review
                           :else                    :admissible)
      :admission/reasons reasons
      :admission/missing-attestations (vec missing-attestations)
      :admission/non-adjudicating true})))

(defn displayable?
  "The single question the buyer surface asks before rendering."
  ([l] (displayable? l {}))
  ([l opts] (= :admissible (:admission/outcome (admission l opts)))))

;; ───────────────────────────── search projection ─────────────────────────────

(defn ->search-document
  "Project a listing into a `search.model` document.

  `:search/tags` carries the seller/operator keywords plus the category
  and seller id, which is what makes faceting and (partially) Japanese
  retrieval work despite the upstream tokenizer's lack of morphological
  segmentation — see this namespace's docstring."
  [l]
  (search/document
   (:listing/id l)
   {:search/title (str (:listing/title l))
    :search/body  (str/join " " [(:listing/description l)
                                 (:listing/condition-note l)])
    :search/tags  (into #{(name (or (:listing/category l) :uncategorized))
                          (:listing/seller l)
                          (:listing/product l)}
                        (map str (:listing/keywords l)))}))

(defn index-listings
  "Build a search index over the listings that are actually displayable
  under `opts`. A refused or under-review listing is never indexed —
  the buyer surface cannot leak something the admission layer declined
  to display, because it simply is not in the index."
  ([ls] (index-listings ls {}))
  ([ls opts]
   (reduce (fn [idx l]
             (if (displayable? l opts)
               (search/add-document idx (->search-document l))
               idx))
           (search/index)
           ls)))

(defn index-admissible
  "Like `index-listings` but takes pre-decided pairs
  `[[listing admission] ..]`, so an actor that already ran admission
  through its governor does not run it twice (and cannot disagree with
  itself between the two runs)."
  [pairs]
  (reduce (fn [idx [l adm]]
            (if (= :admissible (:admission/outcome adm))
              (search/add-document idx (->search-document l))
              idx))
          (search/index)
          pairs))

(defn search-listings
  "Run a buyer query against an index built here. Delegates scoring to
  `search.model/search` — this namespace adds no ranking of its own, so
  there is no hidden placement boost (the same discipline
  `marketplace.catalog/buy-box` follows)."
  [idx q]
  (search/search idx q))

;; ───────────────────────────── product page ─────────────────────────────

(defn product-page
  "Everything a buyer-facing product page needs, assembled from the
  catalog and the listings on one canonical product.

  Returns the buy-box result alongside the full offer list, so the page
  can show 'N sellers' and the losing offers too — a marketplace that
  hides the losing offers is hiding the mechanism, which is exactly
  what this design set out not to do (ADR-2607264000 D1).

  Listings are matched to offers by `:listing/offer` = `:offer/id`. A
  listing whose offer id matches nothing in the catalog is reported in
  `:page/orphan-listings` rather than silently dropped, and an offer
  with no listing is reported in `:page/unlisted-offers`. Both are
  ordinary states (a seller can price before writing copy), but a
  page that quietly discarded them would hide a wiring mistake until a
  buyer noticed the item missing."
  ([cat product-id listings] (product-page cat product-id listings {}))
  ([cat product-id listings opts]
   (let [offers   (catalog/offers-for-product cat product-id)
         bb       (catalog/buy-box cat product-id opts)
         by-offer (into {} (map (juxt :listing/offer identity) listings))
         offer-ids (set (map :offer/id offers))
         matched  (vec (keep #(get by-offer (:offer/id %)) offers))]
     {:page/product         product-id
      :page/offers          offers
      :page/sellers         (catalog/sellers-for-product cat product-id)
      :page/buy-box         bb
      :page/listings        matched
      :page/offer-count     (count offers)
      :page/orphan-listings (vec (remove #(contains? offer-ids (:listing/offer %)) listings))
      :page/unlisted-offers (vec (remove #(contains? by-offer (:offer/id %)) offers))})))
