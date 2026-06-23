(ns kotoba.cacao
  "Bridge a membership grant (access-DAG datom, kotoba.office) into a CACAO that
   kotoba's server already verifies (kotoba-auth DelegationChain::verify /
   datomic_transact). See docs/gftd-office/b-webauthn-cacao-adapter.md and
   d-did-identity-layer.md.

   PURE (.cljc, bb-testable): grant -> CacaoPayload map, capability/resource mapping,
   and a byte-exact reproduction of kotoba-auth cacao.rs `siwe_message()` (the string
   that gets Ed25519-signed).

   CLJS: the wasm node now exposes native CACAO minting — `KotobaNode.mintCacao`
   (kotoba-wasm WriteCrypto::mint_cacao) reuses kotoba-auth's exact Cacao type +
   did:key + siwe_message, so the bytes verify byte-identically under the server's
   DelegationChain::verify (proven by cargo test -p kotoba-wasm). Prefer `mint-cacao!`.
   `sign-cacao->b64` (INJECTED Ed25519 + dag-cbor, e.g. @noble/ed25519 + cbor-x)
   remains as a portable fallback that doesn't require the wasm identity.

   Capability tokens are the DATOMIC ones (kotoba-auth CacaoPayload::OP_*):
   datom:read / datom:transact / tx:create — NOT the kotoba-graph quad:* tokens."
  (:require [clojure.string :as str]))

;; ===========================================================================
;; grant capability -> CACAO operation token + resources
;; ===========================================================================

(def cap->op
  {:cap/read     "datom:read"
   :cap/transact "datom:transact"
   :cap/admin    "tx:create"})

(defn grant->resources
  "[:kotoba://op/{op} :kotoba://graph/{scope}] for a grant {:cap :scope}."
  [{:keys [cap scope]}]
  [(str "kotoba://op/" (cap->op cap))
   (str "kotoba://graph/" scope)])

;; ===========================================================================
;; CacaoPayload (clojure-side keys; wire renames iat/exp applied at CBOR time)
;; ===========================================================================

(defn grant->payload
  "Build a CacaoPayload map from a grant + opts.
   opts: :iss  (REQUIRED — signing DID = the authority; for an account writing its
                own graph this is the account/owner DID; for member→server use a
                depth-2 chain, a follow-up)
         :aud  (REQUIRED — server/operator DID or URI)
         :nonce :issued-at :expiry  (REQUIRED for replay-safety / temporal scope)
         :domain (default \"gftd.office\") :version (default \"1\") :statement."
  [grant {:keys [iss aud nonce issued-at expiry domain version statement]
          :or {domain "gftd.office" version "1"}}]
  {:iss        iss
   :aud        aud
   :issued-at  issued-at
   :expiry     expiry
   :nonce      nonce
   :domain     domain
   :statement  statement
   :version    version
   :resources  (grant->resources grant)})

;; ===========================================================================
;; siwe_message — byte-exact mirror of kotoba-auth cacao.rs::siwe_message()
;; ===========================================================================

(defn- iss-address [iss] (last (str/split iss #":")))

(defn- iss-chain-id [iss]
  (if (str/starts-with? iss "did:key:")
    "1"
    (let [segs (str/split iss #":")]
      (if (>= (count segs) 2) (nth segs (- (count segs) 2)) "1"))))

(defn siwe-message
  "Reproduce the exact plaintext kotoba-auth signs. Lines joined with '\\n'."
  [{:keys [iss aud issued-at expiry nonce domain statement version resources]}]
  (->> (concat
        [(str domain " wants you to sign in with your Ethereum account:")
         (iss-address iss)
         ""]
        (when statement [statement ""])
        [(str "URI: " aud)
         (str "Version: " version)
         (str "Chain ID: " (iss-chain-id iss))
         (str "Nonce: " nonce)
         (str "Issued At: " issued-at)]
        (when expiry [(str "Expiration Time: " expiry)])
        (when (seq resources)
          (cons "Resources:" (map #(str "- " %) resources))))
       (str/join "\n")))

;; ===========================================================================
;; wire object (CBOR-ready): clojure payload -> {h,p,s} with iat/exp renames
;; ===========================================================================

(defn ->wire
  "Assemble the {h,p,s} object kotoba-auth deserializes (ciborium). `sig-b64` is the
   base64url-no-pad Ed25519 signature over (siwe-message payload); pass nil to stage."
  [payload sig-b64]
  {:h {:t "eip4361"}
   :p (cond-> {:iss       (:iss payload)
               :aud       (:aud payload)
               :iat       (:issued-at payload)
               :nonce     (:nonce payload)
               :domain    (:domain payload)
               :version   (:version payload)
               :resources (:resources payload)}
        (:expiry payload)    (assoc :exp (:expiry payload))
        (:statement payload) (assoc :statement (:statement payload)))
   :s {:t "EdDSA" :s (or sig-b64 "")}})

;; ===========================================================================
;; CLJS-only: sign + CBOR-encode -> cacao_b64
;; ===========================================================================

#?(:cljs
   (do
     (def write-caps ["datom:transact" "tx:create"])  ; server verifies BOTH for a write
     (def read-caps  ["datom:read"])

     (defn mint-cacao!
       "Mint a server-verifiable CACAO via the wasm node (KotobaNode.mintCacao).
        Requires the node identity (useIdentity/generateIdentity).
          caps:  op tokens, e.g. write-caps / read-caps
          scope: graph CID (write) or \"private/{account-did}\" (private read)
          opts:  {:aud :nonce :issued-at :expiry}.
        Returns the base64 cacao_b64."
       [^js node scope caps {:keys [aud nonce issued-at expiry]}]
       (.mintCacao node aud scope (clj->js caps) nonce issued-at expiry))

     (defn mint-delegated!
       "Build a depth-2 chain as the delegate (member) for team sharing.
        root-grant-b64: a CACAO the OWNER minted via
          (mint-cacao! owner-node org-graph write-caps {:aud member-did …}).
        scope: the OWNER's graph CID; caps ⊆ root's. opts {:aud(server) :nonce …}.
        Returns the base64 [root,leaf] chain for cacao_b64."
       [^js node root-grant-b64 scope caps {:keys [aud nonce issued-at expiry]}]
       (.mintDelegated node root-grant-b64 aud scope (clj->js caps) nonce issued-at expiry))

     (defn sign-cacao->b64
       "grant + opts -> base64(dag-cbor(Cacao)) for the datomic.transact cacao_b64 field.
        Injected fns (kotoba-auth has no wasm CACAO export yet):
          :sign-fn  (Uint8Array msg) -> Uint8Array(64)   Ed25519 over UTF-8 siwe bytes
          :sig->b64url (Uint8Array)  -> string           base64url-no-pad
          :cbor-encode (js-obj)      -> Uint8Array        dag-cbor
          :b64-encode  (Uint8Array)  -> string           base64-standard
        (e.g. @noble/ed25519 + cbor-x + js btoa-helpers, or a future wasm-bindgen API)."
       [grant {:keys [sign-fn sig->b64url cbor-encode b64-encode] :as opts}]
       (let [payload (grant->payload grant opts)
             msg     (siwe-message payload)
             bytes   (.encode (js/TextEncoder.) msg)
             sig     (sign-fn bytes)
             sig-b64 (sig->b64url sig)
             wire    (clj->js (->wire payload sig-b64))]
         (b64-encode (cbor-encode wire))))

     (def ^:export mintCacao      mint-cacao!)
     (def ^:export mintDelegated  mint-delegated!)
     (def ^:export grantToCacaoB64 sign-cacao->b64)))
