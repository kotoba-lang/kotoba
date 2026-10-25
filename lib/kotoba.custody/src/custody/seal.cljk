;; custody.seal — the bytes half of threshold custody: real randomness, a
;; real digest, and each share wrapped to its custodian's X25519 public key.
;;
;; ClojureScript, not .cljc, and every function returns a Promise, for the
;; same reason `envelope.seal` is: Web Crypto has no synchronous API. The
;; pure half (`custody.shamir`, `custody.model`) deliberately holds neither
;; a CSPRNG nor a hash; this namespace is where that decision gets paid for
;; exactly once, next to the runtime that actually has both.
;;
;; The wrap is `envelope.seal/wrap-bytes` — the same X25519 + HKDF-SHA256 +
;; AES-256-GCM construction that wraps an envelope's content key, given a
;; different AAD (`custody.model/share-aad`). A second X25519 in this
;; workspace would be a second one to get wrong.
;;
;;   (-> (seal/split-and-wrap! {:deal-id "deal:…" :secret-id "…"
;;                              :secret key-bytes :threshold 3
;;                              :custodians [{:custodian/id … :custodian/domain …
;;                                            :custodian/pub …} …]})
;;       (.then (fn [{:keys [deal]}] …)))
(ns custody.seal
  (:require [custody.model :as m]
            [custody.shamir :as shamir]
            [envelope.seal :as env-seal]))

;; --------------------------------------------------------------- primitives

(defn random-bytes
  "The CSPRNG `custody.shamir/split` refuses to choose on a caller's behalf.
  Synchronous: `getRandomValues` is, everywhere Web Crypto exists."
  [n]
  (vec (array-seq (js/crypto.getRandomValues (js/Uint8Array. n)))))

(defn sha256-b64url
  "-> Promise<unpadded base64url SHA-256>. This is what `:deal/secret-digest`
  holds, and `:deal/digest-alg :sha-256` names."
  [bytes]
  (-> (js/crypto.subtle.digest "SHA-256" (js/Uint8Array.from (clj->js (vec bytes))))
      (.then (fn [buf] (env-seal/b64url (js/Uint8Array. buf))))))

;; -------------------------------------------------------------------- split

(defn split-and-wrap!
  "Split `secret` into one share per custodian, wrap each share to that
  custodian's X25519 public key, and return the deal.
  -> Promise<{:deal …}>.

  **Refuses by default to produce a deal whose threshold is decorative.**
  `custody.model/independence` decides: if one domain holds enough shares to
  reach the threshold alone, this rejects with the report attached rather
  than handing back a 3-of-5 that is really a 1-of-1. That check is the
  reason this library exists, so it is on by default; `:require-sound? false`
  exists for tests and for a deliberate single-domain deal (a tenant that
  wants nobody but itself to be able to recover), and a caller that passes
  it is stating that on the record.

  The secret is never returned and never stored. Each custodian's entry
  carries only the wrap; the share itself exists in plaintext only inside
  this call."
  [{:keys [deal-id secret-id secret threshold custodians epoch require-sound?]
    :or {epoch 0 require-sound? true}}]
  (-> (sha256-b64url secret)
      (.then
       (fn [digest]
         (let [shares (shamir/split secret threshold (count custodians) random-bytes)
               d (m/deal deal-id {:secret-id secret-id
                                  :threshold threshold
                                  :total (count custodians)
                                  :custodians custodians
                                  :epoch epoch
                                  :secret-digest digest})
               ind (m/independence d)]
           (when-let [e (m/deal-error d)]
             (throw (ex-info "invalid custody deal" {:custody/error e})))
           (when (and require-sound? (not (:independence/sound? ind)))
             (throw (ex-info "refusing to wrap a threshold one party can reach alone"
                             {:custody/error :independence-not-sound
                              :custody/independence ind})))
           (-> (js/Promise.all
                (clj->js
                 (map (fn [c]
                        (let [x (:custodian/share-x c)
                              share (first (filter #(= x (:share/x %)) shares))]
                          (-> (env-seal/wrap-bytes
                               (js/Uint8Array.from (clj->js (:share/y share)))
                               (:custodian/pub c)
                               (m/share-aad d (:custodian/id c) x))
                              (.then (fn [w] (merge c w))))))
                      (:deal/custodians d))))
               (.then (fn [wrapped]
                        {:deal (assoc d :deal/custodians (vec wrapped))
                         :independence ind}))))))))

;; ------------------------------------------------------------------ release

(defn unwrap-share!
  "One custodian recovering its own share with its own X25519 private key.
  -> Promise<{:share/x … :share/y […]}>.

  Rejects if the wrap belongs to another custodian, another coordinate,
  another epoch, or another deal — none of which is checked here, all of
  which fail because `share-aad` bound them and AES-GCM will not open under
  a different AAD."
  [d {:keys [:custodian/id :custodian/share-x] :as custodian} priv]
  (-> (env-seal/unwrap-bytes custodian priv (m/share-aad d id share-x))
      (.then (fn [y] {:share/x share-x
                      :share/y (vec (array-seq y))}))))

(defn release!
  "Unwrap and package one custodian's share as a release record."
  [d custodian priv {:keys [at reason]}]
  (-> (unwrap-share! d custodian priv)
      (.then (fn [share] (m/release d custodian share {:at at :reason reason})))))

;; --------------------------------------------------------------------- open

(defn open!
  "Reconstruct the secret from `releases`, verified against the deal's
  digest. -> Promise<{:custody/opened? …}>.

  Same contract as `custody.model/open`, with a real SHA-256 instead of an
  injected one. A structurally invalid quorum resolves (it does not reject)
  with `:custody/reason` — a custodian handing back a stale share in good
  faith is an expected condition, and the caller has to be able to say which
  one it was."
  [d releases]
  (if-let [e (m/quorum-error d releases)]
    (js/Promise.resolve {:custody/opened? false :custody/reason e})
    (let [secret (shamir/combine (mapv :release/share releases))]
      (-> (sha256-b64url secret)
          (.then (fn [digest] (m/verify-secret d secret digest)))))))
