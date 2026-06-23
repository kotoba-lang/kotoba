(ns kotoba.office-test
  "Pure (.cljc) verification of the office datom wire format + CACAO bridge.
   Runs under babashka WITHOUT building wasm:
     bb --classpath src -e \"(require 'kotoba.office-test)(kotoba.office-test/-main)\"
   Verifies the kotoba wire contract (v_edn encode/decode mirrors parse_edn_scalar)
   and the byte-exact siwe_message reproduction."
  (:require [kotoba.office :as o]
            [kotoba.cacao :as c]
            [clojure.test :refer [deftest is run-tests]]))

;; ---- simulate kotoba store+read: tx [{:e :a :v_edn}] -> decoded [e a v] rows ----
(defn- tx->rows [tx]
  (mapv (fn [{:keys [e a v_edn]}] [e a (o/parse-edn-scalar v_edn)]) tx))

;; ---- samples (org-first + DID + access-DAG) ----
(def sample-orgs
  [{:id "org-root" :did "did:key:zRoot" :kind :org.kind/root
    :display-name "gftd.ai" :data-graph "g-root" :created-at 1719000000000
    :vms [{:vid "did:key:zRoot#k1" :type :Ed25519 :pk "zRoot"
           :rels #{:authentication :capabilityDelegation}}]}
   {:id "org-alice" :did "did:key:zAlice" :kind :org.kind/account
    :display-name "Alice" :parent "org-acme" :data-graph "g-alice" :created-at 1719000002000
    :vms [{:vid "did:key:zAlice#k1" :type :Ed25519 :pk "zAlice"
           :rels #{:authentication :capabilityInvocation :keyAgreement}}]}])

(def sample-grants
  [{:id "grant-alice-acme" :org "org-acme" :subject "did:key:zAlice"
    :cap :cap/transact :scope "g-acme" :role :role/member :issued-at 1719000003000}
   {:id "grant-alice-beta" :org "org-beta" :subject "did:key:zAlice"
    :cap :cap/read :scope "g-beta" :role :role/guest
    :issued-at 1719000004000 :expires-at 1726000000000}])

(def sample-doc
  {:id "doc1" :kind :doc/document :title "Q3 戦略メモ"
   :owner-org "org-alice" :created-at 1719000005000
   :blocks [{:id "b0" :kind :block/heading :text "概要" :order "a0"}
            {:id "b1" :kind :block/paragraph :text "原材料費が上昇し…" :order "a1"
             :children [{:id "b1a" :kind :block/paragraph :text "詳細" :order "a0"}]}]})

;; ---- v_edn wire-format contract ----
(deftest v-edn-encoding-matches-kotoba
  (is (= "\"hello\""        (o/encode-value :doc/title "hello")))   ; string -> JSON string
  (is (= ":org.kind/account" (o/encode-value :org/kind :org.kind/account))) ; keyword -> bare ':'
  (is (= "1719000000000"    (o/encode-value :org/created-at 1719000000000))) ; long -> bare
  (is (= "true"             (o/encode-value :block/deleted true)))  ; boolean -> bare
  ;; decode mirrors kotoba parse_edn_scalar
  (is (= "hello"            (o/decode-value :doc/title (o/parse-edn-scalar (o/encode-value :doc/title "hello")))))
  (is (= :org.kind/account  (o/decode-value :org/kind (o/parse-edn-scalar (o/encode-value :org/kind :org.kind/account)))))
  (is (= 1719000000000      (o/decode-value :org/created-at (o/parse-edn-scalar (o/encode-value :org/created-at 1719000000000)))))
  (is (= true               (o/decode-value :block/deleted (o/parse-edn-scalar (o/encode-value :block/deleted true))))))

(deftest doc-round-trip-through-wire
  (is (= sample-doc (o/rows->doc (tx->rows (o/doc->tx sample-doc))))))

(deftest server-read-back-reconstructs-via-lid
  ;; The server content-addresses the entity (e -> CID), losing the caller's logical
  ;; id. :node/lid + lid-keyed rows->doc must still rebuild the original nested doc.
  (let [cid  (fn [e] (str "bafy-" e))           ; simulate server CID-ifying the entity
        rows (mapv (fn [{:keys [e a v_edn]}] [(cid e) a (o/parse-edn-scalar v_edn)])
                   (o/doc->tx sample-doc))]
    (is (= sample-doc (o/rows->doc rows)))))

(deftest org-round-trip-through-wire
  (doseq [org sample-orgs]
    (is (= org (o/rows->org (tx->rows (o/org->tx org)) (:id org)))
        (str "org: " (:id org)))))

(deftest grant-round-trip-through-wire
  (doseq [g sample-grants]
    (is (= g (o/rows->grant (tx->rows (o/grant->tx g)) (:id g)))
        (str "grant: " (:id g)))))

;; ---- server sync form (tx_edn for datomic.transact) ----
(deftest tx-edn-is-datomic-add-ops
  (let [edn (o/doc->tx-edn sample-doc)]
    ;; re-edit safety: retractEntity for the doc + every block precedes the adds
    (is (clojure.string/starts-with? edn "[[:db.fn/retractEntity \"doc1\"]"))
    (is (clojure.string/includes? edn "[:db.fn/retractEntity \"b0\"]"))
    (is (clojure.string/includes? edn "[:db.fn/retractEntity \"b1a\"]"))
    (is (clojure.string/ends-with? edn "]]"))
    ;; [:db/add e a v]; entity + string values quoted, keywords bare, longs bare
    (is (clojure.string/includes? edn "[:db/add \"doc1\" :doc/kind :doc/document]"))
    (is (clojure.string/includes? edn "[:db/add \"doc1\" :doc/title \"Q3 戦略メモ\"]"))
    (is (clojure.string/includes? edn "[:db/add \"doc1\" :doc/created-at 1719000005000]"))
    (is (clojure.string/includes? edn "[:db/add \"b0\" :block/parent \"doc1\"]"))))

;; ---- sovereign body transform (encrypt/decrypt are inverse over :text) ----
(deftest map-doc-text-transforms-only-block-text
  (let [enc (o/map-doc-text #(str "E(" % ")") sample-doc)]
    ;; structure untouched; every :text wrapped (incl nested)
    (is (= "E(概要)" (get-in enc [:blocks 0 :text])))
    (is (= "E(原材料費が上昇し…)" (get-in enc [:blocks 1 :text])))
    (is (= "E(詳細)" (get-in enc [:blocks 1 :children 0 :text])))
    (is (= (:title enc) (:title sample-doc)))            ; non-text untouched
    ;; inverse transform restores the original (encrypt then decrypt)
    (is (= sample-doc (o/map-doc-text #(subs % 2 (dec (count %))) enc)))))

;; ---- CACAO bridge ----
(deftest grant-maps-to-cacao-resources
  (is (= ["kotoba://op/datom:transact" "kotoba://graph/g-acme"]
         (c/grant->resources (first sample-grants))))
  (is (= ["kotoba://op/datom:read" "kotoba://graph/g-beta"]
         (c/grant->resources (second sample-grants)))))

(deftest siwe-message-is-byte-exact
  ;; matches kotoba-auth cacao.rs::siwe_message() exactly (see CACAO surface report)
  (let [payload (c/grant->payload
                 {:cap :cap/read :scope "graph-cid"}
                 {:iss "did:key:z6MkABC" :aud "https://kotoba.test"
                  :nonce "test-nonce" :issued-at "2026-01-01T00:00:00Z"
                  :expiry "2099-01-01T00:00:00Z" :domain "kotoba.test"})
        expected (clojure.string/join
                  "\n"
                  ["kotoba.test wants you to sign in with your Ethereum account:"
                   "z6MkABC"
                   ""
                   "URI: https://kotoba.test"
                   "Version: 1"
                   "Chain ID: 1"
                   "Nonce: test-nonce"
                   "Issued At: 2026-01-01T00:00:00Z"
                   "Expiration Time: 2099-01-01T00:00:00Z"
                   "Resources:"
                   "- kotoba://op/datom:read"
                   "- kotoba://graph/graph-cid"])]
    (is (= expected (c/siwe-message payload)))))

(deftest cacao-wire-has-renamed-fields
  (let [payload (c/grant->payload (first sample-grants)
                                  {:iss "did:key:zAlice" :aud "https://srv"
                                   :nonce "n" :issued-at "2026-01-01T00:00:00Z"})
        wire (c/->wire payload "sigb64")]
    (is (= "eip4361" (get-in wire [:h :t])))
    (is (= "EdDSA"   (get-in wire [:s :t])))
    (is (= "did:key:zAlice" (get-in wire [:p :iss])))
    (is (= "2026-01-01T00:00:00Z" (get-in wire [:p :iat])))  ; renamed issued-at->iat
    (is (contains? (set (get-in wire [:p :resources])) "kotoba://op/datom:transact"))))

(defn -main [& _]
  (let [{:keys [fail error]} (run-tests 'kotoba.office-test)]
    (System/exit (if (zero? (+ fail error)) 0 1))))
