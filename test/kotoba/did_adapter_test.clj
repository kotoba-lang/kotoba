(ns kotoba.did-adapter-test
  (:require [clojure.test :refer [deftest is]]
            [did.core :as did]
            [kotoba.did-adapter :as adapter]))

(deftest resolve-did-key
  (let [pub (vec (range 32))
        id (did/public-key->did-key pub)
        {:keys [ok document]} (adapter/resolve-did id)]
    (is ok)
    (is (= id (:id document)))
    (is (= [(str id "#" (subs id (count "did:key:")))] (:authentication document)))))

(deftest resolve-did-web
  (let [{:keys [ok document]} (adapter/resolve-did "did:web:example.com:users:alice")]
    (is ok)
    (is (= "did:web:example.com:users:alice" (:id document)))))

(deftest resolve-did-invalid
  (let [{:keys [ok error]} (adapter/resolve-did "not-a-did")]
    (is (not ok))
    (is (string? error))))

(deftest publish-did-key-document
  (let [pub (vec (range 32))
        doc (adapter/publish-did-key pub)]
    (is (= (did/public-key->did-key pub) (:id doc)))
    (is (= pub (did/did-key->public-key (:id doc))))))
