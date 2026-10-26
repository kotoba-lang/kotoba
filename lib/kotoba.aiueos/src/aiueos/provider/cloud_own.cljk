(ns aiueos.provider.cloud-own
  "The same requests as `aiueos.provider.cloud`, over this workspace's own TLS
  and HTTP instead of the platform's.

  `kotoba-lang/org-ietf-tls` moves the bytes and `kotoba.lang.http.wire` frames
  them. Neither knows about the other: the whole of the coupling is
  `tls-transport` below, which turns `tls.client/write!` and `read!` into the
  `{:write :read}` pair the wire layer asks for. That seam is the reason this
  is twenty lines of adapter rather than a third HTTP client.

  ## Why this lives beside the consumer and not in a repository of its own

  The adapter is small; what is *not* small is the policy it carries -- that
  redirects are never followed, that a body over the ceiling is refused rather
  than truncated, that a request which could not complete yields no status and
  no digest, and that the peer verdict is `grant.cloud/admit-peer`'s. Those are
  decisions about what this machine will act on, and they belong with the
  machine. The trigger for extracting a shared library is a *second* consumer,
  not this one.

  ## `admit-peer` is the only pin check

  `tls.client` can authenticate a peer against a pin itself. It is not asked
  to. It is handed a `:verify-chain` function that measures the leaf's
  SubjectPublicKeyInfo -- with `tls.cert/spki-sha256-hex`, which is the same
  digest of the same DER that `PublicKey.getEncoded` gives the platform path --
  and then asks `grant.cloud/admit-peer`, which is the same question the
  platform path's trust manager asks.

  One pin check, in the decision plane, on both paths. Two would eventually
  disagree, and the failure mode of a disagreement here is that a peer one
  layer refused another layer already accepted.

  ## What an `[:ok …]` from the peer check does NOT mean

  The same set as the platform path, because the platform path was measured
  and not assumed. On 2026-08-22 a certificate whose only subjectAltName is
  `IP:127.0.0.1`, reached as `localhost`, was **accepted** by
  `aiueos.provider.cloud` -- so `java.net.http` with a custom trust manager
  checks no server name either. Neither path validates a chain to a trust
  anchor, checks revocation, checks certificate transparency, checks name
  constraints, verifies the leaf's issuer signature, checks validity dates, or
  matches the certificate against the name it was reached by. The pin, bound to
  the host by policy, is the whole of the trust decision on both.

  ## What is still the platform's on this path

  The *protocol* is this workspace's: the record layer, the key schedule, the
  handshake state machine, certificate parsing and HTTP/1.1 framing. The
  *primitives* are not -- `tls.provider.jvm` is the JDK's AES-GCM, SHA-256,
  HMAC, X25519 and ECDSA, and the socket is `java.net.Socket`. Calling this
  path \"no JDK\" would be false; what left is `java.net.http`."
  (:require [kotoba.lang.text :as str]
            [grant.cloud :as cloud]
            [grant.json :as json]
            [kotoba.lang.http :as http]
            [kotoba.lang.http.wire :as wire]
            [tls.cert :as cert]
            [tls.client :as tls]
            [tls.result :as r]
            #?@(:clj [[tls.provider.jvm :as jvm]
                      [tls.transport.jvm :as tp]])))

(def default-user-agent "aiueos.provider.cloud-own/1")

(def errors
  "Faults this namespace adds to `aiueos.provider.cloud/errors`.

  `:transport-scheme-unsupported` is the honest edge of this path: it speaks
  https and nothing else, so a plaintext URL is refused by name rather than
  silently handed to the other transport."
  #{:transport-scheme-unsupported :response-unframable :request-unsendable})

(def incomplete-reasons
  "Wire and transport reasons that mean the exchange could not complete, as
  against a response that arrived and was refused.

  The distinction is the one `aiueos.cloud-live/unmeasured-faults` reads: a
  socket that timed out is UNMEASURED and a peer that framed its response two
  incompatible ways is REFUSED. Collapsing them would make a broken authority
  and an unreachable one report the same word."
  #{:tls-write-failed :tls-read-failed :transport-io :transport-stalled
    :transport-missing-read :transport-missing-write
    :empty-response :truncated-response-head :truncated-body
    :truncated-chunk-data :missing-last-chunk})

;; ── the peer verdict ───────────────────────────────────────────────────────

(defn verify-chain
  "A `tls.client` `:verify-chain` that asks `grant.cloud/admit-peer` and
  nothing else, recording the verdict in VERDICT.

  Records it on the refusals too. The handshake failure a refusal causes
  arrives at the caller as an alert that says nothing about pins, and a
  refusal that will not say which key it saw cannot be acted on -- rotation
  and attack look identical without it.

  RAW-PROVIDER is the byte-array-shaped provider, which is what `tls.cert`
  takes; `tls.client/handshake` adapts its own copy for the protocol layer."
  [raw-provider policy host verdict]
  (fn [leaf _entries]
    (let [measured (cert/spki-sha256-hex raw-provider leaf)]
      (if (cert/error? measured)
        (let [v (cloud/admit-peer policy {:spki-sha256 nil :host host})]
          (reset! verdict v)
          (r/error :bad_certificate :peer-unmeasured
                   {:tls/detail (cert/reason measured)}))
        (let [spki (second measured)
              v (cloud/admit-peer policy {:spki-sha256 spki :host host})]
          (reset! verdict v)
          (if (cloud/allowed? v)
            (r/ok {:tls/authenticated-by :grant.cloud/admit-peer
                   :tls/spki-sha256 spki
                   ;; In the value, not only in the docstring. A caller that
                   ;; logs the decision logs its limit with it.
                   :tls/not-checked #{:chain-to-trust-anchor :revocation
                                      :certificate-transparency :name-constraints
                                      :issuer-signature :validity :server-name}})
            (r/error :bad_certificate (:aiueos.cloud/reason v)
                     {:tls/spki-sha256 spki})))))))

;; ── the coupling ───────────────────────────────────────────────────────────

(defn tls-transport
  "Adapt a live TLS 1.3 connection to `kotoba.lang.http.wire`'s transport seam.

  This is the entire coupling between the two libraries. `read!` hands back one
  record at a time and signals close_notify as a value; the socket underneath
  it signals a timeout by *throwing*, so that one throw is converted here -- at
  the seam, so nothing above this line has to catch, and so a
  `SocketTimeoutException` leaves this namespace as a value like everything
  else."
  [conn]
  {:write (fn [octets]
            (let [res (tls/write! conn (vec octets))]
              (if (r/ok? res) [:ok (count octets)] [:error :tls-write-failed (r/err res)])))
   :read (fn []
           (try
             (let [res (tls/read! conn)]
               (cond
                 (r/error? res) [:error :tls-read-failed (r/err res)]
                 (:tls/closed (r/val res)) [:eof]
                 :else [:ok (:tls/content (r/val res))]))
             (catch #?(:clj Exception :cljs :default) e
               [:error :transport-io
                #?(:clj {:message (.getMessage ^Exception e)
                         :class (.getSimpleName (class e))}
                   :cljs {:message (.-message e)})])))})

;; ── translating one request ────────────────────────────────────────────────

(defn- header-present? [headers nm]
  (some #(= (str/lower (str %)) nm) (keys headers)))

(defn wire-request
  "A `kotoba.lang.http` request for `grant.cloud`'s REQUEST, or
  `{:error <keyword> :detail …}`.

  The body rules are `aiueos.provider.cloud`'s, restated against octets rather
  than a `BodyPublisher`: `:body-bytes` in OPTS is the caller's own bytes and
  goes out verbatim -- a block write must not be reshaped by a serialiser --
  and otherwise a plan's `:body` is data that `grant.json` turns into bytes.

  `Connection: close` because this path has no connection reuse: one request,
  one TLS session, one socket. Saying so is what lets the peer close instead of
  holding a connection nothing will use again."
  [request opts]
  (let [method (:method request)
        headers (:headers opts)]
    (cond
      (not (contains? #{:get :post :put} method))
      {:error :method-unsupported :detail method}

      :else
      (let [body (cond
                   (contains? opts :body-bytes) (wire/->octets (:body-bytes opts))
                   (contains? request :body)
                   (let [encoded (json/write-json (:body request))]
                     (if (json/failed? encoded)
                       {:error :body-unencodable :detail (json/error-of encoded)}
                       (wire/->octets encoded)))
                   :else nil)]
        (if (:error body)
          body
          (let [base (cond-> {"Connection" "close"
                              "User-Agent" default-user-agent}
                       (and (seq body) (not (header-present? headers "content-type")))
                       (assoc "Content-Type" "application/json"))]
            {:request (http/request method (:url request)
                                    (cond-> {:headers (merge base headers)}
                                      (seq body) (assoc :body body)))}))))))

(defn fault-of
  "The `aiueos.provider.cloud` fault for a wire-layer refusal.

  Three buckets, kept apart because three people fix them differently: a body
  over the ceiling is the ceiling doing its job, an exchange that could not
  finish is unmeasured, and a response this machine will not frame is a
  refusal that names the authority."
  [reason detail max-bytes]
  (cond
    (= :body-too-large reason)
    {:aiueos.provider.cloud/error :response-too-large :max-bytes max-bytes :detail detail}

    (contains? incomplete-reasons reason)
    {:aiueos.provider.cloud/error :request-failed
     :exception (name reason)
     :message (str "wire: " (name reason) " " (pr-str detail))}

    :else
    {:aiueos.provider.cloud/error :response-unframable
     :reason reason :detail detail}))

;; ── the socket half ────────────────────────────────────────────────────────
;;
;; One reader conditional around the lot rather than five. Everything above is
;; portable and is exercised by tests that never open a socket; below is
;; `java.net.Socket` and nothing else that is not already portable.

#?(:clj
   (do

     (defn- close-quietly! [f]
       (try (f) (catch Exception _ nil)))

     (defn fetch!
       "Perform one REQUEST over one fresh TLS 1.3 connection to HOST:PORT.

  Returns `{:status … :body-octets … :content-type …}` on a response that
  arrived, or an `{:aiueos.provider.cloud/error …}` fault. Never throws:
  `tls.client` and the wire layer both answer in values, and the one place a
  throw can still come from -- the socket -- is caught at the transport seam
  and at the connect.

  VERDICT is the atom `verify-chain` records `grant.cloud/admit-peer`'s answer
  in. The caller reads it to tell a refused peer from an unreachable one, which
  is a distinction the alert alone cannot make."
       [policy host port request opts verdict]
       (let [max-bytes (:max-bytes opts)
             built (wire-request request opts)]
         (if-let [error (:error built)]
           {:aiueos.provider.cloud/error error :detail (:detail built)}
           (let [raw (jvm/provider)
                 transport (try
                             {:ok (tp/socket-transport
                                   host port {:timeout-ms (:connect-timeout-ms opts)})}
                             (catch Exception e
                               {:error {:aiueos.provider.cloud/error :request-failed
                                        :exception (.getSimpleName (class e))
                                        :message (.getMessage e)}}))]
             (if-let [error (:error transport)]
               error
               (let [t (:ok transport)]
                 (try
                   ;; The connect deadline was the connect's. Reads get the
                   ;; request deadline, which for an inference call is minutes
                   ;; and for a block is seconds -- one number for both would
                   ;; have to be the larger, and a dead host would then hang
                   ;; for the length of the longest request this machine makes.
                   (when-let [socket (:socket t)]
                     (.setSoTimeout ^java.net.Socket socket (int (:request-timeout-ms opts))))
                   (let [hs (tls/handshake raw t {:server-name host
                                                  :verify-chain (verify-chain raw policy host verdict)})]
                     (if (r/error? hs)
                       (let [v @verdict]
                         (if (and v (not (cloud/allowed? v)))
                           ;; The handshake failed because the peer was refused.
                           ;; Report the refusal, not the alert it turned into.
                           (merge {:aiueos.provider.cloud/error (:aiueos.cloud/reason v)} v)
                           {:aiueos.provider.cloud/error :request-failed
                            :exception "tls-handshake"
                            :message (pr-str (r/err hs))}))
                       (let [conn (r/val hs)
                             res (wire/exchange (tls-transport conn) (:request built)
                                                {:limits {:max-body-bytes max-bytes}})]
                         (close-quietly! #(tls/close! conn))
                         (if (wire/error? res)
                           (fault-of (wire/reason res) (wire/detail res) max-bytes)
                           (let [resp (wire/value res)]
                             {:status (:http/status resp)
                              :body-octets (vec (:http/body resp))
                              :content-type (http/header (:http/headers resp) "content-type")})))))
                   (catch Exception e
                     {:aiueos.provider.cloud/error :request-failed
                      :exception (.getSimpleName (class e))
                      :message (.getMessage e)})
                   (finally (close-quietly! (:close t)))))))))))) 
