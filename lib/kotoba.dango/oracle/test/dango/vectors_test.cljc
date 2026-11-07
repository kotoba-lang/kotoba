(ns dango.vectors-test
  "The same inputs must give the bytes, CIDs and signatures that the `.cljk`
  reference gave. `vectors_data.cljc` records how they were made."
  (:require [clojure.test :refer [deftest is]]
            [dango.bytes :as b]
            [dango.chain :as chain]
            [dango.vectors-data :as data]
            [ed25519.sign :as ed]))

(defn- seed [n] (vec (repeat 32 n)))

(defn- hexes [bs] (b/->vec bs))

(defn token []
  (let [ds "kotoba://storage/did:key:z6MkTenant/ds"]
    (chain/attenuate
     (chain/root {:issuer-seed (seed 1)
                  :grant {:caps #{[:data/read (str ds "/*")] [:data/write (str ds "/*")]} :before 1800000000}
                  :caveats [[:and [:<= :req/bytes 1000] [:member? :req/kind #{:data/read :data/write}]]]
                  :next-seed (seed 2)})
     {:grant {:caps #{[:data/read (str ds "/raw/*")]} :holder "did:key:z6MkAgent" :before 1750000000}
      :caveats [[:prefix? :req/path "raw/"]] :next-seed (seed 3)})))

(defn observed
  "What the suite compares, as plain data."
  []
  (let [t (token) p (chain/present t)
        d (chain/verify p {:roots #{(ed/public-key (seed 1))}
                           :request {:req/kind :data/read
                                     :req/resource "kotoba://storage/did:key:z6MkTenant/ds/raw/a"
                                     :req/now 1700000000 :req/path "raw/a" :req/bytes 10
                                     :req/holder "did:key:z6MkAgent"}})]
    {:blocks (mapv (comp hexes :bytes) (:blocks t))
     :sigs (mapv (comp hexes :sig) (:blocks t))
     :seal (hexes (:seal p))
     :reason (:dango/reason d)
     :cids (:dango/cids d)}))

(deftest bytes-match-the-reference
  (let [o (observed)]
    (is (= :granted (:reason o)))
    (doseq [k [:blocks :sigs :seal :cids :reason]]
      (is (= (get data/reference k) (get o k)) (str k)))))
