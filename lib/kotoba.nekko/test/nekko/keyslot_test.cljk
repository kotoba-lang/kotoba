(ns nekko.keyslot-test
  "Run: npm run test:async"
  (:require [cljs.test :refer [deftest is testing async run-tests]]
            [nekko.keyslot :as ks]
            [nekko.recipient-grant-async :as rga]))

(defn- rejects? [p]
  (-> p (.then (fn [_] false)) (.catch (fn [_] true))))

(def ^:private prf-id "prf:AAAABBBBCCCC")
(def ^:private rec-id "recovery")

(deftest roundtrip
  (async done
    (let [secret (rga/random-bytes 32)
          factor (rga/random-bytes 32)]
      (-> (ks/wrap secret prf-id factor)
          (.then (fn [slot]
                   (is (= 1 (:v slot)))
                   (is (= prf-id (:factor slot)))
                   (is (= "HKDF-SHA-256" (:kdf slot)))
                   (is (= 64 (count (:salt slot))) "32-byte salt")
                   (is (= 24 (count (:iv slot))) "12-byte iv")
                   (is (= 96 (count (:ct slot))) "32B secret + 16B tag")
                   (ks/unwrap slot factor)))
          (.then (fn [out]
                   (is (= (rga/hexify secret) (rga/hexify out)))
                   (done)))
          (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done)))))))

(deftest any-one-factor-opens-it-and-they-are-independent
  (testing "one slot per enrolled passkey plus a recovery code: losing one
            factor must not lose the mailbox, which is the entire reason slots
            exist rather than a single wrap"
    (async done
      (let [secret (rga/random-bytes 32)
            prf (rga/random-bytes 32)
            rec (rga/random-bytes 32)]
        (-> (ks/wrap-many secret [[prf-id prf] [rec-id rec]])
            (.then (fn [slots]
                     (is (= #{prf-id rec-id} (set (keys slots))))
                     (js/Promise.all
                      #js [(ks/unwrap (get slots prf-id) prf)
                           (ks/unwrap (get slots rec-id) rec)
                           ;; a factor must not open the OTHER slot
                           (rejects? (ks/unwrap (get slots rec-id) prf))
                           (rejects? (ks/unwrap (get slots prf-id) rec))])))
            (.then (fn [r]
                     (is (= (rga/hexify secret) (rga/hexify (aget r 0))) "passkey slot")
                     (is (= (rga/hexify secret) (rga/hexify (aget r 1))) "recovery slot")
                     (is (true? (aget r 2)) "prf secret must not open the recovery slot")
                     (is (true? (aget r 3)) "recovery secret must not open the prf slot")
                     (done)))
            (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done))))))))

(deftest a-reused-factor-secret-still-never-reuses-key-and-iv
  (testing "THE regression this test exists for: recipient-grant uses a ZERO
            iv, which is safe there because its key is a single-use ephemeral
            ECDH output. A keyslot key is derived from a long-lived factor
            secret, so copying that zero iv here would reuse (key, iv) across
            rewraps and break AES-GCM outright. Both salt and iv must be fresh
            per wrap, and the ciphertext must therefore differ even when the
            secret, the factor id and the factor secret are all identical."
    (async done
      (let [secret (rga/random-bytes 32)
            factor (rga/random-bytes 32)]
        (-> (js/Promise.all #js [(ks/wrap secret prf-id factor)
                                 (ks/wrap secret prf-id factor)])
            (.then (fn [pair]
                     (let [a (js->clj (aget pair 0) :keywordize-keys true)
                           b (js->clj (aget pair 1) :keywordize-keys true)]
                       (is (not= (:salt a) (:salt b)) "salt must be fresh per wrap")
                       (is (not= (:iv a) (:iv b)) "iv must be fresh per wrap")
                       (is (not= (:ct a) (:ct b))
                           "identical inputs must not produce identical ciphertext")
                       (is (not= (apply str (repeat 24 "0")) (:iv a))
                           "the iv must not be the zero iv copied from recipient-grant")
                       ;; ...and both still open
                       (js/Promise.all #js [(ks/unwrap a factor) (ks/unwrap b factor)]))))
            (.then (fn [outs]
                     (is (= (rga/hexify secret) (rga/hexify (aget outs 0))))
                     (is (= (rga/hexify secret) (rga/hexify (aget outs 1))))
                     (done)))
            (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done))))))))

(deftest tampering-and-relabelling-are-rejected
  (async done
    (let [secret (rga/random-bytes 32)
          factor (rga/random-bytes 32)]
      (-> (ks/wrap secret prf-id factor)
          (.then (fn [slot]
                   (let [flip (fn [h] (str (subs h 0 (- (count h) 2))
                                           (if (= "00" (subs h (- (count h) 2))) "01" "00")))]
                     (js/Promise.all
                      #js [(rejects? (ks/unwrap (update slot :ct flip) factor))
                           (rejects? (ks/unwrap (update slot :salt flip) factor))
                           ;; relabelling is caught by the AAD binding, so whoever
                           ;; STORES slots cannot move one between factors
                           (rejects? (ks/unwrap (assoc slot :factor "prf:someone-else") factor))
                           (rejects? (ks/unwrap slot (rga/random-bytes 32)))]))))
          (.then (fn [r]
                   (is (true? (aget r 0)) "flipped ciphertext")
                   (is (true? (aget r 1)) "flipped salt")
                   (is (true? (aget r 2)) "relabelled factor")
                   (is (true? (aget r 3)) "foreign factor secret")
                   (done)))
          (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done)))))))

(deftest a-keyslotted-mailbox-key-can-still-open-a-real-grant
  (testing "the pieces have to compose: the thing in the slot is a mailbox
            X25519 private key, and after a round trip through a keyslot it
            must still open a grant sealed to its public half. Testing wrap and
            unwrap in isolation would not catch a key that survives byte-wise
            but no longer works."
    (async done
      (let [factor (rga/random-bytes 32)
            epoch-key-hex (rga/new-epoch-key)]
        (-> (rga/gen-recipient-keypair)
            (.then (fn [{:keys [priv pub]}]
                     ;; seal to the mailbox pubkey, as the inbound Worker would
                     (-> (rga/grant 1 pub (rga/unhex epoch-key-hex))
                         (.then (fn [g]
                                  ;; the private half lives only inside a slot
                                  (-> (ks/wrap (rga/unhex priv) prf-id factor)
                                      (.then (fn [slot] (ks/unwrap slot factor)))
                                      (.then (fn [recovered]
                                               (is (= priv (rga/hexify recovered))
                                                   "same key bytes back")
                                               ;; and it still decrypts the grant
                                               (rga/open g (rga/hexify recovered))))))))))
            (.then (fn [opened]
                     (is (= epoch-key-hex (rga/hexify opened))
                         "the keyslotted mailbox key opened a real grant")
                     (done)))
            (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done))))))))

(defmethod cljs.test/report [:cljs.test/default :end-run-tests] [m]
  (println (str "\n" (:test m) " tests, " (:pass m) " assertions passed, "
                (:fail m) " failed, " (:error m) " errored"))
  (when (pos? (+ (:fail m) (:error m)))
    (js/process.exit 1)))

(run-tests)
