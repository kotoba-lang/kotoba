(ns opcua.nodeid
  "OPC UA NodeId (§7.2.11 / Part 6 §5.2.2) and ExpandedNodeId (§7.2.11.5 /
  Part 6 §5.2.2.15) — the two identity types with FOUR different wire
  shapes selected by the first byte, the classic source of NodeId codec
  bugs because every shape parses as *something* if you assume the wrong
  one.

  The first byte's low 6 bits (0x3F) select the identifier encoding:

  | code | name     | namespace field   | identifier field |
  |------|----------|--------------------|-------------------|
  | 0x00 | two-byte | implied 0          | Byte (0-255)      |
  | 0x01 | four-byte| Byte (0-255)       | UInt16            |
  | 0x02 | numeric  | UInt16              | UInt32            |
  | 0x03 | string   | UInt16              | String            |
  | 0x04 | guid     | UInt16              | Guid              |
  | 0x05 | opaque   | UInt16              | ByteString        |

  **Two-byte and four-byte are compact special cases of numeric, not a
  separate identifier type** — `ns=0, i=5` can legally be encoded three
  different ways (two-byte if i <= 255, four-byte if ns <= 255 and
  i <= 65535, or numeric always), and a decoder that only recognizes the
  numeric form because 'that is the general case' will reject perfectly
  valid two-byte-encoded messages every real server sends for the common,
  small, namespace-0 identifiers.

  ExpandedNodeId reuses the identical NodeId body but repurposes the top 2
  bits of that same first byte as flags rather than extending the 6-bit
  code: 0x80 = a NamespaceUri String follows the NodeId body (and the
  NodeId's own NamespaceIndex is then conventionally 0 and the URI is
  authoritative), 0x40 = a ServerIndex UInt32 follows after that. This
  means an ExpandedNodeId decoder MUST mask off the top 2 bits before
  looking up the identifier-encoding code — using the raw first byte as
  the table key silently rejects (or worse, misreads as a different
  identifier type) every ExpandedNodeId that actually sets either flag."
  (:require [opcua.builtin :as b]))

(def encoding-codes
  {:two-byte 0x00 :four-byte 0x01 :numeric 0x02 :string 0x03 :guid 0x04 :opaque 0x05})
(def code->encoding (into {} (map (fn [[k v]] [v k])) encoding-codes))

(def namespace-uri-flag 0x80)
(def server-index-flag 0x40)
(def identifier-mask 0x3F)

;; ── NodeId ─────────────────────────────────────────────────────────────

(defn encode
  "`{:encoding :two-byte|:four-byte|:numeric|:string|:guid|:opaque
     :namespace-index n :identifier v}` — `v` is a Byte, UInt16, UInt32,
  String, Guid map, or byte vector matching `:encoding`. Choosing the
  smallest legal encoding for a given (namespace, identifier) pair is the
  caller's decision, not this function's — it encodes exactly the shape
  requested."
  [{:keys [encoding namespace-index identifier]}]
  (case encoding
    :two-byte
    (if (<= 0 identifier 0xFF)
      {:status :ok :bytes [(:two-byte encoding-codes) (b/u8 identifier)]}
      [:error :opcua/identifier-out-of-range])

    :four-byte
    (if (and (<= 0 namespace-index 0xFF) (<= 0 identifier 0xFFFF))
      {:status :ok :bytes (into [(:four-byte encoding-codes) namespace-index] (b/le16 identifier))}
      [:error :opcua/identifier-out-of-range])

    :numeric
    {:status :ok :bytes (into (into [(:numeric encoding-codes)] (b/le16 namespace-index))
                               (b/le32 identifier))}

    :string
    {:status :ok :bytes (into (into [(:string encoding-codes)] (b/le16 namespace-index))
                               (b/encode-string identifier))}

    :guid
    {:status :ok :bytes (into (into [(:guid encoding-codes)] (b/le16 namespace-index))
                               (b/encode-guid identifier))}

    :opaque
    {:status :ok :bytes (into (into [(:opaque encoding-codes)] (b/le16 namespace-index))
                               (b/encode-byte-string identifier))}

    [:error :opcua/unknown-encoding]))

(defn- decode-body
  "Decodes a NodeId body given the already-masked 6-bit `code` starting at
  `offset` (the byte right after the first/flags byte). Shared by `decode`
  and `opcua.nodeid/decode` for the ExpandedNodeId case below."
  [code bs offset]
  (case (code->encoding code)
    :two-byte
    (if-let [ident (b/safe-nth bs offset)]
      {:status :ok :encoding :two-byte :namespace-index 0 :identifier ident :next (inc offset)}
      [:error :opcua/truncated])

    :four-byte
    (if-let [ns (b/safe-nth bs offset)]
      (let [ident-r (b/decode-uint16 bs (inc offset))]
        (if (= :error (first ident-r)) ident-r
            {:status :ok :encoding :four-byte :namespace-index ns
             :identifier (:value ident-r) :next (:next ident-r)}))
      [:error :opcua/truncated])

    :numeric
    (let [ns-r (b/decode-uint16 bs offset)]
      (if (= :error (first ns-r)) ns-r
          (let [id-r (b/decode-uint32 bs (:next ns-r))]
            (if (= :error (first id-r)) id-r
                {:status :ok :encoding :numeric :namespace-index (:value ns-r)
                 :identifier (:value id-r) :next (:next id-r)}))))

    :string
    (let [ns-r (b/decode-uint16 bs offset)]
      (if (= :error (first ns-r)) ns-r
          (let [id-r (b/decode-string bs (:next ns-r))]
            (if (= :error (first id-r)) id-r
                {:status :ok :encoding :string :namespace-index (:value ns-r)
                 :identifier (:value id-r) :next (:next id-r)}))))

    :guid
    (let [ns-r (b/decode-uint16 bs offset)]
      (if (= :error (first ns-r)) ns-r
          (let [id-r (b/decode-guid bs (:next ns-r))]
            (if (= :error (first id-r)) id-r
                {:status :ok :encoding :guid :namespace-index (:value ns-r)
                 :identifier (:value id-r) :next (:next id-r)}))))

    :opaque
    (let [ns-r (b/decode-uint16 bs offset)]
      (if (= :error (first ns-r)) ns-r
          (let [id-r (b/decode-byte-string bs (:next ns-r))]
            (if (= :error (first id-r)) id-r
                {:status :ok :encoding :opaque :namespace-index (:value ns-r)
                 :identifier (:value id-r) :next (:next id-r)}))))

    [:error :opcua/unknown-encoding]))

(defn decode
  [bs offset]
  (if-let [first-byte (b/safe-nth bs offset)]
    (decode-body first-byte bs (inc offset))
    [:error :opcua/truncated]))

;; ── ExpandedNodeId ─────────────────────────────────────────────────────

(defn encode-expanded
  "`node-id` as for `encode`, plus optional `:namespace-uri` (String) and
  `:server-index` (UInt32). The flag bits are set/cleared to match which
  optional fields are present — they are derived, not a separate input a
  caller could set inconsistently with the actual trailing fields."
  [{:keys [node-id namespace-uri server-index]}]
  (let [base (encode node-id)]
    (if (= :error (first base))
      base
      (let [[first-byte & rest-bytes] (:bytes base)
            flagged (bit-or first-byte
                             (if namespace-uri namespace-uri-flag 0)
                             (if server-index server-index-flag 0))]
        {:status :ok
         :bytes (into (into [flagged] rest-bytes)
                      (concat (when namespace-uri (b/encode-string namespace-uri))
                              (when server-index (b/encode-uint32 server-index))))}))))

(defn decode-expanded
  [bs offset]
  (if-let [first-byte (b/safe-nth bs offset)]
    (let [code (bit-and first-byte identifier-mask)
          has-uri? (not (zero? (bit-and first-byte namespace-uri-flag)))
          has-server-index? (not (zero? (bit-and first-byte server-index-flag)))
          body (decode-body code bs (inc offset))]
      (if (= :error (first body)) body
          (let [uri-r (if has-uri? (b/decode-string bs (:next body))
                          {:status :ok :value nil :next (:next body)})]
            (if (= :error (first uri-r)) uri-r
                (let [srv-r (if has-server-index? (b/decode-uint32 bs (:next uri-r))
                                {:status :ok :value nil :next (:next uri-r)})]
                  (if (= :error (first srv-r)) srv-r
                      {:status :ok
                       :node-id (dissoc body :status :next)
                       :namespace-uri (:value uri-r)
                       :server-index (:value srv-r)
                       :next (:next srv-r)}))))))
    [:error :opcua/truncated]))
