;; kotoba.signal.group — group ratchet via the "sender-keys" pattern, for
;; ClojureScript. CLJS sibling of kotoba.signal.group (JVM) — same 7-function
;; shape, built on kotoba.signal.ratchet's already-ported kdf-chain-key/
;; ratchet-encrypt/ratchet-decrypt, so this file is mostly glue: the only new
;; primitive is Ed25519 sign/verify (via @noble/curves, same import pattern
;; kotoba.signal.x25519 already uses).
;;
;; DIFFERENCE FROM THE JVM VERSION: `:sig-pub` here is the raw 32-byte
;; Ed25519 public key, not a `did:key` string — this package doesn't depend
;; on a did:key encoder and doesn't need one for what the signature actually
;; proves: that a later distribution-message (e.g. re-sent to a newly added
;; member) is self-consistent with the SAME sender-key identity as an
;; earlier one, not that it's bound to any particular account DID. A
;; distribution travels over an already-DID-authenticated 1:1 channel (see
;; the caller, e.g. app-aozora's yoro-ui.interop.signal-group), so binding
;; to the account identity is the CALLER's job, not this library's.
;;
;; Every function that touches the chain KDF (sender-advance, member-derive)
;; is Promise-based, because kotoba.signal.ratchet/kdf-chain-key is (Web
;; Crypto has no synchronous API). create-sender-key/distribution-message/
;; verify-distribution are plain sync values (Ed25519 sign/verify + random
;; bytes are all synchronous via @noble/curves).
;;
;; SCOPE NOTE (matches the JVM version): no group membership management or
;; key revocation here — see the ns docstring on group.clj for the reasoning.
;; app-aozora's caller layer is where membership-change-triggered rotation
;; lives, because it needs to know who the current members ARE, which this
;; library deliberately doesn't track.
;;
;;   (require '[kotoba.signal.group :as group])
;;   (def sender-key (group/create-sender-key))
;;   (def dist (group/distribution-message sender-key 0))   ; send to each member via 1:1 Signal
;;   (group/verify-distribution dist)                       ;=> true (member checks first)
;;   (-> (group/sender-advance sender-key)
;;       (.then (fn [[sender-key' mk]] (group/encrypt-segment mk (utf8 "segment bytes")))))
;;   (-> (group/member-derive (:chain-key dist))
;;       (.then (fn [[member-ck' mk]] (group/decrypt-segment mk envelope))))
(ns kotoba.signal.group
  (:require [kotoba.signal.ratchet :as ratchet]
            ["@noble/curves/ed25519.js" :refer [ed25519]]))

(defn- rand-bytes [n] (doto (js/Uint8Array. n) js/crypto.getRandomValues))

(defn- concat-bytes [a b]
  (let [out (js/Uint8Array. (+ (.-length a) (.-length b)))]
    (.set out a 0) (.set out b (.-length a))
    out))

(defn create-sender-key
  "New group, as its sender: {:chain-key Uint8Array(32) :sig-seed
   Uint8Array(32) :sig-pub Uint8Array(32)}. :sig-seed is an Ed25519 identity
   used ONLY to sign distribution messages (see ns docstring for why it's
   not a did:key here)."
  []
  (let [chain-key (rand-bytes 32)
        sig-seed (rand-bytes 32)]
    {:chain-key chain-key :sig-seed sig-seed :sig-pub (.getPublicKey ed25519 sig-seed)}))

(defn- distribution-payload [chain-key iteration]
  (concat-bytes chain-key (.encode (js/TextEncoder.) (str iteration))))

(defn distribution-message
  "What the sender sends to each member, over a pairwise 1:1-encrypted
   channel, to bootstrap them into the group: the CURRENT chain key + its
   iteration number + a signature binding both to the sender-key's identity.
   {:chain-key :iteration :sig-pub :sig}."
  [{:keys [chain-key sig-seed sig-pub]} iteration]
  {:chain-key chain-key
   :iteration iteration
   :sig-pub sig-pub
   :sig (.sign ed25519 (distribution-payload chain-key iteration) sig-seed)})

(defn verify-distribution
  "Members MUST call this (and refuse on false) before trusting a
   distribution message's :chain-key."
  [{:keys [chain-key iteration sig-pub sig]}]
  (.verify ed25519 sig (distribution-payload chain-key iteration) sig-pub))

(defn sender-advance
  "Sender-side: advance the chain key one step. -> Promise<[new-sender-key
   message-key]>. Only the sender ever calls this — sender-keys' defining
   property is that only the sender advances the authoritative chain."
  [sender-key]
  (-> (ratchet/kdf-chain-key (:chain-key sender-key))
      (.then (fn [{:keys [chain-key message-key]}]
               [(assoc sender-key :chain-key chain-key) message-key]))))

(defn member-derive
  "Member-side: from a chain-key it holds (from a distribution-message, or
   the result of a prior member-derive), derive the NEXT message-key and the
   next chain-key. -> Promise<[next-chain-key message-key]>. Members never
   invent chain state — they only step the copy they were given forward, in
   lockstep with the sender's own `sender-advance` calls."
  [chain-key]
  (-> (ratchet/kdf-chain-key chain-key)
      (.then (fn [{:keys [chain-key message-key]}] [chain-key message-key]))))

(defn encrypt-segment
  "message-key + plaintext segment bytes -> Promise<{:iv :ciphertext}>
   (AES-256-GCM)."
  ([message-key plaintext] (ratchet/ratchet-encrypt message-key plaintext))
  ([message-key plaintext aad] (ratchet/ratchet-encrypt message-key plaintext aad)))

(defn decrypt-segment
  ([message-key envelope] (ratchet/ratchet-decrypt message-key envelope))
  ([message-key envelope aad] (ratchet/ratchet-decrypt message-key envelope aad)))
