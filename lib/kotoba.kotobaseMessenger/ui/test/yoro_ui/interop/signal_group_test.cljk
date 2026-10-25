(ns yoro-ui.interop.signal-group-test
  "Multi-party round trip for yoro-ui.interop.signal-group, with no real
  network — same set!-based stub approach signal_test.cljc uses, extended to
  also fake app.aozora.convo.distributeSenderKey/listKeyDistributions (group
  key distribution rides the SAME at/at-procedure and at/at-appview-query
  vars as prekey bundles and 1:1 messages)."
  (:require [cljs.test :refer-macros [deftest is async]]
            [yoro-ui.interop.signal :as signal]
            [yoro-ui.interop.signal-group :as signal-group]
            [yoro-ui.interop.actor-key :as ak]
            [yoro-ui.interop.atproto :as at]
            [kotobase.cid :as cid]
            ["@noble/curves/ed25519.js" :refer [ed25519]]))

(when-not (and (exists? js/localStorage) (fn? (.-setItem js/localStorage)))
  (let [store (js/Map.)]
    (set! js/localStorage
          #js {:getItem (fn [k] (if (.has store k) (.get store k) nil))
               :setItem (fn [k v] (.set store k v) nil)
               :removeItem (fn [k] (.delete store k) nil)})))

(defn- rand-seed [] (doto (js/Uint8Array. 32) (js/crypto.getRandomValues)))

(defn- make-party []
  (let [seed (rand-seed)]
    {:seed seed :did (cid/did-key-from-ed25519-pub (.getPublicKey ed25519 seed))}))

;; `current-seed` stands in for "whichever party's browser is currently
;; calling" — every fn under test reads ak/seed synchronously at call time,
;; so swapping it between (not mid-) calls correctly simulates several
;; separate devices sharing one node process. `distributions` accumulates
;; ALL delivered key-distribution records across every party (matching a
;; real single shared PDS collection each party's device reads from).
(defn- install-fakes! [current-seed bundles distributions]
  (set! ak/seed (fn [] @current-seed))
  (set! at/at-procedure
        (fn
          ([nsid] (at/at-procedure nsid {}))
          ([nsid body]
           (case nsid
             "app.aozora.convo.registerPrekeys"
             (let [did (cid/did-key-from-ed25519-pub (.getPublicKey ed25519 @current-seed))]
               (swap! bundles assoc did body)
               (js/Promise.resolve {:did did :uri "at://x/y/self" :cid "bafyx" :rkey "self"}))

             "app.aozora.convo.distributeSenderKey"
             (let [from-did (cid/did-key-from-ed25519-pub (.getPublicKey ed25519 @current-seed))
                   rec (assoc body :fromDid from-did)]
               ;; The real PDS writes under a deterministic (convoId,toDid,
               ;; fromDid) rkey — a rotation OVERWRITES, it doesn't accumulate.
               ;; Mirror that here or a stale pre-rotation record would win.
               (swap! distributions (fn [ds]
                                      (conj (vec (remove #(and (= (:convoId %) (:convoId rec))
                                                               (= (:toDid %) (:toDid rec))
                                                               (= (:fromDid %) (:fromDid rec)))
                                                         ds))
                                            rec)))
               (js/Promise.resolve {:convoId (:convoId body) :toDid (:toDid body) :did from-did
                                    :uri "at://x/y/z" :cid "bafyy" :rkey "z"}))

             (js/Promise.reject (js/Error. (str "unexpected procedure " nsid)))))))
  (set! at/at-appview-query
        (fn
          ([nsid] (at/at-appview-query nsid {}))
          ([nsid params]
           (case nsid
             "app.aozora.convo.getPrekeyBundle"
             (js/Promise.resolve (if-let [b (get @bundles (:did params))]
                                   (assoc b :found true)
                                   {:found false}))

             "app.aozora.convo.listKeyDistributions"
             (js/Promise.resolve
              {:distributions (vec (filter #(and (= (:convoId params) (:convoId %))
                                                 (= (:toDid params) (:toDid %)))
                                           @distributions))})

             (js/Promise.reject (js/Error. (str "unexpected query " nsid))))))))

(defn- restore-fakes! [orig]
  (set! ak/seed (:seed orig))
  (set! at/at-procedure (:proc orig))
  (set! at/at-appview-query (:query orig)))

(defn- as! [current-seed party f]
  (fn [world]
    (reset! current-seed (:seed party))
    (f world)))

(defn- then-all [promise & steps]
  (reduce (fn [p step] (.then p step)) promise steps))

(deftest three-party-round-trip-and-removal-rotation
  (async done
    (let [alice (make-party) bob (make-party) carol (make-party)
          convo-id "group-1"
          all3 [(:did alice) (:did bob) (:did carol)]
          bob-and-alice [(:did alice) (:did bob)]
          bundles (atom {}) distributions (atom [])
          current-seed (atom (:seed alice))
          orig {:seed ak/seed :proc at/at-procedure :query at/at-appview-query}
          finish! (fn [] (restore-fakes! orig) (done))]
      (install-fakes! current-seed bundles distributions)
      (-> (then-all
           (js/Promise.resolve {})
           (as! current-seed alice (fn [_] (signal/ensure-identity! (:did alice))))
           (as! current-seed bob (fn [_] (signal/ensure-identity! (:did bob))))
           (as! current-seed carol (fn [_] (signal/ensure-identity! (:did carol))))

           ;; Alice sends to the full group (creating+distributing her sender-key
           ;; to Bob AND Carol along the way, via 1:1 sessions established on demand).
           (as! current-seed alice
                (fn [_] (signal-group/encrypt-group-message (:did alice) convo-id all3 "hello group")))
           (fn [env] {:env1 env})

           ;; Bob decrypts — has no local copy of Alice's chain yet, so this
           ;; fetches+verifies her distribution first.
           (as! current-seed bob
                (fn [{:keys [env1] :as world}]
                  (-> (signal-group/decrypt-group-message (:did bob) convo-id (:did alice) env1)
                      (.then (fn [pt] (assoc world :pt1-bob pt))))))
           ;; Carol decrypts the SAME ciphertext independently — this is
           ;; sender-keys' whole point, one envelope, N members.
           (as! current-seed carol
                (fn [{:keys [env1] :as world}]
                  (-> (signal-group/decrypt-group-message (:did carol) convo-id (:did alice) env1)
                      (.then (fn [pt] (assoc world :pt1-carol pt))))))

           ;; Carol is removed from the roster (server-side membership change
           ;; is out of scope for this crypto-only test — we just simulate the
           ;; NEXT encrypt-group-message call seeing a smaller member list).
           (as! current-seed alice
                (fn [world] (-> (signal-group/encrypt-group-message (:did alice) convo-id bob-and-alice "carol is gone now")
                                (.then (fn [env2] (assoc world :env2 env2))))))

           ;; Bob (still a member) decrypts the post-rotation message fine.
           (as! current-seed bob
                (fn [{:keys [env2] :as world}]
                  (-> (signal-group/decrypt-group-message (:did bob) convo-id (:did alice) env2)
                      (.then (fn [pt] (assoc world :pt2-bob pt))))))

           ;; Carol was excluded from the rotation's distribution list, so her
           ;; only recourse is her STALE pre-removal distribution — the
           ;; property org-signal's group.clj/group.cljs deliberately leave
           ;; unimplemented (no membership tracking) and this wrapper adds:
           ;; there is no route by which she can obtain the genuinely NEW
           ;; chain, so decrypting the post-rotation ciphertext fails (the
           ;; stale chain derives the wrong message-key, and AES-GCM's tag
           ;; check rejects it — fail-closed, not a fabricated result).
           (as! current-seed carol
                (fn [world]
                  (-> (signal-group/decrypt-group-message (:did carol) convo-id (:did alice) (:env2 world))
                      (.then (fn [_] (assoc world :carol-post-removal-decrypt :unexpectedly-succeeded)))
                      (.catch (fn [_] (assoc world :carol-post-removal-decrypt :correctly-rejected)))))))
          (.then (fn [world]
                   (is (= "hello group" (:pt1-bob world)))
                   (is (= "hello group" (:pt1-carol world)) "sender-keys: one ciphertext, both members decrypt independently")
                   (is (= "carol is gone now" (:pt2-bob world)) "remaining member reads the post-rotation message fine")
                   (is (= :correctly-rejected (:carol-post-removal-decrypt world))
                       "removed member's retained chain-key can't decrypt post-rotation messages")
                   (finish!)))
          (.catch (fn [e]
                    (is false (str "unexpected rejection in round trip: " e))
                    (finish!)))))))
