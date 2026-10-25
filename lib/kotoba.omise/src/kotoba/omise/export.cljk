(ns kotoba.omise.export
  "Operator-facing export for a courier actor's store directory.

  Renders stores and pickup points to CSV and JSON for audit and
  downstream reporting. Pure data → text: no network."
  (:require [kotoba.lang.text :as str]
            [kotoba.omise :as omise]))

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
  `\\n`, so a store name containing a tab or a carriage return — ordinary
  when the record came from a spreadsheet paste — emitted a raw control
  character inside the string and produced output **no JSON parser will
  accept**. The export looked fine right up to the moment something
  downstream tried to read it."
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

(defn stores->csv [stores]
  (str/join "\n"
    (cons (csv-row ["store_id" "name" "address" "jurisdiction" "pickup_ready" "status"])
          (for [s stores]
            (csv-row [(:omise/id s)
                      (:omise/name s)
                      (:omise/address s)
                      (or (:omise/jurisdiction s) "")
                      (if (:omise/pickup-ready? s) "yes" "no")
                      (name (:omise/status s))])))))

(defn pickup-points->csv [points]
  (str/join "\n"
    (cons (csv-row ["pickup_id" "store" "label" "lat" "lng"])
          (for [p points]
            (csv-row [(:pickup/id p)
                      (:pickup/store p)
                      (or (:pickup/label p) "")
                      (get-in p [:pickup/geo :lat] "")
                      (get-in p [:pickup/geo :lng] "")])))))

(defn stores->json [stores]
  (str "["
       (str/join ","
                 (for [s stores]
                   (str "{\"store_id\":\"" (json-str (:omise/id s)) "\","
                        "\"name\":\"" (json-str (:omise/name s)) "\","
                        "\"address\":\"" (json-str (:omise/address s)) "\","
                        "\"pickup_ready\":" (if (:omise/pickup-ready? s) "true" "false") ","
                        "\"status\":\"" (name (:omise/status s)) "\"}")))
       "]"))

(defn open-report->csv
  "Open/closed report for every store at a caller-supplied moment."
  [stores [day hhmm]]
  (str/join "\n"
    (cons (csv-row ["store_id" "day" "time" "open" "pickup_available"])
          (for [s stores]
            (csv-row [(:omise/id s)
                      (name day)
                      hhmm
                      (if (omise/open-at? s day hhmm) "yes" "no")
                      (if (omise/pickup-available? s day hhmm) "yes" "no")])))))
