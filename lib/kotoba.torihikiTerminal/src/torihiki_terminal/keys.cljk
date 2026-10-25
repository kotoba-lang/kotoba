(ns torihiki-terminal.keys
  "A session key held in the browser, and the signature that turns a form into
  a transaction.

  ## The browser computes the payload with the engine's own function

  `torihiki.auth/signing-payload` is `.cljc`, so this requires it and calls it.
  Writing the string here in JavaScript would be a second implementation of
  the one thing that must agree byte for byte with the node, and the failure
  mode when it drifts is a rejection that says `bad-signature` — which reads
  as a cryptography problem and is not one.

  That is also why `normalize-tx` runs on the node BEFORE it computes the
  payload: both sides must see `:order`, not `\"order\"`, or `(name ...)` gives
  them different strings.

  ## What this key is, and what it is not

  It is generated here, kept in `localStorage`, and never leaves the browser.
  It is not a wallet: there is no chain holding value that this key controls,
  and the account it claims holds devnet collateral that anybody can mint
  (see the node's `/head`). Clearing site data destroys it, and there is no
  recovery, because there is nothing worth recovering.

  Calling it a wallet would be the more impressive word for the same object
  and would invite somebody to treat it as one.

  ## The account id comes from the key

  It used to be claimed by first use, and this walked candidates until it
  found one nobody had taken. That is gone: a key may only claim the id
  `torihiki.address/derive` gives it, and the chain refuses anything else.

  The reason is not tidiness. First-use binding means whoever gets a
  transaction in first owns the id — under a single sequencer, whoever asks
  first; under consensus, whoever orders the block. A Byzantine leader claimed
  an account that way in engi's harness and the owner was locked out of it
  permanently."
  (:require [torihiki.address :as addr]
            [torihiki.auth :as auth]))

(def ^:const storage-key "torihiki.session-key.v1")

;; ── base64 ──────────────────────────────────────────────────────────────────

(defn- bytes->b64 [^js buf]
  (let [a (js/Uint8Array. buf)]
    (js/btoa (.apply js/String.fromCharCode nil a))))

(defn- b64->bytes [s]
  (let [bin (js/atob s)
        n (.-length bin)
        out (js/Uint8Array. n)]
    (dotimes [i n] (aset out i (.charCodeAt bin i)))
    out))

;; ── the key ─────────────────────────────────────────────────────────────────

(defn supported?
  "Ed25519 in WebCrypto. Chrome shipped it in 137, Safari and Firefox have it;
  older browsers do not, and the page has to say so rather than presenting a
  form whose submit button cannot work."
  []
  (boolean (and (exists? js/crypto) (.-subtle js/crypto))))

(defn- generate []
  (-> (js/crypto.subtle.generateKey #js {:name "Ed25519"} true #js ["sign" "verify"])
      (.then (fn [^js kp]
               (js/Promise.all
                #js [(js/crypto.subtle.exportKey "pkcs8" (.-privateKey kp))
                     (js/crypto.subtle.exportKey "raw" (.-publicKey kp))])))
      (.then (fn [[priv pub]]
               {:private (bytes->b64 priv) :public (bytes->b64 pub)}))))

(defn- import-signer [priv-b64]
  (js/crypto.subtle.importKey "pkcs8" (b64->bytes priv-b64)
                              #js {:name "Ed25519"} false #js ["sign"]))

(defn- stored []
  (when-let [raw (.getItem js/localStorage storage-key)]
    (try (js->clj (js/JSON.parse raw) :keywordize-keys true)
         (catch :default _ nil))))

(defn- store! [m]
  (.setItem js/localStorage storage-key (js/JSON.stringify (clj->js m)))
  m)

(defn load-or-create!
  "A promise of `{:private b64 :public b64 :account n-or-nil}`."
  []
  (if-let [k (stored)]
    (js/Promise.resolve k)
    (.then (generate) store!)))

(defn remember-account! [k account]
  (store! (assoc k :account account)))

;; ── seeding an account id ───────────────────────────────────────────────────

(defn account-for
  "The account id this key owns, from `torihiki.address` — the engine's own
  derivation, not a second one written here.

  There is nothing to walk any more. An id used to be claimed by first use, so
  this seeded a candidate from the key and stepped along until it found one
  nobody had taken; now a key may only claim the id derived from it, and the
  chain refuses anything else with `:not-your-account`. Deriving it in the
  browser and having the chain derive something different would be a user who
  cannot sign for the account they are shown."
  [pub-b64]
  (addr/derive pub-b64))

;; ── signing ─────────────────────────────────────────────────────────────────

(defn sign-tx
  "A promise of the envelope the node's `/tx` expects.

  `chain-id`, `account`, `nonce` and every field of `tx` are covered, because
  `torihiki.auth/signing-payload` covers them — this does not choose what is
  signed, it only signs it."
  [k chain-id account nonce tx]
  (let [payload (auth/signing-payload chain-id account nonce tx)]
    (-> (import-signer (:private k))
        (.then (fn [sk]
                 (js/crypto.subtle.sign #js {:name "Ed25519"} sk
                                        (.encode (js/TextEncoder.) payload))))
        (.then (fn [sig]
                 {:tx tx :account account :nonce nonce
                  :pubkey (:public k) :sig (bytes->b64 sig)})))))
