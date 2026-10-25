(ns kotoba.signal.ratchet-test
  (:require [cljs.test :refer-macros [deftest is async]]
            [kotoba.signal.x25519 :as x25519]
            [kotoba.signal.ratchet :as ratchet]))

(defn- rand-bytes [n] (doto (js/Uint8Array. n) js/crypto.getRandomValues))
(defn- utf8 [^string s] (.encode (js/TextEncoder.) s))
(defn- utf8-decode [^js b] (.decode (js/TextDecoder.) b))

;; Simulates the wire: a header's :dh-pub travels as JSON (base64), so the
;; receiver always gets a FRESHLY allocated Uint8Array — this is what makes
;; the bytes= (content, not identity) fix in ratchet.cljs load-bearing.
(defn- b64 [^js b] (js/btoa (apply str (map #(js/String.fromCharCode %) (array-seq b)))))
(defn- unb64 [^string s] (let [bin (js/atob s) n (.-length bin) out (js/Uint8Array. n)]
                           (dotimes [i n] (aset out i (.charCodeAt bin i)))
                           out))
(defn- roundtrip-envelope
  "Re-derive `env` as if it had gone through JSON.stringify → parse, so
   :header's :dh-pub is a new array object, never `identical?` to anything
   the sender held."
  [{:keys [header iv ciphertext]}]
  {:header {:dh-pub (unb64 (b64 (:dh-pub header))) :n (:n header)}
   :iv (unb64 (b64 iv))
   :ciphertext (unb64 (b64 ciphertext))})

(defn- chain3 [ck0]
  (-> (ratchet/kdf-chain-key ck0)
      (.then (fn [{ck1 :chain-key mk1 :message-key}]
               (-> (ratchet/kdf-chain-key ck1)
                   (.then (fn [{ck2 :chain-key mk2 :message-key}]
                            (-> (ratchet/kdf-chain-key ck2)
                                (.then (fn [{ck3 :chain-key mk3 :message-key}]
                                         {:ck0 ck0 :ck1 ck1 :ck2 ck2 :ck3 ck3
                                          :mk1 mk1 :mk2 mk2 :mk3 mk3}))))))))))

(deftest chain-key-forward-secrecy
  (async done
    (-> (chain3 (rand-bytes 32))
        (.then (fn [{:keys [ck0 ck1 ck2 mk1 mk2 mk3]}]
                 (is (not (ratchet/bytes= mk1 mk2)))
                 (is (not (ratchet/bytes= mk2 mk3)))
                 (is (not (ratchet/bytes= ck0 ck1)))
                 (is (not (ratchet/bytes= ck1 ck2)))
                 (is (not (ratchet/bytes= ck0 mk1)) "message-key never equals the chain-key it's derived from")
                 (done))))))

(deftest message-key-uniqueness-across-many-steps
  (async done
    (let [n 50]
      (letfn [(step [ck i acc]
                (if (= i n)
                  (do (is (= n (count (into #{} (map js/JSON.stringify) (map vec acc)))) "no two message keys collide")
                      (done))
                  (-> (ratchet/kdf-chain-key ck)
                      (.then (fn [{:keys [chain-key message-key]}] (step chain-key (inc i) (conj acc message-key)))))))]
        (step (rand-bytes 32) 0 [])))))

(deftest ratchet-encrypt-decrypt-roundtrip
  (async done
    (let [mk (rand-bytes 32) pt (utf8 "the segment key rotates every message")]
      (-> (ratchet/ratchet-encrypt mk pt)
          (.then (fn [env] (ratchet/ratchet-decrypt mk env)))
          (.then (fn [pt'] (is (= "the segment key rotates every message" (utf8-decode pt'))) (done)))))))

(deftest ratchet-decrypt-rejects-tamper
  (async done
    (let [mk (rand-bytes 32) pt (utf8 "hello")]
      (-> (ratchet/ratchet-encrypt mk pt)
          (.then (fn [{:keys [iv ^js ciphertext]}]
                   (aset ciphertext 0 (bit-xor (aget ciphertext 0) 1))
                   (-> (ratchet/ratchet-decrypt mk {:iv iv :ciphertext ciphertext})
                       (.then (fn [_] (is false "tampered ciphertext must reject")))
                       (.catch (fn [_] (is true "tampered ciphertext correctly rejected"))))))
          (.then done)))))

(defn- fake-x3dh-session
  "Stands in for kotoba.signal.x3dh (JVM-only elsewhere in this package for
   now) — a shared-secret + Bob's initial DH keypair, exactly what X3DH hands
   the ratchet regardless of how it was derived."
  []
  {:shared-secret (rand-bytes 32) :bob-initial-dh (x25519/generate-keypair)})

;; ── multi-step actor helpers — each takes/returns a plain map ("world") so
;; a .then chain never has to smuggle values past intermediate steps. ───────

(defn- start-session [{:keys [shared-secret bob-initial-dh] :as world}]
  (-> (js/Promise.all #js [(ratchet/init-sender shared-secret (:pub bob-initial-dh))
                           (ratchet/init-receiver shared-secret bob-initial-dh)])
      (.then (fn [^js pair] (assoc world :alice (aget pair 0) :bob (aget pair 1))))))

(defn- alice-sends [text k]
  (fn [world]
    (-> (ratchet/encrypt-message (:alice world) (utf8 text))
        (.then (fn [[alice' env]] (assoc world :alice alice' k env))))))

(defn- bob-sends [text k]
  (fn [world]
    (-> (ratchet/encrypt-message (:bob world) (utf8 text))
        (.then (fn [[bob' env]] (assoc world :bob bob' k env))))))

(defn- bob-receives [env-key pt-key]
  (fn [world]
    (-> (ratchet/decrypt-message (:bob world) (roundtrip-envelope (get world env-key)))
        (.then (fn [[bob' pt]] (assoc world :bob bob' pt-key pt))))))

(defn- alice-receives [env-key pt-key]
  (fn [world]
    (-> (ratchet/decrypt-message (:alice world) (roundtrip-envelope (get world env-key)))
        (.then (fn [[alice' pt]] (assoc world :alice alice' pt-key pt))))))

(defn- then-all [promise & steps]
  (reduce (fn [p step] (.then p step)) promise steps))

(deftest full-session-roundtrip-both-directions-over-the-wire
  (async done
    (-> (then-all (start-session (fake-x3dh-session))
                  (alice-sends "hello bob" :env1)
                  (bob-receives :env1 :pt1)
                  (bob-sends "hi alice" :env2)
                  (alice-receives :env2 :pt2)
                  (alice-sends "second message from alice" :env3)
                  (bob-receives :env3 :pt3))
        (.then (fn [{:keys [pt1 pt2 pt3 env1 env2]}]
                 (is (= "hello bob" (utf8-decode pt1)))
                 (is (= "hi alice" (utf8-decode pt2)))
                 (is (= "second message from alice" (utf8-decode pt3)))
                 (is (not (ratchet/bytes= (:dh-pub (:header env1)) (:dh-pub (:header env2))))
                     "each side ratchets to its own fresh DH keypair per turn")
                 (done))))))

(deftest post-compromise-security-healing-after-a-fresh-dh-turn
  ;; An attacker who steals Alice's CURRENT send-chain state can follow her
  ;; chain forward — but the moment she DH-ratchets to a fresh keypair (which
  ;; happens automatically the first time she sends after Bob replies), the
  ;; new root key depends on her new ephemeral PRIVATE key, which the
  ;; attacker never had.
  (async done
    (-> (then-all (start-session (fake-x3dh-session))
                  (alice-sends "m1" :env1)
                  (fn [world] (assoc world :stolen (:send-chain-key (:alice world))
                                    :alice1-dh-pub (:dh-pub (:alice world))))
                  (bob-receives :env1 :pt1)
                  (bob-sends "reply, new epoch" :env-reply)
                  (alice-receives :env-reply :pt-reply)
                  (alice-sends "healed message" :env3))
        (.then (fn [{:keys [stolen alice1-dh-pub env3 alice]}]
                 (is (not (ratchet/bytes= (:dh-pub (:header env3)) alice1-dh-pub))
                     "the healed message rides a NEW DH keypair the attacker never held")
                 (is (not (ratchet/bytes= stolen (:send-chain-key alice)))
                     "post-turn chain state is unrelated to what the attacker stole")
                 (done))))))

(deftest decrypt-message-rejects-a-tampered-header-n
  ;; the header {:dh-pub :n} is bound into the AEAD's authenticated data
  ;; (header-aad) -- previously it was NOT, so an active party on the
  ;; delivery path could flip :n (or :dh-pub) in transit and decrypt-
  ;; message would trust it unconditionally. Tampering :n ALONE here
  ;; (leaving :dh-pub unchanged, so the DH-ratchet decision branch is
  ;; untouched) isolates the AAD-binding check specifically: pre-fix,
  ;; this tampered call would have resolved successfully, since :n
  ;; played no role in the AEAD computation at all.
  (async done
    (-> (then-all (start-session (fake-x3dh-session))
                  (alice-sends "hello bob" :env1))
        (.then (fn [{:keys [bob env1]}]
                 (let [wire (roundtrip-envelope env1)
                       tampered (update wire :header assoc :n (inc (:n (:header wire))))]
                   (-> (ratchet/decrypt-message bob tampered)
                       (.then (fn [_] (is false "tampered header :n must reject")))
                       (.catch (fn [_] (is true "tampered header :n correctly rejected")))))))
        (.then done))))
