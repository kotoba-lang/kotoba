(ns yoro-ui.interop.signal-group
  "Group E2E encryption — Signal \"sender-keys\" (kotoba-lang/org-signal's
  kotoba.signal.group), for aozora group chats. Each member creates and
  advances their OWN signed chain-key (\"sender-key\") and distributes it to
  every other member over the EXISTING 1:1 Signal v2 session (yoro-ui.
  interop.signal) — no new key-agreement primitive, just X3DH-lite bootstrap
  reused as the transport for the distribution payload.

  Membership-change handling (org-signal's group.clj/group.cljs explicitly
  leave this out — it needs to know who the current members ARE, which that
  library deliberately doesn't track): `ensure-sender-key!` is the pre-send
  check every encrypt-group-message call runs first. It compares the
  current member roster against who this device last distributed its CURRENT
  chain to:
    - nobody distributed to yet (or missing some current members) → send
      the CURRENT chain state to whoever's missing. A newcomer can only
      derive messages from THIS point forward (HMAC one-wayness already
      gives that for free — no rotation needed for joins).
    - a previously-distributed member is no longer in the roster (removed)
      → ROTATE: generate a brand-new sender-key and redistribute to the
      current (smaller) roster, so the removed member's retained old
      chain-key can't produce any future message-key. This rotation is
      what closes the gap org-signal's group ratchet deliberately left open.

  Fail-closed, same as the 1:1 layer: no silent plaintext fallback, no
  accepting an unverified distribution, no re-deriving an out-of-order
  message (in-order delivery only, same documented scope as the 1:1
  ratchet)."
  (:require [clojure.set :as set]
            [kotobase.cacao :as cacao]
            [yoro-ui.interop.key-crypto :as kc]
            [yoro-ui.interop.atproto :as at]
            [yoro-ui.interop.signal :as signal]
            [kotoba.signal.group :as group]))

(def scheme "signal-group-v1")
(def content-type "application/x-aozora-signal-group-v1+json")

;; ── localStorage ─────────────────────────────────────────────────────────────

(def ^:private ns-prefix "aozora-signal-group:")

(defn- ls-get [k] (when (exists? js/localStorage) (try (.getItem js/localStorage k) (catch :default _ nil))))
(defn- ls-set! [k v] (when (exists? js/localStorage) (try (.setItem js/localStorage k v) (catch :default _ nil))))
(defn- json-get [k] (when-let [s (ls-get k)] (try (js->clj (js/JSON.parse s) :keywordize-keys true) (catch :default _ nil))))
(defn- json-set! [k v] (ls-set! k (js/JSON.stringify (clj->js v))))

(defn- b64u [v] (when v (cacao/bytes->base64url v)))
(defn- unb64u [v] (when v (cacao/base64url->bytes v)))

;; my own sender-key for a convo: {:chainKey :sigSeed :sigPub :sendIteration :distributedTo [dids]}
(defn- sender-key-storage-key [my-did convo-id] (str ns-prefix "sender:" my-did ":" convo-id))
(defn- load-sender-key [my-did convo-id] (json-get (sender-key-storage-key my-did convo-id)))
(defn- store-sender-key! [my-did convo-id state] (json-set! (sender-key-storage-key my-did convo-id) state))

;; my copy of ANOTHER member's chain for a convo: {:chainKey :recvIteration}
(defn- member-key-storage-key [my-did convo-id sender-did] (str ns-prefix "member:" my-did ":" convo-id ":" sender-did))
(defn- load-member-key [my-did convo-id sender-did] (json-get (member-key-storage-key my-did convo-id sender-did)))
(defn- store-member-key! [my-did convo-id sender-did state] (json-set! (member-key-storage-key my-did convo-id sender-did) state))

;; ── distribution transport (rides the existing 1:1 Signal v2 session) ──────

(defn- distribute-to!
  "Encrypt+send the CURRENT (chain-key, iteration, sig) of `sender-key` to
  one peer, over their 1:1 Signal v2 session (established on demand if none
  exists yet — see yoro-ui.interop.signal/encrypt-message)."
  [my-did convo-id sender-key iteration peer-did]
  (let [dist (group/distribution-message
              {:chain-key (unb64u (:chainKey sender-key))
               :sig-seed (unb64u (:sigSeed sender-key))
               :sig-pub (unb64u (:sigPub sender-key))}
              iteration)
        payload (js/JSON.stringify
                 (clj->js {:convoId convo-id
                           :chainKey (b64u (:chain-key dist))
                           :iteration (:iteration dist)
                           :sigPub (b64u (:sig-pub dist))
                           :sig (b64u (:sig dist))}))]
    (-> (signal/encrypt-message my-did peer-did payload)
        (.then (fn [envelope]
                 (at/at-procedure "app.aozora.convo.distributeSenderKey"
                                  {:convoId convo-id :toDid peer-did
                                   :text (js/JSON.stringify (clj->js envelope))
                                   :contentType content-type
                                   :encryption signal/scheme}))))))

(defn- distribute-to-many! [my-did convo-id sender-key iteration peer-dids]
  (-> (js/Promise.all (clj->js (mapv #(distribute-to! my-did convo-id sender-key iteration %) peer-dids)))
      (.then (fn [_] nil))))

;; ── sender-side: create / rotate / keep-in-sync-with-membership ────────────

(defn ensure-sender-key!
  "Pre-send check: create this device's sender-key for `convo-id` if none
  exists, distribute to any current member it hasn't reached yet, and ROTATE
  (fresh chain, fresh distribution to everyone current) if a previously-
  distributed member has left the roster. → Promise<stored-sender-key-map>."
  [my-did convo-id members]
  (let [others (vec (remove #(= % my-did) members))
        existing (load-sender-key my-did convo-id)
        distributed-to (set (:distributedTo existing))
        current (set others)]
    (cond
      (nil? existing)
      (let [sk (group/create-sender-key)
            state {:chainKey (b64u (:chain-key sk)) :sigSeed (b64u (:sig-seed sk)) :sigPub (b64u (:sig-pub sk))
                   :sendIteration 0 :distributedTo []}]
        (-> (distribute-to-many! my-did convo-id state 0 others)
            (.then (fn [_]
                     (let [state' (assoc state :distributedTo others)]
                       (store-sender-key! my-did convo-id state')
                       state')))))

      (not (set/subset? distributed-to current))
      ;; someone we'd distributed our OLD chain to is no longer a member —
      ;; rotate so their retained copy can't produce any future message-key.
      (let [sk (group/create-sender-key)
            state {:chainKey (b64u (:chain-key sk)) :sigSeed (b64u (:sig-seed sk)) :sigPub (b64u (:sig-pub sk))
                   :sendIteration 0 :distributedTo []}]
        (-> (distribute-to-many! my-did convo-id state 0 others)
            (.then (fn [_]
                     (let [state' (assoc state :distributedTo others)]
                       (store-sender-key! my-did convo-id state')
                       state')))))

      (not (set/subset? current distributed-to))
      ;; roster grew (or an earlier distribution attempt was incomplete) —
      ;; catch up the missing members on the CURRENT chain position, no
      ;; rotation needed (they simply can't derive anything earlier).
      (let [missing (remove distributed-to others)]
        (-> (distribute-to-many! my-did convo-id existing (:sendIteration existing) missing)
            (.then (fn [_]
                     (let [state' (assoc existing :distributedTo others)]
                       (store-sender-key! my-did convo-id state')
                       state')))))

      :else (js/Promise.resolve existing))))

(defn encrypt-group-message
  "Encrypt `plaintext` for `convo-id`'s current `members`, running
  `ensure-sender-key!` first. → Promise<envelope-map>."
  [my-did convo-id members plaintext]
  (-> (ensure-sender-key! my-did convo-id members)
      (.then (fn [state]
               (let [sk {:chain-key (unb64u (:chainKey state)) :sig-seed (unb64u (:sigSeed state)) :sig-pub (unb64u (:sigPub state))}]
                 (-> (group/sender-advance sk)
                     (.then (fn [[sk' message-key]]
                              (-> (group/encrypt-segment message-key (kc/utf8->bytes plaintext))
                                  (.then (fn [{:keys [iv ciphertext]}]
                                           (let [n (:sendIteration state)]
                                             (store-sender-key! my-did convo-id
                                                                (assoc state :chainKey (b64u (:chain-key sk'))
                                                                       :sendIteration (inc n)))
                                             {:v 1 :alg scheme :n n :iv (b64u iv) :ct (b64u ciphertext)}))))))))))))

;; ── receive-side: fetch/verify a distribution on demand, then walk forward ──

(defn- fetch-and-store-distribution!
  "→ Promise<member-state>; rejects when no distribution is found from
  `sender-did`, or its 1:1 decrypt fails, or its signature doesn't verify —
  never resolves with an unverified chain-key."
  [my-did convo-id sender-did]
  (-> (at/at-appview-query "app.aozora.convo.listKeyDistributions" {:convoId convo-id :toDid my-did})
      (.then (fn [resp]
               (if-let [mine (first (filter #(= sender-did (:fromDid %)) (:distributions resp)))]
                 (-> (signal/decrypt-message my-did sender-did (js->clj (js/JSON.parse (:text mine)) :keywordize-keys true))
                     (.then (fn [plaintext]
                              (let [payload (js->clj (js/JSON.parse plaintext) :keywordize-keys true)
                                    dist {:chain-key (unb64u (:chainKey payload)) :iteration (:iteration payload)
                                          :sig-pub (unb64u (:sigPub payload)) :sig (unb64u (:sig payload))}]
                                (if-not (group/verify-distribution dist)
                                  (js/Promise.reject (js/Error. (str "signal-group: distribution signature verification failed from " sender-did)))
                                  (let [state {:chainKey (:chainKey payload) :recvIteration (:iteration payload)}]
                                    (store-member-key! my-did convo-id sender-did state)
                                    state))))))
                 (js/Promise.reject (js/Error. (str "signal-group: no key distribution found from " sender-did " for " convo-id))))))))

(defn decrypt-group-message
  "Decrypt one incoming group `envelope` from `sender-did` in `convo-id`.
  Fetches+verifies a fresh distribution first if this device has no local
  copy of `sender-did`'s chain yet, or the envelope's iteration is BEHIND
  what's already been consumed (only possible after `sender-did` rotated).
  Same one-shot/in-order scope as the 1:1 ratchet: must be called exactly
  once, in delivery order, per message. → Promise<string>."
  [my-did convo-id sender-did envelope]
  (-> (let [existing (load-member-key my-did convo-id sender-did)]
        (if (and existing (>= (:n envelope) (:recvIteration existing 0)))
          (js/Promise.resolve existing)
          (fetch-and-store-distribution! my-did convo-id sender-did)))
      (.then (fn [state]
               (if (not= (:n envelope) (:recvIteration state))
                 (js/Promise.reject (js/Error. (str "signal-group: out-of-order message from " sender-did
                                                    " (expected n=" (:recvIteration state) ", got n=" (:n envelope) ")")))
                 (-> (group/member-derive (unb64u (:chainKey state)))
                     (.then (fn [[chain-key' message-key]]
                              (-> (group/decrypt-segment message-key {:iv (unb64u (:iv envelope)) :ciphertext (unb64u (:ct envelope))})
                                  (.then (fn [pt]
                                           (store-member-key! my-did convo-id sender-did
                                                              (assoc state :chainKey (b64u chain-key')
                                                                     :recvIteration (inc (:recvIteration state))))
                                           (kc/bytes->utf8 pt))))))))))))
