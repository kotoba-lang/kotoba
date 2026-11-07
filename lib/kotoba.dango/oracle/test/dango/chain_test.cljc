(ns dango.chain-test
  (:require [clojure.test :refer [deftest is testing]]
            [clojure.string]
            [dango.bytes :as b]
            [dango.chain :as chain]
            [ed25519.sign :as ed]
            [dango.value :as codec]))

(defn- seed [n] (vec (repeat 32 n)))
(def issuer (seed 1))
(def roots #{(ed/public-key issuer)})
(def tenant "did:key:z6MkTenant")
(def ds (str "kotoba://storage/" tenant "/ds"))

(def token
  (chain/root {:issuer-seed issuer
               :grant {:caps #{[:data/read (str ds "/*")] [:data/write (str ds "/*")]}
                       :before 1800000000}
               :caveats []
               :next-seed (seed 2)}))

(defn- req [& {:as m}]
  (merge {:req/kind :data/read :req/resource (str ds "/raw/a") :req/now 1700000000
          :req/path "raw/a" :req/bytes 10}
         m))

(defn- decide
  ([t] (decide t (req)))
  ([t r] (chain/verify (chain/present t) {:roots roots :request r})))

(defn- reason [d] (:dango/reason d))

(deftest external-root-adapter-binds-exact-root-and-keeps-chain-checks
  (let [p (chain/present token)
        expected (:bytes (first (:blocks p)))
        adapter (fn [{:keys [bytes signature cid]}]
                  (and (= expected bytes) (string? cid)
                       (ed/verify (first roots) bytes signature)))
        opts {:request (req) :root-verifier adapter}]
    (is (= :granted (reason (chain/verify p opts))))
    (is (= :dango/not-covered (reason (chain/verify p (assoc opts :request (req :req/kind :data/delete))))))
    (is (= :dango/expired (reason (chain/verify p (assoc opts :request (req :req/now 1800000000))))))
    (is (= :dango/bad-seal (reason (chain/verify (assoc p :seal (vec (repeat 64 0))) opts))))
    (is (= :dango/bad-signature (reason (chain/verify p (assoc opts :roots roots :root-verifier (constantly false))))))))

(deftest external-root-adapter-refuses-unresolved-or-failed-verification
  (doseq [adapter [(constantly #?(:clj (future true) :cljs (js/Promise.resolve true))) (constantly {:valid true})
                   (fn [_] (throw (ex-info "RPC unavailable" {})))]]
    (is (= :dango/bad-signature
           (reason (chain/verify (chain/present token) {:roots roots :request (req) :root-verifier adapter}))))))

(deftest root-token-grants-what-it-says
  (is (= :granted (reason (decide token))))
  (is (= :granted (reason (decide token (req :req/kind :data/write)))))
  (is (= :dango/not-covered (reason (decide token (req :req/kind :data/delete)))))
  (is (= :dango/not-covered
         (reason (decide token (req :req/resource "kotoba://storage/did:key:zOther/ds/raw/a"))))))

(deftest expiry-boundary
  ;; live while now < before; the boundary instant itself is expired
  (is (= :granted (reason (decide token (req :req/now 1799999999)))))
  (is (= :dango/expired (reason (decide token (req :req/now 1800000000))))))

(def narrowed
  (chain/attenuate token {:grant {:caps #{[:data/read (str ds "/raw/*")]}
                                  :holder "did:key:z6MkAgent" :before 1750000000}
                          :caveats [[:<= :req/bytes 100]]
                          :next-seed (seed 3)}))

(deftest attenuation-only-narrows
  (is (= :granted (reason (decide narrowed (req :req/holder "did:key:z6MkAgent")))))
  (is (= :dango/not-covered
         (reason (decide narrowed (req :req/kind :data/write :req/holder "did:key:z6MkAgent"))))
      "write was dropped by the second block")
  (is (= :dango/expired
         (reason (decide narrowed (req :req/now 1760000000 :req/holder "did:key:z6MkAgent")))))
  (is (= :dango/wrong-holder (reason (decide narrowed (req :req/holder "did:key:z6MkMallory")))))
  (is (= :dango/caveat-false
         (reason (decide narrowed (req :req/bytes 101 :req/holder "did:key:z6MkAgent"))))))

(deftest a-wider-block-contributes-nothing
  (let [wider (chain/attenuate narrowed
                               {:grant {:caps #{[:data/write (str ds "/*")]}}
                                :caveats [] :next-seed (seed 4)})]
    (is (= :dango/not-covered
           (reason (decide wider (req :req/kind :data/write :req/holder "did:key:z6MkAgent")))))))

(deftest holder-may-be-added-never-readdressed
  (is (= :dango/holder-readdressed
         (reason (decide (chain/attenuate narrowed {:grant {:caps #{[:data/read (str ds "/raw/*")]}
                                                            :holder "did:key:z6MkMallory"}
                                                    :caveats [] :next-seed (seed 5)}))))))

(deftest authentication-refusals
  (testing "an untrusted root"
    (is (= :dango/bad-signature
           (reason (chain/verify (chain/present token) {:roots #{(ed/public-key (seed 9))} :request (req)})))))
  (testing "a tampered block"
    (let [blk (codec/decode (:bytes (first (:blocks token))))
          forged (codec/encode (assoc-in blk [:grant :before] 1900000000))]
      (is (= :dango/bad-signature
             (reason (decide (assoc-in token [:blocks 0 :bytes] forged)))))))
  (testing "a dropped block: the holder cannot seal the shorter chain"
    (is (= :dango/bad-seal
           (reason (decide (assoc narrowed :blocks [(first (:blocks narrowed))]))))))
  (testing "blocks swapped: the link breaks"
    (is (= :dango/broken-link
           (reason (decide (update narrowed :blocks (comp vec reverse))))))
  (testing "no blocks"
    (is (= :dango/empty-chain
           (reason (chain/verify {:blocks [] :seal (b/->bytes (repeat 64 0))} {:roots roots :request (req)})))))
  (testing "revoked by CID"
    (let [cid (first (:dango/cids (decide token)))]
      (is (string? cid))
      (is (= :dango/revoked
             (reason (chain/verify (chain/present token) {:roots roots :revoked #{cid} :request (req)}))))))))

(deftest the-seal-is-what-a-verifier-checks
  (let [p (chain/present narrowed)]
    (is (not (contains? p :proof)) "the proof never leaves the holder")
    (is (= 64 (b/size (:seal p)))))
  (testing "a seal by the wrong key"
    (is (= :dango/bad-seal
           (reason (chain/verify (chain/present (assoc narrowed :proof (b/->bytes (seed 7))))
                                 {:roots roots :request (req :req/holder "did:key:z6MkAgent")})))))
  (testing "a seal over a different block"
    (let [p (chain/present narrowed)
          other (chain/present token)]
      (is (= :dango/bad-seal
             (reason (chain/verify (assoc p :seal (:seal other))
                                   {:roots roots :request (req :req/holder "did:key:z6MkAgent")}))))))
  (testing "no seal at all"
    (is (= :dango/bad-seal
           (reason (chain/verify (dissoc (chain/present token) :seal) {:roots roots :request (req)}))))))

(deftest before-must-be-an-epoch-second-in-range
  ;; a negative :before used to become "no expiry"
  (is (thrown? #?(:clj Exception :cljs :default) (chain/root {:issuer-seed issuer :grant {:caps #{[:data/read ds]} :before -1}
                                     :caveats [] :next-seed (seed 2)})))
  (is (thrown? #?(:clj Exception :cljs :default) (chain/root {:issuer-seed issuer :grant {:caps #{[:data/read ds]} :before 1000000000000}
                                     :caveats [] :next-seed (seed 2)})))
  (is (= :granted (reason (decide (chain/root {:issuer-seed issuer
                                               :grant {:caps #{[:data/read (str ds "/*")]} :before 999999999999}
                                               :caveats [] :next-seed (seed 2)}))))))

(deftest kinds-do-not-collide
  ;; :a.b/c and :a/b.c were one kind when the kind was one "ns.name" segment
  (let [t (chain/root {:issuer-seed issuer :grant {:caps #{[:a.b/c (str ds "/*")]} :before 1800000000}
                       :caveats [] :next-seed (seed 2)})]
    (is (= :granted (reason (decide t (req :req/kind :a.b/c)))))
    (is (= :dango/not-covered (reason (decide t (req :req/kind :a/b.c))))))
  (testing "a kind that makes no valid scope is refused, not dropped"
    (is (thrown? #?(:clj Exception :cljs :default) (chain/root {:issuer-seed issuer :grant {:caps #{[:data/* ds]}}
                                       :caveats [] :next-seed (seed 2)})))))

(deftest malformed-inputs-name-their-reason
  (is (= :dango/malformed-block
         (reason (decide (assoc-in token [:blocks 0 :bytes] (b/->bytes [0xff 0x00]))))))
  (is (= :dango/malformed-request (reason (decide token (dissoc (req) :req/now)))))
  (is (= :dango/malformed-request (reason (decide token (req :req/resource "not a resource")))))
  (is (thrown? #?(:clj Exception :cljs :default)
               (chain/attenuate token {:grant {:caps #{[:data/read ds]}}
                                       :caveats [[:eval "x"]] :next-seed (seed 6)}))))

(deftest token-round-trips-through-the-codec
  (let [bs (chain/encode-token narrowed)
        back (chain/decode-token bs)]
    (is (= :granted (reason (decide back (req :req/holder "did:key:z6MkAgent")))))
    (is (= (mapv (comp vec :bytes) (:blocks narrowed)) (mapv (comp vec :bytes) (:blocks back))))))

(deftest an-external-root-signs-its-own-message
  (let [wallet (seed 8)
        grant {:caps #{[:os/service-restart "kotoba://host/h1/service/*"]} :before 1800000000}
        t (chain/root-for-external-signer
           {:grant grant :caveats [] :next-seed (seed 2)
            :sign (fn [{:keys [message]}]
                    (is (clojure.string/starts-with? message "Awai dango delegation v1"))
                    (b/->bytes (ed/sign (ed/secret-key! wallet) (b/utf8 message))))})
        checks (fn [{:keys [cid signature]}]
                 (ed/verify (ed/public-key wallet) (b/utf8 (chain/root-message cid)) signature))
        r {:req/kind :os/service-restart :req/resource "kotoba://host/h1/service/a" :req/now 1700000000}
        opts {:roots #{} :request r}]
    (is (= :granted (reason (chain/verify (chain/present t) (assoc opts :root-verifier checks)))))
    (is (= :dango/bad-signature (reason (chain/verify (chain/present t) opts)))
        "with no adapter, an external root is refused")
    (testing "another account's signature is refused"
      (is (= :dango/bad-signature
             (reason (chain/verify (chain/present t)
                                   (assoc opts :root-verifier
                                          (fn [{:keys [cid signature]}]
                                            (ed/verify (ed/public-key (seed 9))
                                                       (b/utf8 (chain/root-message cid)) signature))))))))
    (testing "a bot narrows it offline, and cannot widen it"
      (let [bot (chain/attenuate t {:grant {:caps #{[:os/service-restart "kotoba://host/h1/service/a"]}
                                            :holder "did:key:zBot" :before 1750000000}
                                    :caveats [] :next-seed (seed 3)})
            o (assoc opts :root-verifier checks)]
        (is (= :granted (reason (chain/verify (chain/present bot)
                                              (assoc o :request (assoc r :req/holder "did:key:zBot"))))))
        (is (= :dango/not-covered
               (reason (chain/verify (chain/present bot)
                                     (assoc o :request (assoc r :req/holder "did:key:zBot"
                                                              :req/resource "kotoba://host/h1/service/b"))))))
        (is (= :dango/wrong-holder
               (reason (chain/verify (chain/present bot)
                                     (assoc o :request (assoc r :req/holder "did:key:zOther"))))))))))
