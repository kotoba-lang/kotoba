(ns noise.provider.reference-hash-test
  "`noise.provider.reference` routes SHA-256 through `sha2.core` and agrees
  with `noise.provider.noble` on digest output. BLAKE2s is not substituted here.

  Run from a west checkout (sibling `org-nist-sha2`):
    npm run test:reference-hashes"
  (:require [cljs.test :refer [deftest is testing run-tests]]
            [noise.provider.noble :as noble]
            [noise.provider.reference :as reference]
            ["@noble/hashes/sha2.js" :refer [sha256]]))

(defn- bytes= [a b]
  (and (= (.-length a) (.-length b))
       (every? #(= (aget a %) (aget b %)) (range (.-length a)))))

(deftest reference-sha256-matches-noble
  (let [noble-ports (noble/ports {:hash :sha256})
        ref-ports (reference/ports {:hash :sha256})]
    (testing "empty input"
      (let [empty (js/Uint8Array. 0)]
        (is (bytes= (sha256 empty)
                    (js/Uint8Array.from (clj->js ((:hash ref-ports) empty)))))))
    (testing "random block"
      (let [bs (js/crypto.getRandomValues (js/Uint8Array. 128))]
        (is (= ((:hash noble-ports) (vec (js/Array.from bs)))
               ((:hash ref-ports) (vec (js/Array.from bs)))))))))

(defn -main [& _]
  (run-tests 'noise.provider.reference-hash-test))
