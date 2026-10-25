(ns provider.tls-channel
  "Bounded TLS netlayer channel for host runtimes such as CapTP.

  The channel is an opaque live capability. It frames bytes with a fixed
  unsigned 32-bit length and exposes only bounded write/read/exchange
  operations; no socket or stream crosses the boundary."
  (:require [kotoba.lang.text :as str])
  (:import [java.io DataInputStream DataOutputStream EOFException]
           [java.net IDN InetAddress InetSocketAddress Socket]
           [java.security MessageDigest]
           [java.security.cert X509Certificate]
           [javax.net.ssl SNIHostName SSLContext SSLParameters SSLSocket]))

(def default-max-frame-bytes (* 1024 1024))

(defprotocol ^:private TlsChannelValue
  (-channel-info [channel])
  (-channel-lock [channel])
  (-channel-input [channel])
  (-channel-output [channel])
  (-channel-socket [channel])
  (-channel-counter [channel]))

(deftype ^:private TlsChannel [info lock input output socket counter]
  TlsChannelValue
  (-channel-info [_] info)
  (-channel-lock [_] lock)
  (-channel-input [_] input)
  (-channel-output [_] output)
  (-channel-socket [_] socket)
  (-channel-counter [_] counter))

(defn tls-channel? [x]
  (satisfies? TlsChannelValue x))

(defn description
  "Return inert authenticated transport metadata, never socket authority."
  [channel]
  (when (tls-channel? channel) (-channel-info channel)))

(defn- hex [^bytes bytes]
  (apply str (map #(format "%02x" (bit-and 0xff %)) bytes)))

(defn- sha256 [^bytes bytes]
  (.digest (MessageDigest/getInstance "SHA-256") bytes))

(defn- ip-literal? [host]
  (or (str/includes? host ":")
      (boolean (re-matches #"[0-9]+(?:\.[0-9]+){3}" host))))

(defn- canonical-host [host]
  (try
    (when (and (string? host) (seq host) (= host (str/trim host))
               (not (str/includes? host "\u0000")))
      (let [unbracketed (if (and (str/starts-with? host "[")
                                 (str/ends-with? host "]"))
                          (subs host 1 (dec (count host)))
                          host)]
        (if (ip-literal? unbracketed)
          (str/lower (.getHostAddress (InetAddress/getByName unbracketed)))
          (let [without-root-dot (if (str/ends-with? unbracketed ".")
                                   (subs unbracketed 0 (dec (count unbracketed)))
                                   unbracketed)
                ascii (IDN/toASCII without-root-dot IDN/USE_STD3_ASCII_RULES)]
            (when (seq ascii) (str/lower ascii))))))
    (catch Exception _ nil)))

(defn- endpoint [host port]
  (str (if (str/includes? host ":") (str "[" host "]") host) ":" port))

(defn- peer-certificate [^SSLSocket socket]
  ^X509Certificate (first (.getPeerCertificates (.getSession socket))))

(defn- frame-error [max-frame bytes]
  (cond
    (not (= (class bytes) (Class/forName "[B")))
    {:problem :tls-channel/bytes-required}
    (zero? (alength ^bytes bytes))
    {:problem :tls-channel/empty-frame}
    (> (alength ^bytes bytes) max-frame)
    {:problem :tls-channel/frame-too-large
     :max max-frame :actual (alength ^bytes bytes)}))

(defn open-client!
  "Open a verified TLS client channel to one exact allowlisted endpoint.

  SSL-CONTEXT is an injected trust/client-identity capability. DNS resolution
  is injectable for tests and pinned deployments. Endpoint identity uses the
  HTTPS algorithm and SNI; an optional SHA-256 certificate pin is checked
  after the TLS handshake."
  [{:keys [ssl-context host port endpoint-allowlist resolved-address-allowlist
           connect-timeout-ms read-timeout-ms max-frame-bytes
           peer-certificate-sha256 peer-certificate-sha256-set
           resolve-addresses]
    :or {connect-timeout-ms 5000
         read-timeout-ms 5000
         max-frame-bytes default-max-frame-bytes
         resolve-addresses #(seq (InetAddress/getAllByName %))}}]
  (let [canonical (canonical-host host)
        endpoint* (when canonical (endpoint canonical port))]
    (when-not (and (instance? SSLContext ssl-context)
                   canonical
                   (int? port) (<= 1 port 65535)
                   (set? endpoint-allowlist)
                   (contains? endpoint-allowlist endpoint*)
                   (or (nil? resolved-address-allowlist)
                       (set? resolved-address-allowlist))
                   (int? connect-timeout-ms) (pos? connect-timeout-ms)
                   (int? read-timeout-ms) (pos? read-timeout-ms)
                   (int? max-frame-bytes) (pos? max-frame-bytes)
                   (not (and peer-certificate-sha256
                             peer-certificate-sha256-set))
                   (or (nil? peer-certificate-sha256)
                       (boolean (re-matches #"[0-9a-f]{64}"
                                            peer-certificate-sha256)))
                   (or (nil? peer-certificate-sha256-set)
                       (and (set? peer-certificate-sha256-set)
                            (seq peer-certificate-sha256-set)
                            (every? #(boolean (re-matches #"[0-9a-f]{64}" %))
                                    peer-certificate-sha256-set)))
                   (ifn? resolve-addresses))
      (throw (ex-info "TLS channel options are not admitted"
                      {:problem :tls-channel/options-invalid})))
    (let [addresses (try (vec (resolve-addresses canonical))
                         (catch Exception _ []))
          address (first
                   (filter (fn [^InetAddress candidate]
                             (or (nil? resolved-address-allowlist)
                                 (contains? resolved-address-allowlist
                                            (.getHostAddress candidate))))
                           addresses))]
      (when-not address
        (throw (ex-info "TLS endpoint resolved to no admitted address"
                        {:problem :tls-channel/address-denied})))
      (let [plain (Socket.)]
        (try
          (.connect plain (InetSocketAddress. ^InetAddress address port)
                    connect-timeout-ms)
          (.setSoTimeout plain read-timeout-ms)
          (let [^SSLSocket tls (.createSocket (.getSocketFactory ssl-context)
                                               plain canonical port true)
                params (doto (SSLParameters.)
                         (.setEndpointIdentificationAlgorithm "HTTPS"))]
            (when-not (ip-literal? canonical)
              (.setServerNames params [(SNIHostName. canonical)]))
            (.setSSLParameters tls params)
            (.setSoTimeout tls read-timeout-ms)
            (.startHandshake tls)
            (let [certificate (peer-certificate tls)
                  certificate-digest (hex (sha256 (.getEncoded certificate)))]
              (when (and (or peer-certificate-sha256
                             peer-certificate-sha256-set)
                         (not (or (= peer-certificate-sha256
                                     certificate-digest)
                                  (contains? peer-certificate-sha256-set
                                             certificate-digest))))
                (throw (ex-info "TLS peer certificate pin mismatch"
                                {:problem :tls-channel/peer-pin-mismatch})))
              (TlsChannel.
               {:tls/encrypted? true
                :tls/endpoint endpoint*
                :tls/resolved-address (.getHostAddress ^InetAddress address)
                :tls/protocol (.getProtocol (.getSession tls))
                :tls/cipher-suite (.getCipherSuite (.getSession tls))
                :tls/peer-certificate-sha256 certificate-digest
                :tls/peer-pin-profile
                (cond peer-certificate-sha256 :single
                      peer-certificate-sha256-set :rotation-set
                      :else :trust-store)
                :tls/max-frame-bytes max-frame-bytes}
               (Object.)
               (DataInputStream. (.getInputStream tls))
               (DataOutputStream. (.getOutputStream tls))
               tls
               (atom 0))))
          (catch Exception error
            (try (.close plain) (catch Exception _ nil))
            (if (ex-data error)
              (throw error)
              (throw (ex-info "TLS channel could not be established"
                              {:problem :tls-channel/connect-failed}
                              error)))))))))

(defn- write-frame-locked! [channel ^bytes bytes]
  (let [max-frame (:tls/max-frame-bytes (-channel-info channel))]
    (when-let [error (frame-error max-frame bytes)]
      (throw (ex-info "TLS frame denied" error)))
    (let [^DataOutputStream output (-channel-output channel)
          counter (swap! (-channel-counter channel) inc)]
      (.writeInt output (alength bytes))
      (.write output bytes)
      (.flush output)
      {:netlayer/accepted? true
       :netlayer/message-id
       (str "tls:" counter ":" (subs (hex (sha256 bytes)) 0 16))})))

(defn write-frame!
  "Write one bounded length-prefixed frame over the authenticated TLS stream."
  [channel bytes]
  (when-not (tls-channel? channel)
    (throw (ex-info "live TLS channel required"
                    {:problem :tls-channel/required})))
  (locking (-channel-lock channel)
    (write-frame-locked! channel bytes)))

(defn- read-frame-locked! [channel]
  (let [^DataInputStream input (-channel-input channel)
        max-frame (:tls/max-frame-bytes (-channel-info channel))
        length (try (.readInt input)
                    (catch EOFException _
                      (throw (ex-info "TLS peer closed before a frame"
                                      {:problem :tls-channel/eof}))))]
    (when-not (<= 1 length max-frame)
      (throw (ex-info "TLS peer supplied an invalid frame length"
                      {:problem :tls-channel/frame-length-invalid
                       :max max-frame :actual length})))
    (let [bytes (byte-array length)]
      (.readFully input bytes)
      bytes)))

(defn read-frame!
  "Read one bounded frame. This is blocking only up to the socket timeout."
  [channel]
  (when-not (tls-channel? channel)
    (throw (ex-info "live TLS channel required"
                    {:problem :tls-channel/required})))
  (locking (-channel-lock channel)
    (read-frame-locked! channel)))

(defn exchange-frame!
  "Write one frame and read one response under the same channel lock.

  The one-element vector matches the bounded CapTP runtime exchange contract."
  [channel bytes]
  (when-not (tls-channel? channel)
    (throw (ex-info "live TLS channel required"
                    {:problem :tls-channel/required})))
  (locking (-channel-lock channel)
    (write-frame-locked! channel bytes)
    [(read-frame-locked! channel)]))

(defn close! [channel]
  (when (tls-channel? channel)
    (locking (-channel-lock channel)
      (.close ^SSLSocket (-channel-socket channel))))
  nil)
