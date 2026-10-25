(ns kotoba.p2p.graphsync
  "GraphSync 2.0 message codec and bounded responder core.

  `/ipfs/graphsync/2.0.0` uses a varint-length-prefixed DAG-CBOR message whose
  shape is the GraphSync v2 IPLD Schema (`gs2`, `req`, `rsp`, `blk`). This
  namespace implements that wire boundary for the IPLD subset this workspace
  can execute. Network streams, request scheduling, cancellation state, and
  extensions remain host concerns."
  (:require [ipld.core :as ipld]
            [ipld.data-model :as dm]
            [ipld.graph :as graph]
            [ipld.link :as link]
            [ipld.selector :as selector]
            [multiformats.core :as mf]))

(def protocol-id "/ipfs/graphsync/2.0.0")

(def request-type->wire {:new "n" :cancel "c" :update "u"})
(def wire->request-type (into {} (map (fn [[k v]] [v k])) request-type->wire))
(def action->wire {:present "p" :duplicate-not-sent "d" :missing "m"
                   :duplicate-dag-skipped "s"})
(def wire->action (into {} (map (fn [[k v]] [v k])) action->wire))

(def status
  {:acknowledged 10 :additional-peers 11 :not-enough-gas 12
   :other-protocol 13 :partial-response 14 :paused 15
   :completed-full 20 :completed-partial 21
   :rejected 30 :failed-busy 31 :failed-unknown 32 :failed-legal 33
   :content-not-found 34 :cancelled 35})

(def ^:private valid-statuses (set (vals status)))

(def ^:private dag-cbor-sha2-256-prefix [0x01 0x71 0x12 0x20])

(defn- byte-length [bytes]
  #?(:clj (if (bytes? bytes) (alength ^bytes bytes) (count bytes))
     :cljs (if (vector? bytes) (count bytes) (.-length bytes))))

(defn- byte-at [bytes index]
  #?(:clj (if (bytes? bytes) (aget ^bytes bytes index) (nth bytes index))
     :cljs (if (vector? bytes) (nth bytes index) (aget bytes index))))

(defn- ints->bytes [values]
  #?(:clj (byte-array (map unchecked-byte values))
     :cljs (js/Uint8Array.from (clj->js values))))

(defn- byte-value? [value]
  (= :bytes (dm/kind value)))

(defn- invalid! [message data]
  (throw (ex-info message (assoc data :type :graphsync/invalid-message))))

(defn- exact-subset! [value allowed required context]
  (when-not (map? value)
    (invalid! "graphsync: expected map" {:context context :value value}))
  (let [actual (set (keys value))]
    (when-not (and (every? allowed actual)
                   (every? #(contains? actual %) required))
      (invalid! "graphsync: unexpected or missing fields"
                {:context context :allowed allowed :required required :actual actual}))))

(defn- id! [id]
  (when-not (and (byte-value? id) (= 16 (byte-length id)))
    (invalid! "graphsync: request id must be 16 bytes" {:id id}))
  id)

(defn- extensions! [extensions]
  (when-not (and (map? extensions) (every? string? (keys extensions)))
    (invalid! "graphsync: extensions must be a string-keyed IPLD map"
              {:extensions extensions}))
  extensions)

(defn- encode-request [{:keys [id type root selector priority extensions] :as request}]
  (id! id)
  (when-not (contains? request-type->wire type)
    (invalid! "graphsync: unknown request type" {:request-type type}))
  (case type
    :new
    (do
      (exact-subset! request #{:id :type :root :selector :priority :extensions}
                     #{:id :type :root :selector} :request)
      (when-not (string? root)
        (invalid! "graphsync: new request requires a CID root" {:root root}))
      (when-not (or (nil? priority) (integer? priority))
        (invalid! "graphsync: priority must be an integer" {:priority priority}))
      (cond-> {"id" id "type" "n" "root" (link/link root)
               "sel" (selector/to-data-model selector)}
        (some? priority) (assoc "pri" priority)
        (some? extensions) (assoc "ext" (extensions! extensions))))

    :cancel
    (do (exact-subset! request #{:id :type} #{:id :type} :cancel-request)
        {"id" id "type" "c"})

    :update
    (do (exact-subset! request #{:id :type :extensions} #{:id :type :extensions}
                       :update-request)
        {"id" id "type" "u" "ext" (extensions! extensions)})))

(defn- decode-request [request]
  (when-not (map? request)
    (invalid! "graphsync: request must be a map" {:request request}))
  (let [type (get wire->request-type (get request "type"))
        id (id! (get request "id"))]
    (case type
      :new
      (do
        (exact-subset! request #{"id" "type" "root" "sel" "pri" "ext"}
                       #{"id" "type" "root" "sel"} :request)
        (when-not (link/link? (get request "root"))
          (invalid! "graphsync: request root must be an IPLD Link" {:request request}))
        (when-not (or (not (contains? request "pri"))
                      (integer? (get request "pri")))
          (invalid! "graphsync: priority must be an integer"
                    {:priority (get request "pri")}))
        (cond-> {:id id :type :new
                 :root (link/link-cid (get request "root"))
                 :selector (selector/from-data-model (get request "sel"))}
          (contains? request "pri") (assoc :priority (get request "pri"))
          (contains? request "ext") (assoc :extensions (extensions! (get request "ext")))))
      :cancel
      (do (exact-subset! request #{"id" "type"} #{"id" "type"} :cancel-request)
          {:id id :type :cancel})
      :update
      (do (exact-subset! request #{"id" "type" "ext"} #{"id" "type" "ext"}
                         :update-request)
          {:id id :type :update :extensions (extensions! (get request "ext"))})
      (invalid! "graphsync: unknown request type" {:wire-type (get request "type")}))))

(defn- encode-metadatum [{:keys [cid action] :as metadatum}]
  (exact-subset! metadatum #{:cid :action} #{:cid :action} :metadata)
  (when-not (contains? action->wire action)
    (invalid! "graphsync: unknown link action" {:action action}))
  [(link/link cid) (get action->wire action)])

(defn- decode-metadatum [value]
  (when-not (and (vector? value) (= 2 (count value))
                 (link/link? (first value)) (contains? wire->action (second value)))
    (invalid! "graphsync: malformed link metadata" {:value value}))
  {:cid (link/link-cid (first value)) :action (get wire->action (second value))})

(defn- encode-response [{:keys [id status metadata extensions] :as response}]
  (exact-subset! response #{:id :status :metadata :extensions} #{:id :status} :response)
  (id! id)
  (when-not (contains? valid-statuses status)
    (invalid! "graphsync: unknown response status" {:status status}))
  (cond-> {"reqid" id "stat" status}
    (some? metadata) (assoc "meta" (mapv encode-metadatum metadata))
    (some? extensions) (assoc "ext" (extensions! extensions))))

(defn- decode-response [response]
  (exact-subset! response #{"reqid" "stat" "meta" "ext"}
                 #{"reqid" "stat"} :response)
  (when-not (contains? valid-statuses (get response "stat"))
    (invalid! "graphsync: unknown response status" {:status (get response "stat")}))
  (cond-> {:id (id! (get response "reqid")) :status (get response "stat")}
    (contains? response "meta") (assoc :metadata (mapv decode-metadatum (get response "meta")))
    (contains? response "ext") (assoc :extensions (extensions! (get response "ext")))))

(defn- cid-prefix [cid bytes]
  (let [actual (ipld/cid bytes)
        raw (vec (map #(bit-and % 0xff) (mf/cid->bytes cid)))]
    (when-not (= cid actual)
      (invalid! "graphsync: block bytes do not match CID" {:cid cid :actual actual}))
    (when-not (= dag-cbor-sha2-256-prefix (subvec raw 0 (min 4 (count raw))))
      (invalid! "graphsync: only CIDv1 dag-cbor sha2-256 blocks are supported"
                {:cid cid :prefix (subvec raw 0 (min 4 (count raw)))}))
    (ints->bytes dag-cbor-sha2-256-prefix)))

(defn- encode-block [{:keys [cid bytes] :as block}]
  (exact-subset! block #{:cid :bytes} #{:cid :bytes} :block)
  [(cid-prefix cid bytes) bytes])

(defn- decode-block [value]
  (when-not (and (vector? value) (= 2 (count value))
                 (byte-value? (first value)) (byte-value? (second value)))
    (invalid! "graphsync: malformed block tuple" {:value value}))
  (let [[prefix bytes] value
        prefix (vec (map #(bit-and % 0xff) prefix))]
    (when-not (= dag-cbor-sha2-256-prefix prefix)
      (invalid! "graphsync: unsupported block CID prefix" {:prefix prefix}))
    {:cid (ipld/cid bytes) :bytes bytes}))

(defn- positive-limit! [limits key]
  (let [value (get limits key)]
    (when-not (and (integer? value) (pos? value))
      (invalid! "graphsync: positive wire limit required" {:limit key :value value}))
    value))

(defn- enforce-count! [items maximum kind]
  (when (> (count items) maximum)
    (throw (ex-info "graphsync: message exceeds item limit"
                    {:type :graphsync/resource-limit :limit kind
                     :maximum maximum :actual (count items)}))))

(defn- list-value! [value context]
  (when-not (sequential? value)
    (invalid! "graphsync: expected list" {:context context :value value}))
  (vec value))

(defn- unique-ids! [items context]
  (let [ids (mapv (comp vec :id) items)]
    (when-not (= (count ids) (count (set ids)))
      (invalid! "graphsync: duplicate request id" {:context context}))))

(defn encode-message
  "Encode a GraphSync v2 message payload as DAG-CBOR. `limits` must provide
  max-message-bytes, max-requests, max-responses, and max-blocks."
  [message limits]
  (let [max-bytes (positive-limit! limits :max-message-bytes)
        max-requests (positive-limit! limits :max-requests)
        max-responses (positive-limit! limits :max-responses)
        max-blocks (positive-limit! limits :max-blocks)
        requests (list-value! (:requests message []) :requests)
        responses (list-value! (:responses message []) :responses)
        blocks (list-value! (:blocks message []) :blocks)]
    (exact-subset! message #{:requests :responses :blocks} #{} :message)
    (when (and (empty? requests) (empty? responses) (empty? blocks))
      (invalid! "graphsync: empty message" {}))
    (enforce-count! requests max-requests :max-requests)
    (enforce-count! responses max-responses :max-responses)
    (enforce-count! blocks max-blocks :max-blocks)
    (unique-ids! requests :requests)
    (unique-ids! responses :responses)
    (let [body (cond-> {}
                 (seq requests) (assoc "req" (mapv encode-request requests))
                 (seq responses) (assoc "rsp" (mapv encode-response responses))
                 (seq blocks) (assoc "blk" (mapv encode-block blocks)))
          bytes (ipld/encode {"gs2" body})]
      (when (> (byte-length bytes) max-bytes)
        (throw (ex-info "graphsync: encoded message exceeds byte limit"
                        {:type :graphsync/resource-limit :limit :max-message-bytes
                         :maximum max-bytes :actual (byte-length bytes)})))
      bytes)))

(defn decode-message
  "Decode and validate a GraphSync v2 DAG-CBOR message payload under mandatory
  request, response, block, and byte limits."
  [bytes limits]
  (let [max-bytes (positive-limit! limits :max-message-bytes)
        max-requests (positive-limit! limits :max-requests)
        max-responses (positive-limit! limits :max-responses)
        max-blocks (positive-limit! limits :max-blocks)]
    (when (> (byte-length bytes) max-bytes)
      (throw (ex-info "graphsync: message exceeds byte limit"
                      {:type :graphsync/resource-limit :limit :max-message-bytes
                       :maximum max-bytes :actual (byte-length bytes)})))
    (let [root (ipld/decode bytes)]
      (when-not (and (map? root) (= #{"gs2"} (set (keys root))))
        (invalid! "graphsync: expected GraphSyncMessageRoot gs2 union" {:value root}))
      (let [body (get root "gs2")]
        (exact-subset! body #{"req" "rsp" "blk"} #{} :message)
        (when (empty? body) (invalid! "graphsync: empty message" {}))
        (let [requests (list-value! (get body "req" []) :requests)
              responses (list-value! (get body "rsp" []) :responses)
              blocks (list-value! (get body "blk" []) :blocks)]
          (enforce-count! requests max-requests :max-requests)
          (enforce-count! responses max-responses :max-responses)
          (enforce-count! blocks max-blocks :max-blocks)
          (let [requests (mapv decode-request requests)
                responses (mapv decode-response responses)]
            (unique-ids! requests :requests)
            (unique-ids! responses :responses)
            (cond-> {}
              (seq requests) (assoc :requests requests)
              (seq responses) (assoc :responses responses)
              (seq blocks) (assoc :blocks (mapv decode-block blocks)))))))))

(defn- read-uvarint [bytes]
  (loop [index 0 shift 0 value 0]
    (when (or (>= index (byte-length bytes)) (>= index 9))
      (invalid! "graphsync: truncated or overlong frame length" {:at index}))
    (let [octet (bit-and (byte-at bytes index) 0xff)
          value (+ value (bit-shift-left (bit-and octet 0x7f) shift))]
      (if (zero? (bit-and octet 0x80))
        [value (inc index)]
        (recur (inc index) (+ shift 7) value)))))

(defn encode-frame
  "Encode one libp2p GraphSync v2 frame (unsigned-varint length + payload)."
  [message limits]
  (let [payload (encode-message message limits)]
    (ints->bytes (concat (map #(bit-and % 0xff) (mf/varint (byte-length payload)))
                         (map #(bit-and % 0xff) payload)))))

(defn decode-frame
  "Decode exactly one length-delimited GraphSync v2 frame; trailing frames or
  bytes are rejected so stream ownership remains explicit."
  [frame limits]
  (let [[length offset] (read-uvarint frame)
        end (+ offset length)]
    (when-not (= end (byte-length frame))
      (invalid! "graphsync: frame length mismatch"
                {:declared length :available (- (byte-length frame) offset)}))
    (decode-message (ints->bytes (subvec (vec frame) offset end)) limits)))

(defn fulfill-request
  "Execute one decoded `:new` request through IPLD's CID-verifying bounded
  selector traversal and return a terminal-full GraphSync message."
  [get-fn request traversal-limits]
  (when-not (= :new (:type request))
    (invalid! "graphsync: only new requests can be fulfilled" {:request request}))
  (let [result (graph/select-blocks get-fn (:root request) (:selector request)
                                    traversal-limits)
        blocks (:blocks result)]
    {:responses [{:id (:id request)
                  :status (:completed-full status)
                  :metadata (mapv (fn [{:keys [cid]}]
                                    {:cid cid :action :present}) blocks)}]
     :blocks blocks}))
