(ns kotoba.webrtc.export
  "Operator-facing export for a video-call/WebRTC host runtime.

  Renders session and call-quality stats records to CSV and JSON for audit
  and downstream reporting. Pure data → text: no network."
  (:require [kotoba.lang.text :as str]
            [kotoba.webrtc.stats :as stats]))

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

(defn sessions->csv [sessions]
  (str/join "\n"
    (cons (csv-row ["call_id" "local_id" "remote_id" "state" "ice_candidates"])
          (for [s sessions]
            (csv-row [(:webrtc.session/call-id s)
                      (or (:webrtc.session/local-id s) "")
                      (or (:webrtc.session/remote-id s) "")
                      (name (:webrtc.session/state s))
                      (count (:webrtc.session/ice-candidates s))])))))

(defn stats->csv [samples]
  (str/join "\n"
    (cons (csv-row ["quality" "packets_sent" "packets_lost" "jitter_ms" "round_trip_ms"])
          (for [s samples]
            (csv-row [(name (stats/classify s))
                      (:webrtc.stats/packets-sent s)
                      (:webrtc.stats/packets-lost s)
                      (:webrtc.stats/jitter-ms s)
                      (:webrtc.stats/round-trip-ms s)])))))

(defn sessions->json [sessions]
  (str "["
       (str/join ","
                 (for [s sessions]
                   (str "{\"call_id\":\"" (json-str (:webrtc.session/call-id s)) "\","
                        "\"local_id\":\"" (json-str (:webrtc.session/local-id s)) "\","
                        "\"remote_id\":\"" (json-str (:webrtc.session/remote-id s)) "\","
                        "\"state\":\"" (name (:webrtc.session/state s)) "\","
                        "\"ice_candidates\":" (count (:webrtc.session/ice-candidates s)) "}")))
       "]"))

(defn stats->json [samples]
  (str "["
       (str/join ","
                 (for [s samples]
                   (str "{\"quality\":\"" (name (stats/classify s)) "\","
                        "\"packets_sent\":" (:webrtc.stats/packets-sent s) ","
                        "\"packets_lost\":" (:webrtc.stats/packets-lost s) ","
                        "\"jitter_ms\":" (:webrtc.stats/jitter-ms s) ","
                        "\"round_trip_ms\":" (:webrtc.stats/round-trip-ms s) "}")))
       "]"))
