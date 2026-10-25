(ns kotoba.dtn.export
  "Operator-facing export for a DTN store-and-forward node.

  Renders bundles-in-store and link-reachability records to CSV and JSON
  for audit and downstream reporting. Pure data → text: no network."
  (:require [kotoba.lang.text :as str]))

(defn- csv-cell [v]
  (let [s (str (if (nil? v) "" v))]
    ;; RFC 4180 requires quoting a field containing a comma, a double
    ;; quote, OR a line break -- \r alone is also a line break (a CR-only
    ;; row terminator every standard CSV reader recognizes).
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
  a JSON string, not just \\ \" and \\n."
  (into {\" "\\\"" \\ "\\\\"}
        (for [i (range 0x20)]
          [(char i) (case i
                      8 "\\b" 9 "\\t" 10 "\\n" 12 "\\f" 13 "\\r"
                      (str "\\u" (json-hex4 i)))])))

(defn- json-str [v]
  (str/escape (str (if (nil? v) "" v)) json-string-escapes))

(defn bundles->csv [bundles]
  (str/join "\n"
    (cons (csv-row ["bundle_id" "source" "destination" "creation_timestamp" "sequence_number" "lifetime_ms"])
          (for [b bundles]
            (csv-row [(:dtn/bundle-id b)
                      (or (:dtn/source b) "")
                      (or (:dtn/destination b) "")
                      (:dtn/creation-timestamp b)
                      (:dtn/sequence-number b)
                      (:dtn/lifetime-ms b)])))))

(defn links->csv [links]
  (str/join "\n"
    (cons (csv-row ["link_id" "neighbor" "transport_kind" "reachable" "bandwidth_bps"])
          (for [l links]
            (csv-row [(:dtn/link-id l)
                      (or (:dtn/neighbor l) "")
                      (name (:dtn/transport-kind l))
                      (if (:dtn/reachable? l) "yes" "no")
                      (:dtn/bandwidth-bps l)])))))

(defn bundles->json [bundles]
  (str "["
       (str/join ","
                 (for [b bundles]
                   (str "{\"bundle_id\":\"" (json-str (:dtn/bundle-id b)) "\","
                        "\"source\":\"" (json-str (:dtn/source b)) "\","
                        "\"destination\":\"" (json-str (:dtn/destination b)) "\","
                        "\"creation_timestamp\":" (or (:dtn/creation-timestamp b) 0) ","
                        "\"sequence_number\":" (or (:dtn/sequence-number b) 0) ","
                        "\"lifetime_ms\":" (or (:dtn/lifetime-ms b) 0) "}")))
       "]"))

(defn links->json [links]
  (str "["
       (str/join ","
                 (for [l links]
                   (str "{\"link_id\":\"" (json-str (:dtn/link-id l)) "\","
                        "\"neighbor\":\"" (json-str (:dtn/neighbor l)) "\","
                        "\"transport_kind\":\"" (name (:dtn/transport-kind l)) "\","
                        "\"reachable\":" (if (:dtn/reachable? l) "true" "false") ","
                        "\"bandwidth_bps\":" (or (:dtn/bandwidth-bps l) 0) "}")))
       "]"))
