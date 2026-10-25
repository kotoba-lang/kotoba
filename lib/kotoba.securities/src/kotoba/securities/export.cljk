(ns kotoba.securities.export
  "Operator-facing export for a securities/fund actor.

  Renders positions, trades and fund NAVs to CSV and JSON for audit and
  downstream reporting. Pure data -> text: no network."
  (:require [kotoba.lang.text :as str]))

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

(defn trades->csv [trades]
  (str/join "\n"
    (cons (csv-row ["trade_id" "account" "instrument" "side" "quantity" "price" "currency"])
          (for [t trades]
            (csv-row [(:trade/id t) (:trade/account t) (:trade/instrument t)
                      (name (or (:trade/side t) :unspecified))
                      (:trade/quantity t) (:trade/price t) (:trade/currency t)])))))

(defn positions->csv [positions]
  (str/join "\n"
    (cons (csv-row ["position_id" "holder" "instrument" "quantity"])
          (for [p positions]
            (csv-row [(:position/id p) (or (:position/holder p) "")
                      (:position/instrument p) (:position/quantity p)])))))

(defn trades->json [trades]
  (str "["
       (str/join ","
                 (for [t trades]
                   (str "{\"trade_id\":\"" (json-str (:trade/id t)) "\","
                        "\"side\":\"" (name (or (:trade/side t) :unspecified)) "\","
                        "\"quantity\":" (or (:trade/quantity t) 0) "}")))
       "]"))
