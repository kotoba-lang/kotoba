(ns kotoba.logistics
  "Shipments, tracking numbers, routes and freight — pure data contracts.

  A kotoba-lang capability library for the cloud-itonami-4920 (community
  freight transport) open business. No network, no I/O. Models the records a
  logistics operator keeps: shipment records, tracking-number normalization
  and structural validation, route legs, and freight/consignment records.

  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM."
  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------------------
;; Tracking number — carrier-agnostic structural contract
;; ---------------------------------------------------------------------------

(defn normalize-tracking
  "Normalize a tracking number: upper-case, strip spaces/dashes. Returns nil
  for non-strings."
  [s]
  (when (string? s)
    (str/upper (str/replace s #"[ \-]" ""))))

(defn tracking-valid?
  "True when s is a plausible tracking number: 8..35 chars, upper alnum."
  [s]
  (when-let [t (normalize-tracking s)]
    (boolean (re-matches #"[A-Z0-9]{8,35}" t))))

;; ---------------------------------------------------------------------------
;; Shipment
;; ---------------------------------------------------------------------------

(defn shipment
  "Construct a shipment record. status is one of :booked/:picked-up
  /:in-transit/:delivered/:exception."
  [id origin destination carrier & {:keys [tracking weight items status]}]
  (let [st (or status :booked)]
    (when (contains? #{:booked :picked-up :in-transit :delivered :exception} st)
      {:shipment/id          id
       :shipment/origin      origin
       :shipment/destination destination
       :shipment/carrier     carrier
       :shipment/tracking    tracking
       :shipment/weight      weight
       :shipment/items       (or items 1)
       :shipment/status      st})))

(defn delivered? [s] (= :delivered (:shipment/status s)))
(defn in-transit? [s] (= :in-transit (:shipment/status s)))

;; ---------------------------------------------------------------------------
;; Route leg and freight consignment
;; ---------------------------------------------------------------------------

(defn leg
  "Construct a route leg between two nodes. mode is :road/:rail/:air/:sea."
  [from to mode & {:keys [distance-km]}]
  (when (contains? #{:road :rail :air :sea} mode)
    {:leg/from        from
     :leg/to          to
     :leg/mode        mode
     :leg/distance-km distance-km}))

(defn consignment
  "Construct a freight consignment: a shipment moved over a route of legs."
  [id shipment-record legs & {:keys [declared-value]}]
  {:cons/id         id
   :cons/shipment   (:shipment/id shipment-record)
   :cons/route      legs
   :cons/declared-value declared-value
   :cons/status     (:shipment/status shipment-record)})

;; ---------------------------------------------------------------------------
;; Validation
;; ---------------------------------------------------------------------------

(defn validate-tracking
  "Return a validation result for a candidate tracking number."
  [s]
  (cond
    (not (string? s))         {:logistics/valid? false :logistics/error :not-a-string}
    (not (tracking-valid? s)) {:logistics/valid? false :logistics/error :malformed-tracking}
    :else                     {:logistics/valid? true :logistics/normalized (normalize-tracking s)}))
