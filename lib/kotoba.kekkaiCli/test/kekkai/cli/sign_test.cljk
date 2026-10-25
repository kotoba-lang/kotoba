(ns kekkai.cli.sign-test
  "The claim this CLI rests on: signing a netmap in ClojureScript produces the
  same bytes as signing it on the JVM.

  If that is false, `kekkai netmap publish` emits envelopes the fleet's other
  two implementations may reject, and the failure appears as an unverifiable
  signature at a node rather than as a test. So it is pinned against
  `kotoba-lang/kekkai`'s committed fixture — the same artifact
  `kekkai.fixture-test` asserts is byte-exactly what the JVM publisher emits,
  and the same one `kekkai.node.publisher-parity-test` verifies.

  Three implementations of one format, one set of bytes. The fixture is read
  from the sibling checkout rather than vendored: a copy here would be a fourth
  thing to keep in step, and a stale copy would make this test pass while the
  real contract moved."
  (:require [kotoba.lang.text :as str]
            [cljs.reader :as reader]
            [cljs.test :refer [deftest is testing]]
            [kekkai.cli.sign :as sign]
            [kekkai.netmap :as netmap]
            [kekkai.node.signed-netmap :as signed]
            ["node:fs" :as fs]
            ["node:path" :as path]))

(def fixture-dir
  "kekkai's own test fixtures, next to this checkout."
  (.join path ".." "kekkai" "test" "fixtures"))

(defn- fixture [name]
  (.readFileSync fs (.join path fixture-dir name) "utf8"))

(def available?
  (.existsSync fs (.join path fixture-dir "netmap.signed.edn")))

(def authority (when available? (reader/read-string (fixture "netmap-authority.edn"))))
(def envelope-text (when available? (fixture "netmap.signed.edn")))

;; The plane the fixture was published from — kekkai.store/demo-data, as the
;; pure value `netmap/publish` takes. Written out here rather than required
;; from `kekkai.store`, which pulls in langchain.db and does not belong in a
;; CLI's dependency graph.
(def plane
  {:nodes
   [{:id "n-laptop" :hostname "alice-mbp" :os "macos" :did "did:key:zLaptop"
     :user "alice" :tailnet "default" :tags ["tag:laptop"]
     :static-pub "1111111111111111111111111111111111111111111111111111111111111111"
     :overlay-ip "100.64.0.1" :key-expiry 1757776000 :status "authorized"}
    {:id "n-server" :hostname "prod-db" :os "linux" :did "did:key:zServer"
     :user "alice" :tailnet "default" :tags ["tag:server"]
     :static-pub "2222222222222222222222222222222222222222222222222222222222222222"
     :overlay-ip "100.64.0.2" :key-expiry 1757776000 :status "authorized"}
    {:id "n-gw" :hostname "edge-gw" :os "linux" :did "did:key:zGateway"
     :user "alice" :tailnet "default" :tags ["tag:exit"]
     :static-pub "3333333333333333333333333333333333333333333333333333333333333333"
     :overlay-ip "100.64.0.3" :key-expiry 1757776000 :status "authorized"}
    {:id "n-pending" :hostname "alice-phone" :os "ios" :did "did:key:zPhone"
     :user "alice" :tailnet "default" :tags ["tag:laptop"]
     :static-pub "4444444444444444444444444444444444444444444444444444444444444444"
     :overlay-ip "100.64.0.4" :key-expiry 1757776000 :status "pending"}
    {:id "n-rogue" :hostname "evil-box" :os "linux" :did "did:key:zRogue"
     :user "mallory" :tailnet "default" :tags ["tag:server"]
     :static-pub "5555555555555555555555555555555555555555555555555555555555555555"
     :overlay-ip "100.64.0.5" :key-expiry 1749996400 :status "pending"}
    {:id "a-server" :hostname "acme-db" :os "linux" :did "did:key:zAcmeDb"
     :user "bob" :tailnet "acme" :tags ["tag:server"]
     :static-pub "6666666666666666666666666666666666666666666666666666666666666666"
     :overlay-ip "100.64.1.1" :key-expiry 1757776000 :status "authorized"}
    {:id "a-cache" :hostname "acme-cache" :os "linux" :did "did:key:zAcmeCache"
     :user "bob" :tailnet "acme" :tags ["tag:cache"]
     :static-pub "7777777777777777777777777777777777777777777777777777777777777777"
     :overlay-ip "100.64.1.2" :key-expiry 1757776000 :status "authorized"}]
   :plane
   {:policies
    {"default"
     {:tag-owners {"tag:server" ["alice"] "tag:laptop" ["alice"] "tag:exit" ["alice"]}
      :grants [{:src ["tag:laptop"] :dst ["tag:server"] :ports [22 443]
                :capabilities [:overlay :ssh]}
               {:src ["alice"] :dst ["tag:server" "tag:exit"] :ports ["*"]}]}
     "acme"
     {:tag-owners {"tag:server" ["bob"] "tag:cache" ["bob"]}
      :grants [{:src ["bob"] :dst ["tag:server" "tag:cache"] :ports ["*"]}]}}
    :peerings
    [{:id "p-alice-acme" :a "default" :b "acme" :status "active"
      :approved-by ["acme"]
      :grants [{:from "default" :src ["tag:laptop"] :dst ["tag:cache"]
                :ports [443]}]}]}
   :heartbeats {"n-laptop" [{:last-seen 1750000000 :endpoint "203.0.113.7:41641"}]}
   :relays [{:name "jp-tyo-1" :region "jp" :host "relay.example"
             :port 41642 :key "abcd"}]
   :version 42})

(deftest the-projection-runs-unchanged-on-this-runtime
  (testing "kekkai.netmap is pure .cljc, so the CLI projects natively rather
            than shelling out to a JVM"
    (let [nm (netmap/publish plane "n-laptop")]
      (is (= 42 (:netmap/version nm)))
      (is (= "default" (:netmap/tailnet nm)))
      (is (= ["n-gw" "n-rogue" "n-server"]
             (mapv :node/id (:netmap/peers nm)))))))

(deftest the-signed-payload-is-byte-identical-to-the-jvm-publishers
  (if-not available?
    (println "  (skipped: ../kekkai/test/fixtures not checked out)")
    (let [nm (netmap/publish plane "n-laptop")
          committed (reader/read-string envelope-text)]
      (testing "the payload — this is the fragile part, and the reason it is a
                test: maps of eight keys or fewer are array-maps on both
                runtimes and print in insertion order. A nine-key map would
                print in hash order and the runtimes would silently disagree"
        (is (= (:netmap/payload-b64 committed)
               (.toString (sign/encode-payload nm) "base64"))))
      (testing "and therefore the digest"
        (is (= (:netmap/sha256 committed)
               (:netmap/sha256 (sign/seal nm authority)))))
      (testing "and therefore the signature — Ed25519 is deterministic, so
                identical bytes give an identical signature"
        (is (= (:netmap/signature-b64 committed)
               (:netmap/signature-b64 (sign/seal nm authority)))))
      (testing "the whole envelope, byte for byte"
        (is (= (str/trim envelope-text)
               (str/trim (sign/envelope-string (sign/seal nm authority)))))))))

(deftest what-this-cli-signs-the-node-verifier-accepts
  (if-not available?
    (println "  (skipped)")
    (let [nm (netmap/publish plane "n-server")
          envelope (sign/seal nm authority)
          text (sign/envelope-string envelope)
          back (signed/verify-envelope text (:public-b64 authority))]
      (testing "a freshly-signed netmap for a DIFFERENT node — not the fixture —
                goes through kekkai-node's independent verifier"
        (is (= "n-server" (get-in back [:netmap/self :node/id])))
        (is (= nm back)))
      (testing "and a different authority refuses it"
        (is (thrown? js/Error
                     (signed/verify-envelope
                      text
                      (:public-b64 (sign/generate-authority)))))))))

(deftest a-generated-authority-round-trips
  (let [id (sign/generate-authority)
        nm (netmap/publish plane "n-laptop")
        text (sign/envelope-string (sign/seal nm id))]
    (is (= nm (signed/verify-envelope text (:public-b64 id))))
    (testing "and the fingerprint is stable and short enough to read aloud"
      (is (= (sign/fingerprint (:public-b64 id))
             (sign/fingerprint (:public-b64 id))))
      (is (= 19 (count (sign/fingerprint (:public-b64 id))))))))

(deftest signing-without-a-key-is-refused
  (is (thrown? js/Error (sign/seal (netmap/publish plane "n-laptop") {})))
  (is (thrown? js/Error (sign/seal (netmap/publish plane "n-laptop")
                                   {:public-b64 "x"}))))
