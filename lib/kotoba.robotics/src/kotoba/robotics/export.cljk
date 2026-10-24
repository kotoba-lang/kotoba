(ns kotoba.robotics.export
  "Operator-facing export for a robotics actor.

  Renders missions and actions to CSV and JSON for safety audit export and
  downstream reporting. Pure data → text: no network, no I/O. Exports are
  read-only evidence the audit ledger can append; they never dispatch."
  (:require [kotoba.lang.text :as str]
            [kotoba.robotics :as rob]))

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
  a JSON string, not just \\ \" and \\n -- an operator-supplied mission/
  action field (objective text, ledger memo) containing a raw \\t, \\r, or
  other control byte would otherwise be copied through raw, producing
  invalid JSON (verified against Python's strict json module)."
  (into {\" "\\\"" \\ "\\\\"}
        (for [i (range 0x20)]
          [(char i) (case i
                      8 "\\b" 9 "\\t" 10 "\\n" 12 "\\f" 13 "\\r"
                      (str "\\u" (json-hex4 i)))])))

(defn- json-str [v]
  (str/escape (str (if (nil? v) "" v)) json-string-escapes))

(defn missions->csv [missions]
  (str/join "\n"
    (cons (csv-row ["mission_id" "robot" "objective" "status"])
          (for [m missions]
            (csv-row [(:mission/id m)
                      (:mission/robot m)
                      (:mission/objective m)
                      (name (or (:mission/status m) :planned))])))))

(defn actions->csv
  "Export actions to CSV. `allowed` is the safety-class set the governor
  permitted; the `gate` column records the governor's decision per action."
  ([actions] (actions->csv actions #{:none :low :medium}))
  ([actions allowed]
   (let [gate (fn [a]
                (let [g (rob/gate a allowed)]
                  (name (:gate/decision g))))]
     (str/join "\n"
       (cons (csv-row ["action_id" "mission" "kind" "safety" "actuates_hardware" "requires_sign_off" "gate"])
             (for [a actions]
               (csv-row [(:action/id a)
                         (:action/mission a)
                         (name (:action/kind a))
                         (name (:action/safety a))
                         (if (rob/actuates-hardware? a) "yes" "no")
                         (if (rob/requires-sign-off? a) "yes" "no")
                         (gate a)])))))))

(defn missions->json [missions]
  (str "["
       (str/join ","
                 (for [m missions]
                   (str "{\"mission_id\":\"" (json-str (:mission/id m)) "\","
                        "\"robot\":\"" (json-str (:mission/robot m)) "\","
                        "\"objective\":\"" (json-str (:mission/objective m)) "\","
                        "\"status\":\"" (name (or (:mission/status m) :planned)) "\"}")))
       "]"))

(defn actions->json
  ([actions] (actions->json actions #{:none :low :medium}))
  ([actions allowed]
   (str "["
        (str/join ","
                  (for [a actions]
                    (let [g (rob/gate a allowed)]
                      (str "{\"action_id\":\"" (json-str (:action/id a)) "\","
                           "\"mission\":\"" (json-str (:action/mission a)) "\","
                           "\"kind\":\"" (name (:action/kind a)) "\","
                           "\"safety\":\"" (name (:action/safety a)) "\","
                           "\"actuates_hardware\":" (if (rob/actuates-hardware? a) "true" "false") ","
                           "\"requires_sign_off\":" (if (rob/requires-sign-off? a) "true" "false") ","
                           "\"gate\":\"" (name (:gate/decision g)) "\"}"))))
        "]")))
