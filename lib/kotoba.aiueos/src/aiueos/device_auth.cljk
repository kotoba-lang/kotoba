(ns aiueos.device-auth
  "Pure OS account and device-claim ceremony.

  Passkeys, phone scans and wallet signatures are front doors into the same
  state machine. The verifier is an injected authority port: this namespace
  never trusts a browser supplied `verified=true`, never handles a private
  passkey or a private wallet key, and never copies either onto the node. A
  claim becomes a node plan only after both account authentication and proof by
  the device-owned key.

  What a verified assertion has to CARRY differs by method, and that is why the
  requirements are a table rather than one list of conditions. A passkey
  assertion has user presence, user verification, an RP id and a signature
  count. A SIWE assertion has none of those; it has a server-issued single-use
  nonce, domain/URI/chain binding, an expiry and a signature, and ERC-1271 adds
  the contract's current authority. Running the passkey conditions over a
  wallet proof would either refuse every wallet or, if they were relaxed to fit,
  admit one that proved nothing."
  (:require [kotoba.security.information-flow :as sec-info-flow]))

(def version 1)

(def supported-methods
  "The vocabulary. Matches `manifest/human-authentication-policy.edn`
  `:human-auth/approved-active-methods`, whose preferred family is the wallet
  one and whose authority (auth.kotoba.cloud) defaults to :siwe-erc1271.
  Before 2026-09-09 this set was #{:passkey :phone-scan}, so an account whose
  credential is a Base Account -- the authority's default and the first way in
  on its page -- could not complete a device claim at all."
  #{:passkey :phone-scan :siwe-erc191 :siwe-erc1271})

(def webauthn-methods #{:passkey :phone-scan})
(def wallet-methods #{:siwe-erc191 :siwe-erc1271})

(defn- flag
  "A boolean flag must be literally true. `truthy` would let a proof carrying
  the string \"no\" through, and an authority adapter that drifts to strings is
  exactly the kind of change that should be loud."
  [k] (fn [_ proof] (true? (get proof k))))

(defn- same-as-state [state-key proof-key]
  (fn [state proof] (= (get state state-key) (get proof proof-key))))

(def ^:private webauthn-ceremony
  [[:passkey/user-not-present  (flag :auth/user-present?)]
   [:passkey/user-not-verified (flag :auth/user-verified?)]
   [:passkey/rp-id-mismatch    (same-as-state :auth/rp-id :auth/rp-id)]
   [:passkey/origin-mismatch   (same-as-state :auth/origin :auth/origin)]])

(def ^:private siwe-ceremony
  ;; The wallet analogue of the passkey bindings. `:siwe/domain` is held to the
  ;; same string as the RP id and `:siwe/uri` to the same origin, but this is
  ;; NOT the phishing resistance WebAuthn gives -- the reasons are named
  ;; separately so a reader cannot mistake one for the other
  ;; (human-authentication-policy: do not call SIWE domain verification the
  ;; same phishing resistance as WebAuthn).
  ;;
  ;; A connected wallet is not an authenticated one
  ;; (:wallet/connection-is-authentication? false). That is enforced here by
  ;; requiring the signature, not by inspecting a "connected" flag: an address
  ;; and a chain id prove nothing on their own.
  [[:siwe/address-required             (fn [_ p] (string? (:siwe/address p)))]
   [:siwe/nonce-not-server-issued      (flag :siwe/nonce-server-issued?)]
   [:siwe/nonce-not-consumed-atomically (flag :siwe/nonce-consumed-atomically?)]
   [:siwe/domain-mismatch              (same-as-state :auth/rp-id :siwe/domain)]
   [:siwe/uri-mismatch                 (same-as-state :auth/origin :siwe/uri)]
   [:siwe/chain-not-admitted           (flag :siwe/chain-admitted?)]
   [:siwe/expired                      (flag :siwe/not-expired?)]
   [:siwe/signature-required           (flag :siwe/signature-verified?)]])

(def method-requirements
  "Method -> what its verified assertion must carry.

  A method that is in `supported-methods` but absent from this table is
  REFUSED, not admitted (`:method/requirements-undeclared`). Widening the
  vocabulary is then a change that fails closed by default: to actually open a
  method you have to say what it must prove."
  {:passkey (conj webauthn-ceremony
                  [:passkey/clone-signal (flag :passkey/sign-count-ok?)])

   :phone-scan (into webauthn-ceremony
                     [[:phone/passkey-required (flag :phone/passkey-verified?)]
                      [:phone/not-approved (flag :phone/approved?)]
                      [:phone/device-identity-required
                       (fn [_ p] (string? (:phone/device-did p)))]])

   :siwe-erc191 siwe-ceremony

   ;; ERC-1271 is a contract wallet: the signature is only meaningful while the
   ;; contract still says that key may sign for it. Unverifiable authority
   ;; fails closed (policy: contract-current-authorization-required,
   ;; verification-fails-closed).
   :siwe-erc1271 (conj siwe-ceremony
                       [:siwe/contract-authority-stale
                        (flag :siwe/contract-authority-current?)])})

(defn factory
  [{:keys [device-did model rp-id origin authority]}]
  {:aiueos.device-auth/version version
   :aiueos.device-auth/state :factory
   :device/did device-did
   :device/model model
   :auth/rp-id rp-id
   :auth/origin origin
   :auth/authority authority
   :auth/challenge nil
   :auth/challenge-expires-at-ms nil
   :auth/challenge-consumed? false
   :auth/method nil
   :account/principal-id nil
   :account/did nil
   :device/key-proved? false})

(defn issue-challenge
  "Issue one bounded, single-use challenge. `challenge` is public entropy, not
  an account credential or an enrollment bearer token."
  [state {:keys [challenge now-ms ttl-ms]}]
  (if (not= :factory (:aiueos.device-auth/state state))
    (assoc state :aiueos.device-auth/decision :deny
                 :aiueos.device-auth/reason :challenge/already-issued)
    (assoc state
           :aiueos.device-auth/state :challenge-issued
           :aiueos.device-auth/decision :continue
           :auth/challenge challenge
           :auth/challenge-expires-at-ms (+ now-ms ttl-ms)
           :auth/challenge-consumed? false)))

(defn- deny [state reason]
  (assoc state
         :aiueos.device-auth/decision :deny
         :aiueos.device-auth/reason reason))

(defn- proof-problem
  [state proof now-ms]
  (cond
    (not= :challenge-issued (:aiueos.device-auth/state state))
    :challenge/not-issued

    (:auth/challenge-consumed? state)
    :challenge/already-consumed

    (>= now-ms (:auth/challenge-expires-at-ms state))
    :challenge/expired

    (not= (:auth/challenge state) (:auth/challenge proof))
    :challenge/mismatch

    (not (contains? supported-methods (:auth/method proof)))
    :method/unsupported

    ;; In the vocabulary but with nothing declared about what it must prove.
    ;; Refused rather than admitted: adding a method should fail closed until
    ;; someone writes down what it has to carry.
    (not (contains? method-requirements (:auth/method proof)))
    :method/requirements-undeclared

    (not (:authority/verified? proof))
    :authority/not-verified

    :else
    (or (some (fn [[reason satisfied?]]
                (when-not (satisfied? state proof) reason))
              (method-requirements (:auth/method proof)))
        (cond
          (not (string? (:account/did proof))) :account/did-required
          (not (string? (:account/principal-id proof))) :account/principal-id-required
          :else nil))))

(defn authenticate-account
  "Accept the result of a cryptographic authority adapter.

  The adapter must bind the verified assertion to this challenge and account
  DID, and to whatever else the method requires -- RP and origin for a passkey,
  nonce, domain, URI, chain and expiry for a wallet. A phone scan is not a
  weaker password path: the phone must itself have completed a passkey ceremony
  before approving the device.

  The wallet identifiers are recorded beside the passkey ones, not merged with
  them: a wallet DID and a passkey DID are separate principals unless an
  existing owner links them, which is not something this ceremony can do
  (human-authentication-policy: no implicit principal linking)."
  [state proof now-ms]
  (if-let [problem (proof-problem state proof now-ms)]
    (deny state problem)
    (assoc state
           :aiueos.device-auth/state :account-authenticated
           :aiueos.device-auth/decision :continue
           :auth/method (:auth/method proof)
           :account/principal-id (:account/principal-id proof)
           :account/did (:account/did proof)
           :passkey/credential-id (:passkey/credential-id proof)
           :passkey/sign-count (:passkey/sign-count proof)
           :phone/device-did (:phone/device-did proof)
           :siwe/address (:siwe/address proof)
           :siwe/chain-id (:siwe/chain-id proof)
           :auth/authenticated-at-ms now-ms)))

(defn prove-device
  "Bind the authenticated account to the key owned by the device being added.
  `proof-valid?` is produced by the device-key verifier port."
  [state {:keys [device-did public-key proof-valid?]} now-ms]
  (cond
    (not= :account-authenticated (:aiueos.device-auth/state state))
    (deny state :account/not-authenticated)

    (not= (:device/did state) device-did)
    (deny state :device/did-mismatch)

    (not proof-valid?)
    (deny state :device/possession-proof-invalid)

    (not (string? public-key))
    (deny state :device/public-key-required)

    :else
    (assoc state
           :aiueos.device-auth/state :claimed
           :aiueos.device-auth/decision :grant
           :auth/challenge-consumed? true
           :device/key-proved? true
           :device/public-key public-key
           :device/claimed-at-ms now-ms)))

(defn claimed? [state]
  (and (= :grant (:aiueos.device-auth/decision state))
       (= :claimed (:aiueos.device-auth/state state))
       (:auth/challenge-consumed? state)
       (:device/key-proved? state)))

(defn node-plan
  "Project a completed claim into bounded intents. This does not report the
  native Kekkai adapter, SSD storage, or Murakumo workload as live before each
  has its own runtime proof."
  [state]
  (if-not (claimed? state)
    {:aiueos.device-auth/decision :deny
     :aiueos.device-auth/reason :device/not-claimed}
    {:aiueos.device-auth/decision :grant
     :account {:principal-id (:account/principal-id state)
               :did (:account/did state)
               :sync :ready-to-append
               :authority (:auth/authority state)
               :private-key-copied? false}
     :device {:did (:device/did state)
              :model (:device/model state)
              :public-key (:device/public-key state)
              :auth-method (:auth/method state)}
     :ui {:engine :kotoba-lang/browser
          :surface :aiueos/session
          :hosted-html-js :verification-adapter-only}
     :murakumo {:node-state :pending-runtime-proof
                :ready? false
                :required-proof [:authenticated-heartbeat
                                 :real-job-result
                                 :reboot-recovery]}
     :kekkai {:node-state :pending-native-adapter
              :transport :noise-ik
              :required-proof [:device-key-custody :netmap-signature
                               :peer-handshake]}
     :storage {:local-cache :pending-ssd-install
               :replication :opt-in-not-started
               :contracts [:kotobase-storage/cid-block
                           :kotobase-storage-pack/car-v2]
               :plaintext-cloud-copy? false}}))
