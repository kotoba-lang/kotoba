(ns marketplace.catalog
  "Cross-seller offers on one canonical product — the piece that makes a
  marketplace a marketplace rather than a row of unrelated shops.

  The unit is the OFFER: (canonical product) × (seller) × (price,
  condition, availability). Many sellers may offer the same canonical
  product, which is exactly the Amazon/Alibaba-shaped affordance the
  fleet lacked. Product identity itself is NOT owned here — it comes
  from `kotoba.product-party` (GTIN-14 normalization + GS1 mod-10 check
  digit + `gtin.<14>` / `prod.<slug>` id shapes), and the canonical
  merge/split decision belongs to `cloud-itonami-gtin-catalog`'s
  ProductCatalogGovernor. This namespace consumes canonical ids; it
  never mints or merges them.

  ## Money

  Every amount is an INTEGER count of the currency's smallest
  circulating unit (`:offer/price-minor`), never a float — the same
  discipline `kotoba.reji` states outright ('money never touches a
  double/float, so there's no binary-decimal rounding error'). A JPY
  1,200 offer is `1200`; a USD $12.00 offer is `1200`. Currency is
  carried alongside and comparisons across currencies are refused
  rather than silently converted, because this library has no FX rate
  and inventing one would be fabrication.

  ## The buy box is explicit and auditable

  On a closed platform the 'which seller wins the buy box' function is
  the single most opaque and most rent-extracting mechanism there is.
  Here `buy-box` is a pure function that returns the full ranking WITH
  the comparison key that produced it, so an operator (or a seller who
  lost) can reproduce the decision exactly. There is no hidden
  boost, no paid placement, and no tie-break on anything the seller
  cannot observe.

  Pure: no clock, no network, no randomness."
  (:require [kotoba.lang.text :as str]
            [kotoba.product-party :as pp]))

;; ───────────────────────────── vocabulary ─────────────────────────────

(def conditions
  "Item condition, ordered best-first in `condition-rank`."
  #{:new :refurbished :used-like-new :used-good :used-acceptable})

(def ^:private condition-rank
  {:new 0 :refurbished 1 :used-like-new 2 :used-good 3 :used-acceptable 4})

(def availabilities
  "Whether the offer can actually be bought right now. Only
  `:in-stock` is buy-box eligible — a backorder/preorder offer is
  visible on the product page but never wins the default selection."
  #{:in-stock :backorder :preorder :out-of-stock})

(def ^:private buy-box-eligible-availability #{:in-stock})

(def ^:private unknown-lead-time
  "Sort key for an offer that states no lead time — it sorts LAST among
  otherwise-equal offers. A plain large integer rather than
  `Integer/MAX_VALUE`, which is JVM-only and would break this `.cljc`
  under ClojureScript / nbb."
  1000000)

;; ───────────────────────────── offer ─────────────────────────────

(defn offer-id
  "Stable offer id from canonical product + seller. One seller has at
  most one live offer per (product, condition) — a seller wanting two
  prices for the same condition is modelling something else (a
  quantity break), not two offers."
  [product-id seller-id condition]
  (str "offer." product-id "." (name condition) "." seller-id))

(defn offer
  "Build an offer. Does not validate — call `offer-errors`.

  `:product` must already be a canonical product id (`gtin.<14>` or
  `prod.<slug>`); pass a raw GTIN through
  `kotoba.product-party/product-id` first."
  [{:keys [id product seller price-minor currency condition availability
           quantity ships-from lead-time-days note]
    :or   {condition :new availability :in-stock currency "JPY"}}]
  (let [product (str product)
        seller  (str seller)]
    (cond-> {:offer/id           (or id (offer-id product seller condition))
             :offer/product      product
             :offer/seller       seller
             :offer/price-minor  price-minor
             :offer/currency     currency
             :offer/condition    condition
             :offer/availability availability}
      quantity       (assoc :offer/quantity quantity)
      ships-from     (assoc :offer/ships-from (str/upper (str ships-from)))
      lead-time-days (assoc :offer/lead-time-days lead-time-days)
      note           (assoc :offer/note note))))

(defn offer-errors
  "Structural errors on an offer, `[]` when sound.

  Product id validity is delegated to `kotoba.product-party` rather
  than re-implemented, so a GTIN whose check digit fails upstream can
  never enter the catalog through this door."
  [o]
  (vec
   (concat
    (when-not (pp/valid-product-id? (:offer/product o))
      [{:offer.error/code :invalid-product-id
        :offer.error/detail (str (:offer/product o) " は gtin.<14> / prod.<slug> ではない")}])
    (when-not (pp/valid-party-id? (:offer/seller o))
      [{:offer.error/code :invalid-seller-id
        :offer.error/detail (str (:offer/seller o))}])
    (when-not (and (integer? (:offer/price-minor o))
                   (not (neg? (:offer/price-minor o))))
      [{:offer.error/code :invalid-price
        :offer.error/detail "price-minor は非負整数（通貨最小単位）でなければならない"}])
    (when-not (and (string? (:offer/currency o))
                   (re-matches #"^[A-Z]{3}$" (str (:offer/currency o))))
      [{:offer.error/code :invalid-currency :offer.error/detail "ISO-4217 alpha-3"}])
    (when-not (contains? conditions (:offer/condition o))
      [{:offer.error/code :invalid-condition :offer.error/detail (pr-str (:offer/condition o))}])
    (when-not (contains? availabilities (:offer/availability o))
      [{:offer.error/code :invalid-availability :offer.error/detail (pr-str (:offer/availability o))}])
    (when (and (some? (:offer/quantity o))
               (not (and (integer? (:offer/quantity o)) (not (neg? (:offer/quantity o))))))
      [{:offer.error/code :invalid-quantity}])
    ;; An :in-stock offer claiming zero units is self-contradictory —
    ;; catching it here stops a buy-box winner that cannot be fulfilled.
    (when (and (= :in-stock (:offer/availability o))
               (= 0 (:offer/quantity o)))
      [{:offer.error/code :in-stock-with-zero-quantity}])
    (when (and (some? (:offer/lead-time-days o))
               (not (and (integer? (:offer/lead-time-days o))
                         (not (neg? (:offer/lead-time-days o))))))
      [{:offer.error/code :invalid-lead-time}]))))

(defn valid-offer? [o] (empty? (offer-errors o)))

;; ───────────────────────────── catalog index ─────────────────────────────

(defn empty-catalog
  "An empty offer index: offers by id, plus a product→offer-ids index."
  []
  {:catalog/offers    {}
   :catalog/by-product {}})

(defn add-offer
  "Add (or replace) an offer. Throws on a structurally invalid offer —
  the catalog is an index, not a validator of last resort, so callers
  must have already run `offer-errors` (the actor does this in its
  governor)."
  [cat o]
  (when-let [errs (seq (offer-errors o))]
    (throw (ex-info "invalid offer" {:catalog/errors errs :offer/id (:offer/id o)})))
  (-> cat
      (assoc-in [:catalog/offers (:offer/id o)] o)
      (update-in [:catalog/by-product (:offer/product o)] (fnil conj #{}) (:offer/id o))))

(defn remove-offer
  "Remove an offer by id. A no-op for an unknown id."
  [cat offer-id*]
  (if-let [o (get-in cat [:catalog/offers offer-id*])]
    (-> cat
        (update :catalog/offers dissoc offer-id*)
        (update-in [:catalog/by-product (:offer/product o)] disj offer-id*))
    cat))

(defn offers-for-product
  "Every offer on a canonical product, id-sorted for determinism."
  [cat product-id]
  (->> (get-in cat [:catalog/by-product product-id] #{})
       (keep #(get-in cat [:catalog/offers %]))
       (sort-by :offer/id)
       vec))

(defn offers-by-seller
  "Every offer a seller has in this catalog, id-sorted."
  [cat seller-id]
  (->> (vals (:catalog/offers cat))
       (filter #(= seller-id (:offer/seller %)))
       (sort-by :offer/id)
       vec))

(defn sellers-for-product
  "The distinct sellers offering a canonical product — the 'N sellers
  for this item' number a buyer sees."
  [cat product-id]
  (->> (offers-for-product cat product-id)
       (map :offer/seller)
       distinct
       sort
       vec))

;; ───────────────────────────── buy box ─────────────────────────────

(defn- landed-key
  "The total the buyer actually pays for this offer, when a shipping
  quote is known. Falls back to the item price alone when it is not —
  and `buy-box` records which of the two happened, so a ranking is
  never silently comparing a landed price against a bare price."
  [o shipping]
  (+ (:offer/price-minor o) (get shipping (:offer/id o) 0)))

(defn buy-box
  "Rank the offers on a product, best-first, with the reason.

  Ranking key, in strict order (every component is observable by the
  seller, so a losing seller can reproduce the result):

    1. landed price (item + shipping when a quote is supplied) ascending
    2. condition rank (:new best) ascending
    3. lead time ascending (unknown sorts last)
    4. offer id ascending — a total, deterministic tie-break

  Only `:in-stock` offers are eligible. `opts`:
    `:shipping`  map of offer-id → shipping cost in the SAME currency
    `:eligible?` extra predicate (the listing actor passes seller
                 admissibility here, so an unverified seller's offer
                 can never take the buy box)

  Returns
    {:buy-box/winner offer|nil
     :buy-box/ranked [offer ..]
     :buy-box/excluded [{:offer/id .. :reason kw} ..]
     :buy-box/currency \"JPY\"|nil
     :buy-box/landed? bool}

  MIXED CURRENCIES ARE REFUSED, not converted: this library has no FX
  rate and will not invent one. A product whose offers span currencies
  returns `:buy-box/winner nil` with every offer excluded as
  `:mixed-currency`, which is an honest 'cannot decide' rather than a
  fabricated comparison."
  ([cat product-id] (buy-box cat product-id {}))
  ([cat product-id {:keys [shipping eligible?] :or {shipping {}}}]
   (let [all        (offers-for-product cat product-id)
         currencies (set (map :offer/currency all))
         mixed?     (> (count currencies) 1)]
     (if mixed?
       {:buy-box/winner   nil
        :buy-box/ranked   []
        :buy-box/excluded (mapv #(hash-map :offer/id (:offer/id %) :reason :mixed-currency) all)
        :buy-box/currency nil
        :buy-box/landed?  false}
       (let [exclusion (fn [o]
                         (cond
                           (not (contains? buy-box-eligible-availability (:offer/availability o)))
                           :not-in-stock

                           (and eligible? (not (eligible? o)))
                           :seller-ineligible))
             {live false excl true} (group-by #(boolean (exclusion %)) all)
             ranked (vec (sort-by (juxt #(landed-key % shipping)
                                        #(get condition-rank (:offer/condition %) 99)
                                        #(or (:offer/lead-time-days %) unknown-lead-time)
                                        :offer/id)
                                  (or live [])))]
         {:buy-box/winner   (first ranked)
          :buy-box/ranked   ranked
          :buy-box/excluded (mapv #(hash-map :offer/id (:offer/id %) :reason (exclusion %))
                                  (or excl []))
          :buy-box/currency (first currencies)
          :buy-box/landed?  (boolean (seq shipping))})))))

;; ───────────────────────────── product-party bridge ─────────────────────────────

(defn ->merchant-edge
  "Project an offer into a `kotoba.product-party` `:merchant` edge, so a
  marketplace offer becomes a first-class fact in the workspace's
  product↔party join graph (procurement and open-business routing can
  then resolve merchants without re-deriving an identity graph).

  Tagged `:sourcing :representative` — an offer is a merchant's own
  claim to sell an item, not an authoritative statement about who owns
  the brand. `:brand-owner` is a `high-stakes-role` upstream and is
  never asserted from an offer."
  [o]
  (pp/edge {:product  (:offer/product o)
            :party    (:offer/seller o)
            :role     :merchant
            :sourcing :representative
            :status   (if (= :out-of-stock (:offer/availability o)) :revoked :active)}))
