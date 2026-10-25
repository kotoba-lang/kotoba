(ns senden.projection
  "Cross-domain projection: mise.order → senden attribution.

  Bridges retail EC (mise) and marketing (senden): a placed mise order's
  customer touch-path is attributed to a campaign so a purchase can credit the
  marketing funnel. v1 is a pure stub — the host app owns the touch store;
  this namespace computes attribution given touches and records a conversion on
  the credited campaign."
  (:require [senden.attribution :as attr]
            [senden.campaign :as campaign]
            [chobo.ledger :as ledger]))

(defn attribute-order
  "Attribute a mise order's purchase touch-path to a campaign by `model`
  (:first/:last/:linear/:multi). Returns {campaign-id → weight/credit}."
  [touches model]
  (attr/attribute model touches))

(defn credit-campaign
  "Record a conversion (default n=1) on the campaign credited by attribution.
  Returns the updated campaign, or the original if uncredited."
  ([campaigns touches model]
   (credit-campaign campaigns touches model 1))
  ([campaigns touches model n]
   (let [weights (attr/attribute model touches)]
     (if-let [top (first (sort-by second > weights))]
       (let [campaign-id (key top)]
         (if-let [c (some #(when (= (:id %) campaign-id) %) campaigns)]
           (campaign/record-conversion c n)
           (first campaigns)))
       (first campaigns)))))

(defn attribution-activity
  "Project the order→attribution event onto chobo.ledger as a :marketing
  activity (kind :attribution). Caller appends to its ILedgerStore."
  [ord weights opts]
  (ledger/activity
   (merge {:lane :marketing :kind :attribution
           :title (str "Attribution for order " (:id ord))
           :props {:order-id (:id ord) :weights weights}}
          opts)))
