(ns storj.node.host.tls
  "Sockets — the mechanism under `storj.node.tls`.

  This is the first namespace in the repo that is *only* plumbing. It decides
  nothing: which certificates are acceptable is `storj.node.tls/verify-peer`'s
  answer, and everything here does is arrange for that answer to be asked at
  the right moment and to be acted on.

  ## The two runtimes do not ask at the same moment

  On the JVM the check runs **inside the handshake**, as an
  `X509ExtendedTrustManager`, which is where Go runs it too
  (`VerifyPeerCertificate`). A refused peer never completes a handshake.

  On Node there is no equivalent hook that fires without a certificate
  authority to check against, and Storj has none by construction. So the check
  runs on `secureConnect`/`secureConnection`, and a refused peer has completed
  a handshake before being disconnected — **before any application byte is
  written or read**, but after. That difference is real and is stated here
  rather than papered over: it means a refused peer on Node learns that this
  process exists and speaks TLS, which on the JVM it does not.

  ## What is missing

  DRPC is framed by `kotoba-lang/drpc` and is not wired in here; this hands
  back a connected, verified socket and stops.

  ## What has actually happened over one of these

  A check-in against a real Storj satellite (`storj-up`, satellite 1.158.2),
  accepted, with the satellite dialling back and being served — on both
  runtimes. That required `drpc-mux-header` in both directions and is the
  reason this namespace has `:preamble` and `:expect-preamble` at all. What is
  still untried against a real satellite is everything after introduction.
  Pieces do move over these sockets between this library's own node and its
  own uplink — see `storj.node.transfer` — but not to or from the network."
  (:require [storj.node.bytes :as b]
            [storj.node.host.keys :as hk]
            [storj.node.host.verify :as v]
            [storj.node.identity :as ident]
            [storj.node.tls :as tls]
            #?(:cljs ["node:tls" :as node-tls])
            #?(:cljs ["node:net" :as node-net]))
  #?(:clj (:import (java.io ByteArrayInputStream)
                   (java.net InetSocketAddress)
                   (java.security KeyStore)
                   (java.security.cert CertificateFactory X509Certificate)
                   (javax.net.ssl KeyManagerFactory SSLContext SSLSocket
                                  X509ExtendedTrustManager))))

(def protocol
  "`tls.VersionTLS12` as each runtime spells it."
  #?(:clj "TLSv1.2" :cljs "TLSv1.2"))

(defn- fail [msg data]
  (throw (ex-info (str "storj.node.host.tls: " msg) data)))

;; ── the identity, in the form each runtime's TLS stack wants ────────────────

#?(:clj
   (defn- x509 [der]
     (.generateCertificate (CertificateFactory/getInstance "X.509")
                           (ByteArrayInputStream. (b/->native (vec der))))))

#?(:clj
   (defn- key-managers
     "A KeyManagerFactory holding the identity, via an in-memory keystore.

      The keystore password is empty and never leaves this function: it exists
      because `KeyStore.setKeyEntry` requires one, not because anything is
      being protected."
     [{:keys [chain private-key]}]
     (let [pw (char-array 0)
           ks (doto (KeyStore/getInstance "PKCS12")
                (.load nil pw)
                (.setKeyEntry "identity" private-key pw
                              (into-array X509Certificate (map x509 chain))))]
       (.getKeyManagers (doto (KeyManagerFactory/getInstance
                               (KeyManagerFactory/getDefaultAlgorithm))
                          (.init ks pw))))))

#?(:clj
   (defn- trust-manager
     "An `X509ExtendedTrustManager` that answers with `verify-peer`.

      Both the client and server callbacks route to the same check, because
      Storj asks the same question in both directions — the only difference is
      whether a whitelist is supplied, and that is the caller's to decide."
     [verify-opts on-peer]
     (let [check (fn [^"[Ljava.security.cert.X509Certificate;" chain]
                   (let [ders   (mapv #(b/->ints (.getEncoded ^X509Certificate %)) chain)
                         result (tls/verify-peer ders verify-opts)]
                     (when on-peer (on-peer result))
                     (when-not (:ok? result)
                       (fail "peer certificate refused" {:reasons (:reasons result)}))))]
       (proxy [X509ExtendedTrustManager] []
         (getAcceptedIssuers [] (into-array X509Certificate []))
         (checkClientTrusted
           ([chain _auth-type] (check chain))
           ([chain _auth-type _socket-or-engine] (check chain)))
         (checkServerTrusted
           ([chain _auth-type] (check chain))
           ([chain _auth-type _socket-or-engine] (check chain)))))))

#?(:clj
   (defn ssl-context
     "An `SSLContext` carrying the identity and the peer rules."
     [identity verify-opts on-peer]
     (doto (SSLContext/getInstance protocol)
       (.init (key-managers identity)
              (into-array javax.net.ssl.TrustManager [(trust-manager verify-opts on-peer)])
              nil))))

(defn pem-of
  "An identity as the PEM text a TLS stack takes.

  Public and not reader-conditional even though only the Node path uses it
  internally: both halves are portable, and hiding a portable function inside
  a platform branch is how a second copy gets written for the other one."
  [identity]
  {:cert (ident/chain-pem (:chain identity))
   :key  (ident/private-key-pem (hk/export-private-key (:private-key identity)))})

#?(:cljs
   (defn- peer-chain
     "The peer's certificates as DER, leaf first.

      Node hands back a linked structure rather than a list, and the last
      certificate points at itself — following that link forever is the
      obvious loop and the wrong one."
     [socket]
     (loop [cert (.getPeerCertificate socket true), out []]
       (if (or (nil? cert) (nil? (.-raw cert)))
         out
         (let [out'   (conj out (b/->ints (.-raw cert)))
               issuer (.-issuerCertificate cert)]
           (if (or (nil? issuer) (identical? issuer cert))
             out'
             (recur issuer out')))))))

;; ── connecting ──────────────────────────────────────────────────────────────

(def drpc-mux-header
  "The eight bytes a Storj peer expects before the TLS ClientHello.

  Storj serves several protocols on one port and routes by a prefix, so
  `rpc.TCPConnector` wraps the raw connection in `drpcmigrate.NewHeaderConn`
  with `drpcmigrate.DRPCHeader` — which prepends this to the *first write*,
  and the first write is the ClientHello. A dialler that starts the handshake
  directly is talking to a listener that has not been told which protocol this
  is, and the connection closes without a TLS alert: on the JVM that surfaces
  as `SSLException: SSL peer shut down incorrectly` with nothing at all in the
  satellite's log, which reads like a certificate problem and is not one.

  Not sent by default. A plain TLS peer — including this project's own Go test
  harness, which is why nothing here needed it until a real satellite was on
  the other end — would see these bytes as a malformed record."
  [0x44 0x52 0x50 0x43 0x21 0x21 0x21 0x31]) ; "DRPC!!!1"

(defn connect
  "Dial `host:port` as a Storj peer and verify who answered.

  `identity` is `{:chain [leaf-der ca-der] :private-key <host key object>}`.
  `verify-opts` goes to `storj.node.tls/verify-peer` — pass
  `:expected-node-id` when the node being dialled is known, and
  `:whitelist (storj.node.tls/whitelist-certificates)` when it is a satellite.

  Returns `{:socket ... :peer {...}}` where `:peer` is the verification
  result, so the caller can read the node id it actually reached. On the JVM
  the handshake is forced before returning, so a refused peer surfaces here
  rather than on the first write.

  `:preamble` is bytes to put on the wire *before* the handshake — pass
  `drpc-mux-header` when the peer is a real Storj node or satellite. It cannot
  be sent through the TLS socket, so this layers TLS over a plain socket that
  has already been written to.

  On cljs this returns a promise, because a Node socket has no synchronous
  handshake."
  [{:keys [host port identity verify-opts timeout-ms preamble] :or {timeout-ms 20000}}]
  #?(:clj
     (let [seen (atom nil)
           ctx  (ssl-context identity (assoc verify-opts :verifier
                                             (or (:verifier verify-opts) v/verifier))
                             #(reset! seen %))
           ^SSLSocket sock
           (if (seq preamble)
             ;; the preamble has to precede the ClientHello, so the plain
             ;; socket is connected and written first and TLS is layered over
             ;; it — `createSocket` on an existing socket is the only form that
             ;; allows anything to have been sent already
             (let [raw (java.net.Socket.)]
               (.connect raw (InetSocketAddress. ^String host (int port)) (int timeout-ms))
               (.setSoTimeout raw (int timeout-ms))
               (doto (.getOutputStream raw)
                 (.write (byte-array (map unchecked-byte preamble)))
                 (.flush))
               (.createSocket (.getSocketFactory ctx) raw ^String host (int port) true))
             (doto ^SSLSocket (.createSocket (.getSocketFactory ctx))
               (.connect (InetSocketAddress. ^String host (int port)) (int timeout-ms))))]
       (.setEnabledProtocols sock (into-array String [protocol]))
       (.setSoTimeout sock (int timeout-ms))
       ;; force the handshake now: without this a refused peer is discovered by
       ;; whichever later read or write happens to trigger it
       (.startHandshake sock)
       {:socket sock :peer @seen})

     :cljs
     (js/Promise.
      (fn [resolve reject]
        (let [{:keys [cert key]} (pem-of identity)
              base {:cert cert :key key :rejectUnauthorized false
                    :minVersion protocol}
              opts (clj->js (if (seq preamble)
                              ;; `tls.connect` takes an existing socket, which
                              ;; is how the preamble gets out before the
                              ;; handshake starts on top of it
                              (assoc base :socket
                                     (doto (.connect node-net #js {:host host :port port})
                                       (.write (js/Buffer.from (clj->js (vec preamble))))))
                              (assoc base :host host :port port)))
              sock (.connect node-tls opts)]
          (.setTimeout sock timeout-ms)
          (.on sock "error" reject)
          (.on sock "timeout" #(do (.destroy sock) (reject (js/Error. "tls: timeout"))))
          (.on sock "secureConnect"
               (fn []
                 (let [result (tls/verify-peer
                               (peer-chain sock)
                               (assoc verify-opts :verifier
                                      (or (:verifier verify-opts) v/verifier)))]
                   (if (:ok? result)
                     (resolve {:socket sock :peer result})
                     (do (.destroy sock)
                         (reject (try (fail "peer certificate refused"
                                            {:reasons (:reasons result)})
                                      (catch :default e e)))))))))))))

(defn listen
  "Accept Storj peers on `port`, calling `on-connection` with
  `{:socket ... :peer {...}}` once a peer has been verified.

  A peer that fails verification is disconnected and `on-connection` is not
  called; `on-refused`, if given, is called with the result instead.

  `:expect-preamble` is bytes to read and discard before the handshake — pass
  `drpc-mux-header` when the peer is a real Storj satellite. A satellite dials
  a node back through the same `rpc.TCPConnector` it accepts connections on,
  so the ping arrives with the mux header in front of its ClientHello; a
  listener that hands those eight bytes to TLS sees a malformed record and the
  ping fails, which the satellite reports as the node being unreachable."
  [{:keys [port identity verify-opts on-connection on-refused expect-preamble]}]
  #?(:clj
     (let [ctx (ssl-context identity (assoc verify-opts :verifier
                                            (or (:verifier verify-opts) v/verifier))
                            nil)
           ;; with a preamble the raw bytes have to be read before TLS starts,
           ;; so the listening socket is plain and each accepted connection is
           ;; wrapped individually
           server (if (seq expect-preamble)
                    (java.net.ServerSocket. (int port))
                    (doto ^javax.net.ssl.SSLServerSocket
                          (.createServerSocket (.getServerSocketFactory ctx) (int port))
                      (.setNeedClientAuth true)
                      (.setEnabledProtocols (into-array String [protocol]))))]
       {:server server
        :port (.getLocalPort ^java.net.ServerSocket server)
        :accept (fn []
                  (let [^SSLSocket s
                        (if (seq expect-preamble)
                          (let [raw (.accept ^java.net.ServerSocket server)
                                in  (.getInputStream raw)
                                buf (byte-array (count expect-preamble))]
                            (loop [off 0]
                              (when (< off (alength buf))
                                (let [n (.read in buf off (- (alength buf) off))]
                                  (when (neg? n)
                                    (fail "peer closed before sending the preamble" {}))
                                  (recur (+ off n)))))
                            (when-not (= (vec expect-preamble) (b/->ints buf))
                              (fail "peer sent a different preamble"
                                    {:expected (vec expect-preamble) :got (b/->ints buf)}))
                            ;; the (Socket, String, int, boolean) overload —
                            ;; there is no (Socket, InetAddress, int, boolean)
                            (doto ^SSLSocket (.createSocket (.getSocketFactory ctx) raw
                                                            ^String (.getHostAddress
                                                                     (.getInetAddress raw))
                                                            (int (.getPort raw)) true)
                              (.setUseClientMode false)
                              (.setNeedClientAuth true)
                              (.setEnabledProtocols (into-array String [protocol]))))
                          (.accept ^javax.net.ssl.SSLServerSocket server))]
                    (try
                      (.startHandshake s)
                      ;; the trust manager already ran; re-reading the chain
                      ;; here is how the caller learns which node it was
                      (let [ders (mapv #(b/->ints (.getEncoded ^X509Certificate %))
                                       (.getPeerCertificates (.getSession s)))
                            result (tls/verify-peer ders
                                                    (assoc verify-opts :verifier
                                                           (or (:verifier verify-opts) v/verifier)))]
                        (on-connection {:socket s :peer result}))
                      (catch Exception e
                        (.close s)
                        (when on-refused (on-refused e))))))})

     :cljs
     (let [{:keys [cert key]} (pem-of identity)
           tls-opts (clj->js {:cert cert :key key
                              :requestCert true
                              :rejectUnauthorized false
                              :minVersion protocol})
           secured  (fn [sock]
                      (let [result (tls/verify-peer
                                    (peer-chain sock)
                                    (assoc verify-opts :verifier
                                           (or (:verifier verify-opts) v/verifier)))]
                        (if (:ok? result)
                          (on-connection {:socket sock :peer result})
                          (do (.destroy sock)
                              (when on-refused (on-refused result))))))
           server   (if (seq expect-preamble)
                      ;; a plain server, so the preamble can be read off the
                      ;; raw socket before TLS is layered over it
                      (.createServer
                       node-net
                       (fn [raw]
                         (let [want (vec expect-preamble)
                               n    (count want)
                               ;; `read(n)` rather than a `data` listener: a
                               ;; `data` listener puts the socket in flowing
                               ;; mode, and every byte of the ClientHello that
                               ;; arrives before TLS is layered on is delivered
                               ;; to a handler that is not looking for it and
                               ;; lost. Paused, the leftover simply stays in the
                               ;; socket's buffer and TLSSocket reads it.
                               try-read
                               (fn try-read []
                                 (when-let [head (.read raw n)]
                                   (.removeListener raw "readable" try-read)
                                   (let [got (b/->ints head)]
                                     (if-not (= want got)
                                       (do (.destroy raw)
                                           (when on-refused
                                             (on-refused {:ok? false
                                                          :reasons [{:reason :preamble-mismatch
                                                                     :expected want :got got}]})))
                                       (let [sock (new (.-TLSSocket node-tls) raw
                                                       (js/Object.assign
                                                        #js {} tls-opts #js {:isServer true}))]
                                         ;; `secure`, not `secureConnect`: a
                                         ;; TLSSocket built by hand in server
                                         ;; mode emits that one. Getting it
                                         ;; wrong is silent — the handshake
                                         ;; completes, the client is satisfied,
                                         ;; and nothing is ever served.
                                         (.on sock "secure" #(secured sock))
                                         (.on sock "error"
                                              (fn [e] (when on-refused (on-refused e)))))))))]
                           (.on raw "readable" try-read)
                           (.on raw "error" (fn [e] (when on-refused (on-refused e)))))))
                      (.createServer node-tls tls-opts secured))]
       (.listen server port)
       {:server server})))

(defn close! [{:keys [socket server]}]
  #?(:clj  (do (when socket (.close socket)) (when server (.close server)))
     :cljs (do (when socket (.destroy socket)) (when server (.close server)))))
