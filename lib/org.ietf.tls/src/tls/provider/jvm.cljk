(ns ^{:clj-kondo/ignore [:unused-namespace]} tls.provider.jvm
  "A `tls.provider` implementation backed by the JDK's own crypto providers.

  No external dependency: SHA-2, HMAC, X25519, AES-GCM, ChaCha20-Poly1305,
  Ed25519, ECDSA and RSASSA-PSS all ship with the JDK. Availability is measured
  at construction by `capabilities`, not assumed -- a JVM missing an algorithm
  reports it rather than failing at the first record.

  Every JDK primitive object here (`MessageDigest`, `Mac`, `Cipher`,
  `Signature`) is created per call. They are stateful and not thread-safe, and a
  provider map is shared by every connection.

  Errors are values throughout; see `tls.provider` for the contract and for why
  every post-validation AEAD failure collapses to `:aead/bad-tag`."
  (:require [tls.provider :as p])
  #?(:clj
  (:import [java.security MessageDigest KeyFactory KeyPairGenerator Signature
            SecureRandom]
           [java.security.spec NamedParameterSpec XECPublicKeySpec XECPrivateKeySpec
            PSSParameterSpec MGF1ParameterSpec X509EncodedKeySpec]
           [java.security.interfaces XECPublicKey XECPrivateKey]
           [javax.crypto Cipher Mac KeyAgreement]
           [javax.crypto.spec SecretKeySpec GCMParameterSpec IvParameterSpec]
           [java.math BigInteger]
           [java.util Arrays])))

;; ---------------------------------------------------------------------------
;; This namespace is JVM-only by construction: it is the JDK-backed provider.
;; It is `.cljc` rather than `.clj` because this workspace forbids new
;; production `.clj` (ADR-2608201300, runtime priority), and the whole body is
;; therefore spliced in under `:clj` rather than merely carrying a portable file
;; extension it could not honour. A ClojureScript or `.kotoba` provider does not
;; belong here -- it belongs in a sibling namespace behind the same
;; `tls.provider` contract, which is the point of the seam.
;; ---------------------------------------------------------------------------

#?(:clj
(do
(set! *warn-on-reflection* true)

;; ---------------------------------------------------------------------------
;; Byte helpers
;; ---------------------------------------------------------------------------

(def ^:private byte-array-class (Class/forName "[B"))

(defn- bytes?* [x] (instance? byte-array-class x))

(defn- blen ^long [^bytes b] (alength b))

(defn- le32
  "A little-endian 32-byte encoding of a non-negative BigInteger.

  `BigInteger/toByteArray` is big-endian, minimal-length, and may carry a
  leading sign byte -- so neither its length nor its orientation can be used
  directly for an X25519 u-coordinate."
  ^bytes [^BigInteger u]
  (let [be  (.toByteArray u)
        n   (alength be)
        out (byte-array 32)]
    (dotimes [i (min n 32)]
      (aset-byte out i (aget be (- n 1 i))))
    out))

(defn- le->u
  "Decode a 32-byte little-endian X25519 u-coordinate.

  RFC 7748 s5 requires the most significant bit of the final byte to be masked
  off before use; peers are permitted to set it and a conforming implementation
  must ignore it rather than reject the key share."
  ^BigInteger [^bytes le]
  (let [c (Arrays/copyOf le 32)]
    (aset-byte c 31 (unchecked-byte (bit-and (aget c 31) 0x7f)))
    (let [be (byte-array 32)]
      (dotimes [i 32] (aset-byte be i (aget c (- 31 i))))
      (BigInteger. 1 be))))

;; ---------------------------------------------------------------------------
;; Hash
;; ---------------------------------------------------------------------------

(def ^:private jdk-digest {:sha256 "SHA-256" :sha384 "SHA-384"})
(def ^:private jdk-mac    {:sha256 "HmacSHA256" :sha384 "HmacSHA384"})

(defn- digest
  [hash-kw ^bytes input]
  (if-not (bytes?* input)
    [:error :hash/bad-input]
    (.digest (MessageDigest/getInstance ^String (jdk-digest hash-kw)) input)))

;; ---------------------------------------------------------------------------
;; HMAC
;; ---------------------------------------------------------------------------

(defn- hmac
  "HMAC over `data` keyed by `key`, per RFC 2104.

  An empty key is accepted rather than refused. RFC 2104 zero-pads the key to
  the hash's block size, so an empty key and an all-zero key of any length up to
  the block size produce the identical K0 and therefore the identical MAC. The
  JDK's `SecretKeySpec` rejects a zero-length key outright, so the equivalent
  single zero byte is substituted -- this changes no output, it only routes
  around a constructor precondition."
  [hash-kw key data]
  (let [alg (jdk-mac hash-kw)]
    (cond
      (nil? alg)                            [:error :hmac/unknown-hash]
      (not (and (bytes?* key) (bytes?* data))) [:error :hmac/bad-input]
      :else
      (let [^bytes k (if (zero? (blen key)) (byte-array 1) key)
            m (Mac/getInstance ^String alg)]
        (.init m (SecretKeySpec. k ^String alg))
        (.doFinal m ^bytes data)))))

;; ---------------------------------------------------------------------------
;; X25519
;; ---------------------------------------------------------------------------

(def ^:private x25519-spec (NamedParameterSpec/X25519))

(defn- x25519-keypair
  []
  (let [kpg (KeyPairGenerator/getInstance "X25519")
        kp  (.generateKeyPair kpg)
        priv ^XECPrivateKey (.getPrivate kp)
        pub  ^XECPublicKey  (.getPublic kp)]
    {:private (.orElse (.getScalar priv) (byte-array 0))
     :public  (le32 (.getU pub))}))

(defn- x25519-dh
  "Raw X25519 as RFC 7748 defines it: 32-byte scalar, 32-byte u-coordinate,
  32-byte shared secret.

  Returns the shared secret on success, or `[:error reason]`. The refusal that
  carries protocol weight is `:x25519/small-order-point`: RFC 8446 s7.4.2
  requires the handshake to abort when the shared secret would be all zeroes,
  and the JDK enforces this by rejecting small-order peer keys outright
  (`InvalidKeyException: Point has small order`) rather than returning a
  degenerate secret."
  [priv peer-pub]
  (cond
    (not (and (bytes?* priv) (bytes?* peer-pub))) [:error :x25519/bad-input]
    (not= 32 (blen priv))     [:error :x25519/bad-private-key-length]
    (not= 32 (blen peer-pub)) [:error :x25519/bad-peer-key-length]
    :else
    (try
      (let [kf  (KeyFactory/getInstance "XDH")
            sk  (.generatePrivate kf (XECPrivateKeySpec. x25519-spec priv))
            pk  (.generatePublic  kf (XECPublicKeySpec. x25519-spec (le->u peer-pub)))
            ka  (KeyAgreement/getInstance "X25519")]
        (.init ka sk)
        (.doPhase ka pk true)
        (.generateSecret ka))
      (catch java.security.InvalidKeyException e
        (if (re-find #"(?i)small order" (str (.getMessage e)))
          [:error :x25519/small-order-point]
          [:error :x25519/agreement-failed]))
      (catch Throwable _ [:error :x25519/agreement-failed]))))

;; ---------------------------------------------------------------------------
;; AEAD
;; ---------------------------------------------------------------------------

(defn- aead-cipher
  ^Cipher [suite mode ^bytes key ^bytes nonce]
  (case suite
    :aes-128-gcm
    (doto (Cipher/getInstance "AES/GCM/NoPadding")
      (.init ^int mode (SecretKeySpec. key "AES") (GCMParameterSpec. 128 nonce)))
    :chacha20-poly1305
    (doto (Cipher/getInstance "ChaCha20-Poly1305")
      (.init ^int mode (SecretKeySpec. key "ChaCha20") (IvParameterSpec. nonce)))))

(defn- check-params
  "Validate caller-supplied key and nonce lengths before any cipher runs.

  These are not redundant with the JDK. Measured on this JVM: AES-GCM accepts an
  11-byte nonce without complaint, which for TLS would silently produce frames
  no conforming peer can open."
  [suite key nonce]
  (let [{:keys [key-len nonce-len]} (p/aead-params suite)]
    (cond
      (nil? key-len)                    [:error :aead/unknown-suite]
      (not (and (bytes?* key) (bytes?* nonce))) [:error :aead/bad-input]
      (not= key-len   (blen key))       [:error :aead/bad-key-length]
      (not= nonce-len (blen nonce))     [:error :aead/bad-nonce-length]
      :else nil)))

(defn- seal
  "Encrypt-and-authenticate. Returns ciphertext||tag, or `[:error reason]`."
  [suite key nonce aad plaintext]
  (or (check-params suite key nonce)
      (if-not (and (bytes?* aad) (bytes?* plaintext))
        [:error :aead/bad-input]
        (try
          (let [c (aead-cipher suite Cipher/ENCRYPT_MODE key nonce)]
            (when (pos? (blen ^bytes aad)) (.updateAAD c ^bytes aad))
            (.doFinal c ^bytes plaintext))
          (catch Throwable _ [:error :aead/bad-input])))))

(defn- open*
  "Verify-and-decrypt. `[:ok plaintext]` or `[:error reason]`.

  Past the parameter gate every failure is `:aead/bad-tag`, and no plaintext is
  returned with it. The JDK is well-behaved here -- measured, both AES-GCM and
  ChaCha20-Poly1305 throw `AEADBadTagException` and buffer the plaintext rather
  than releasing it -- but the guarantee this function offers does not rest on
  that: the plaintext never escapes the `try`, so a provider that did release
  bytes could not leak them through this path."
  [suite key nonce aad ciphertext]
  (or (check-params suite key nonce)
      (if-not (and (bytes?* aad) (bytes?* ciphertext))
        [:error :aead/bad-input]
        (try
          (let [c (aead-cipher suite Cipher/DECRYPT_MODE key nonce)]
            (when (pos? (blen ^bytes aad)) (.updateAAD c ^bytes aad))
            [:ok (.doFinal c ^bytes ciphertext)])
          ;; Every downstream failure -- bad tag, truncated frame, forged frame --
          ;; is one indistinguishable reason. See tls.provider.
          (catch Throwable _ [:error :aead/bad-tag])))))

;; ---------------------------------------------------------------------------
;; Signature verification
;; ---------------------------------------------------------------------------

(def ^:private scheme-table
  "TLS 1.3 SignatureScheme -> how the JDK spells it.

  `:pss` carries the salt length, which RFC 8446 s4.2.3 fixes to the digest
  length for the rsa_pss_rsae_* schemes."
  {:ecdsa-secp256r1-sha256 {:kf "EC"      :sig "SHA256withECDSA"}
   :ed25519                {:kf "Ed25519" :sig "Ed25519"}
   :rsa-pss-rsae-sha256    {:kf "RSA" :sig "RSASSA-PSS"
                            :pss {:md "SHA-256" :mgf MGF1ParameterSpec/SHA256 :salt 32}}
   :rsa-pss-rsae-sha384    {:kf "RSA" :sig "RSASSA-PSS"
                            :pss {:md "SHA-384" :mgf MGF1ParameterSpec/SHA384 :salt 48}}})

(defn- verify
  "Verify `signature` over `message` under the SubjectPublicKeyInfo `spki-der`.

  Returns `[:ok true]` or `[:error reason]`. There is deliberately no
  `[:ok false]`: a rejected signature is an error value, so a caller matching
  `[:ok _]` cannot read a rejection as an acceptance.

  A key whose type does not match the scheme (an RSA SPKI offered for
  `:ed25519`, say) is `:signature/bad-public-key` -- distinguishing a malformed
  key from a bad signature is safe here, since the key comes from the
  certificate rather than from the signature under attack."
  [scheme spki-der message signature]
  (let [{:keys [kf sig pss]} (scheme-table scheme)]
    (cond
      (nil? kf) [:error :signature/unknown-scheme]

      (not (and (bytes?* spki-der) (bytes?* message) (bytes?* signature)))
      [:error :signature/bad-input]

      :else
      (let [pub (try
                  (.generatePublic (KeyFactory/getInstance ^String kf)
                                   (X509EncodedKeySpec. ^bytes spki-der))
                  (catch Throwable _ nil))]
        (if (nil? pub)
          [:error :signature/bad-public-key]
          (try
            (let [v (Signature/getInstance ^String sig)]
              (when pss
                (.setParameter v (PSSParameterSpec. ^String (:md pss) "MGF1"
                                                    ^MGF1ParameterSpec (:mgf pss)
                                                    ^int (int (:salt pss)) 1)))
              (.initVerify v ^java.security.PublicKey pub)
              (.update v ^bytes message)
              (if (.verify v ^bytes signature)
                [:ok true]
                [:error :signature/bad-signature]))
            (catch java.security.InvalidKeyException _ [:error :signature/bad-public-key])
            ;; A structurally malformed signature (bad DER for ECDSA, wrong
            ;; length for Ed25519) is a rejected signature, not a distinct event.
            (catch Throwable _ [:error :signature/bad-signature])))))))

;; ---------------------------------------------------------------------------
;; Random
;; ---------------------------------------------------------------------------

(defonce ^:private secure-random (SecureRandom.))

(defn- random-bytes
  [n]
  (if-not (and (integer? n) (nat-int? n))
    [:error :random/bad-length]
    (let [out (byte-array n)]
      (.nextBytes ^SecureRandom secure-random out)
      out)))

;; ---------------------------------------------------------------------------
;; Capability measurement
;; ---------------------------------------------------------------------------

(defn capabilities
  "Which JDK algorithms this JVM actually offers, measured rather than assumed.

  Returns a map of label -> true, or label -> the failure string. Intended for
  the report a wiring site prints when it refuses to start."
  []
  (into {}
        (map (fn [[label f]]
               [label (try (f) true (catch Throwable t (str (.getSimpleName (class t))
                                                            ": " (.getMessage t))))]))
        {"SHA-256"           #(MessageDigest/getInstance "SHA-256")
         "SHA-384"           #(MessageDigest/getInstance "SHA-384")
         "HmacSHA256"        #(Mac/getInstance "HmacSHA256")
         "HmacSHA384"        #(Mac/getInstance "HmacSHA384")
         "X25519"            #(KeyPairGenerator/getInstance "X25519")
         "AES/GCM/NoPadding" #(Cipher/getInstance "AES/GCM/NoPadding")
         "ChaCha20-Poly1305" #(Cipher/getInstance "ChaCha20-Poly1305")
         "Ed25519"           #(Signature/getInstance "Ed25519")
         "SHA256withECDSA"   #(Signature/getInstance "SHA256withECDSA")
         "RSASSA-PSS"        #(Signature/getInstance "RSASSA-PSS")}))

;; ---------------------------------------------------------------------------
;; The provider
;; ---------------------------------------------------------------------------

(defn provider
  "Build the JDK-backed provider map.

  Self-checks against `tls.provider/validate` before returning. That check can
  only fail if this namespace itself is malformed, so it throws rather than
  returning an error value -- it is an internal invariant at wiring time, not a
  protocol event on a data path."
  []
  (let [m {:hash      {:sha256 #(digest :sha256 %)
                       :sha384 #(digest :sha384 %)}
           :hmac      hmac
           :x25519    {:keypair x25519-keypair
                       :dh      x25519-dh}
           :aead      {:aes-128-gcm
                       {:seal (fn [k n aad pt] (seal  :aes-128-gcm k n aad pt))
                        :open (fn [k n aad ct] (open* :aes-128-gcm k n aad ct))}
                       :chacha20-poly1305
                       {:seal (fn [k n aad pt] (seal  :chacha20-poly1305 k n aad pt))
                        :open (fn [k n aad ct] (open* :chacha20-poly1305 k n aad ct))}}
           :signature {:verify verify}
           :random    random-bytes}
        result (p/validate m)]
    (if (= :ok (first result))
      m
      (throw (ex-info (str "tls.provider.jvm/provider is internally incomplete: "
                           (p/explain result))
                      {:result result})))))
))
