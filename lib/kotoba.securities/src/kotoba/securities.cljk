(ns kotoba.securities
  "Positions, trades and fund shares — pure data contracts.

  A kotoba-lang capability library for the cloud-itonami securities/fund
  vertical (ISIC 6420 holding companies, 6430 trusts/funds, 6611 market
  administration, 6612 securities/commodity brokerage, 6630 fund
  management): equity-position, trade, fund-share/NAV, and investment-
  mandate pure-data contracts + validation.

  This library carries no real market data, price feed or custody
  integration -- an operator supplies their own licensed data/custody
  providers; the pure functions here only combine supplied facts (a
  position's quantity/price, a fund's asset value and outstanding units)
  the same way kotoba-lang/banking supplies IBAN math but not a real
  correspondent network.

  Amounts are plain numbers in the smallest unit of the account currency.
  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM."
  )

;; ---------------------------------------------------------------------------
;; Position -- an equity/asset holding (holding-company subsidiary stake,
;; brokerage client position, fund-manager mandate holding)
;; ---------------------------------------------------------------------------

(defn position
  "Construct a position record. quantity is a plain number of units/shares."
  [id holder instrument quantity & {:keys [currency price]}]
  {:position/id         id
   :position/holder     holder
   :position/instrument instrument
   :position/quantity   quantity
   :position/currency   (or currency "USD")
   :position/price      price})

(defn position-value [pos]
  (when (and (:position/quantity pos) (:position/price pos))
    (* (:position/quantity pos) (:position/price pos))))

;; ---------------------------------------------------------------------------
;; Trade
;; ---------------------------------------------------------------------------

(def trade-sides #{:buy :sell})

(defn trade
  "Construct a trade record. side is :buy or :sell."
  [id account instrument side quantity price & {:keys [currency]}]
  (when (contains? trade-sides side)
    {:trade/id         id
     :trade/account    account
     :trade/instrument instrument
     :trade/side       side
     :trade/quantity   quantity
     :trade/price      price
     :trade/currency   (or currency "USD")}))

(defn trade-notional [tr]
  (when (and (:trade/quantity tr) (:trade/price tr))
    (* (:trade/quantity tr) (:trade/price tr))))

;; ---------------------------------------------------------------------------
;; Fund share / NAV
;; ---------------------------------------------------------------------------

(defn fund-nav
  "Construct a fund NAV-per-share record from total net assets and
  outstanding units. Pure arithmetic -- no valuation judgement."
  [fund-id net-assets outstanding-units & {:keys [currency as-of]}]
  (when (pos? outstanding-units)
    {:nav/fund fund-id
     :nav/net-assets net-assets
     :nav/outstanding-units outstanding-units
     :nav/per-share (double (/ net-assets outstanding-units))
     :nav/currency (or currency "USD")
     :nav/as-of as-of}))

;; ---------------------------------------------------------------------------
;; Investment mandate (fund-management guideline)
;; ---------------------------------------------------------------------------

(defn mandate
  "Construct an investment-mandate record. limits is a map of guideline
  keys to numeric constraints (e.g. {:max-single-issuer-pct 10})."
  [id fund limits]
  {:mandate/id id :mandate/fund fund :mandate/limits limits})

(defn breaches-mandate?
  "True when the position's share of the fund exceeds a
  :max-single-issuer-pct limit in the mandate."
  [mandate-rec position-value-pct]
  (when-let [limit (get-in mandate-rec [:mandate/limits :max-single-issuer-pct])]
    (> position-value-pct limit)))

;; ---------------------------------------------------------------------------
;; Validation
;; ---------------------------------------------------------------------------

(defn validate-trade
  "Return a validation result for a trade record."
  [m]
  (cond
    (not (map? m))                       {:securities/valid? false :securities/error :not-a-map}
    (not (:trade/id m))                  {:securities/valid? false :securities/error :missing-id}
    (not (contains? trade-sides (:trade/side m)))
    {:securities/valid? false :securities/error :unknown-side}
    (not (pos? (or (:trade/quantity m) 0)))
    {:securities/valid? false :securities/error :non-positive-quantity}
    :else                                 {:securities/valid? true :trade/side (:trade/side m)}))

(defn validate-position
  "Return a validation result for a position record."
  [m]
  (cond
    (not (map? m))         {:securities/valid? false :securities/error :not-a-map}
    (not (:position/id m)) {:securities/valid? false :securities/error :missing-id}
    :else                  {:securities/valid? true}))
