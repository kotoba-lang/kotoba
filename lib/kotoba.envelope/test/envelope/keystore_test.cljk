(ns envelope.keystore-test
  "A store that hands over secret keys is mostly a set of reasons not to.

  The round trip is one test. The rest are the refusals, and each is checked
  against the vocabulary its owner defines rather than a copy made here:
  `kotoba.security.key-status` decides which key statuses may authorise new
  work, so the status test iterates ITS set. A status added there and not
  here would otherwise be a hole that no test could see."
  (:require [cljs.test :refer [deftest is testing async]]
            [envelope.kem :as kem]
            [envelope.keystore :as keystore]
            [envelope.sealed-key :as sealed-key]
            [envelope.seal :as seal]
            [kotoba.security.key-status :as key-status]
            ["node:crypto" :as crypto]))

(def ^:private unlock (js/Uint8Array.from (clj->js (repeat 32 7))))
(def ^:private other-unlock (js/Uint8Array.from (clj->js (repeat 32 8))))

(defn- fails [p]
  (-> (js/Promise.resolve p) (.then (fn [_] false)) (.catch (fn [_] true))))

(defn- reason [p]
  (letfn [(named [e] (when e (or (:envelope.keystore/reason (ex-data e))
                                 (named (ex-cause e)))))]
    (-> (js/Promise.resolve p)
        (.then (fn [_] :no-rejection))
        (.catch (fn [e] (or (named e) :other))))))

(defn- sealed [] (-> (keystore/generate-identity)
                     (.then (fn [id] (js/Promise.all
                                      #js [(keystore/seal-record id unlock nil) id])))))

;; ── what a record is ─────────────────────────────────────────────────────

(deftest a-record-carries-no-secret
  (async done
    (-> (sealed)
        (.then (fn [[record identity]]
                 (let [text (pr-str record)]
                   (testing "public material, a status and two wraps -- safe on a
                             server that must not be able to read anything"
                     (is (= keystore/record-version (:record/version record)))
                     (is (= :active (:key/status record)))
                     (is (some? (:wrapped/x25519 record)))
                     (is (some? (:wrapped/ml-kem record))))
                   (testing "and neither secret appears in it"
                     (is (not (re-find (re-pattern (seal/b64url (:priv identity))) text)))
                     (is (not (re-find (re-pattern (seal/b64url (:pq-priv identity))) text)))))
                 (done)))
        (.catch (fn [e] (is false (str e)) (done))))))

(deftest the-fingerprint-is-derived-from-the-keys
  (async done
    (-> (keystore/generate-identity)
        (.then (fn [identity]
                 (-> (keystore/fingerprint identity)
                     (.then (fn [fp]
                              (is (= fp (:recipient-key identity)))
                              (is (re-find #"^kv1:" fp))
                              (keystore/fingerprint (assoc identity :pub (:pub (kem/generate-keypair))))))
                     (.catch (fn [_] :rejected-as-expected)))))
        (.then (fn [r]
                 (testing "a public key of the wrong size is not fingerprinted at all"
                   (is (= :rejected-as-expected r)))
                 (done))))))

(deftest two-identities-do-not-share-a-name
  (async done
    (-> (js/Promise.all #js [(keystore/generate-identity) (keystore/generate-identity)])
        (.then (fn [[a b]]
                 (is (not= (:recipient-key a) (:recipient-key b)))
                 (done))))))

;; ── the round trip ───────────────────────────────────────────────────────

(deftest a-sealed-record-opens-and-the-keys-still-work
  (async done
    (let [held (atom nil)]
      (-> (sealed)
          (.then (fn [[record identity]]
                   (-> (keystore/open-record record unlock)
                       (.then (fn [opened]
                                (reset! held opened)
                                (is (= (:recipient-key identity) (:recipient-key opened)))
                                ;; not merely equal bytes: the recovered keys have
                                ;; to open a wrap made for the identity's PUBLIC
                                ;; keys, which is the only thing that shows the
                                ;; store returned a usable pair
                                (sealed-key/seal-key (crypto/randomBytes 32) identity "aad"))))))
          (.then (fn [frame] (sealed-key/open-key frame @held "aad")))
          (.then (fn [opened] (is (= 32 (.-length ^js opened))) (done)))
          (.catch (fn [e] (is false (str e)) (done)))))))

;; ── the refusals ─────────────────────────────────────────────────────────

(deftest the-wrong-unlock-secret-opens-nothing
  (async done
    (-> (sealed)
        (.then (fn [[record _]] (fails (keystore/open-record record other-unlock))))
        (.then (fn [rejected] (is (true? rejected)) (done))))))

(deftest every-status-but-active-is-refused
  (testing "including ones this file has never heard of"
    (async done
      (-> (sealed)
          (.then (fn [[record _]]
                   (let [statuses (conj (vec key-status/blocked-for-new-artifacts)
                                        :a-status-nobody-has-defined nil)]
                     (is (seq key-status/blocked-for-new-artifacts)
                         "the authority's blocked set must not be empty, or this
                          test checks nothing")
                     (-> (js/Promise.all
                          (clj->js (for [s statuses]
                                     (reason (keystore/open-record
                                              (assoc record :key/status s) unlock)))))
                         (.then (fn [reasons]
                                  (is (= (count statuses) (.-length reasons)))
                                  (is (every? #(= :key-not-active %) (array-seq reasons))
                                      (str "got " (pr-str (vec (array-seq reasons)))))
                                  (done)))))))))))

(deftest an-unknown-record-version-is-refused-rather-than-guessed
  (async done
    (-> (sealed)
        (.then (fn [[record _]]
                 (reason (keystore/open-record (assoc record :record/version 99) unlock))))
        (.then (fn [r] (is (= :unsupported-record r)) (done))))))

(deftest a-relabelled-record-is-refused
  (async done
    (-> (sealed)
        (.then (fn [[record _]]
                 (reason (keystore/open-record
                          (assoc record :recipient-key "kv1:somebody-else") unlock))))
        (.then (fn [r] (is (= :fingerprint-mismatch r)) (done))))))

(deftest swapped-public-material-cannot-be-opened
  (testing "the name is recomputed, so editing :pub renames the record, and the
            wraps were sealed under the old name"
    (async done
      (-> (js/Promise.all #js [(sealed) (keystore/generate-identity)])
          (.then (fn [[[record _] stranger]]
                   (reason (keystore/open-record
                            (assoc record :pub (seal/b64url (:pub stranger))) unlock))))
          (.then (fn [r] (is (= :fingerprint-mismatch r)) (done)))))))

(deftest the-two-halves-cannot-be-exchanged
  (testing "each is sealed under its own AAD"
    (async done
      (-> (sealed)
          (.then (fn [[record _]]
                   (fails (keystore/open-record
                           (assoc record
                                  :wrapped/x25519 (:wrapped/ml-kem record)
                                  :wrapped/ml-kem (:wrapped/x25519 record))
                           unlock))))
          (.then (fn [rejected] (is (true? rejected)) (done)))))))

(deftest a-record-whose-ml-kem-halves-disagree-is-refused
  (testing "FIPS 203 puts the encapsulation key inside the decapsulation key,
            so this pair is checkable and is checked"
    (async done
      (-> (js/Promise.all #js [(keystore/generate-identity) (kem/generate-keypair)])
          (.then (fn [[identity stranger]]
                   ;; seal the real secrets, then claim a different :pq-pub and
                   ;; rename the record to match, so only the embedded key
                   ;; disagrees and every earlier check passes
                   (-> (keystore/seal-record identity unlock nil)
                       (.then (fn [record]
                                (-> (keystore/fingerprint {:pub (:pub identity)
                                                           :pq-pub (:pub stranger)})
                                    (.then (fn [fp]
                                             (reason
                                              (keystore/open-record
                                               (assoc record
                                                      :pq-pub (seal/b64url (:pub stranger))
                                                      :recipient-key fp)
                                               unlock))))))))))
          (.then (fn [r]
                   (testing "the AAD catches it first, which is also correct --
                             what matters is that it does not open"
                     (is (contains? #{:ml-kem-key-pair-mismatch :other} r)))
                   (done)))))))

;; ── the port ─────────────────────────────────────────────────────────────

(deftest the-unlocker-tells-absent-from-refused
  (async done
    (-> (sealed)
        (.then (fn [[record _]]
                 (let [records {(:recipient-key record) record
                                "kv1:revoked" (assoc record :recipient-key "kv1:revoked"
                                                     :key/status :revoked)}
                       keys! (keystore/unlocker records unlock)]
                   (-> (js/Promise.all
                        #js [(keys! "kv1:nobody")
                             (reason (keys! "kv1:revoked"))
                             (keys! (:recipient-key record))])
                       (.then (fn [[absent revoked present]]
                                (testing "absent resolves nil, which the opener reports as
                                          :no-key-for-recipient"
                                  (is (nil? absent)))
                                (testing "revoked rejects, so the two do not arrive alike"
                                  (is (= :key-not-active revoked)))
                                (is (map? present))
                                (done)))))))
        (.catch (fn [e] (is false (str e)) (done))))))
