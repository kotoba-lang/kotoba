(ns kotoba.insurance.export
  "Operator-facing export for an insurance actor.

  Renders policies, premium quotes and claims to CSV and JSON for audit and
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

(defn policies->csv [policies]
  (str/join "\n"
    (cons (csv-row ["policy_id" "holder" "type" "coverage" "currency" "start" "end"])
          (for [p policies]
            (csv-row [(:policy/id p) (or (:policy/holder p) "")
                      (name (or (:policy/type p) :unspecified))
                      (:policy/coverage p) (:policy/currency p)
                      (:policy/start p) (:policy/end p)])))))

(defn claims->csv [claims]
  (str/join "\n"
    (cons (csv-row ["claim_id" "policy" "claimant" "incident_date" "amount_requested" "status"])
          (for [c claims]
            (csv-row [(:claim/id c) (:claim/policy c) (or (:claim/claimant c) "")
                      (:claim/incident-date c) (:claim/amount-requested c)
                      (name (or (:claim/status c) :intake))])))))

(defn policies->json [policies]
  (str "["
       (str/join ","
                 (for [p policies]
                   (str "{\"policy_id\":\"" (json-str (:policy/id p)) "\","
                        "\"holder\":\"" (json-str (:policy/holder p)) "\","
                        "\"type\":\"" (name (or (:policy/type p) :unspecified)) "\","
                        "\"coverage\":" (or (:policy/coverage p) 0) "}")))
       "]"))

(defn claims->json [claims]
  (str "["
       (str/join ","
                 (for [c claims]
                   (str "{\"claim_id\":\"" (json-str (:claim/id c)) "\","
                        "\"policy\":\"" (json-str (:claim/policy c)) "\","
                        "\"amount_requested\":" (or (:claim/amount-requested c) 0) ","
                        "\"status\":\"" (name (or (:claim/status c) :intake)) "\"}")))
       "]"))
