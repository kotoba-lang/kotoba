(ns bitcoin.node.peer
  "Bounded JVM Bitcoin P2P client for read-only consensus synchronization.

  It performs version/verack, answers ping, and requests headers in protocol
  batches. Transaction relay, wallet, mempool, and mining commands are absent."
  (:require [bitcoin.consensus.codec :as codec]
            [bitcoin.consensus.sync :as sync]
            [bitcoin.node.compact-filter :as compact-filter]
            [bitcoin.node.headers-sync :as headers-sync]
            [bitcoin.node.wire :as wire]
            [kotoba.lang.text :as str]
            [kotobase.bitcoin.protocol :as protocol])
  (:import [java.io DataInputStream DataOutputStream EOFException]
           [java.net InetSocketAddress Socket SocketTimeoutException]
           [java.security SecureRandom]))

(def network-configuration
  {:mainnet {:magic [0xf9 0xbe 0xb4 0xd9] :port 8333}
   :testnet {:magic [0x0b 0x11 0x09 0x07] :port 18333}
   :testnet4 {:magic [0x1c 0x16 0x3f 0x28] :port 48333}
   :signet {:magic [0x0a 0x03 0xcf 0x40] :port 38333}
   :regtest {:magic [0xfa 0xbf 0xb5 0xda] :port 18444}})

(defrecord PeerConnection
  [^Socket socket ^DataInputStream input ^DataOutputStream output
   network magic peer-version timeout-ms]
  java.io.Closeable
  (close [_] (.close socket)))

(def minimum-peer-version 31800)
(def node-network-service 1)
(def node-network-limited-service 1024)
(def node-compact-filters-service 64)
(def maximum-service-mask 18446744073709551615N)
(def witness-block-inventory-type 0x40000002)
(def maximum-filter-headers 2000)
(def maximum-block-download-peers 8)
(def maximum-block-download-batch sync/max-inflight)

(defn- fail! [type message data]
  (codec/fail! type message data))

(defn- deadline-nanos [timeout-ms]
  (+ (System/nanoTime) (* (long timeout-ms) 1000000)))

(defn- set-read-timeout!
  [connection deadline operation]
  (let [remaining (- deadline (System/nanoTime))]
    (when-not (pos? remaining)
      (fail! :bitcoin.node/peer-timeout
             "Bitcoin peer exceeded the overall request deadline."
             {:operation operation}))
    (.setSoTimeout
     ^Socket (:socket connection)
     (int (max 1 (quot (+ remaining 999999) 1000000))))))

(defn- read-exactly-until
  [connection deadline operation length]
  (let [bytes (byte-array length)]
    (try
      (loop [offset 0]
        (if (= offset length)
          (mapv #(bit-and 0xff %) bytes)
          (do
            (set-read-timeout! connection deadline operation)
            (let [read
                  (.read ^DataInputStream (:input connection)
                         bytes offset (- length offset))]
              (if (neg? read)
                (fail! :bitcoin.node/peer-eof
                       "Bitcoin peer closed a partial message."
                       {:expected length :received offset})
                (recur (+ offset read)))))))
      (catch EOFException _
        (fail! :bitcoin.node/peer-eof
               "Bitcoin peer closed a partial message."
               {:expected length})))))

(defn- write-message!
  [^DataOutputStream output magic command payload]
  (let [message (protocol/encode-message magic command payload)]
    (.write output (byte-array (map unchecked-byte message)))
    (.flush output)))

(defn- read-message-until!
  [connection deadline operation expected-magic]
  (let [header
        (wire/decode-message-header
         (read-exactly-until
         connection deadline operation protocol/header-size)
         expected-magic)
        payload
        (read-exactly-until
         connection deadline operation (:length header))]
    (wire/decode-message-payload header payload)))

(defn- positive-nonce []
  (bit-and (.nextLong (SecureRandom.)) Long/MAX_VALUE))

(defn- handle-control!
  [connection {:keys [command payload]}]
  (case command
    "ping"
    (do
      (write-message! (:output connection) (:magic connection)
                      "pong" payload)
      :control)

    "version"
    (do
      (write-message! (:output connection) (:magic connection)
                      "verack" [])
      [:version (wire/decode-version-payload payload)])

    "verack" :verack
    nil))

(defn connect!
  "Connect and complete mutual version/verack.

  Options: `:host`, `:port`, `:network`, `:timeout-ms`, `:start-height`,
  `:user-agent`, and an optional `:required-services` bit mask. The returned
  connection must be closed with `close!`."
  [{:keys [host port network timeout-ms start-height user-agent
           required-services]
    :or {host "127.0.0.1" network :mainnet timeout-ms 10000
         start-height 0 user-agent "/kotoba-lang:bitcoin-node:0.39.0/"
         required-services 0}}]
  (let [base-config (get network-configuration network)]
    (when-not base-config
      (fail! :bitcoin.node/peer-network
             "Unsupported Bitcoin peer network." {:network network}))
    (let [{:keys [magic port]}
          (assoc base-config :port (or port (:port base-config)))]
    (when-not (and (integer? timeout-ms) (pos? timeout-ms)
                   (<= timeout-ms Integer/MAX_VALUE)
                   (integer? required-services)
                   (<= 0 required-services maximum-service-mask))
      (fail! :bitcoin.node/peer-configuration
             "Peer timeout or required service mask is invalid."
             {:timeout-ms timeout-ms
              :required-services required-services}))
    (let [socket (Socket.)]
      (try
        (.connect socket (InetSocketAddress. ^String host (int port))
                  (int timeout-ms))
        (.setSoTimeout socket (int timeout-ms))
        (.setTcpNoDelay socket true)
        (let [input (DataInputStream. (.getInputStream socket))
              output (DataOutputStream. (.getOutputStream socket))
              base (->PeerConnection
                    socket input output network magic nil timeout-ms)
              deadline (deadline-nanos timeout-ms)]
          (write-message!
           output magic "version"
           (protocol/encode-version-payload
            {:timestamp (quot (System/currentTimeMillis) 1000)
             :nonce (positive-nonce)
             :recv-addr {:ip host :port port}
             :user-agent user-agent
             :start-height start-height :relay? false}))
          (loop [peer-version nil verack? false]
            (if (and peer-version verack?)
              (do
                (when (< (:version peer-version) minimum-peer-version)
                  (fail! :bitcoin.node/peer-version
                         "Bitcoin peer does not support getheaders."
                         {:minimum minimum-peer-version
                          :actual (:version peer-version)}))
                (when-not
                 (= (biginteger required-services)
                    (.and (biginteger required-services)
                          (biginteger (:services peer-version))))
                  (fail!
                   :bitcoin.node/peer-required-services
                   "Bitcoin peer lacks required advertised services."
                   {:required required-services
                    :actual (:services peer-version)}))
                (assoc base :peer-version peer-version))
              (let [message
                    (read-message-until!
                     base deadline :handshake magic)
                    result (handle-control! base message)]
                (cond
                  (and (vector? result) (= :version (first result)))
                  (recur (second result) verack?)

                  (= :verack result)
                  (recur peer-version true)

                  :else
                  (recur peer-version verack?))))))
        (catch SocketTimeoutException error
          (.close socket)
          (throw
           (ex-info "Bitcoin peer handshake timed out."
                    {:type :bitcoin.node/peer-timeout
                     :host host :port port}
                    error)))
        (catch Throwable error
          (.close socket)
          (throw error)))))))

(defn close! [connection]
  (.close ^java.io.Closeable connection)
  nil)

(defn get-headers!
  "Request at most 2,000 headers after the supplied natural-order locators."
  [connection locator-hashes]
  (when-not (and (sequential? locator-hashes)
                 (<= 1 (count locator-hashes) 101)
                 (every? #(= 32 (count %)) locator-hashes))
    (fail! :bitcoin.node/peer-locator
           "Header locator must contain 1..101 natural-order hashes."
           {:count (count locator-hashes)}))
  (write-message!
   (:output connection) (:magic connection) "getheaders"
   (protocol/encode-getheaders-payload
    {:locator-hashes locator-hashes}))
  (let [deadline (deadline-nanos (:timeout-ms connection))]
    (try
      (loop []
        (let [message
              (read-message-until!
               connection deadline :headers (:magic connection))
              _ (handle-control! connection message)]
          (if (= "headers" (:command message))
            (wire/decode-headers-payload (:payload message))
            ;; Unknown announcements are deliberately ignored; this client
            ;; never changes behavior based on inv/addr/feefilter traffic.
            (recur))))
      (catch SocketTimeoutException error
        (throw
         (ex-info "Bitcoin peer headers request timed out."
                  {:type :bitcoin.node/peer-timeout
                   :operation :headers}
                  error))))))

(defn get-block!
  "Fetch one witness-capable raw block by its natural-order 32-byte hash.

  The response remains bounded by the transport payload limit and its header
  hash must match the request before raw bytes are returned for full consensus
  validation by `bitcoin.node.disk-consensus/accept-block!`."
  [connection block-hash]
  (when-not (= 32 (count block-hash))
    (fail! :bitcoin.node/peer-block-hash
           "Block request requires one natural-order 32-byte hash."
           {:length (count block-hash)}))
  (write-message!
   (:output connection) (:magic connection) "getdata"
   (vec
    (concat
     (protocol/encode-varint 1)
     (protocol/uint-le->bytes witness-block-inventory-type 4)
     block-hash)))
  (let [deadline (deadline-nanos (:timeout-ms connection))]
    (try
      (loop []
        (let [message
              (read-message-until!
               connection deadline :block (:magic connection))
              _ (handle-control! connection message)]
          (case (:command message)
            "block"
            (let [payload (:payload message)]
              (when (< (count payload) protocol/block-header-size)
                (fail! :bitcoin.node/peer-malformed-block
                       "Bitcoin peer returned a truncated block."
                       {:length (count payload)}))
              (let [actual
                    (:hash
                     (protocol/decode-block-header
                      (subvec payload 0 protocol/block-header-size)))]
                (when-not (= block-hash actual)
                  (fail! :bitcoin.node/peer-unrequested-block
                         "Bitcoin peer returned a different block."
                         {:requested block-hash :actual actual}))
                payload))

            "notfound"
            (fail! :bitcoin.node/peer-block-not-found
                   "Bitcoin peer does not have the requested block." {})

            (recur))))
      (catch SocketTimeoutException error
        (throw
         (ex-info "Bitcoin peer block request timed out."
                  {:type :bitcoin.node/peer-timeout
                   :operation :block}
                  error))))))

(defn- compact-filter-service! [connection]
  (when-not
   (.testBit
    (biginteger (get-in connection [:peer-version :services]))
    6)
    (fail! :bitcoin.node/peer-compact-filters-unavailable
           "Bitcoin peer did not advertise NODE_COMPACT_FILTERS."
           {:services (get-in connection [:peer-version :services])})))

(defn- compact-filter-request-payload [start-height stop-hash]
  (when-not (and (integer? start-height)
                 (<= 0 start-height 0xffffffff)
                 (= 32 (count stop-hash)))
    (fail! :bitcoin.node/peer-compact-filter-request
           "Compact-filter requests require a uint32 height and 32-byte hash."
           {:start-height start-height
            :stop-hash-length (count stop-hash)}))
  (vec (concat [0] (codec/uint-le start-height 4) stop-hash)))

(defn- await-command! [connection operation expected-command]
  (let [deadline (deadline-nanos (:timeout-ms connection))]
    (try
      (loop []
        (let [message
              (read-message-until!
               connection deadline operation (:magic connection))
              _ (handle-control! connection message)]
          (if (= expected-command (:command message))
            (:payload message)
            (recur))))
      (catch SocketTimeoutException error
        (throw
         (ex-info "Bitcoin peer compact-filter request timed out."
                  {:type :bitcoin.node/peer-timeout
                   :operation operation}
                  error))))))

(defn get-basic-filter-headers!
  "Fetch and authenticate at most 2,000 consecutive BIP157 basic headers.

  `expected-previous-header` is a natural-order trusted or cross-checked
  anchor. A single peer's filter-header chain is not consensus data, so callers
  must retain the anchor and compare independent peers before scanning."
  [connection start-height stop-height stop-hash expected-previous-header]
  (compact-filter-service! connection)
  (when-not (and (integer? stop-height)
                 (<= start-height stop-height 0xffffffff)
                 (< (- stop-height start-height)
                    maximum-filter-headers))
    (fail! :bitcoin.node/peer-compact-filter-request
           "Compact-filter header ranges must contain 1..2,000 blocks."
           {:start-height start-height :stop-height stop-height
            :limit maximum-filter-headers}))
  (when-not (= 32 (count expected-previous-header))
    (fail! :bitcoin.node/peer-compact-filter-anchor
           "Compact-filter header synchronization requires a 32-byte anchor."
           {:length (count expected-previous-header)}))
  (write-message!
   (:output connection) (:magic connection) "getcfheaders"
   (compact-filter-request-payload start-height stop-hash))
  (let [payload (vec (await-command! connection :cfheaders "cfheaders"))
        [filter-type offset] (codec/read-uint-le payload 0 1)
        [actual-stop offset] (codec/read-bytes payload offset 32)
        [previous-header offset] (codec/read-bytes payload offset 32)
        [count-value offset] (codec/read-compact-size payload offset)]
    (when-not (zero? filter-type)
      (fail! :bitcoin.node/peer-compact-filter-type
             "Peer returned an unsupported compact-filter type."
             {:filter-type filter-type}))
    (when-not (= stop-hash actual-stop)
      (fail! :bitcoin.node/peer-compact-filter-stop
             "Peer returned compact-filter headers for another stop block."
             {:requested stop-hash :actual actual-stop}))
    (when-not (= expected-previous-header previous-header)
      (fail! :bitcoin.node/peer-compact-filter-anchor
             "Peer compact-filter header response does not extend the anchor."
             {:expected expected-previous-header :actual previous-header}))
    (when (> count-value maximum-filter-headers)
      (fail! :bitcoin.node/peer-compact-filter-count
             "Peer returned too many compact-filter hashes."
             {:count count-value :limit maximum-filter-headers}))
    (let [expected-count (inc (- stop-height start-height))]
      (when-not (= expected-count count-value)
        (fail! :bitcoin.node/peer-compact-filter-count
               "Peer omitted or added compact-filter hashes."
               {:expected expected-count :actual count-value
                :start-height start-height :stop-height stop-height})))
    (let [[hash-bytes end]
          (codec/read-bytes payload offset (* count-value 32))]
      (when-not (= end (count payload))
        (fail! :bitcoin.node/peer-compact-filter-trailing-data
               "Peer compact-filter header response contains trailing data."
               {:offset end :length (count payload)}))
      (second
       (reduce
        (fn [[previous result] filter-hash-value]
          (let [header
                (compact-filter/next-header-from-hash
                 filter-hash-value previous)]
            [header
             (conj result
                   {:filter-hash filter-hash-value :header header})]))
        [previous-header []]
        (mapv vec (partition 32 hash-bytes)))))))

(defn get-basic-filter!
  "Fetch one BIP158 filter and authenticate it against an expected header.

  The encoded filter is returned only after strict GCS decoding, response
  correlation, and BIP157 header verification."
  [connection height block-hash previous-header expected-header]
  (compact-filter-service! connection)
  (when-not (and (= 32 (count previous-header))
                 (= 32 (count expected-header)))
    (fail! :bitcoin.node/peer-compact-filter-anchor
           "Compact-filter verification requires two 32-byte headers."
           {:previous-length (count previous-header)
            :expected-length (count expected-header)}))
  (write-message!
   (:output connection) (:magic connection) "getcfilters"
   (compact-filter-request-payload height block-hash))
  (let [payload (vec (await-command! connection :cfilter "cfilter"))
        [filter-type offset] (codec/read-uint-le payload 0 1)
        [actual-block offset] (codec/read-bytes payload offset 32)
        [encoded end]
        (codec/read-var-bytes
         payload offset protocol/max-protocol-payload-bytes "compact filter")]
    (when-not (= end (count payload))
      (fail! :bitcoin.node/peer-compact-filter-trailing-data
             "Peer compact-filter response contains trailing data."
             {:offset end :length (count payload)}))
    (when-not (zero? filter-type)
      (fail! :bitcoin.node/peer-compact-filter-type
             "Peer returned an unsupported compact-filter type."
             {:filter-type filter-type}))
    (when-not (= block-hash actual-block)
      (fail! :bitcoin.node/peer-unrequested-compact-filter
             "Peer returned a compact filter for another block."
             {:requested block-hash :actual actual-block}))
    (compact-filter/decode-values encoded)
    (let [actual-header
          (compact-filter/filter-header encoded previous-header)]
      (when-not (= expected-header actual-header)
        (fail! :bitcoin.node/peer-compact-filter-header
               "Peer compact filter does not match its authenticated header."
               {:expected expected-header :actual actual-header})))
    encoded))

(defn sync-headers!
  "Drive sequential getheaders batches through a validating batch callback.

  `accept-batch!` receives decoded headers and must reject invalid linkage,
  PoW, difficulty, or time context before returning. Sync stops on a short
  batch, an empty batch, or `max-batches`.

  When `:presync` supplies a durable anchor context and minimum chainwork,
  low-work chains are downloaded twice using salted periodic commitments.
  No header reaches `accept-batch!` until the redownload is commitment
  protected, matching Bitcoin Core's headers-sync anti-DoS boundary."
  [connection locator-hashes accept-batch!
   {:keys [max-batches presync] :or {max-batches 10000}}]
  (when-not (ifn? accept-batch!)
    (fail! :bitcoin.node/peer-callback
           "Header synchronization requires a validating callback." {}))
  (when-not (and (integer? max-batches) (pos? max-batches))
    (fail! :bitcoin.node/peer-configuration
           "Header batch limit must be a positive integer."
           {:max-batches max-batches}))
  (let [initial-presync
        (when presync (headers-sync/create presync))]
   (loop [locator
          (if (= :presync (:phase initial-presync))
            (headers-sync/locator initial-presync)
            locator-hashes)
          batches 0
          accepted 0
          security-state
          (when (= :presync (:phase initial-presync)) initial-presync)
          security-evidence nil]
    (if (= batches max-batches)
      (if security-state
        (headers-sync/require-complete! security-state)
        (cond->
         {:status :batch-limit :batches batches :accepted accepted
          :locator (first locator)}
          security-evidence (assoc :headers-presync security-evidence)))
      (let [headers (get-headers! connection locator)
            header-count (count headers)]
        (if (zero? header-count)
          (if security-state
            (headers-sync/require-complete! security-state)
            (cond->
             {:status :synced :batches (inc batches) :accepted accepted
              :locator (first locator)}
              security-evidence
              (assoc :headers-presync security-evidence)))
          (if security-state
            (let [{next-security :state ready :ready}
                  (headers-sync/process-batch security-state headers)
                  _ (doseq [batch (partition-all
                                   protocol/max-headers-per-message ready)]
                      (accept-batch! (vec batch)))
                  next-accepted (+ accepted (count ready))
                  completed? (= :complete (:phase next-security))
                  evidence
                  (when completed?
                    {:presynced (:presynced next-security)
                     :redownloaded (:redownloaded next-security)
                     :commitments (count (:commitments next-security))
                     :commitment-period
                     (:commitment-period next-security)
                     :redownload-buffer-size
                     (:redownload-buffer-size next-security)})
                  short?
                  (< header-count protocol/max-headers-per-message)]
              (when (and short?
                         (not completed?)
                         (not (and (= :presync (:phase security-state))
                                   (= :redownload
                                      (:phase next-security)))))
                (headers-sync/require-complete! next-security))
              (recur
               (if completed?
                 [(:hash (last headers))]
                 (headers-sync/locator next-security))
               (inc batches)
               next-accepted
               (when-not completed? next-security)
               (or evidence security-evidence)))
            (do
              (accept-batch! headers)
              (let [tip (:hash (last headers))
                    result
                    (cond->
                     {:batches (inc batches)
                      :accepted (+ accepted header-count)
                      :locator tip}
                      security-evidence
                      (assoc :headers-presync security-evidence))]
                (if (< header-count protocol/max-headers-per-message)
                  (assoc result :status :synced)
                  (recur [tip] (inc batches) (+ accepted header-count)
                         nil security-evidence)))))))))))

(defn- peer-summary [configuration]
  (let [network (or (:network configuration) :mainnet)]
    {:host (:host configuration)
     :port (or (:port configuration)
               (get-in network-configuration [network :port]))
     :network network}))

(defn- failure-summary [configuration error elapsed-ms]
  (let [data (ex-data error)]
    (cond->
     {:peer (peer-summary configuration)
      :type (or (:type data) :bitcoin.node/peer-error)
      :message (.getMessage ^Throwable error)
      :elapsed-ms elapsed-ms}
      (:reason data) (assoc :reason (:reason data))
      (:validation-type data)
      (assoc :validation-type (:validation-type data)))))

(defn- validate-block-download!
  [peer-configurations block-hashes parallel-peers per-peer-limit
   batch-timeout-ms]
  (let [peers (vec peer-configurations)
        hashes (vec block-hashes)]
    (when-not
     (and (<= 1 (count peers) 32)
          (every? #(and (map? %)
                        (string? (:host %))
                        (not (str/blank? (:host %))))
                  peers)
          (= (count peers)
             (count (into #{} (map peer-summary) peers))))
      (fail!
       :bitcoin.node/block-peer-set
       "Block download requires 1..32 unique peers with explicit hosts."
       {:peer-count (count peers)}))
    (when-not
     (and (<= (count hashes) maximum-block-download-batch)
          (= (count hashes) (count (distinct hashes)))
          (every? #(and (sequential? %) (= 32 (count %))) hashes))
      (fail!
       :bitcoin.node/block-download-set
       "Block download hashes must be unique natural-order values within the bounded window."
       {:count (count hashes) :limit maximum-block-download-batch}))
    (when-not
     (and (integer? parallel-peers)
          (<= 1 parallel-peers maximum-block-download-peers)
          (integer? per-peer-limit)
          (<= 1 per-peer-limit sync/max-inflight-per-peer)
          (integer? batch-timeout-ms)
          (<= 1000 batch-timeout-ms 120000))
      (fail!
       :bitcoin.node/block-download-configuration
       "Block download parallelism is outside its bounded limits."
       {:parallel-peers parallel-peers
        :maximum-parallel-peers maximum-block-download-peers
        :per-peer-limit per-peer-limit
        :maximum-per-peer sync/max-inflight-per-peer
        :batch-timeout-ms batch-timeout-ms}))
    [peers hashes]))

(defn- fetch-block-batch!
  [configuration hashes connection downloaded started]
  (let [elapsed-ms #(/ (- (System/nanoTime) started) 1e6)]
    (try
      (let [connected (connect! configuration)]
        (reset! connection connected)
        (doseq [hash hashes]
          (swap! downloaded conj
                 {:hash hash :raw (get-block! connected hash)}))
        {:configuration configuration
         :peer (peer-summary configuration)
         :blocks @downloaded
         :elapsed-ms (elapsed-ms)
         :services (get-in connected [:peer-version :services])})
      (catch Throwable error
        {:configuration configuration
         :peer (peer-summary configuration)
         :blocks @downloaded
         :elapsed-ms (elapsed-ms)
         :failure (failure-summary configuration error (elapsed-ms))})
      (finally
        (when-let [connected @connection]
          (try
            (close! connected)
            (catch Throwable _)))))))

(defn- await-block-batches!
  [jobs batch-timeout-ms]
  (let [deadline
        (+ (System/nanoTime) (* (long batch-timeout-ms) 1000000))]
    (mapv
     (fn [{:keys [configuration connection downloaded started task]}]
       (let [remaining (- deadline (System/nanoTime))
             result
             (when (pos? remaining)
               (deref task
                      (max 1 (quot (+ remaining 999999) 1000000))
                      ::timeout))]
         (if (and result (not= ::timeout result))
           result
           (do
             (when-let [connected @connection]
               (try
                 (close! connected)
                 (catch Throwable _)))
             (future-cancel task)
             {:configuration configuration
              :peer (peer-summary configuration)
              :blocks @downloaded
              :elapsed-ms (/ (- (System/nanoTime) started) 1e6)
              :failure
              (failure-summary
               configuration
               (ex-info
                "Bitcoin peer exceeded the overall block-batch deadline."
                {:type :bitcoin.node/block-download-timeout})
               (/ (- (System/nanoTime) started) 1e6))}))))
     jobs)))

(defn- process-block-batch
  [scheduler peer-id entries]
  (loop [state scheduler
         remaining (vec entries)
         accepted []]
    (if-let [{:keys [hash raw]} (first remaining)]
        (let [scheduler-hash (protocol/natural-hash->hex hash)
              attempt
            (try
              {:result
               (sync/process-block
                state peer-id scheduler-hash
                {:header
                 (protocol/decode-block-header
                  (first (codec/read-bytes (vec raw) 0 80)))})}
              (catch Throwable error
                {:error
                 (ex-info
                  "Bitcoin peer returned a malformed block header."
                  {:type :bitcoin.node/block-response-mismatch
                   :reason :malformed-block-header
                   :validation-type (:type (ex-data error))}
                  error)}))]
        (if-let [error (:error attempt)]
          {:state (sync/disconnect state peer-id)
           :accepted accepted
           :error error}
          (let [result (:result attempt)]
            (if (:accepted? result)
              (recur (:state result) (subvec remaining 1)
                     (conj accepted [hash raw]))
              {:state (sync/disconnect (:state result) peer-id)
               :accepted accepted
               :error
               (ex-info
                "Bitcoin peer response did not match its scheduled block."
                {:type :bitcoin.node/block-response-mismatch
                 :reason (:error result)
                 :hash hash})}))))
      {:state state :accepted accepted})))

(defn download-blocks-from-peers!
  "Download one bounded block window concurrently with deterministic failover.

  The pure `bitcoin.consensus.sync` state machine owns assignment, global and
  per-peer in-flight limits, response correlation, and requeue. Each peer has
  one sequential connection, while up to `:parallel-peers` connections run in
  parallel. Returned blocks retain the caller's chronological hash order so a
  chainstate host can publish them atomically one at a time.

  A failed peer's unfinished work is requeued to another peer. Successfully
  downloaded prefixes are retained, and typed per-peer evidence is returned
  for durable health scoring."
  [peer-configurations block-hashes
   {:keys [parallel-peers per-peer-limit batch-timeout-ms]
    :or {parallel-peers 4
         per-peer-limit sync/max-inflight-per-peer
         batch-timeout-ms (* 1000 sync/request-timeout-seconds)}}]
  (let [[peers hashes]
        (validate-block-download!
         peer-configurations block-hashes parallel-peers per-peer-limit
         batch-timeout-ms)
        peer-order (mapv peer-summary peers)
        scheduler-hashes (mapv protocol/natural-hash->hex hashes)
        natural-hash-by-scheduler
        (zipmap scheduler-hashes hashes)
        initial
        (reduce sync/register-peer
                (sync/create scheduler-hashes) peer-order)]
    (if (empty? hashes)
      {:status :downloaded :downloaded 0 :blocks []
       :block-sources [] :observations [] :failures []}
      (loop [scheduler initial
             downloaded {}
             sources {}
             observations {}
             failures []]
        (if (= (count hashes) (count downloaded))
          {:status :downloaded
           :downloaded (count downloaded)
           :blocks (mapv downloaded hashes)
           :block-sources (mapv sources hashes)
           :observations
           (mapv observations (filter observations peer-order))
           :failures failures}
          (let [eligible
                (->> peers
                     (filter #(sync/eligible?
                               scheduler (peer-summary %)))
                     (take parallel-peers)
                     vec)
                [assigned jobs]
                (reduce
                 (fn [[state result] configuration]
                   (let [peer-id (peer-summary configuration)
                         [next-state requested]
                         (sync/assign state peer-id
                                      (System/currentTimeMillis)
                                      per-peer-limit)]
                     [next-state
                      (cond-> result
                        (seq requested)
                        (conj
                         [configuration
                          (mapv natural-hash-by-scheduler requested)]))]))
                 [scheduler []]
                 eligible)]
            (when (empty? jobs)
              (fail!
               :bitcoin.node/block-peer-set-exhausted
               "Every bounded block-download peer was exhausted."
               {:downloaded (count downloaded)
                :remaining (count (:pending scheduler))
                :observations
                (mapv observations (filter observations peer-order))
                :failures failures}))
            (let [attempts
                  (mapv
                   (fn [[configuration requested]]
                     (let [connection (atom nil)
                           downloaded (atom [])
                           started (System/nanoTime)]
                       {:configuration configuration
                        :connection connection
                        :downloaded downloaded
                        :started started
                        :task
                        (future
                          (fetch-block-batch!
                           configuration requested connection downloaded
                           started))}))
                   jobs)
                  results
                  (await-block-batches! attempts batch-timeout-ms)
                  next
                  (reduce
                   (fn [{:keys [state] :as result}
                        {:keys [configuration peer elapsed-ms services
                                failure]
                         :as attempt}]
                     (let [processed
                           (process-block-batch
                            state peer (:blocks attempt))
                           response-error (:error processed)
                           terminal-error (or response-error failure)
                           state'
                           (if terminal-error
                             (sync/disconnect (:state processed) peer)
                             (:state processed))
                           accepted (:accepted processed)
                           failure'
                           (when terminal-error
                             (if response-error
                               (failure-summary
                                configuration response-error elapsed-ms)
                               failure))]
                       (cond->
                        (assoc result :state state')
                         (seq accepted)
                         (update :blocks into accepted)

                         (seq accepted)
                         (update :sources
                                 (fn [values]
                                   (reduce (fn [sources [hash _]]
                                             (assoc sources hash peer))
                                           values accepted)))

                         terminal-error
                         (update :failed conj failure')

                         (not terminal-error)
                         (update
                          :evidence
                          (fn [values]
                            (update
                             values peer
                             (fn [previous]
                               {:peer peer
                                :elapsed-ms
                                (+ (or (:elapsed-ms previous) 0)
                                   elapsed-ms)
                                :services services
                                :downloaded
                                (+ (or (:downloaded previous) 0)
                                   (count accepted))})))))))
                   {:state assigned :blocks [] :sources sources
                    :evidence observations
                    :failed []}
                   results)]
              (recur
               (:state next)
               (into downloaded (:blocks next))
               (:sources next)
               (:evidence next)
               (into failures (:failed next))))))))))

(defn sync-headers-from-peers!
  "Synchronize through a bounded, ordered peer set with durable failover.

  `locator-fn` is called after each successful handshake, so a replacement
  peer resumes from batches already validated and committed by an earlier
  peer. `:required-successes` can be greater than one to compare independently
  reported tips; differing reports are surfaced as `:disagreement?` while the
  validating callback remains the sole fork-choice authority.

  `:presync-fn`, when supplied, is also called after each handshake so every
  replacement peer receives the latest durable anchor and chainwork."
  [peer-configurations locator-fn accept-batch!
   {:keys [attempts-per-peer required-successes max-batches presync-fn]
    :or {attempts-per-peer 1 required-successes 1 max-batches 10000}}]
  (let [peers (vec peer-configurations)]
    (when-not (and (<= 1 (count peers) 32)
                   (every? #(and (map? %)
                                 (string? (:host %))
                                 (not (str/blank? (:host %))))
                           peers)
                   (= (count peers)
                      (count (into #{} (map peer-summary) peers))))
      (fail! :bitcoin.node/peer-set
             "Peer failover requires 1..32 unique configurations with explicit hosts."
             {:count (count peers)}))
    (when-not (and (ifn? locator-fn)
                   (ifn? accept-batch!)
                   (or (nil? presync-fn) (ifn? presync-fn)))
      (fail! :bitcoin.node/peer-callback
             "Peer failover requires locator and validation callbacks." {}))
    (when-not (and (integer? attempts-per-peer)
                   (<= 1 attempts-per-peer 8)
                   (integer? required-successes)
                   (<= 1 required-successes (count peers)))
      (fail! :bitcoin.node/peer-configuration
             "Peer attempts and required successes are outside their bounds."
             {:attempts-per-peer attempts-per-peer
              :required-successes required-successes
              :peer-count (count peers)}))
    (loop [remaining (vec (mapcat identity
                                  (repeat attempts-per-peer peers)))
           observations []
           failures []]
      (if-let [configuration (first remaining)]
        (if (some #(= (peer-summary configuration) (:peer %))
                  observations)
          (recur (subvec remaining 1) observations failures)
          (let [started (System/nanoTime)
                elapsed-ms
                #(/ (- (System/nanoTime) started) 1e6)
                attempt
                (try
                  (let [connection (connect! configuration)]
                    (try
                      (let [result
                            (sync-headers!
                             connection (locator-fn) accept-batch!
                             (cond-> {:max-batches max-batches}
                               presync-fn
                               (assoc :presync (presync-fn))))
                            tip (:locator result)]
                        {:observation
                         {:peer (peer-summary configuration)
                          :start-height
                          (get-in connection [:peer-version :start-height])
                          :status (:status result)
                          :batches (:batches result)
                          :accepted (:accepted result)
                          :elapsed-ms (elapsed-ms)
                          :services
                          (get-in connection [:peer-version :services])
                          :reported-tip
                          (when tip (protocol/natural-hash->hex tip))}})
                      (finally
                        (close! connection))))
                  (catch Exception error
                    {:failure
                     (failure-summary
                      configuration error (elapsed-ms))}))]
            (if-let [observation (:observation attempt)]
              (let [next-observations (conj observations observation)]
                (if (= required-successes (count next-observations))
                  (let [tips (into #{} (keep :reported-tip)
                                   next-observations)]
                    {:status (:status observation)
                     :successful-peers (count next-observations)
                     :attempted (+ (count next-observations)
                                   (count failures))
                     :disagreement? (> (count tips) 1)
                     :observations next-observations
                     :failures failures})
                  (recur (subvec remaining 1)
                         next-observations failures)))
              (recur (subvec remaining 1) observations
                     (conj failures (:failure attempt))))))
        (fail! :bitcoin.node/peer-set-exhausted
               "Every bounded peer synchronization attempt failed."
               {:attempted (+ (count observations) (count failures))
                :successful-peers (count observations)
                :required-successes required-successes
                :observations observations
                :failures failures})))))

(defn- compact-filter-peer-configuration [configuration]
  (update
   configuration :required-services
   (fn [value]
     (.or (biginteger (or value 0))
          (biginteger node-compact-filters-service)))))

(defn- compact-header-observation [configuration headers elapsed-ms]
  {:peer (peer-summary configuration)
   :count (count headers)
   :terminal-header
   (when-let [header (:header (last headers))]
     (protocol/natural-hash->hex header))
   :elapsed-ms elapsed-ms})

(defn- validate-compact-filter-peer-set!
  [peer-configurations required-successes attempts-per-peer]
  (let [peers (vec peer-configurations)]
    (when-not
     (and (<= 2 (count peers) 32)
          (every? #(and (map? %)
                        (string? (:host %))
                        (not (str/blank? (:host %))))
                  peers)
          (= (count peers)
             (count (into #{} (map peer-summary) peers))))
      (fail! :bitcoin.node/compact-filter-peer-set
             "Compact-filter quorum requires 2..32 unique explicit peers."
             {:count (count peers)}))
    (when-not (and (integer? required-successes)
                   (<= 2 required-successes (count peers))
                   (integer? attempts-per-peer)
                   (<= 1 attempts-per-peer 8))
      (fail! :bitcoin.node/compact-filter-peer-configuration
             "Compact-filter quorum and retry bounds are invalid."
             {:required-successes required-successes
              :attempts-per-peer attempts-per-peer
              :peer-count (count peers)}))
    peers))

(defn get-basic-filter-headers-from-peers!
  "Require exact BIP157 header-chain agreement from independent peers.

  Every peer receives the same height range, stop hash, and retained previous
  header. A result is returned only when `:required-successes` peers return the
  byte-identical chain. Merely collecting that many successful but conflicting
  responses fails closed."
  [peer-configurations start-height stop-height stop-hash previous-header
   {:keys [required-successes attempts-per-peer]
    :or {required-successes 2 attempts-per-peer 1}}]
  (let [peers
        (validate-compact-filter-peer-set!
         peer-configurations required-successes attempts-per-peer)
        attempts
        (vec (mapcat identity (repeat attempts-per-peer peers)))]
    (loop [remaining attempts observations [] failures []]
      (if-let [configuration (first remaining)]
        (if (some #(= (peer-summary configuration) (:peer %)) observations)
          (recur (subvec remaining 1) observations failures)
          (let [started (System/nanoTime)
                elapsed-ms #(/ (- (System/nanoTime) started) 1e6)
                configured (compact-filter-peer-configuration configuration)
                attempt
                (try
                  (let [connection (connect! configured)]
                    (try
                      {:headers
                       (get-basic-filter-headers!
                        connection start-height stop-height stop-hash
                        previous-header)}
                      (finally
                        (close! connection))))
                  (catch Exception error
                    {:failure
                     (failure-summary
                      configuration error (elapsed-ms))}))]
            (if-let [headers (:headers attempt)]
              (let [observation
                    {:peer (peer-summary configuration)
                     :headers headers
                     :elapsed-ms (elapsed-ms)}
                    next-observations (conj observations observation)
                    matching
                    (filterv #(= headers (:headers %)) next-observations)]
                (if (>= (count matching) required-successes)
                  {:status :agreed
                   :required-successes required-successes
                   :agreement-peers (count matching)
                   :successful-peers (count next-observations)
                   :attempted (+ (count next-observations)
                                 (count failures))
                   :disagreement?
                   (> (count (distinct (map :headers next-observations))) 1)
                   :headers headers
                   :observations
                   (mapv
                    #(compact-header-observation
                      (:peer %) (:headers %) (:elapsed-ms %))
                    next-observations)
                   :failures failures}
                  (recur (subvec remaining 1)
                         next-observations failures)))
              (recur (subvec remaining 1) observations
                     (conj failures (:failure attempt))))))
        (fail!
         :bitcoin.node/compact-filter-quorum
         "Independent peers did not reach compact-filter header agreement."
         {:required-successes required-successes
          :successful-peers (count observations)
          :attempted (+ (count observations) (count failures))
          :distinct-responses
          (count (distinct (map :headers observations)))
          :observations
          (mapv
           #(compact-header-observation
             (:peer %) (:headers %) (:elapsed-ms %))
           observations)
          :failures failures})))))

(defn get-basic-filter-from-peers!
  "Fetch one filter with bounded failover against a quorum-authenticated header.

  Since `get-basic-filter!` verifies the filter hash into `expected-header`, a
  malicious or stale peer cannot create a false-negative scan without breaking
  the header quorum or double-SHA256."
  [peer-configurations height block-hash previous-header expected-header]
  (let [peers (vec peer-configurations)]
    (when-not
     (and (<= 1 (count peers) 32)
          (every? #(and (map? %)
                        (string? (:host %))
                        (not (str/blank? (:host %))))
                  peers)
          (= (count peers)
             (count (into #{} (map peer-summary) peers))))
      (fail! :bitcoin.node/compact-filter-peer-set
             "Compact-filter fetch requires 1..32 unique explicit peers."
             {:count (count peers)}))
    (loop [remaining peers failures []]
      (if-let [configuration (first remaining)]
        (let [started (System/nanoTime)
              elapsed-ms #(/ (- (System/nanoTime) started) 1e6)
              configured (compact-filter-peer-configuration configuration)
              attempt
              (try
                (let [connection (connect! configured)]
                  (try
                    {:encoded
                     (get-basic-filter!
                      connection height block-hash
                      previous-header expected-header)}
                    (finally
                      (close! connection))))
                (catch Exception error
                  {:failure
                   (failure-summary
                    configuration error (elapsed-ms))}))]
          (if-let [encoded (:encoded attempt)]
            {:status :authenticated
             :peer (peer-summary configuration)
             :encoded encoded
             :elapsed-ms (elapsed-ms)
             :failures failures}
            (recur (subvec remaining 1)
                   (conj failures (:failure attempt)))))
        (fail! :bitcoin.node/compact-filter-fetch-failed
               "Every peer failed authenticated compact-filter retrieval."
               {:height height :block-hash block-hash
                :failures failures})))))
