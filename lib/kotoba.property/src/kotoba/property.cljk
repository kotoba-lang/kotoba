(ns kotoba.property
  "Parcels, listings and leases — pure data contracts.

  A kotoba-lang capability library for the cloud-itonami-6810 (community
  real-estate agency) open business. No network, no I/O. Models the records a
  property operator keeps: land-parcel identifiers, property listings, and
  lease records (parties, term, rent) with term-overlap detection.

  Amounts are plain numbers in the smallest unit of the account currency.
  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM."
  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------------------
;; Parcel — land identifier (national format-agnostic)
;; ---------------------------------------------------------------------------

(defn parcel
  "Construct a land-parcel record. id is the national cadastre reference."
  [id & {:keys [address area-m2 zoning]}]
  {:parcel/id      id
   :parcel/address address
   :parcel/area-m2 area-m2
   :parcel/zoning  zoning})

;; ---------------------------------------------------------------------------
;; Listing
;; ---------------------------------------------------------------------------

(def listing-types #{:sale :rent})

(defn listing
  "Construct a property listing. type is :sale or :rent."
  [id parcel-id ltype price & {:keys [currency agent]}]
  (when (contains? listing-types ltype)
    {:listing/id      id
     :listing/parcel  parcel-id
     :listing/type    ltype
     :listing/price   price
     :listing/currency (or currency "USD")
     :listing/agent   agent}))

;; ---------------------------------------------------------------------------
;; Lease
;; ---------------------------------------------------------------------------

(defn lease
  "Construct a lease record. start/end are comparable keys (e.g. date strings
  or epoch numbers). rent is the smallest-currency-unit amount per period."
  [id parcel-id tenant landlord rent start end & {:keys [currency]}]
  {:lease/id       id
   :lease/parcel   parcel-id
   :lease/tenant   tenant
   :lease/landlord landlord
   :lease/rent     rent
   :lease/currency (or currency "USD")
   :lease/start    start
   :lease/end      end})

(defn term-overlaps?
  "True when two leases are on the same parcel and their [start,end] terms
  overlap (a double-booking conflict). Leases on different parcels never
  overlap, regardless of dates. Assumes start <= end in the same ordering
  domain for both leases."
  [a b]
  (let [as (:lease/start a) ae (:lease/end a)
        bs (:lease/start b) be (:lease/end b)]
    (and (:lease/parcel a) (= (:lease/parcel a) (:lease/parcel b))
         as ae bs be
         (not (or (neg? (compare ae bs)) (pos? (compare as be)))))))

;; ---------------------------------------------------------------------------
;; Validation
;; ---------------------------------------------------------------------------

(defn validate-listing
  "Return a validation result for a listing record."
  [m]
  (cond
    (not (map? m))                       {:property/valid? false :property/error :not-a-map}
    (not (:listing/id m))                {:property/valid? false :property/error :missing-id}
    (not (contains? listing-types (:listing/type m)))
    {:property/valid? false :property/error :unknown-type}
    :else                                {:property/valid? true :listing/type (:listing/type m)}))
