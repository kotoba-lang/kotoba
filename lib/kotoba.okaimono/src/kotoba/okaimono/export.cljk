(ns kotoba.okaimono.export
  "Operator-facing export for a courier actor's order book.

  Renders orders and line items to CSV and JSON for settlement audit and
  downstream reporting. Pure data → text: no network."
  (:require [kotoba.lang.text :as str]
            [kotoba.okaimono :as ok]))

(defn- csv-cell
  "Quote a CSV cell per RFC 4180.

  `\\r` was missing from the trigger set: a value containing a bare
  carriage return went out unquoted and split the row for any reader that
  treats CR as a line terminator."
  [v]
  (let [s (str (if (nil? v) "" v))]
    (if (re-find #"[\",\r\n]" s)
      (str "\"" (str/replace s "\"" "\"\"") "\"")
      s)))

(defn- csv-row [vals] (str/join "," (map csv-cell vals)))

(defn- u-escape [ch]
  (let [hex #?(:clj (Integer/toHexString (int ch))
               :cljs (.toString (.charCodeAt (str ch) 0) 16))]
    (str "\\u" (subs (str "000" hex) (- (count (str "000" hex)) 4)))))

(defn- json-str
  "Escape a value for use inside a JSON string literal.

  **RFC 8259 requires every code point below U+0020 to be escaped**, not
  just newline. The previous version handled only backslash, quote and
  `\\n`, so a customer name or SKU label containing a tab or a carriage
  return — ordinary when the record came from a spreadsheet paste —
  emitted a raw control character inside the string and produced output
  **no JSON parser will accept**. For an order book that feeds settlement
  audit, that is a silent corruption of the audit trail."
  [v]
  (let [s (str (if (nil? v) "" v))]
    (apply str
           (map (fn [ch]
                  (case ch
                    \\ "\\\\"
                    \" "\\\""
                    \newline "\\n"
                    \return "\\r"
                    \tab "\\t"
                    \formfeed "\\f"
                    \backspace "\\b"
                    (if (< #?(:clj (int ch) :cljs (.charCodeAt (str ch) 0)) 0x20)
                      (u-escape ch)
                      ch)))
                s))))

(defn orders->csv [orders]
  (str/join "\n"
    (cons (csv-row ["order_id" "store" "items" "total" "currency" "cod" "dispatchable" "status"])
          (for [o orders]
            (csv-row [(:okaimono/id o)
                      (:okaimono/store o)
                      (ok/item-count o)
                      (ok/total o)
                      (:okaimono/currency o)
                      (if (:okaimono/cod? o) "yes" "no")
                      (if (ok/dispatchable? o) "yes" "no")
                      (name (:okaimono/status o))])))))

(defn lines->csv [order]
  (str/join "\n"
    (cons (csv-row ["order_id" "sku" "name" "qty" "unit_price" "line_total"])
          (for [l (:okaimono/lines order)]
            (csv-row [(:okaimono/id order)
                      (:line/sku l)
                      (:line/name l)
                      (:line/qty l)
                      (:line/unit-price l)
                      (ok/line-total l)])))))

(defn orders->json [orders]
  (str "["
       (str/join ","
                 (for [o orders]
                   (str "{\"order_id\":\"" (json-str (:okaimono/id o)) "\","
                        "\"store\":\"" (json-str (:okaimono/store o)) "\","
                        "\"total\":" (ok/total o) ","
                        "\"currency\":\"" (json-str (:okaimono/currency o)) "\","
                        "\"cod\":" (if (:okaimono/cod? o) "true" "false") ","
                        "\"dispatchable\":" (if (ok/dispatchable? o) "true" "false") ","
                        "\"status\":\"" (name (:okaimono/status o)) "\"}")))
       "]"))
