(ns bitcoin.node.headers-sync
  "Bitcoin Core-style two-phase headers synchronization.

  Before a peer demonstrates the configured minimum chainwork, headers are
  validated without being handed to durable storage. A salted one-bit
  commitment is retained periodically. The peer must then redownload the same
  chain; headers are released only after enough later commitments make
  equivocation uneconomic. This bounds permanent header-index growth from
  low-work peers while preserving ordinary most-work fork choice."
  (:require [bitcoin.consensus.codec :as codec]
            [kotobase.bitcoin.protocol :as header])
  (:import [java.security MessageDigest SecureRandom]))

(def network-parameters
  "Bitcoin Core v31 headers-sync parameters generated on 2026-02-25."
  {:mainnet {:commitment-period 641 :redownload-buffer-size 15218}
   :testnet {:commitment-period 673 :redownload-buffer-size 14460}
   :testnet4 {:commitment-period 606 :redownload-buffer-size 16092}
   :signet {:commitment-period 620 :redownload-buffer-size 15724}
   :regtest {:commitment-period 275 :redownload-buffer-size 7017}})

(def maximum-header-context 2017)
(def maximum-future-block-time 7200)

(defn- fail! [type message data]
  (codec/fail! type message data))

(defn- chainwork-at-least? [actual minimum]
  (not (header/better-chain? minimum actual)))

(defn- random-key []
  (let [result (byte-array 32)]
    (.nextBytes (SecureRandom.) result)
    (mapv #(bit-and 0xff %) result)))

(defn- salted-commitment-bit [key natural-hash]
  (let [digest (MessageDigest/getInstance "SHA-256")]
    (.update digest (byte-array (map unchecked-byte key)))
    (.update digest (byte-array (map unchecked-byte natural-hash)))
    (bit-and 1 (bit-and 0xff (aget (.digest digest) 0)))))

(defn- median-time-past [headers]
  (let [timestamps (sort (map :timestamp (take-last 11 headers)))]
    (nth timestamps (quot (count timestamps) 2))))

(defn- trim-context [headers]
  (vec (take-last maximum-header-context headers)))

(defn- validate-configuration!
  [{:keys [network context anchor-height anchor-chainwork minimum-chainwork
           now commitment-period redownload-buffer-size commitment-offset
           commitment-key commitment-fn]}]
  (when-not (contains? network-parameters network)
    (fail! :bitcoin.node/headers-sync-network
           "Headers pre-sync requires a supported Bitcoin network."
           {:network network}))
  (when-not (and (vector? context) (seq context)
                 (<= (count context) maximum-header-context))
    (fail! :bitcoin.node/headers-sync-context
           "Headers pre-sync requires 1..2,017 chronological anchor headers."
           {:count (count context)}))
  (when-not (and (nat-int? anchor-height)
                 (= (:hash-hex (peek context))
                    (header/natural-hash->hex (:hash (peek context)))))
    (fail! :bitcoin.node/headers-sync-context
           "Headers pre-sync anchor context is malformed."
           {:anchor-height anchor-height}))
  (when-not (and (= 32 (count anchor-chainwork))
                 (= 32 (count minimum-chainwork)))
    (fail! :bitcoin.node/headers-sync-chainwork
           "Headers pre-sync requires two unsigned 256-bit chainwork values."
           {:anchor-length (count anchor-chainwork)
            :minimum-length (count minimum-chainwork)}))
  (when-not (and (integer? now) (not (neg? now)))
    (fail! :bitcoin.node/headers-sync-time
           "Headers pre-sync requires a non-negative current Unix time."
           {:now now}))
  (when-not (and (integer? commitment-period) (pos? commitment-period)
                 (integer? redownload-buffer-size)
                 (pos? redownload-buffer-size)
                 (integer? commitment-offset)
                 (<= 0 commitment-offset (dec commitment-period))
                 (= 32 (count commitment-key))
                 (ifn? commitment-fn))
    (fail! :bitcoin.node/headers-sync-configuration
           "Headers pre-sync commitment parameters are invalid."
           {:commitment-period commitment-period
            :redownload-buffer-size redownload-buffer-size
            :commitment-offset commitment-offset
            :commitment-key-length (count commitment-key)})))

(defn create
  "Create bounded two-phase synchronization state.

  `context` is chronological and ends at the durable anchor. Tests may inject
  commitment parameters, a key, offset, and commitment function; production
  callers should use the network defaults and generated secret values."
  [{:keys [network context anchor-height anchor-chainwork minimum-chainwork now
           commitment-period redownload-buffer-size commitment-offset
           commitment-key commitment-fn]
    :as options}]
  (let [{default-period :commitment-period
         default-buffer :redownload-buffer-size}
        (get network-parameters network)
        commitment-period (or commitment-period default-period)
        redownload-buffer-size
        (or redownload-buffer-size default-buffer)
        commitment-key (or commitment-key (random-key))
        commitment-offset
        (if (some? commitment-offset)
          commitment-offset
          (.nextInt (SecureRandom.) (int commitment-period)))
        commitment-fn (or commitment-fn salted-commitment-bit)
        configured
        (assoc options
               :context (vec context)
               :commitment-period commitment-period
               :redownload-buffer-size redownload-buffer-size
               :commitment-offset commitment-offset
               :commitment-key commitment-key
               :commitment-fn commitment-fn)]
    (validate-configuration! configured)
    (let [anchor-mtp (median-time-past context)
          possible-seconds
          (max 0 (+ (- now anchor-mtp) maximum-future-block-time))
          max-commitments
          (quot (* 6 possible-seconds) commitment-period)
          anchor (peek context)
          direct?
          (chainwork-at-least? anchor-chainwork minimum-chainwork)]
      {:phase (if direct? :direct :presync)
       :network network
       :now now
       :anchor-height anchor-height
       :anchor-hash (:hash anchor)
       :anchor-chainwork (vec anchor-chainwork)
       :minimum-chainwork (vec minimum-chainwork)
       :context (trim-context context)
       :current-height anchor-height
       :current-chainwork (vec anchor-chainwork)
       :commitment-period commitment-period
       :redownload-buffer-size redownload-buffer-size
       :commitment-offset commitment-offset
       :commitment-key commitment-key
       :commitment-fn commitment-fn
       :commitments []
       :commitment-index 0
       :max-commitments max-commitments
       :presynced 0
       :redownloaded 0
       :buffer []})))

(defn locator
  "Return the next single-hash getheaders locator for a two-phase state."
  [state]
  (case (:phase state)
    :presync [(:hash (peek (:context state)))]
    :redownload [(:hash (peek (:redownload-context state)))]
    :complete [(:hash (peek (:redownload-context state)))]
    :direct [(:anchor-hash state)]
    (fail! :bitcoin.node/headers-sync-state
           "Headers pre-sync state has an invalid phase."
           {:phase (:phase state)})))

(defn- validate-batch!
  [state context current-height headers]
  (let [context (vec context)
        result
        (header/validate-header-consensus
         (into context headers)
         {:network (:network state)
          :start-height (- (inc current-height) (count context))
          :validate-from-index (count context)
          :now (:now state)})]
    (when-not (:valid? result)
      (fail! :bitcoin.node/headers-presync-invalid
             "Peer header batch failed pre-sync consensus validation."
             {:phase (:phase state) :errors (:errors result)})))
  headers)

(defn- commitment-height? [state height]
  (= (:commitment-offset state)
     (mod height (:commitment-period state))))

(defn- commitment-bit [state header]
  ((:commitment-fn state) (:commitment-key state) (:hash header)))

(defn- process-presync [state headers]
  (validate-batch! state (:context state) (:current-height state) headers)
  (let [next-state
        (reduce
         (fn [current value]
           (let [height (inc (:current-height current))
                 commitment?
                 (commitment-height? current height)
                 commitments
                 (cond-> (:commitments current)
                   commitment? (conj (commitment-bit current value)))]
             (when (> (count commitments) (:max-commitments current))
               (fail! :bitcoin.node/headers-presync-length
                      "Peer header chain exceeds the MTP-derived length bound."
                      {:height height
                       :commitments (count commitments)
                       :maximum (:max-commitments current)}))
             (-> current
                 (assoc :commitments commitments
                        :current-height height
                        :current-chainwork
                        (header/add-chainwork
                         (:current-chainwork current)
                         (header/header-work (:bits value))))
                 (update :context #(trim-context (conj % value)))
                 (update :presynced inc))))
         state headers)]
    (if (chainwork-at-least?
         (:current-chainwork next-state)
         (:minimum-chainwork next-state))
      (assoc next-state
             :phase :redownload
             :redownload-context (:initial-context next-state)
             :redownload-height (:anchor-height next-state)
             :redownload-chainwork (:anchor-chainwork next-state)
             :process-all? false)
      next-state)))

(defn- initialize-presync [state]
  (if (:initial-context state)
    state
    (assoc state :initial-context (:context state))))

(defn- decode-buffer [values]
  (mapv #(header/decode-block-header %) values))

(defn- process-redownload [state headers]
  (validate-batch!
   state (:redownload-context state) (:redownload-height state) headers)
  (let [next-state
        (reduce
         (fn [current value]
           (let [height (inc (:redownload-height current))
                 work
                 (header/add-chainwork
                  (:redownload-chainwork current)
                  (header/header-work (:bits value)))
                 process-all?
                 (chainwork-at-least? work (:minimum-chainwork current))
                 commitment?
                 (and (not process-all?)
                      (commitment-height? current height))
                 commitment-index (:commitment-index current)]
             (when commitment?
               (when (>= commitment-index (count (:commitments current)))
                 (fail! :bitcoin.node/headers-presync-commitment-overrun
                        "Peer redownload exceeded its pre-sync commitments."
                        {:height height :commitment-index commitment-index}))
               (when-not
                (= (nth (:commitments current) commitment-index)
                   (commitment-bit current value))
                 (fail! :bitcoin.node/headers-presync-equivocation
                        "Peer redownload does not match its pre-sync chain."
                        {:height height
                         :commitment-index commitment-index})))
             (-> current
                 (assoc :redownload-height height
                        :redownload-chainwork work
                        :process-all? process-all?)
                 (cond-> commitment?
                   (update :commitment-index inc))
                 (update :redownload-context
                         #(trim-context (conj % value)))
                 (update :buffer conj (:bytes value))
                 (update :redownloaded inc))))
         state headers)
        release-count
        (if (:process-all? next-state)
          (count (:buffer next-state))
          (max 0 (- (count (:buffer next-state))
                    (:redownload-buffer-size next-state))))
        [ready retained] (split-at release-count (:buffer next-state))
        complete? (and (:process-all? next-state) (empty? retained))]
    {:state (assoc next-state
                   :buffer (vec retained)
                   :phase (if complete? :complete :redownload))
     :ready (decode-buffer ready)}))

(defn process-batch
  "Validate one non-empty peer batch and return {:state ... :ready [...]}.

  `:ready` remains empty during pre-sync. During redownload it contains only
  commitment-protected headers that may cross the durable indexing boundary."
  [state headers]
  (let [headers (vec headers)]
    (when (empty? headers)
      (fail! :bitcoin.node/headers-presync-empty
             "Headers pre-sync cannot process an empty batch."
             {:phase (:phase state)}))
    (case (:phase state)
      :presync
      {:state (process-presync (initialize-presync state) headers)
       :ready []}

      :redownload (process-redownload state headers)

      (fail! :bitcoin.node/headers-sync-state
             "Headers pre-sync cannot process this phase."
             {:phase (:phase state)}))))

(defn require-complete!
  "Reject a short/empty peer response before sufficient work was redownloaded."
  [state]
  (when-not (contains? #{:complete :direct} (:phase state))
    (fail! :bitcoin.node/peer-insufficient-chainwork
           "Peer ended header synchronization before proving minimum chainwork."
           {:phase (:phase state)
            :height (or (:redownload-height state)
                        (:current-height state))
            :presynced (:presynced state)
            :redownloaded (:redownloaded state)}))
  state)
