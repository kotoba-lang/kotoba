(ns kotoba.p2p.graphsync-stream
  "GraphSync v2 over an authenticated libp2p stream.

  The libp2p host owns TCP, Noise, Yamux, and protocol negotiation. This
  adapter owns GraphSync framing and the bounded scheduler. Authorization is
  evaluated against the PeerId proven by Noise, never an id in application
  bytes."
  (:require [kotoba.net.libp2p.connection :as connection]
            [kotoba.p2p.graphsync :as gs]
            [kotoba.p2p.graphsync-scheduler :as scheduler]))

(def ^:private terminal-statuses
  (set (map gs/status [:completed-full :completed-partial :rejected
                       :failed-busy :failed-unknown :failed-legal
                       :content-not-found :cancelled])))

(defn- fail! [problem data]
  (throw (ex-info (name problem) (assoc data :type problem))))

(defn- max-message-bytes [limits]
  (let [maximum (:max-message-bytes limits)]
    (when-not (and (integer? maximum) (pos? maximum))
      (fail! :graphsync/invalid-stream-limits {:limits limits}))
    maximum))

(defn- read-length! [port maximum]
  (loop [shift 0 value 0 seen 0]
    (when (>= seen 9)
      (fail! :graphsync/invalid-frame {:reason :overlong-varint}))
    (let [octet (bit-and (first ((:read! port) 1)) 0xff)
          value (+ value (bit-shift-left (bit-and octet 0x7f) shift))]
      (when (> value maximum)
        (fail! :graphsync/resource-limit
               {:limit :max-message-bytes :maximum maximum :actual value}))
      (if (zero? (bit-and octet 0x80))
        value
        (recur (+ shift 7) value (inc seen))))))

(defn read-message!
  "Read exactly one bounded GraphSync frame from a libp2p stream."
  [port limits]
  (let [length (read-length! port (max-message-bytes limits))]
    (when (zero? length)
      (fail! :graphsync/invalid-frame {:reason :empty-payload}))
    ;; libp2p ports deliberately expose portable octet vectors. DAG-CBOR's JVM
    ;; decoder consumes a byte-array, so normalize exactly at this boundary.
    (gs/decode-message (byte-array (map unchecked-byte ((:read! port) length)))
                       limits)))

(defn write-message!
  "Write exactly one GraphSync frame to a libp2p stream."
  [port message limits]
  ((:write! port) (gs/encode-frame message limits)))

(defn serve-once!
  "Authorize and fulfill one request message on an authenticated stream.

  CONTEXT is supplied by `io-libp2p` and contains the Noise-authenticated
  `:peer-id`. The host-supplied authorization predicate must explicitly allow
  `:graphsync/respond`."
  [{:keys [port peer-id] :as context}
   {:keys [authorize-fn get-fn wire-limits scheduler-config traversal-limits
           max-response-messages]}]
  (when-not (and (fn? authorize-fn)
                 (true? (authorize-fn {:action :graphsync/respond
                                       :peer-id peer-id})))
    (fail! :graphsync/unauthorized {:peer-id peer-id}))
  (when-not (fn? get-fn)
    (fail! :graphsync/missing-block-store {}))
  (let [incoming (read-message! port wire-limits)
        handled (scheduler/handle-message
                 (scheduler/new-scheduler scheduler-config)
                 get-fn incoming traversal-limits)
        _ (when-let [message (:message handled)]
            (write-message! port message wire-limits))
        drained (scheduler/drain (:scheduler handled) get-fn
                                 max-response-messages)]
    (doseq [message (:messages drained)]
      (write-message! port message wire-limits))
    {:peer-id peer-id
     :events (into (:events handled) (:events drained))
     :messages (+ (if (:message handled) 1 0) (count (:messages drained)))
     :context (dissoc context :port)}))

(defn responder-handler
  "Build an `io-libp2p` custom protocol handler for GraphSync v2."
  [config]
  (fn [{:keys [port] :as context}]
    (try
      (serve-once! context config)
      (finally
        (when-let [close! (:close! port)] (close!))))))

(defn request!
  "Send one GraphSync new request over a live authenticated libp2p connection.

  Every received block has already passed CID verification in the wire codec;
  `put-fn` is the caller-owned physical landing boundary. Returns only after a
  terminal response for the request id, or fails closed at `max-messages`."
  [live request {:keys [wire-limits put-fn max-messages]}]
  (when-not (and (= :new (:type request)) (fn? put-fn)
                 (integer? max-messages) (pos? max-messages))
    (fail! :graphsync/invalid-requester-config {}))
  (let [stream (connection/stream! (:secure live) (:session live) gs/protocol-id)
        request-id (vec (:id request))]
    (write-message! stream {:requests [request]} wire-limits)
    (loop [remaining max-messages responses [] landed []]
      (when (zero? remaining)
        (fail! :graphsync/resource-limit
               {:limit :max-response-messages :maximum max-messages}))
      (let [message (read-message! stream wire-limits)
            blocks (or (:blocks message) [])
            matching (filter #(= request-id (vec (:id %))) (:responses message))]
        (doseq [{:keys [cid bytes]} blocks]
          (put-fn cid bytes))
        (if (some #(contains? terminal-statuses (:status %)) matching)
          {:responses (into responses matching)
           :landed-cids (into landed (map :cid) blocks)
           :messages (- max-messages remaining -1)}
          (recur (dec remaining)
                 (into responses matching)
                 (into landed (map :cid) blocks)))))))
