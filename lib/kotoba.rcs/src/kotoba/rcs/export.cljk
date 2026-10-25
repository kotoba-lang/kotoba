(ns kotoba.rcs.export
  "Operator-facing export for an RCS-capable telecom-access actor.

  Renders chat messages, receipts and capability-discovery records to CSV
  and JSON for audit and downstream reporting. Pure data → text: no
  network."
  (:require [kotoba.lang.text :as str]
            [kotoba.rcs :as rcs]))

(defn- csv-cell [v]
  (let [s (str (if (nil? v) "" v))]
    ;; RFC 4180 requires quoting a field containing a comma, a double
    ;; quote, OR a line break -- \r alone is also a line break (a CR-only
    ;; row terminator every standard CSV reader recognizes). Mirrors
    ;; kotoba-lang/phone's export (verified there against Python's csv
    ;; module: an unquoted bare \r split a row into two corrupted rows).
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
  a JSON string, not just \\ \" and \\n. Mirrors kotoba-lang/phone's
  export (verified there against Python's strict json module)."
  (into {\" "\\\"" \\ "\\\\"}
        (for [i (range 0x20)]
          [(char i) (case i
                      8 "\\b" 9 "\\t" 10 "\\n" 12 "\\f" 13 "\\r"
                      (str "\\u" (json-hex4 i)))])))

(defn- json-str [v]
  (str/escape (str (if (nil? v) "" v)) json-string-escapes))

(defn messages->csv [messages]
  (str/join "\n"
    (cons (csv-row ["message_id" "from" "to" "body" "content_type"])
          (for [m messages]
            (csv-row [(:rcs/message-id m)
                      (or (:rcs/from m) "")
                      (or (:rcs/to m) "")
                      (:rcs/body m)
                      (or (:rcs/content-type m) "")])))))

(defn receipts->csv [receipts]
  (str/join "\n"
    (cons (csv-row ["message_id" "disposition" "timestamp"])
          (for [r receipts]
            (let [valid (rcs/valid-receipt? r)]
              (csv-row [(:rcs/message-id r)
                        (if valid (name (:rcs/disposition r)) "")
                        (or (:rcs/timestamp r) "")]))))))

(defn capabilities->csv [caps]
  (str/join "\n"
    (cons (csv-row ["endpoint" "valid" "features"])
          (for [c caps]
            (let [valid (rcs/valid-capabilities? c)]
              (csv-row [(:rcs/endpoint c)
                        (if valid "yes" "no")
                        (if valid
                          (str/join ";" (map name (sort (:rcs/features c))))
                          "")]))))))

(defn messages->json [messages]
  (str "["
       (str/join ","
                 (for [m messages]
                   (str "{\"message_id\":\"" (json-str (:rcs/message-id m)) "\","
                        "\"from\":\"" (json-str (:rcs/from m)) "\","
                        "\"to\":\"" (json-str (:rcs/to m)) "\","
                        "\"body\":\"" (json-str (:rcs/body m)) "\","
                        "\"content_type\":\"" (json-str (:rcs/content-type m)) "\"}")))
       "]"))

(defn receipts->json [receipts]
  (str "["
       (str/join ","
                 (for [r receipts]
                   (let [valid (rcs/valid-receipt? r)]
                     (str "{\"message_id\":\"" (json-str (:rcs/message-id r)) "\","
                          "\"disposition\":" (if valid (str "\"" (name (:rcs/disposition r)) "\"") "null") ","
                          "\"timestamp\":\"" (json-str (:rcs/timestamp r)) "\"}"))))
       "]"))

(defn capabilities->json [caps]
  (str "["
       (str/join ","
                 (for [c caps]
                   (let [valid (rcs/valid-capabilities? c)]
                     (str "{\"endpoint\":\"" (json-str (:rcs/endpoint c)) "\","
                          "\"valid\":" (if valid "true" "false") ","
                          "\"features\":[" (if valid
                                              (str/join "," (map #(str "\"" (name %) "\"")
                                                                  (sort (:rcs/features c))))
                                              "") "]}"))))
       "]"))
