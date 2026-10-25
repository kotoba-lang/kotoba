(ns kotoba.property.export
  "Operator-facing export for a real-estate-agency actor.

  Renders parcels, listings and leases to CSV and JSON for tenancy audit and
  downstream reporting. Pure data → text: no network."
  (:require [kotoba.lang.text :as str]
            [kotoba.property :as prop]))

(defn- csv-cell [v]
  (let [s (str (if (nil? v) "" v))]
    ;; RFC 4180 requires quoting a field containing a comma, a double
    ;; quote, OR a line break -- \r alone is also a line break (a CR-only
    ;; row terminator every standard CSV reader recognizes), but the
    ;; check here only ever covered \n. A field containing a bare \r
    ;; (verified against Python's csv module) silently split into two
    ;; corrupted rows on read-back instead of round-tripping as one.
    (if (re-find #"[\",\n\r]" s)
      (str "\"" (str/replace s "\"" "\"\"") "\"")
      s)))

(defn- csv-row [vals] (str/join "," (map csv-cell vals)))

(def ^:private json-hex-digits "0123456789abcdef")

(defn- json-hex4
  "4-digit hex for a JSON `\\uXXXX` escape (portable: bit ops + a lookup
  table, no Long/Integer interop that would only work on :clj)."
  [n]
  (apply str (for [shift [12 8 4 0]] (nth json-hex-digits (bit-and (bit-shift-right n shift) 0xf)))))

(def ^:private json-string-escapes
  "RFC 8259 §7: EVERY control character U+0000-U+001F must be escaped in
  a JSON string, not just \\ \" and \\n -- an operator-supplied field
  containing a raw \\t, \\r, or other control byte would otherwise be
  copied through raw, producing invalid JSON (verified against Python's
  strict json module)."
  (into {\" "\\\"" \\ "\\\\"}
        (for [i (range 0x20)]
          [(char i) (case i
                      8 "\\b" 9 "\\t" 10 "\\n" 12 "\\f" 13 "\\r"
                      (str "\\u" (json-hex4 i)))])))

(defn- json-str [v]
  (str/escape (str (if (nil? v) "" v)) json-string-escapes))

(defn parcels->csv [parcels]
  (str/join "\n"
    (cons (csv-row ["parcel_id" "address" "area_m2" "zoning"])
          (for [p parcels]
            (csv-row [(:parcel/id p)
                      (or (:parcel/address p) "")
                      (or (:parcel/area-m2 p) "")
                      (name (or (:parcel/zoning p) :unspecified))])))))

(defn listings->csv [listings]
  (str/join "\n"
    (cons (csv-row ["listing_id" "parcel" "type" "price" "currency"])
          (for [l listings]
            (csv-row [(:listing/id l)
                      (:listing/parcel l)
                      (name (:listing/type l))
                      (:listing/price l)
                      (:listing/currency l)])))))

(defn leases->csv [leases]
  (str/join "\n"
    (cons (csv-row ["lease_id" "parcel" "tenant" "landlord" "rent" "start" "end" "overlap"])
          (for [l leases]
            (csv-row [(:lease/id l)
                      (:lease/parcel l)
                      (or (:lease/tenant l) "")
                      (or (:lease/landlord l) "")
                      (:lease/rent l)
                      (:lease/start l)
                      (:lease/end l)
                      (if (some #(prop/term-overlaps? l %) (remove #{l} leases)) "yes" "no")])))))

(defn parcels->json [parcels]
  (str "["
       (str/join ","
                 (for [p parcels]
                   (str "{\"parcel_id\":\"" (json-str (:parcel/id p)) "\","
                        "\"address\":\"" (json-str (:parcel/address p)) "\","
                        "\"area_m2\":" (or (:parcel/area-m2 p) 0) ","
                        "\"zoning\":\"" (name (or (:parcel/zoning p) :unspecified)) "\"}")))
       "]"))

(defn leases->json [leases]
  (str "["
       (str/join ","
                 (for [l leases]
                   (str "{\"lease_id\":\"" (json-str (:lease/id l)) "\","
                        "\"parcel\":\"" (json-str (:lease/parcel l)) "\","
                        "\"tenant\":\"" (json-str (:lease/tenant l)) "\","
                        "\"rent\":" (or (:lease/rent l) 0) ","
                        "\"start\":\"" (json-str (:lease/start l)) "\","
                        "\"end\":\"" (json-str (:lease/end l)) "\"}")))
       "]"))
