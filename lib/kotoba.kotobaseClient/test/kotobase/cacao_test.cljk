(ns kotobase.cacao-test
  "Offline proof that a minted CACAO is exactly what the kotobase.net edge/pod
  verify: decode the DAG-CBOR envelope, recompute the SIWE message from its
  payload, and check the Ed25519 signature verifies under the issuer key —
  this is precisely verifyWorkerB2Cacao's check, run locally."
  (:require [cljs.test :refer-macros [deftest is testing]]
            [kotoba.lang.text :as str]
            ["@noble/curves/ed25519.js" :refer [ed25519]]
            ["@ipld/dag-cbor" :as dag-cbor]
            [kotobase.cid :as cid]
            [kotobase.cacao :as cacao]))

(def seed (js/Uint8Array.from (clj->js (range 32))))
(def aud "did:web:kotobase.net")
(def graph (cid/canonical-graph
            (cid/did-key-from-ed25519-pub (.getPublicKey ed25519 seed))
            "yoro-social"))

(defn- mint []
  (cacao/mint-cacao {:secret-key seed :aud aud
                     :capability "datom:transact" :extra-capabilities ["tx:create"]
                     :graph graph :now-ms 0 :nonce "testnonce0000000"}))

(deftest base64url-roundtrip
  (let [b (js/Uint8Array.from (clj->js [0 1 2 250 251 252 253 254 255]))]
    (is (= (vec (array-seq b))
           (vec (array-seq (cacao/base64url->bytes (cacao/bytes->base64url b))))))))

(deftest siwe-message-shape
  (let [pub (.getPublicKey ed25519 seed)
        did (cid/did-key-from-ed25519-pub pub)
        msg (cacao/cacao-siwe-message
             {:domain "kotobase.net" :iss did :aud aud :version "1"
              :nonce "testnonce0000000" :iat "1970-01-01T00:00:00Z"
              :exp "1970-01-01T00:05:00Z" :statement nil
              :resources ["kotoba://can/datom:transact"
                          "kotoba://can/tx:create"
                          (str "kotoba://graph/" graph)]})
        lines (str/split-lines msg)]
    (is (= "kotobase.net wants you to sign in with your Ethereum account:" (first lines)))
    (is (= (last (str/split did #":")) (second lines)) "address = last did segment")
    (is (str/includes? msg (str "URI: " aud)))
    (is (str/includes? msg "Version: 1"))
    (is (str/includes? msg "Chain ID: 1") "did:key forces chain-id 1")
    (is (str/includes? msg "Nonce: testnonce0000000"))
    (is (str/includes? msg "Issued At: 1970-01-01T00:00:00Z"))
    (is (str/includes? msg "Expiration Time: 1970-01-01T00:05:00Z"))
    (is (str/includes? msg "Resources:"))
    (is (str/includes? msg "- kotoba://can/datom:transact"))
    (is (str/includes? msg "- kotoba://can/tx:create"))
    (is (str/includes? msg (str "- kotoba://graph/" graph)))))

(deftest cacao-decodes-and-verifies
  (testing "minted CACAO → dag-cbor decode → signature verifies (edge's check)"
    (let [{:keys [cacao-b64 did graph]} (mint)
          env (.decode dag-cbor (cacao/base64->bytes cacao-b64))
          p (.-p env)
          resources (vec (.-resources p))]
      (is (= "caip122" (.. env -h -t)))
      (is (= "EdDSA" (.. env -s -t)))
      (is (= did (.-iss p)))
      (is (= aud (.-aud p)))
      (is (= "testnonce0000000" (.-nonce p)))
      (is (= "1970-01-01T00:00:00Z" (.-iat p)))
      (is (some #{(str "kotoba://graph/" graph)} resources) "graph scope present")
      (is (some #{"kotoba://can/datom:transact"} resources))
      (is (some #{"kotoba://can/tx:create"} resources))
      ;; recompute SIWE from the decoded payload and verify the signature.
      (let [p-clj {:domain (.-domain p) :iss (.-iss p) :aud (.-aud p)
                   :version (.-version p) :nonce (.-nonce p) :iat (.-iat p)
                   :exp (.-exp p) :statement (.-statement p) :resources resources}
            msg (cacao/cacao-siwe-message p-clj)
            sig (cacao/base64url->bytes (.. env -s -s))
            pub (.getPublicKey ed25519 seed)]
        (is (true? (.verify ed25519 sig (cid/text->bytes msg) pub))
            "Ed25519 signature verifies under issuer key")))))

(deftest cacao-is-deterministic-given-fixed-nonce-and-time
  (is (= (:cacao-b64 (mint)) (:cacao-b64 (mint)))))

;; ── tenant binding (kotobase-server verify-grant :require-tenant-binding?) ──

(deftest tenant-resource-is-signed-when-requested
  (let [{:keys [cacao-b64]}
        (cacao/mint-cacao {:secret-key seed :aud aud :capability "datom:read"
                           :graph graph :tenant "tenant-a" :now-ms 0
                           :nonce "tenantnonce00001"})
        ^js env (.decode dag-cbor (cacao/base64->bytes cacao-b64))
        resources (set (vec (.. env -p -resources)))]
    (is (contains? resources "kotoba://tenant/tenant-a")
        "the string kotobase.server.security.authority/verify-grant builds")
    (is (contains? resources (str "kotoba://graph/" graph))
        "the graph resource is still there — this is additive")
    (is (every? #(or (= % (str "kotoba://graph/" graph))
                     (= % "kotoba://tenant/tenant-a")
                     (str/starts-with? % "kotoba://can/"))
                resources)
        "and every resource still passes verify-grant's allowlist")))

(deftest no-tenant-means-byte-identical-to-before
  (testing "a verifier that does not require the binding must be unaffected"
    (let [without (:cacao-b64 (mint))
          explicit-nil (:cacao-b64
                        (cacao/mint-cacao
                         {:secret-key seed :aud aud :capability "datom:transact"
                          :extra-capabilities ["tx:create"] :graph graph
                          :tenant nil :statement nil
                          :now-ms 0 :nonce "testnonce0000000"}))]
      (is (= without explicit-nil)))))

(deftest purpose-is-signed-as-the-siwe-statement
  (let [{:keys [cacao-b64]}
        (cacao/mint-cacao {:secret-key seed :aud aud :capability "datom:read"
                           :graph graph :statement "nightly fold" :now-ms 0
                           :nonce "purposenonce0001"})
        ^js env (.decode dag-cbor (cacao/base64->bytes cacao-b64))
        ^js p (.-p env)
        p-clj {:domain (.-domain p) :iss (.-iss p) :aud (.-aud p)
               :version (.-version p) :nonce (.-nonce p) :iat (.-iat p)
               :exp (.-exp p) :statement (.-statement p)
               :resources (vec (.-resources p))}]
    (is (= "nightly fold" (.-statement p)))
    (is (true? (.verify ed25519
                        (cacao/base64url->bytes (.. env -s -s))
                        (cid/text->bytes (cacao/cacao-siwe-message p-clj))
                        (.getPublicKey ed25519 seed)))
        "it is inside the signed payload, not a side field")))
