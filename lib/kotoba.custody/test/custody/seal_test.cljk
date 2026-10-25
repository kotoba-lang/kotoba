(ns custody.seal-test
  "Real crypto, no fakes: Web Crypto AES-GCM and SHA-256, @noble/curves
  X25519, and a CSPRNG. The pure suite proves the algebra; this one proves
  that a custodian who is not in the quorum cannot get the secret out of a
  real wrap, which is the part a customer is actually buying."
  (:require [cljs.test :refer [deftest is testing async]]
            [custody.model :as m]
            [custody.seal :as seal]
            [kotoba.signal.x25519 :as x25519]
            [envelope.seal :as env-seal]))

(defn- custodian [n domain]
  (let [{:keys [priv pub]} (x25519/generate-keypair)]
    {:priv priv
     :entry {:custodian/id (str "did:key:c" n)
             :custodian/domain domain
             :custodian/pub (env-seal/b64url pub)}}))

(def ^:private recovery-key (vec (repeatedly 32 #(rand-int 256))))

(defn- fails [p]
  (-> p (.then (fn [_] false)) (.catch (fn [_] true))))

(defn- entry-at [d x]
  (first (filter #(= x (:custodian/share-x %)) (:deal/custodians d))))

(defn- five-custodians []
  [(custodian 1 :tenant) (custodian 2 :tenant) (custodian 3 :operator)
   (custodian 4 :notary) (custodian 5 :counsel)])

(defn- split! [cs threshold & [opts]]
  (seal/split-and-wrap! (merge {:deal-id "deal:test"
                                :secret-id "sec:test"
                                :secret recovery-key
                                :threshold threshold
                                :custodians (mapv :entry cs)}
                               opts)))

(deftest three-custodians-in-three-domains-open-it-and-no-plaintext-is-stored
  (async done
    (let [cs (five-custodians)]
      (-> (split! cs 3)
          (.then (fn [{:keys [deal independence]}]
                   (is (true? (:independence/sound? independence)))
                   (testing "no custodian entry carries the share in the clear"
                     (is (every? #(and (:wrap/wrapped %) (nil? (:share/y %)))
                                 (:deal/custodians deal))))
                   (testing "and no wrap equals another — same secret, distinct wraps"
                     (is (= 5 (count (set (map :wrap/wrapped (:deal/custodians deal)))))))
                   (-> (js/Promise.all
                        (clj->js (for [x [1 3 5]]
                                   (seal/release! deal (entry-at deal x)
                                                  (:priv (nth cs (dec x)))
                                                  {:at "2026-07-28T00:00:00Z"
                                                   :reason "test recovery"}))))
                       (.then (fn [releases] (seal/open! deal (vec releases))))
                       (.then (fn [r]
                                (is (true? (:custody/opened? r)))
                                (is (= recovery-key (:custody/secret r)))
                                (done))))))
          (.catch (fn [e] (is false (str e)) (done)))))))

(deftest the-operator-alone-cannot-open-it
  ;; The whole product claim, run against real wraps rather than argued.
  (async done
    (let [cs (five-custodians)]
      (-> (split! cs 3)
          (.then (fn [{:keys [deal]}]
                   (-> (seal/release! deal (entry-at deal 3) (:priv (nth cs 2))
                                      {:at "t" :reason "break-glass"})
                       (.then (fn [only-operator]
                                (seal/open! deal [only-operator])))
                       (.then (fn [r]
                                (is (false? (:custody/opened? r)))
                                (is (= :below-threshold (:custody/reason r)))
                                (is (nil? (:custody/secret r)))
                                (done))))))
          (.catch (fn [e] (is false (str e)) (done)))))))

(deftest a-custodian-cannot-unwrap-another-custodians-share
  ;; share-aad binds the custodian id and the coordinate, so this fails in
  ;; AES-GCM rather than needing a check anywhere in custody's own code.
  (async done
    (let [cs (five-custodians)]
      (-> (split! cs 3)
          (.then (fn [{:keys [deal]}]
                   (js/Promise.all
                    #js [;; operator's private key against the notary's wrap
                         (fails (seal/unwrap-share! deal (entry-at deal 4) (:priv (nth cs 2))))
                         ;; own key, but the entry relabelled to another coordinate
                         (fails (seal/unwrap-share!
                                 deal (assoc (entry-at deal 3) :custodian/share-x 4)
                                 (:priv (nth cs 2))))
                         ;; own key, own entry, but a deal claiming another epoch
                         (fails (seal/unwrap-share!
                                 (update deal :deal/epoch inc)
                                 (entry-at deal 3) (:priv (nth cs 2))))])))
          (.then (fn [[other-key relabelled next-epoch]]
                   (is (true? other-key))
                   (is (true? relabelled))
                   (testing "a share released under a retired generation cannot be replayed
                             into the current one -- it does not even unwrap"
                     (is (true? next-epoch)))
                   (done)))
          (.catch (fn [e] (is false (str e)) (done)))))))

(deftest wrapping-refuses-a-threshold-one-party-can-reach-alone
  ;; The independence gate, executable rather than advisory: three of the
  ;; five custodians are the same operator, so a 3-of-5 here is a 1-of-1.
  (async done
    (let [cs [(custodian 1 :operator) (custodian 2 :operator) (custodian 3 :operator)
              (custodian 4 :tenant) (custodian 5 :notary)]]
      (-> (fails (split! cs 3))
          (.then (fn [refused]
                   (is (true? refused))
                   (testing "and it can be forced, but only by saying so on the record"
                     (-> (split! cs 3 {:require-sound? false})
                         (.then (fn [{:keys [deal independence]}]
                                  (is (= :operator (:independence/captured-by independence)))
                                  (is (= 5 (count (:deal/custodians deal))))
                                  (done)))))))
          (.catch (fn [e] (is false (str e)) (done)))))))

(deftest a-stale-share-fails-on-the-digest-with-real-sha256
  (async done
    (let [cs (five-custodians)]
      (-> (js/Promise.all #js [(split! cs 3) (split! cs 3)])
          (.then (fn [[a b]]
                   (let [da (:deal a) db (:deal b)]
                     (-> (js/Promise.all
                          #js [(seal/release! da (entry-at da 1) (:priv (nth cs 0)) {:at "t"})
                               (seal/release! da (entry-at da 2) (:priv (nth cs 1)) {:at "t"})
                               ;; structurally impeccable, but from the other split
                               (seal/release! db (entry-at db 3) (:priv (nth cs 2)) {:at "t"})])
                         (.then (fn [[r1 r2 r3]]
                                  (let [mixed [r1 r2 r3]]
                                    (testing "nothing structural catches it"
                                      (is (nil? (m/quorum-error da mixed))))
                                    (seal/open! da mixed))))
                         (.then (fn [r]
                                  (is (false? (:custody/opened? r)))
                                  (is (= :digest-mismatch (:custody/reason r)))
                                  (is (nil? (:custody/secret r)))
                                  (done)))))))
          (.catch (fn [e] (is false (str e)) (done)))))))

(deftest the-digest-is-over-the-secret-not-over-any-share
  (async done
    (let [cs (five-custodians)]
      (-> (js/Promise.all #js [(split! cs 3) (seal/sha256-b64url recovery-key)])
          (.then (fn [[{:keys [deal]} digest]]
                   (is (= digest (:deal/secret-digest deal)))
                   (is (= :sha-256 (:deal/digest-alg deal)))
                   (done)))
          (.catch (fn [e] (is false (str e)) (done)))))))
