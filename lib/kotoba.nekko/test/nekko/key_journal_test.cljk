(ns nekko.key-journal-test
  "Run: npm run test:async

  The tests that matter here are the two attacks: a server that swaps the
  published mailbox key, and a server that rolls the history back."
  (:require [cljs.test :refer [deftest is testing async]]
            [nekko.key-journal :as kj]
            [nekko.keyslot :as ks]
            [nekko.recipient-grant-async :as rga]))

(defn- mem-store
  "An in-memory CID->bytes store in chain.core's injected shape. Deliberately
  dumb: it is the untrusted party in these tests."
  []
  (let [m (atom {})]
    {:put! (fn [cid bytes] (swap! m assoc cid bytes) nil)
     :get-fn (fn [cid] (get @m cid))
     :raw m}))

(deftest derivation-is-deterministic-and-separates-the-two-keys
  (async done
    (let [root (kj/new-root-secret)]
      (-> (js/Promise.all #js [(kj/derive root) (kj/derive root)])
          (.then (fn [pair]
                   (let [a (js->clj (aget pair 0) :keywordize-keys true)
                         b (js->clj (aget pair 1) :keywordize-keys true)]
                     (is (= a b) "same root must derive the same keys, on any device")
                     (is (= 64 (count (:x25519-priv a))))
                     (is (= 64 (count (:journal-pub a))))
                     (is (not= (:x25519-priv a) (:journal-seed a))
                         "the mailbox key and the signing key must not be the same bytes")
                     (done))))
          (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done)))))))

(deftest a-real-journal-verifies-and-names-the-key-to-encrypt-to
  (async done
    (let [{:keys [put! get-fn]} (mem-store)
          root (kj/new-root-secret)]
      (-> (kj/derive root)
          (.then (fn [{:keys [x25519-pub journal-pub] :as keys}]
                   (let [h0 (kj/append! put! get-fn nil keys
                                        "mailbox-key/created" x25519-pub nil)
                         h1 (kj/append! put! get-fn h0 keys
                                        "keyslot/added" x25519-pub
                                        {"factor" "prf:device-2"})]
                     (is (kj/verify get-fn h1 journal-pub) "chain must verify")
                     (is (= x25519-pub (kj/current-mailbox-pub get-fn h1))
                         "the newest entry names the key to seal to")
                     (let [r (kj/accept? get-fn h1 journal-pub h0)]
                       (is (:ok? r) "extending a pinned head is accepted")
                       (is (= h1 (:head r)))
                       (is (= x25519-pub (:mailbox-pub r))))
                     (done))))
          (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done)))))))

(deftest the-noble-derived-public-half-matches-the-webcrypto-private-half
  (testing "two different implementations produce the two halves of the mailbox
            key: @noble/curves computes the public key here, WebCrypto consumes
            the private key in recipient-grant-async. If they disagreed, inbound
            mail would be sealed to a key nobody can open — and every unit test
            of either side would still pass. So seal a real grant to the derived
            public half and open it with the derived private half."
    (async done
      (let [root (kj/new-root-secret)
            epoch-hex (rga/new-epoch-key)]
        (-> (kj/derive root)
            (.then (fn [{:keys [x25519-priv x25519-pub]}]
                     (-> (rga/grant 1 x25519-pub (rga/unhex epoch-hex))
                         (.then (fn [g] (rga/open g x25519-priv)))
                         (.then (fn [opened]
                                  (is (= epoch-hex (rga/hexify opened))
                                      "noble-derived pub and WebCrypto priv are the same key")
                                  (done))))))
            (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done))))))))

(deftest a-server-that-swaps-the-mailbox-key-is-caught
  (testing "THE attack this namespace exists for. The attacker controls the
            store completely: it builds its own journal, with its own signing
            key, asserting its own mailbox pubkey. A client that derived the
            journal pubkey from the root secret it recovered out of a keyslot
            rejects it, because the signatures are made by a key the attacker
            could not derive."
    (async done
      (let [honest (mem-store)
            evil (mem-store)
            root (kj/new-root-secret)
            evil-root (kj/new-root-secret)]
        (-> (js/Promise.all #js [(kj/derive root) (kj/derive evil-root)])
            (.then (fn [pair]
                     (let [good (js->clj (aget pair 0) :keywordize-keys true)
                           bad (js->clj (aget pair 1) :keywordize-keys true)
                           gh (kj/append! (:put! honest) (:get-fn honest) nil good
                                          "mailbox-key/created" (:x25519-pub good) nil)
                           eh (kj/append! (:put! evil) (:get-fn evil) nil bad
                                          "mailbox-key/created" (:x25519-pub bad) nil)]
                       (is (kj/verify (:get-fn honest) gh (:journal-pub good))
                           "the honest chain verifies")
                       (is (false? (kj/verify (:get-fn evil) eh (:journal-pub good)))
                           "the substituted chain must NOT verify under the derived signer")
                       (is (false? (:ok? (kj/accept? (:get-fn evil) eh (:journal-pub good) nil)))
                           "accept? must refuse it even on first contact")
                       ;; and the evil chain is internally consistent -- it only
                       ;; fails because the signer is wrong. Otherwise this test
                       ;; would be passing for the wrong reason.
                       (is (kj/verify (:get-fn evil) eh (:journal-pub bad))
                           "the attacker's chain is well-formed; only the signer betrays it")
                       (done))))
            (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done))))))))

(deftest a-rolled-back-history-is-caught-by-the-pin
  (testing "the attacker cannot forge an entry, but it can serve an OLDER head
            to undo a revocation. The pin catches that: the head we saw before
            must still be present in what we are served now."
    (async done
      (let [{:keys [put! get-fn]} (mem-store)
            root (kj/new-root-secret)]
        (-> (kj/derive root)
            (.then (fn [{:keys [x25519-pub journal-pub] :as keys}]
                     (let [h0 (kj/append! put! get-fn nil keys
                                          "mailbox-key/created" x25519-pub nil)
                           h1 (kj/append! put! get-fn h0 keys
                                          "keyslot/removed" x25519-pub
                                          {"factor" "prf:lost-laptop"})]
                       (is (kj/extends-pinned? get-fn h1 h0) "h1 extends h0")
                       (is (false? (kj/extends-pinned? get-fn h0 h1))
                           "serving h0 to a client pinned at h1 is a rollback and must fail")
                       (is (false? (:ok? (kj/accept? get-fn h0 journal-pub h1)))
                           "accept? must refuse the rollback even though h0 verifies")
                       (is (kj/verify get-fn h0 journal-pub)
                           "h0 itself is perfectly valid -- only the pin makes it a rollback")
                       (done))))
            (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done))))))))

(deftest a-tampered-entry-fails
  (async done
    (let [{:keys [put! get-fn raw]} (mem-store)
          root (kj/new-root-secret)]
      (-> (kj/derive root)
          (.then (fn [{:keys [x25519-pub journal-pub] :as keys}]
                   (let [h (kj/append! put! get-fn nil keys
                                       "mailbox-key/created" x25519-pub nil)]
                     (is (kj/verify get-fn h journal-pub))
                     ;; flip a byte in the stored block: chain.core must catch the
                     ;; CID mismatch, so the store cannot lie about content at all
                     (let [b (get @raw h)
                           broken (doto (js/Uint8Array. b) (aset 0 (bit-xor 0xff (aget b 0))))]
                       (swap! raw assoc h broken)
                       ;; chain.core CATCHES and returns false rather than
                       ;; throwing -- verified by reading verify-chain, after this
                       ;; test first asserted a throw and failed.
                       (is (false? (kj/verify get-fn h journal-pub))
                           "a block whose bytes do not hash to its CID must not be accepted"))
                     (done))))
          (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done)))))))

(deftest the-root-secret-round-trips-through-a-keyslot
  (testing "the composition the whole design rests on: the root lives only in
            keyslot ciphertext, and a device that opens one slot recovers
            everything -- the mailbox key AND the ability to verify the journal."
    (async done
      (let [{:keys [put! get-fn]} (mem-store)
            root (kj/new-root-secret)
            factor (rga/random-bytes 32)]
        (-> (kj/derive root)
            (.then (fn [{:keys [x25519-priv x25519-pub journal-pub] :as keys}]
                     (let [h (kj/append! put! get-fn nil keys
                                         "mailbox-key/created" x25519-pub nil)]
                       (-> (ks/wrap root "prf:device-1" factor)
                           (.then (fn [slot] (ks/unwrap slot factor)))
                           (.then (fn [recovered] (kj/derive recovered)))
                           (.then (fn [rederived]
                                    (is (= journal-pub (:journal-pub rederived))
                                        "same signer derived on the second device")
                                    (is (= x25519-priv (:x25519-priv rederived))
                                        "same mailbox key")
                                    (is (kj/verify get-fn h (:journal-pub rederived))
                                        "the second device verifies the chain on its own")
                                    (done)))))))
            (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done))))))))
