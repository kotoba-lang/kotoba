(ns kotoba.logistics.export
  "Operator-facing export for a freight-transport actor.

  Renders tracking validation, shipments and consignments to CSV and JSON for
  settlement audit and downstream reporting. Pure data → text: no network."
  (:require [kotoba.lang.text :as str]
            [kotoba.logistics :as log]))

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

(defn trackings->csv [trackings]
  (str/join "\n"
    (cons (csv-row ["tracking" "valid" "normalized"])
          (for [t trackings]
            (let [r (log/validate-tracking t)]
              (csv-row [t
                        (if (:logistics/valid? r) "yes" "no")
                        (or (:logistics/normalized r) "")]))))))

(defn shipments->csv [shipments]
  (str/join "\n"
    (cons (csv-row ["shipment_id" "origin" "destination" "carrier" "tracking" "status"])
          (for [s shipments]
            (csv-row [(:shipment/id s)
                      (:shipment/origin s)
                      (:shipment/destination s)
                      (:shipment/carrier s)
                      (or (:shipment/tracking s) "")
                      (name (:shipment/status s))])))))

(defn consignments->csv [consignments]
  (str/join "\n"
    (cons (csv-row ["consignment_id" "shipment" "legs" "declared_value" "status"])
          (for [c consignments]
            (csv-row [(:cons/id c)
                      (:cons/shipment c)
                      (count (:cons/route c))
                      (or (:cons/declared-value c) "")
                      (name (:cons/status c))])))))

(defn trackings->json [trackings]
  (str "["
       (str/join ","
                 (for [t trackings]
                   (let [r (log/validate-tracking t)]
                     (str "{\"tracking\":\"" (json-str t) "\","
                          "\"valid\":" (if (:logistics/valid? r) "true" "false") ","
                          "\"normalized\":\"" (json-str (:logistics/normalized r)) "\"}"))))
       "]"))

(defn shipments->json [shipments]
  (str "["
       (str/join ","
                 (for [s shipments]
                   (str "{\"shipment_id\":\"" (json-str (:shipment/id s)) "\","
                        "\"origin\":\"" (json-str (:shipment/origin s)) "\","
                        "\"destination\":\"" (json-str (:shipment/destination s)) "\","
                        "\"carrier\":\"" (json-str (:shipment/carrier s)) "\","
                        "\"status\":\"" (name (:shipment/status s)) "\"}")))
       "]"))
