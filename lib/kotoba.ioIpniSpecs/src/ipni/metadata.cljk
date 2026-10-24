(ns ipni.metadata
  "IPNI advertisement metadata — a multicodec protocol identifier, then
  protocol-specific bytes.

  kotobase retrieval is `transport-ipfs-gateway-http` (`0x0920`). That is
  what kotoba `codebase-routing` already filters for. Bitswap (`0x0900`)
  is here because IPNI talks it; kotobase does not.

  Encoding is unsigned LEB128. This namespace does not import
  io-multiformats: the identifier is one varint, not a CID.")

(def ^:const bitswap 0x0900)
(def ^:const graphsync-filecoin 0x0909)
(def ^:const graphsync 0x0910)
(def ^:const http 0x0911)
(def ^:const gateway-http 0x0920)


;; ── IPQ: bounded, verifiable selection over HTTP ─────────────────────────────
;;
;; What kotobase can already say through IPNI is `transport-ipfs-gateway-http`:
;; "ask me for a CID and I will hand you the bytes". What it cannot say is the
;; thing it actually does -- run a bounded IPLD selector and return exactly the
;; blocks that prove the result. There is no registered protocol identifier for
;; that, so a provider offering it is indistinguishable from one that does not.
;;
;; Verified against the multicodec table on 2026-09-06 before choosing a code:
;;
;;   - README "Reserved Code Ranges / Private Use Area" gives 0x300000-0x3FFFFF,
;;     "reserved for internal use by applications and will never be assigned any
;;     meaning as part of the Multicodec specification".
;;   - table.csv carries ZERO entries in that range, and none at 0x0940.
;;   - the registered transport family is spaced by 0x10: 0x0900 bitswap,
;;     0x0910 graphsync-filecoinv1, 0x0920 ipfs-gateway-http,
;;     0x0930 filecoin-piece-http. 0x0940 is the next free slot.
;;
;; So the code below is the private-use base plus the slot a registration would
;; ask for. Announcing an unregistered code OUTSIDE the private range would be
;; squatting on a registry we do not own; announcing one inside it is what the
;; range is for, and it is self-describing -- a reader that does not know this
;; code learns that it is application-private, not that the advertisement is
;; malformed.
(def ^:const ipq-selection-http 0x300940)

(def ^:const ipq-selection-http-registration-request
  "The code a multicodec registration would ask for. Not announced. Recorded so
  the ask and the private-use code cannot drift apart."
  0x0940)

;; The profile number is where the honesty lives. IPQ/1 proves that a named
;; traversal was executed against CID-verified blocks -- it does NOT prove that
;; a database range or a Datalog answer is complete, which needs authenticated
;; index boundaries (kotobase ADR-2609060000). A later profile that carries
;; those may exist; naming the layer IPQ does not backdate it.
(def ^:const ipq-selection-profile 1)
(def supported-ipq-profiles #{1})

(def protocol-name
  {bitswap "transport-bitswap"
   graphsync-filecoin "transport-graphsync-filecoinv1"
   graphsync "transport-graphsync"
   http "transport-http"
   gateway-http "transport-ipfs-gateway-http"
   ipq-selection-http "transport-ipq-selection-http"})

(defn uvarint-encode
  "Unsigned LEB128. Refuses negatives rather than wrapping."
  [n]
  (cond
    (not (integer? n)) {:error :not-integer :value n}
    (neg? n) {:error :negative :value n}
    :else
    (loop [n n out []]
      (if (< n 128)
        (conj out n)
        (recur (quot n 128)
               (conj out (bit-or (bit-and n 0x7F) 0x80)))))))

(defn uvarint-decode
  "First unsigned LEB128 in `octets`. Returns `{:value :rest}` or an error.
  An empty input is not 0 — silence is not a protocol identifier."
  [octets]
  (let [xs (vec octets)]
    (if (empty? xs)
      {:error :empty}
      (loop [i 0 acc 0 shift 0]
        (if (>= i (count xs))
          {:error :truncated}
          (let [b (bit-and (nth xs i) 0xFF)
                acc (bit-or acc (bit-shift-left (bit-and b 0x7F) shift))]
            (if (zero? (bit-and b 0x80))
              {:value acc :rest (subvec xs (inc i))}
              (if (> shift 63)
                {:error :overflow}
                (recur (inc i) acc (+ shift 7))))))))))

(defn encode
  "Protocol identifier as metadata bytes. Extra protocol bytes may follow."
  ([protocol] (encode protocol nil))
  ([protocol extra]
   (let [head (uvarint-encode protocol)]
     (if (:error head)
       head
       (into head (mapv #(bit-and % 0xFF) (or extra [])))))))

(defn decode
  [octets]
  (let [r (uvarint-decode octets)]
    (if (:error r)
      r
      {:protocol (:value r)
       :name (get protocol-name (:value r))
       :extra (:rest r)})))

(declare entry-bytes)

(defn gateway-http-bytes
  "One trustless-gateway entry: the identifier and a payload length of zero.

  This used to be two bytes, matching IPNI.md's prose. Measured 2026-09-06,
  go-libipni v0.8.2 REJECTS two bytes -- `expected 3 readable bytes but read 2`
  -- because its `ipfsGatewayHttpBytes` is the identifier plus `varint(0)`. The
  live advertisement has always carried three; it was this function that was
  wrong, and only harmlessly so because `ipni-drain` publishes, not this."
  []
  (entry-bytes gateway-http []))

(defn gateway-http?
  [octets]
  (= gateway-http (:protocol (decode octets))))


;; ── one Metadata field, several protocols ────────────────────────────────────
;;
;; IPNI.md says: "metadata begins with a uvarint identifying the protocol,
;; followed by protocol-specific metadata. This may be repeated for additional
;; supported protocols. Specified protocols are expected to be ordered in
;; increasing order."
;;
;; That prose is not the wire format. Measured 2026-09-06 against go-libipni
;; v0.8.2 -- the reference implementation the indexers run -- the framing is
;;
;;     uvarint(protocol) ++ uvarint(payload-length) ++ payload
;;
;; and the spec's "no following metadata" is a payload of length ZERO, not an
;; absent length. The consequences are not cosmetic:
;;
;;   a012                 REJECTED  "expected 3 readable bytes but read 2"
;;   a01200               accepted  (this is what kotobase publishes today)
;;   a01200c092c00101     REJECTED  EOF -- a protocol with no length prefix
;;   a01200c092c0010101   accepted  [transport-ipfs-gateway-http Code(3148096)]
;;                                  and remarshals byte-identically
;;
;; So the third byte in the live advertisement is correct and this namespace's
;; earlier two-byte `gateway-http-bytes` was the wrong one -- it produced bytes
;; the reference rejects, and was harmless only because the publisher that
;; actually publishes is `ipni-drain`, which hardcoded the right ones.
;;
;; Bitswap is the exception, in the reference itself: `bitswapBytes` is the bare
;; identifier with no length. That is why bitswap cannot be concatenated with
;; anything, and why `encode-sequence` refuses to try.

(def length-prefixed?
  "Whether a protocol's entry carries a uvarint payload length.

  Everything in go-libipni does except bitswap. `Unknown` -- which is how a
  code the reference has never seen is parsed, and therefore how IPQ is parsed
  -- reads code, then length, then that many bytes. A private-use protocol that
  omits the length ends the reference's parse at EOF."
  (fn [protocol] (not= bitswap protocol)))

(defn entry-bytes
  "One `uvarint(protocol) ++ uvarint(len) ++ payload` entry."
  ([protocol] (entry-bytes protocol []))
  ([protocol payload]
   (let [head (uvarint-encode protocol)
         body (mapv #(bit-and % 0xFF) (or payload []))]
     (cond
       (:error head) head
       (not (length-prefixed? protocol)) (into head body)
       :else
       (let [len (uvarint-encode (count body))]
         (if (:error len) len (into (into head len) body)))))))

(defn decode-sequence
  "Every protocol in one Metadata field.

  Returns `{:ok? true :entries [{:protocol :name :payload} ...] :ordered? bool}`
  or `{:ok? false :reason ...}`:

      :empty      no bytes. Silence is not \"no protocols\": IPNI.md gives an
                  advertisement with no Metadata its own meaning, an address update
      :truncated  an identifier, a length, or a declared payload runs past the end
      :unframed   a bitswap entry in a sequence. The reference cannot read past
                  one either, so this refuses rather than return a prefix

  `:ordered?` reports the spec's increasing-order expectation rather than
  enforcing it -- the reference accepts unordered input and sorts it on
  remarshal, so refusing here would reject data that is live somewhere.
  `encode-sequence` is where we are strict, because that is the half we own."
  [octets]
  (let [xs (vec octets)]
    (if (empty? xs)
      {:ok? false :reason :empty}
      (loop [rest-bytes xs entries []]
        (if (empty? rest-bytes)
          {:ok? true :entries entries
           :ordered? (= (mapv :protocol entries) (sort (mapv :protocol entries)))}
          (let [h (uvarint-decode rest-bytes)]
            (if (:error h)
              {:ok? false :reason :truncated :detail (:error h) :entries entries}
              (let [proto (:value h)]
                (if-not (length-prefixed? proto)
                  {:ok? false :reason :unframed :protocol proto
                   :name (get protocol-name proto) :entries entries}
                  (let [l (uvarint-decode (:rest h))]
                    (if (:error l)
                      {:ok? false :reason :truncated :protocol proto
                       :detail (:error l) :entries entries}
                      (let [n (:value l) body (vec (:rest l))]
                        (if (< (count body) n)
                          {:ok? false :reason :truncated :protocol proto
                           :detail :payload :entries entries}
                          (recur (subvec body n)
                                 (conj entries {:protocol proto
                                                :name (get protocol-name proto)
                                                :payload (subvec body 0 n)})))))))))))))))

(defn encode-sequence
  "Metadata bytes for several protocols, in increasing protocol order.

  Refuses rather than reorders. The reference sorts on remarshal, so a caller
  who believes their order means something should hear about it here rather
  than discover it changed on the wire."
  [entries]
  (let [protos (mapv :protocol entries)]
    (cond
      (empty? entries) {:error :empty}
      (not= protos (sort protos)) {:error :out-of-order :protocols protos}
      (not= (count protos) (count (distinct protos))) {:error :duplicate-protocol
                                                       :protocols protos}
      (and (> (count protos) 1) (some #(not (length-prefixed? %)) protos))
      {:error :unframed-in-sequence :protocols protos}
      :else
      (reduce (fn [acc {:keys [protocol payload]}]
                (if (:error acc)
                  acc
                  (let [e (entry-bytes protocol payload)]
                    (if (:error e) e (into acc e)))))
              []
              entries))))

(defn ipq-selection-http-bytes
  "IPQ metadata: the identifier, a payload length of one, and the profile."
  ([] (ipq-selection-http-bytes ipq-selection-profile))
  ([profile] (entry-bytes ipq-selection-http [profile])))

(defn kotobase-metadata-bytes
  "What a kotobase advertisement carries: the trustless gateway, then IPQ.

  0x0920 < 0x300940, which is already the increasing order the spec asks for
  and the order the reference remarshals into."
  ([] (kotobase-metadata-bytes ipq-selection-profile))
  ([profile]
   (encode-sequence [{:protocol gateway-http :payload []}
                     {:protocol ipq-selection-http :payload [profile]}])))

(defn read-ipq
  "Find IPQ in a Metadata field, keeping four answers apart that a predicate
  would fuse.

  Returns `{:ok? true :protocol :profile}`, or `{:ok? false :reason ...}` with

      :not-ipq              decodable, and IPQ is not among the protocols
      :undecodable          the Metadata could not be parsed at all, so the
                            question was never answered. NOT the same as
                            :not-ipq, which is an answer
      :profile-missing      our identifier with an empty payload
      :profile-unsupported  our identifier, a profile we do not implement

  There is deliberately no `ipq?` predicate. A boolean makes the last case read
  as the first, and those are opposite instructions: `:not-ipq` means route
  elsewhere, `:profile-unsupported` means this provider speaks a newer IPQ than
  we do and a caller that treats it as \"not IPQ\" will never notice the version
  it is failing to keep up with.

  This SCANS the sequence. Reading only the first entry cannot find IPQ in the
  one shape that matters -- a provider announcing the gateway and IPQ together."
  [octets]
  (let [seq-result (decode-sequence octets)]
    (if-not (:ok? seq-result)
      {:ok? false :reason :undecodable :detail (:reason seq-result)}
      (if-let [entry (first (filter #(= ipq-selection-http (:protocol %))
                                    (:entries seq-result)))]
        (let [profile (first (:payload entry))]
          (cond
            (nil? profile) {:ok? false :reason :profile-missing}
            (not (contains? supported-ipq-profiles profile))
            {:ok? false :reason :profile-unsupported :profile profile
             :supported supported-ipq-profiles}
            :else {:ok? true :protocol ipq-selection-http :profile profile}))
        {:ok? false :reason :not-ipq
         :protocols (mapv :protocol (:entries seq-result))}))))
