(ns opcua.transport
  "OPC UA TCP transport (UACP) framing — Part 6 §7.1.

  Every message on the wire starts with an 8-byte common header:

  ```
  MessageType (3 ASCII bytes)  ChunkType (1 ASCII byte)  MessageSize (UInt32 LE)
  ```

  MessageType is one of `HEL` (Hello), `ACK` (Acknowledge), `ERR` (Error),
  `OPN` (OpenSecureChannel), `CLO` (CloseSecureChannel), `MSG` (an ordinary
  service request/response). ChunkType is `F` (final — the whole message),
  `C` (an intermediate chunk of a larger message; more chunks follow), or
  `A` (abort — the sender gave up mid-message; the bytes that follow are an
  error code and reason, not a truncated payload). **HEL/ACK/ERR/OPN/CLO
  are Never chunked in practice — 'F' only for them** — but this library
  does not reject 'C'/'A' on those types itself, since chunking is a
  transport-layer property this codec has no basis to second-guess for
  message types it does not otherwise validate the shape of.

  **MessageSize counts the entire message, header included** — the same
  'off by the header size' shape as `bacnet.bvlc`'s BVLC Length and
  `modbus.tcp`'s MBAP Length, and the same consequence: a decoder that
  trusts a MessageSize that under-counts the header either truncates a
  valid chunk or reads into the next one, and TCP being a byte stream
  (unlike BACnet/IP's UDP) means the desync does not even stay confined to
  one datagram.

  After the common header, the message-type-specific body:

  - **HEL/ACK**: ProtocolVersion, ReceiveBufferSize, SendBufferSize,
    MaxMessageSize, MaxChunkCount (all UInt32) — HEL adds a trailing
    EndpointUrl String; ACK does not.
  - **ERR**: Error (UInt32 StatusCode) + Reason (String).
  - **OPN** (only ever chunk type F in this library's scope; opening a
    channel is asymmetric): the AsymmetricAlgorithmSecurityHeader —
    SecurityPolicyUri (String), SenderCertificate (ByteString),
    ReceiverCertificateThumbprint (ByteString) — followed by the
    SequenceHeader (SequenceNumber, RequestId, both UInt32). The
    OpenSecureChannelRequest/Response service body itself (the actual
    negotiated SecurityMode/RequestedLifetime/etc.) is a service payload
    this library does not decode — see README.
  - **MSG/CLO** (once a channel is open, secured symmetrically): the
    SymmetricAlgorithmSecurityHeader — just SecureChannelId and TokenId,
    both UInt32 — followed by the same SequenceHeader shape. Confusing
    the asymmetric and symmetric security headers (they are different
    shapes: three fields vs. two, and the asymmetric one has strings and
    a certificate) is the mistake this namespace's two separate encode/
    decode function pairs exist to make structurally hard to make."
  (:require [opcua.builtin :as b]))

;; ── common message header ─────────────────────────────────────────────

(def message-types {:hel "HEL" :ack "ACK" :err "ERR" :opn "OPN" :clo "CLO" :msg "MSG"})
(def type->keyword (into {} (map (fn [[k v]] [v k])) message-types))
(def chunk-types {:final "F" :intermediate "C" :abort "A"})
(def chunk-char->keyword (into {} (map (fn [[k v]] [v k])) chunk-types))

#?(:clj
   (defn- ascii-bytes [^String s] (vec (.getBytes s "US-ASCII")))
   :cljs
   (defn- ascii-bytes [s] (vec (.encode (js/TextEncoder.) s))))

#?(:clj
   (defn- ascii-string [bs] (String. (byte-array (map unchecked-byte bs)) "US-ASCII"))
   :cljs
   (defn- ascii-string [bs] (.decode (js/TextDecoder. "utf-8") (js/Uint8Array.from (clj->js bs)))))

(defn encode-header
  "`message-size` is the TOTAL size (header included) — see namespace
  docstring. This function does not compute it for you, because the
  caller usually needs to know the body's length before it can even build
  this header, and re-deriving 'body length + 8' in two different places
  is how the two go out of sync."
  [{:keys [message-type chunk-type message-size]}]
  (if-let [type-str (message-types message-type)]
    (if-let [chunk-str (chunk-types chunk-type)]
      {:status :ok :bytes (into (into (ascii-bytes type-str) (ascii-bytes chunk-str))
                                 (b/encode-uint32 message-size))}
      [:error :opcua/unknown-chunk-type])
    [:error :opcua/unknown-message-type]))

(defn decode-header
  [bs offset]
  (if (< (count bs) (+ offset 8))
    [:error :opcua/truncated]
    (let [type-str (ascii-string (subvec (vec bs) offset (+ offset 3)))
          chunk-str (ascii-string (subvec (vec bs) (+ offset 3) (+ offset 4)))
          type (type->keyword type-str)
          chunk (chunk-char->keyword chunk-str)
          size-r (b/decode-uint32 bs (+ offset 4))]
      (cond
        (nil? type) [:error :opcua/unknown-message-type]
        (nil? chunk) [:error :opcua/unknown-chunk-type]
        (= :error (first size-r)) size-r
        :else {:status :ok :message-type type :chunk-type chunk
               :message-size (:value size-r) :next (:next size-r)}))))

(defn encode-message
  "Wraps `body` bytes in a header whose `:message-size` is computed as
  `8 + (count body)` — the one place in this namespace that gets to do
  that arithmetic, so every other caller building a message goes through
  here rather than recomputing it."
  [message-type chunk-type body]
  (let [hdr (encode-header {:message-type message-type :chunk-type chunk-type
                             :message-size (+ 8 (count body))})]
    (if (= :error (first hdr)) hdr
        {:status :ok :bytes (into (:bytes hdr) body)})))

(defn decode-message
  "Decodes the header and returns the body as `:body`, sliced to exactly
  `:message-size` bytes total (header included) — a `bs` that is longer
  than the declared message (e.g. it holds a second chunk right after this
  one) is handled correctly; a `bs` shorter than declared is
  `:opcua/truncated`."
  [bs offset]
  (let [hdr (decode-header bs offset)]
    (if (= :error (first hdr)) hdr
        (let [end (+ offset (:message-size hdr))]
          (if (> end (count bs))
            [:error :opcua/truncated]
            {:status :ok :message-type (:message-type hdr) :chunk-type (:chunk-type hdr)
             :message-size (:message-size hdr)
             :body (vec (subvec (vec bs) (:next hdr) end)) :next end})))))

;; ── Hello / Acknowledge (§7.1.2.3 / §7.1.2.4) ─────────────────────────

(defn encode-hello
  [{:keys [protocol-version receive-buffer-size send-buffer-size
           max-message-size max-chunk-count endpoint-url]}]
  (into (into (into (into (b/encode-uint32 protocol-version) (b/encode-uint32 receive-buffer-size))
                     (into (b/encode-uint32 send-buffer-size) (b/encode-uint32 max-message-size)))
              (b/encode-uint32 max-chunk-count))
        (b/encode-string endpoint-url)))

(defn decode-hello
  [bs offset]
  (let [pv (b/decode-uint32 bs offset)]
    (if (= :error (first pv)) pv
        (let [rb (b/decode-uint32 bs (:next pv))]
          (if (= :error (first rb)) rb
              (let [sb (b/decode-uint32 bs (:next rb))]
                (if (= :error (first sb)) sb
                    (let [mm (b/decode-uint32 bs (:next sb))]
                      (if (= :error (first mm)) mm
                          (let [mc (b/decode-uint32 bs (:next mm))]
                            (if (= :error (first mc)) mc
                                (let [url (b/decode-string bs (:next mc))]
                                  (if (= :error (first url)) url
                                      {:status :ok
                                       :protocol-version (:value pv) :receive-buffer-size (:value rb)
                                       :send-buffer-size (:value sb) :max-message-size (:value mm)
                                       :max-chunk-count (:value mc) :endpoint-url (:value url)
                                       :next (:next url)})))))))))))))

(defn encode-acknowledge
  [{:keys [protocol-version receive-buffer-size send-buffer-size max-message-size max-chunk-count]}]
  (into (into (into (b/encode-uint32 protocol-version) (b/encode-uint32 receive-buffer-size))
              (into (b/encode-uint32 send-buffer-size) (b/encode-uint32 max-message-size)))
        (b/encode-uint32 max-chunk-count)))

(defn decode-acknowledge
  [bs offset]
  (let [pv (b/decode-uint32 bs offset)]
    (if (= :error (first pv)) pv
        (let [rb (b/decode-uint32 bs (:next pv))]
          (if (= :error (first rb)) rb
              (let [sb (b/decode-uint32 bs (:next rb))]
                (if (= :error (first sb)) sb
                    (let [mm (b/decode-uint32 bs (:next sb))]
                      (if (= :error (first mm)) mm
                          (let [mc (b/decode-uint32 bs (:next mm))]
                            (if (= :error (first mc)) mc
                                {:status :ok
                                 :protocol-version (:value pv) :receive-buffer-size (:value rb)
                                 :send-buffer-size (:value sb) :max-message-size (:value mm)
                                 :max-chunk-count (:value mc) :next (:next mc)})))))))))))

;; ── Error message (§7.1.2.5) ────────────────────────────────────────────

(defn encode-error-message [{:keys [error reason]}]
  (into (b/encode-status-code error) (b/encode-string reason)))

(defn decode-error-message
  [bs offset]
  (let [e (b/decode-status-code bs offset)]
    (if (= :error (first e)) e
        (let [r (b/decode-string bs (:next e))]
          (if (= :error (first r)) r
              {:status :ok :error (:value e) :reason (:value r) :next (:next r)})))))

;; ── SequenceHeader (§7.1.2.6-ish; shared by OPN and MSG/CLO) ────────────

(defn encode-sequence-header [{:keys [sequence-number request-id]}]
  (into (b/encode-uint32 sequence-number) (b/encode-uint32 request-id)))

(defn decode-sequence-header
  [bs offset]
  (let [sn (b/decode-uint32 bs offset)]
    (if (= :error (first sn)) sn
        (let [ri (b/decode-uint32 bs (:next sn))]
          (if (= :error (first ri)) ri
              {:status :ok :sequence-number (:value sn) :request-id (:value ri) :next (:next ri)})))))

;; ── AsymmetricAlgorithmSecurityHeader (OPN) ─────────────────────────────

(defn encode-asymmetric-security-header
  [{:keys [security-policy-uri sender-certificate receiver-certificate-thumbprint]}]
  (into (into (b/encode-string security-policy-uri) (b/encode-byte-string sender-certificate))
        (b/encode-byte-string receiver-certificate-thumbprint)))

(defn decode-asymmetric-security-header
  [bs offset]
  (let [uri (b/decode-string bs offset)]
    (if (= :error (first uri)) uri
        (let [cert (b/decode-byte-string bs (:next uri))]
          (if (= :error (first cert)) cert
              (let [thumb (b/decode-byte-string bs (:next cert))]
                (if (= :error (first thumb)) thumb
                    {:status :ok :security-policy-uri (:value uri) :sender-certificate (:value cert)
                     :receiver-certificate-thumbprint (:value thumb) :next (:next thumb)})))))))

;; ── SymmetricAlgorithmSecurityHeader (MSG/CLO) ──────────────────────────

(defn encode-symmetric-security-header [{:keys [secure-channel-id token-id]}]
  (into (b/encode-uint32 secure-channel-id) (b/encode-uint32 token-id)))

(defn decode-symmetric-security-header
  [bs offset]
  (let [ch (b/decode-uint32 bs offset)]
    (if (= :error (first ch)) ch
        (let [tok (b/decode-uint32 bs (:next ch))]
          (if (= :error (first tok)) tok
              {:status :ok :secure-channel-id (:value ch) :token-id (:value tok) :next (:next tok)})))))
