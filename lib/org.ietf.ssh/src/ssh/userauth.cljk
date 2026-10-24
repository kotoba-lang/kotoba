(ns ssh.userauth
  "The `publickey` user authentication exchange (RFC 4252 §7) over the encrypted
  transport: the service request/accept, the USERAUTH_REQUEST, and -- the part
  that must be byte-exact -- the blob the client signs and the server
  reconstructs to verify.

  The client proves it holds the private half of an authorized key by signing:

     string    session identifier            (H from the first kex)
     byte      SSH_MSG_USERAUTH_REQUEST (50)
     string    user name
     string    service name  (\"ssh-connection\")
     string    \"publickey\"
     boolean   TRUE
     string    public key algorithm name     (\"ecdsa-sha2-nistp256\")
     string    public key blob               (algo, curve, SEC1 point)

  and the server verifies that signature against the offered key -- which must be
  one of the provisioned authorized keys. Pure byte assembly reusing
  ssh.transport / ssh.kex; the crypto (sign on the client, verify on the server)
  is the caller's. The aiueos kernel is the server: it reconstructs this blob and
  verifies with its existing ECDSA-P256 verify object."
  (:require [ssh.transport :as t]
            [ssh.kex :as kex]))

(def msg-service-request 5)
(def msg-service-accept 6)
(def msg-userauth-request 50)
(def msg-userauth-failure 51)
(def msg-userauth-success 52)

(def service-userauth "ssh-userauth")
(def service-connection "ssh-connection")
(def method-publickey "publickey")
(def pubkey-algorithm kex/host-key-algorithm)   ; "ecdsa-sha2-nistp256"

(defn- s [str-val] (t/string-bytes (t/str->bytes str-val)))

(defn service-request-payload
  "byte(5) string(service)."
  [service]
  (into [msg-service-request] (s service)))

(defn service-accept-payload
  "byte(6) string(service)."
  [service]
  (into [msg-service-accept] (s service)))

(defn userauth-success-payload [] [msg-userauth-success])
(defn userauth-failure-payload
  "byte(51) name-list(methods that can continue) boolean(partial success)."
  [methods]
  (-> [msg-userauth-failure] (into (t/name-list methods)) (conj 0)))

(defn pubkey-blob
  "The ecdsa-sha2-nistp256 public key blob (same shape as the host key blob):
  string algo, string curve, string SEC1-point."
  [point]
  (kex/host-key-blob point))

(defn signed-data
  "The exact bytes the client signs and the server reconstructs (RFC 4252 §7).
  `session-id` is H from the first kex. `pk-blob` is `pubkey-blob`."
  [session-id username pk-blob]
  (-> []
      (into (t/string-bytes session-id))
      (conj msg-userauth-request)
      (into (s username))
      (into (s service-connection))
      (into (s method-publickey))
      (conj 1)                                   ; boolean TRUE: has signature
      (into (s pubkey-algorithm))
      (into (t/string-bytes pk-blob))))

(defn userauth-request-payload
  "The full USERAUTH_REQUEST with the signature appended. `sig-blob` is
  ssh.kex/signature-blob over `signed-data`."
  [username pk-blob sig-blob]
  (-> [msg-userauth-request]
      (into (s username))
      (into (s service-connection))
      (into (s method-publickey))
      (conj 1)
      (into (s pubkey-algorithm))
      (into (t/string-bytes pk-blob))
      (into (t/string-bytes sig-blob))))

(defn parse-userauth-request
  "Server side: pull the fields out of a USERAUTH_REQUEST payload. Returns a map
  with :username :pk-algorithm :pk-blob :sig-blob, or nil if it is not a
  well-formed publickey request with a signature."
  [payload]
  (when (= msg-userauth-request (first payload))
    (let [take-s (fn [b] (let [n (+ (* 16777216 (nth b 0)) (* 65536 (nth b 1))
                                    (* 256 (nth b 2)) (nth b 3))]
                           [(subvec b 4 (+ 4 n)) (subvec b (+ 4 n))]))
          b0 (vec (rest payload))
          [uname r1] (take-s b0)
          [svc r2] (take-s r1)
          [meth r3] (take-s r2)]
      (when (and (= service-connection (apply str (map char svc)))
                 (= method-publickey (apply str (map char meth)))
                 (= 1 (first r3)))
        (let [[algo r4] (take-s (vec (rest r3)))   ; drop the boolean
              [blob r5] (take-s r4)
              [sig _] (take-s r5)]
          {:username (apply str (map char uname))
           :pk-algorithm (apply str (map char algo))
           :pk-blob blob
           :sig-blob sig})))))
