(ns rtc.signal
  "Signaling protocol for WebRTC negotiation (SDP offer/answer, ICE
  candidates), transported over KNP ReliableOrdered channel. Restored
  from kami-rtc's `signal` module (deleted PR #82).

  `to-bytes`/`from-bytes` round-trip via EDN (`pr-str`/`read-string`)
  rather than JSON — a zero-dep portable equivalent to the original's
  `serde_json`, since payload is only ever consumed by other CLJC code
  in this migration, not a real JS/Rust wire peer."
  (:require [kotoba.lang.edn :as edn]))

(def signal-types #{:offer :answer :ice-candidate :join :leave :position :data})

(defn- signal-message [signal-type from to room-id payload seq]
  {:signal-type signal-type :from from :to to :room-id room-id :payload payload :seq seq})

(defn offer [from to room-id sdp seq] (signal-message :offer from to room-id sdp seq))
(defn answer [from to room-id sdp seq] (signal-message :answer from to room-id sdp seq))
(defn ice-candidate [from to room-id candidate-json seq] (signal-message :ice-candidate from to room-id candidate-json seq))
(defn join [from room-id display-name seq] (signal-message :join from "" room-id display-name seq))
(defn leave [from room-id seq] (signal-message :leave from "" room-id "" seq))
(defn position [from room-id pos seq] (signal-message :position from "" room-id (pr-str pos) seq))
(defn data [from room-id data-str seq] (signal-message :data from "" room-id data-str seq))

(defn to-bytes
  "Serialize `msg` to bytes for KNP transport."
  [msg]
  #?(:clj (.getBytes (pr-str msg) "UTF-8")
     :cljs (js/Array.from (js/TextEncoder.) (pr-str msg))))

(defn from-bytes
  "Deserialize a `SignalMessage` from `bytes`, or nil on failure."
  [bytes]
  (try
    (edn/read-string #?(:clj (String. bytes "UTF-8") :cljs (.decode (js/TextDecoder.) bytes)))
    (catch #?(:clj Exception :cljs js/Error) _ nil)))

(defn broadcast?
  "True if `msg` has no specific target (`:to` is empty)."
  [msg]
  (empty? (:to msg)))
