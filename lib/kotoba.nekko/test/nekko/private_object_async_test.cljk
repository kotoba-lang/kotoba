(ns nekko.private-object-async-test
  "Run: npm run test:async

  nbb is the one host with both backends live, so the envelope's real property
  — that the Worker and the JVM produce and open the same thing — can be
  checked in-process rather than by eyeballing hex."
  (:require [cljs.test :refer [deftest is testing async run-tests]]
            [nekko.bytes :as b]
            [nekko.private-object :as sync]
            [nekko.private-object-async :as a]
            [nekko.recipient-grant-async :as rga]))

(defn- rejects? [p]
  (-> p (.then (fn [_] false)) (.catch (fn [_] true))))

(def ^:private msg (rga/random-bytes 512))

(deftest async-roundtrip
  (async done
    (let [k (rga/new-epoch-key)]
      (-> (a/seal 1 k msg)
          (.then (fn [s]
                   (is (= 1 (:epoch s)))
                   (is (= 24 (count (:iv s))) "96-bit iv")
                   (is (re-find #"^r2sha256:[0-9a-f]{64}$" (:plaintext-cid s)))
                   (a/open s k)))
          (.then (fn [out]
                   (is (= (rga/hexify msg) (rga/hexify out)))
                   (done)))
          (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done)))))))

(deftest a-worker-sealed-object-opens-on-the-jvm-backend
  (testing "the Worker is the only place a message is ever in the clear, and
            the JVM drain is what reads it back; if these two disagreed, mail
            would be sealed to nothing"
    (async done
      (let [k (rga/new-epoch-key)]
        (-> (a/seal 7 k msg)
            (.then (fn [s]
                     (is (= (rga/hexify msg) (b/hexify (sync/open s k)))
                         "async seal -> sync open")
                     (done)))
            (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done))))))))

(deftest a-sync-sealed-object-opens-in-the-worker
  (async done
    (let [k (rga/new-epoch-key)
          s (sync/seal 3 k (b/unhex (rga/hexify msg)))]
      (-> (a/open s k)
          (.then (fn [out]
                   (is (= (rga/hexify msg) (rga/hexify out)) "sync seal -> async open")
                   (done)))
          (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done)))))))

(deftest the-replication-id-agrees-across-hosts
  (async done
    (let [k (rga/new-epoch-key)]
      (-> (a/seal 1 k msg)
          (.then (fn [s] (.then (a/ciphertext-cid s)
                                (fn [cid] [s cid]))))
          (.then (fn [[s cid]]
                   (is (= (sync/ciphertext-cid s) cid)
                       "a store addressing an object must not depend on who sealed it")
                   (done)))
          (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done)))))))

(deftest a-valid-envelope-around-a-substituted-plaintext-is-refused
  (testing "THE reason plaintext-cid exists. The GCM tag proves nobody edited
            the ciphertext; it proves nothing about which plaintext the sealer
            meant. Someone who holds the content key can produce a perfectly
            valid envelope around a message they wrote — re-sealing different
            bytes under the same key and epoch — and only the committed hash
            catches it."
    (async done
      (let [k (rga/new-epoch-key)
            forged (rga/random-bytes 512)]
        (-> (js/Promise.all #js [(a/seal 1 k msg) (a/seal 1 k forged)])
            (.then (fn [pair]
                     (let [honest (js->clj (aget pair 0) :keywordize-keys true)
                           evil (js->clj (aget pair 1) :keywordize-keys true)
                           ;; keep the honest message's committed hash, swap in
                           ;; the attacker's ciphertext and iv
                           swapped (assoc honest :iv (:iv evil) :ct (:ct evil))]
                       (js/Promise.all
                        #js [(rejects? (a/open swapped k))
                             (a/open evil k)]))))
            (.then (fn [r]
                     (is (true? (aget r 0))
                         "decrypts cleanly under the key, and is still refused")
                     (is (= (rga/hexify forged) (rga/hexify (aget r 1)))
                         "the attacker's own envelope opens fine -- so the refusal
                          above is the hash check, not a broken ciphertext")
                     (done)))
            (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done))))))))

(deftest a-wrong-key-and-an-edited-ciphertext-are-refused
  (async done
    (let [k (rga/new-epoch-key)]
      (-> (a/seal 1 k msg)
          (.then (fn [s]
                   (let [flip (fn [h] (str (subs h 0 (- (count h) 2))
                                           (if (= "00" (subs h (- (count h) 2))) "01" "00")))]
                     (js/Promise.all
                      #js [(rejects? (a/open s (rga/new-epoch-key)))
                           (rejects? (a/open (update s :ct flip) k))]))))
          (.then (fn [r]
                   (is (true? (aget r 0)) "wrong key")
                   (is (true? (aget r 1)) "edited ciphertext")
                   (done)))
          (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done)))))))

(defmethod cljs.test/report [:cljs.test/default :end-run-tests] [m]
  (println (str "\n" (:test m) " tests, " (:pass m) " assertions passed, "
                (:fail m) " failed, " (:error m) " errored"))
  (when (pos? (+ (:fail m) (:error m))) (js/process.exit 1)))

(run-tests)
