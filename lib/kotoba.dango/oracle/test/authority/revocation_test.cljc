(ns authority.revocation-test
  (:require [clojure.test :refer [deftest is testing]]
            [authority.revocation :as rev]
            [dango.chain :as chain]
            [dango.cid :as cid]
            [ed25519.sign :as ed]))

(defn- seed [n] (vec (repeat 32 n)))
(def issuer (seed 1))
(def roots #{(ed/public-key issuer)})
(def tenant "did:key:z6MkTenant")
(def ds (str "kotoba://storage/" tenant "/ds"))

(def token
  (chain/root {:issuer-seed issuer
               :grant {:caps #{[:data/read (str ds "/*")]} :before 1800000000}
               :caveats []
               :next-seed (seed 2)}))

(defn- req []
  {:req/kind :data/read :req/resource (str ds "/raw/a") :req/now 1700000000
   :req/path "raw/a" :req/bytes 10})

(defn- block-cid [presentation i]
  (cid/cidv1-dag-cbor (:bytes (nth (:blocks presentation) i))))

(defn- reason [d] (:dango/reason d))

(deftest revoked-block-refuses-with-revoked
  (let [p (chain/present token)
        c (block-cid p 0)
        store (rev/revoke rev/empty c)]
    (is (true? (rev/revoked? store c)))
    (is (= :dango/revoked
           (reason (chain/verify p {:roots roots :revoked store :request (req)}))))))

(deftest empty-store-changes-nothing
  (let [p (chain/present token)]
    (is (false? (rev/revoked? rev/empty (block-cid p 0))))
    (is (= :granted
           (reason (chain/verify p {:roots roots :revoked rev/empty :request (req)}))))))

(deftest merge-unites-distributed-sets
  (let [p (chain/present token)
        c (block-cid p 0)
        other (cid/cidv1-dag-cbor [9 9 9])
        a (rev/revoke rev/empty c)
        b (rev/revoke rev/empty other)
        m (rev/merge a b)]
    (testing "union is commutative and idempotent"
      (is (= m (rev/merge b a)))
      (is (= m (rev/merge m m)))
      (is (= m (rev/merge m nil))))
    (testing "both revocations hold after distribution"
      (is (true? (rev/revoked? m c)))
      (is (true? (rev/revoked? m other))))
    (testing "the merged store plugs into verify"
      (is (= :dango/revoked
             (reason (chain/verify p {:roots roots :revoked m :request (req)})))))))

(deftest wire-round-trips-deterministically
  (let [cids (mapv #(cid/cidv1-dag-cbor [%]) [3 1 2])
        store (reduce rev/revoke rev/empty cids)
        w (rev/wire store)]
    (is (= 3 (count w)))
    (is (= w (vec (sort w))))
    (is (= w (rev/wire (reduce rev/revoke rev/empty (reverse cids)))))
    (is (= {:store store} (rev/read w)))
    (is (= {:store store} (rev/read (vec (reverse w)))))))

(deftest read-refuses-corrupt-payload-wholesale
  (let [good (block-cid (chain/present token) 0)]
    (testing "one bad entry voids the whole payload, never a partial store"
      (doseq [bad ["not-a-cid" 42 nil ""]]
        (let [r (rev/read [good bad])]
          (is (seq (:problems r)))
          (is (not (contains? r :store))))))
    (testing "a non-sequential payload is refused too"
      (let [r (rev/read good)]
        (is (seq (:problems r)))
        (is (not (contains? r :store)))))))

(deftest revoke-refuses-what-is-not-a-cid
  (doseq [bad ["not-a-cid" 42 nil "" "b!!!!"]]
    (is (= :thrown
           (try (rev/revoke rev/empty bad)
                :returned
                (catch #?(:clj clojure.lang.ExceptionInfo :cljs :default) _ :thrown)))
        (str "revoking " (pr-str bad) " must be loud, never a silent no-op"))))
