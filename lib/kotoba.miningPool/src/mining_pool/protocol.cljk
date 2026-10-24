(ns mining-pool.protocol
  "Stratum v1 (JSON-RPC over newline-delimited TCP) message shapes. Pure
  encode/decode — no socket I/O here (a server harness composes this with
  actual sockets; see the ADR's out-of-scope list re: v1 not shipping a
  hardened network daemon). Uses kotoba-lang/json rather than re-deriving a
  JSON parser."
  (:require [kotoba.lang.json :as json]
            [kotoba.lang.text :as str]))

(defn encode-line
  "Encode a Stratum message map to a newline-terminated JSON string (the
  wire framing: one JSON object per line)."
  ^String [msg]
  (str (json/encode msg) "\n"))

(defn decode-line
  "Decode one Stratum wire line (JSON object, keys stringified) into an EDN
  map with keyword keys: {:id :method :params} for requests/notifications,
  {:id :result :error} for responses."
  [^String line]
  (let [m (json/decode (str/trim line))]
    (cond-> {}
      (contains? m "id") (assoc :id (get m "id"))
      (contains? m "method") (assoc :method (get m "method") :params (get m "params"))
      (contains? m "result") (assoc :result (get m "result"))
      (contains? m "error") (assoc :error (get m "error")))))

;; ─── client -> server requests ───────────────────────────────────────────

(defn subscribe-request
  ([id user-agent] (subscribe-request id user-agent nil))
  ([id user-agent session-id]
   {"id" id "method" "mining.subscribe"
    "params" (cond-> [user-agent] session-id (conj session-id))}))

(defn authorize-request [id username password]
  {"id" id "method" "mining.authorize" "params" [username password]})

(defn submit-request [id username job-id extranonce2 ntime nonce]
  {"id" id "method" "mining.submit" "params" [username job-id extranonce2 ntime nonce]})

;; ─── server -> client responses ──────────────────────────────────────────

(defn ok-response [id result] {"id" id "result" result "error" nil})

(defn err-response
  ([id message] (err-response id 20 message))
  ([id code message] {"id" id "result" nil "error" [code message nil]}))

(defn subscribe-response
  "{subscription-ids extranonce1 extranonce2-size} -> the mining.subscribe
  result triple: [[[\"mining.set_difficulty\" sub-id] [\"mining.notify\" sub-id]] extranonce1 extranonce2-size]."
  [id subscription-id extranonce1 extranonce2-size]
  (ok-response id [[["mining.set_difficulty" subscription-id] ["mining.notify" subscription-id]]
                   extranonce1 extranonce2-size]))

;; ─── server -> client notifications ──────────────────────────────────────

(defn set-difficulty-notification [difficulty]
  {"id" nil "method" "mining.set_difficulty" "params" [difficulty]})

(defn notify-notification
  "job-id prevhash(hex) coinb1(hex) coinb2(hex) merkle-branch(hex seq)
  version(hex) nbits(hex) ntime(hex) clean-jobs?(bool)."
  [job-id prevhash coinb1 coinb2 merkle-branch version nbits ntime clean-jobs?]
  {"id" nil "method" "mining.notify"
   "params" [job-id prevhash coinb1 coinb2 merkle-branch version nbits ntime clean-jobs?]})
