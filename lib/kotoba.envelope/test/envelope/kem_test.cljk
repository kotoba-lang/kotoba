(ns envelope.kem-test
  "Real ML-KEM-768 and real X25519 — no fakes.

  The round trip is the easy part. What this has to show is that the hybrid
  is actually hybrid: that breaking either half alone breaks it, and that a
  classical wrap cannot stand in for a post-quantum one."
  (:require [cljs.test :refer [deftest is testing async]]
            [envelope.model :as m]
            [envelope.kem :as kem]
            [envelope.seal :as seal]
            [kotoba.signal.x25519 :as x25519]))

(defn- utf8 [s] (.encode (js/TextEncoder.) s))
(defn- from-utf8 [u8] (.decode (js/TextDecoder.) u8))
(defn- bytes= [^js a ^js b]
  (and (= (.-length a) (.-length b))
       (every? true? (map #(= (aget a %) (aget b %)) (range (.-length a))))))

(defn- hybrid-recipient []
  (let [x (x25519/generate-keypair)
        pq (kem/generate-keypair)]
    {:id "did:key:zTestHybrid"
     :pub (:pub x) :priv (:priv x)
     :pq-pub (:pub pq) :pq-priv (:priv pq)}))

(defn- env-for [kem]
  (assoc (m/envelope "drv:pq-test" {:chunks 1}) :envelope/kem kem))

;; ── the sizes are the ones FIPS 203 specifies ────────────────────────────

(deftest mlkem768-sizes-are-fips-203
  (let [{:keys [pub]} (kem/generate-keypair)]
    (is (= kem/public-bytes (.-length pub)))
    (is (= 1184 (.-length pub)) "ML-KEM-768 public key")))

;; ── round trip ───────────────────────────────────────────────────────────

(deftest hybrid-encapsulate-decapsulate-agree
  (async done
    (let [r (hybrid-recipient)]
      (-> (kem/encapsulate {:pub (:pub r) :pq-pub (:pq-pub r)})
          (.then (fn [{:keys [wrap-key ephemeral-pub pq-ct]}]
                   (is (= kem/wrap-key-bytes (.-length wrap-key)))
                   (is (= kem/ciphertext-bytes (.-length pq-ct))
                       "ML-KEM-768 ciphertext is 1088 B — the per-recipient price")
                   (-> (kem/decapsulate {:priv (:priv r) :pq-priv (:pq-priv r)}
                                        {:ephemeral-pub ephemeral-pub
                                         :pq-ct pq-ct
                                         :recipient-pub (:pub r)})
                       (.then (fn [wk2]
                                (is (bytes= wrap-key wk2)
                                    "both sides derive the same wrap key")
                                (done))))))
          (.catch (fn [e] (is false (str e)) (done)))))))

(deftest hybrid-wrap-round-trips-a-content-key
  (async done
    (let [r (hybrid-recipient)
          env (env-for m/hybrid-kem)
          ck (.getRandomValues js/crypto (js/Uint8Array. 32))]
      (-> (seal/wrap-for-hybrid env r ck)
          (.then (fn [entry]
                   (is (= m/hybrid-kem (:recipient/kem entry)))
                   (is (some? (:recipient/pq-ct entry)))
                   (-> (seal/unwrap-with env entry (:priv r) (:pq-priv r))
                       (.then (fn [ck2]
                                (is (bytes= ck ck2))
                                (done))))))
          (.catch (fn [e] (is false (str e)) (done)))))))

;; ── it is genuinely hybrid: either half alone is not enough ──────────────

(deftest wrong-classical-half-fails
  (async done
    (let [r (hybrid-recipient)
          other (x25519/generate-keypair)
          env (env-for m/hybrid-kem)
          ck (.getRandomValues js/crypto (js/Uint8Array. 32))]
      (-> (seal/wrap-for-hybrid env r ck)
          (.then (fn [entry]
                   ;; correct ML-KEM key, wrong X25519 key
                   (-> (seal/unwrap-with env entry (:priv other) (:pq-priv r))
                       (.then (fn [_] (is false "must not open with a wrong X25519 half") (done))
                              (fn [_] (is true "rejected") (done))))))
          (.catch (fn [e] (is false (str e)) (done)))))))

(deftest wrong-post-quantum-half-fails
  (async done
    (let [r (hybrid-recipient)
          other (kem/generate-keypair)
          env (env-for m/hybrid-kem)
          ck (.getRandomValues js/crypto (js/Uint8Array. 32))]
      (-> (seal/wrap-for-hybrid env r ck)
          (.then (fn [entry]
                   ;; correct X25519 key, wrong ML-KEM key
                   (-> (seal/unwrap-with env entry (:priv r) (:priv other))
                       (.then (fn [_] (is false "must not open with a wrong ML-KEM half") (done))
                              (fn [_] (is true "rejected") (done))))))
          (.catch (fn [e] (is false (str e)) (done)))))))

(deftest substituted-encapsulation-fails
  (async done
    (let [r (hybrid-recipient)
          env (env-for m/hybrid-kem)
          ck (.getRandomValues js/crypto (js/Uint8Array. 32))]
      (-> (js/Promise.all
           #js [(seal/wrap-for-hybrid env r ck)
                (seal/wrap-for-hybrid env r ck)])
          (.then (fn [[a b]]
                   ;; graft the second wrap's ML-KEM ciphertext onto the first
                   (let [frankenstein (assoc a :recipient/pq-ct (:recipient/pq-ct b))]
                     (-> (seal/unwrap-with env frankenstein (:priv r) (:pq-priv r))
                         (.then (fn [_] (is false "a substituted encapsulation must not open") (done))
                                (fn [_] (is true "rejected — the transcript binds the ciphertext") (done)))))))
          (.catch (fn [e] (is false (str e)) (done)))))))

;; ── downgrade resistance ─────────────────────────────────────────────────

(deftest hybrid-and-classical-aad-differ
  (testing "so a classical wrap cannot be presented where a hybrid one is expected"
    (let [env (m/envelope "drv:abc" {:chunks 1})]
      (is (not= (m/wrap-aad env "did:key:zA" :x25519)
                (m/wrap-aad env "did:key:zA" m/hybrid-kem))))))

(deftest classical-aad-is-frozen
  (testing "every wrap already written must keep opening — the classical AAD
            must be byte-identical to what it was before the hybrid existed"
    (let [env (m/envelope "drv:abc" {:chunks 1})]
      (is (= "kotoba/envelope/wrap|1|drv:abc|did:key:zA"
             (m/wrap-aad env "did:key:zA" :x25519))))))

(deftest a-hybrid-entry-refuses-to-open-without-the-pq-key
  (async done
    (let [r (hybrid-recipient)
          env (env-for m/hybrid-kem)
          ck (.getRandomValues js/crypto (js/Uint8Array. 32))]
      (-> (seal/wrap-for-hybrid env r ck)
          (.then (fn [entry]
                   ;; no silent fallback to the classical path
                   (is (thrown? js/Error (seal/unwrap-with env entry (:priv r))))
                   (done)))
          (.catch (fn [e] (is false (str e)) (done)))))))

;; ── the classical path is untouched ──────────────────────────────────────

(deftest classical-wrap-still-round-trips
  (async done
    (let [{:keys [priv pub]} (x25519/generate-keypair)
          env (env-for :x25519)
          ck (.getRandomValues js/crypto (js/Uint8Array. 32))]
      (-> (seal/wrap-for env {:id "did:key:zClassic" :pub pub} ck)
          (.then (fn [entry]
                   (is (nil? (:recipient/kem entry)) "unchanged shape")
                   (-> (seal/unwrap-with env entry priv)
                       (.then (fn [ck2] (is (bytes= ck ck2)) (done))))))
          (.catch (fn [e] (is false (str e)) (done)))))))

(deftest both-kems-are-supported-and-validate
  (is (m/valid? (assoc (m/envelope "drv:a" {:chunks 1}) :envelope/kem :x25519)))
  (is (m/valid? (assoc (m/envelope "drv:a" {:chunks 1}) :envelope/kem m/hybrid-kem)))
  (is (not (m/valid? (assoc (m/envelope "drv:a" {:chunks 1}) :envelope/kem :rsa))))
  (is (m/hybrid? (assoc (m/envelope "drv:a" {:chunks 1}) :envelope/kem m/hybrid-kem)))
  (is (not (m/hybrid? (m/envelope "drv:a" {:chunks 1})))))

;; ── the explicit-AAD hybrid primitive ────────────────────────────────────
;;
;; `wrap-for-hybrid` derives its AAD from the envelope and recipient id.
;; kotobase's recipient-bound disclosure cannot: what binds a wrapped data
;; key there is `binding(grant)`, a CID this repo has no way to compute. So
;; the hybrid primitive takes the AAD, exactly as `wrap-bytes` already does
;; for the classical one — and these tests are here to keep the property
;; that made sharing the classical primitive safe: the AAD, not the call
;; site, is what stops a wrap being transplanted.

(defn- fails
  "Resolves true when `p` rejects. Written out rather than assumed: a test
  that awaits a rejection and forgets to assert it passes silently."
  [p]
  (-> (js/Promise.resolve p) (.then (fn [_] false)) (.catch (fn [_] true))))

(deftest hybrid-wrap-bytes-round-trips-under-an-explicit-aad
  (async done
    (let [r (hybrid-recipient)
          secret (js/Uint8Array.from #js [1 2 3 4 5 6 7 8])
          aad "kotobase/disclosure|bafy...binding"]
      (-> (seal/wrap-bytes-hybrid secret r aad)
          (.then (fn [w]
                   (is (= m/hybrid-kem (:wrap/kem w)))
                   (is (not= (seal/b64url secret) (:wrap/wrapped w)))
                   (is (= 1088 (.-length (seal/unb64url (:wrap/pq-ct w)))))
                   (seal/unwrap-bytes-hybrid w {:priv (:priv r) :pq-priv (:pq-priv r)} aad)))
          (.then (fn [opened]
                   (is (bytes= secret opened))
                   (done)))
          (.catch (fn [e] (is false (str e)) (done)))))))

(deftest a-hybrid-wrap-does-not-open-under-another-aad
  (async done
    (let [r (hybrid-recipient)
          secret (js/Uint8Array.from #js [7 7 7 7])
          aad "binding:a"]
      (-> (seal/wrap-bytes-hybrid secret r aad)
          (.then (fn [w]
                   (fails (seal/unwrap-bytes-hybrid
                           w {:priv (:priv r) :pq-priv (:pq-priv r)} "binding:b"))))
          (.then (fn [rejected]
                   (testing "one character of the binding is the whole authorisation"
                     (is (true? rejected)))
                   (done)))
          (.catch (fn [e] (is false (str e)) (done)))))))

(deftest a-hybrid-wrap-does-not-open-for-another-recipient
  (async done
    (let [alice (hybrid-recipient)
          bob (hybrid-recipient)
          secret (js/Uint8Array.from #js [5 5 5 5])]
      (-> (seal/wrap-bytes-hybrid secret alice "aad")
          (.then (fn [w]
                   (js/Promise.all
                    #js [(fails (seal/unwrap-bytes-hybrid
                                 w {:priv (:priv bob) :pq-priv (:pq-priv bob)} "aad"))
                         (fails (seal/unwrap-bytes-hybrid
                                 w {:priv (:priv bob) :pq-priv (:pq-priv alice)} "aad"))
                         (fails (seal/unwrap-bytes-hybrid
                                 w {:priv (:priv alice) :pq-priv (:pq-priv bob)} "aad"))])))
          (.then (fn [[neither classical-wrong pq-wrong]]
                   (is (true? neither))
                   (testing "and either half alone being wrong is enough"
                     (is (true? classical-wrong))
                     (is (true? pq-wrong)))
                   (done)))
          (.catch (fn [e] (is false (str e)) (done)))))))

(deftest neither-construction-will-open-the-other-one
  (async done
    (let [r (hybrid-recipient)
          secret (js/Uint8Array.from #js [3 3 3 3])]
      (-> (js/Promise.all
           #js [(seal/wrap-bytes-hybrid secret r "aad")
                (seal/wrap-bytes secret (:pub r) "aad")])
          (.then (fn [[hybrid classical]]
                   (js/Promise.all
                    #js [(fails (seal/unwrap-bytes hybrid (:priv r) "aad"))
                         (fails (seal/unwrap-bytes-hybrid
                                 classical {:priv (:priv r) :pq-priv (:pq-priv r)} "aad"))])))
          (.then (fn [[hybrid-opened-classically classical-opened-as-hybrid]]
                   (testing "a hybrid wrap refused by the classical opener — the downgrade
                             the hybrid exists to prevent is not reachable by mistake"
                     (is (true? hybrid-opened-classically)))
                   (testing "and the hybrid opener will not accept a classical wrap either"
                     (is (true? classical-opened-as-hybrid)))
                   (done)))
          (.catch (fn [e] (is false (str e)) (done)))))))

(deftest a-substituted-encapsulation-does-not-open-an-explicit-aad-wrap
  (async done
    (let [r (hybrid-recipient)
          secret (js/Uint8Array.from #js [8 8 8 8])]
      (-> (js/Promise.all
           #js [(seal/wrap-bytes-hybrid secret r "aad")
                (seal/wrap-bytes-hybrid secret r "aad")])
          (.then (fn [[a b]]
                   (fails (seal/unwrap-bytes-hybrid
                           (assoc a :wrap/pq-ct (:wrap/pq-ct b))
                           {:priv (:priv r) :pq-priv (:pq-priv r)} "aad"))))
          (.then (fn [rejected] (is (true? rejected)) (done)))
          (.catch (fn [e] (is false (str e)) (done)))))))
