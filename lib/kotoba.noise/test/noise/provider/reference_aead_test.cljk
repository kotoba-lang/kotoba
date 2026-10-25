(ns noise.provider.reference-aead-test
  "`noise.provider.reference` routes AEAD through `chacha20.aead` and agrees
  with `noise.provider.noble` on seal output.

  Run from a west checkout (sibling `org-ietf-chacha20-poly1305`):
    npm run test:reference"
  (:require [cljs.test :refer [deftest is testing run-tests]]
            [noise.provider.noble :as noble]
            [noise.provider.reference :as reference]))

(defn- rand-bytes [n]
  (vec (js/Array.from (js/crypto.getRandomValues (js/Uint8Array. n)))))

(defn- utf8 [s]
  (vec (js/Array.from (.encode (js/TextEncoder.) s))))

(deftest reference-aead-matches-noble
  (let [noble-ports (noble/ports)
        ref-ports (reference/ports)
        k (rand-bytes 32)
        nonce (rand-bytes 12)
        ad (utf8 "noise-transcript-ad")
        pt (rand-bytes 96)]
    (testing "encrypt output matches noble"
      (is (= (noble/aead-encrypt k nonce ad pt)
             ((:aead-encrypt ref-ports) k nonce ad pt))))
    (testing "reference decrypt round-trips"
      (let [ct ((:aead-encrypt ref-ports) k nonce ad pt)]
        (is (= pt ((:aead-decrypt ref-ports) k nonce ad ct)))))
    (testing "aad mismatch fails closed"
      (let [ct ((:aead-encrypt ref-ports) k nonce ad pt)]
        (is (nil? ((:aead-decrypt ref-ports) k nonce (utf8 "other-ad") ct)))))))

(defn -main [& _]
  (run-tests 'noise.provider.reference-aead-test))
