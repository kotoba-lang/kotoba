(ns authentication.siwe-edge-smoke
  (:require [authentication.adapters.siwe-edge :as adapter]
            [authentication.async :as async]
            [authentication.model :as m]
            [siwe.core :as core]
            [siwe.edge :as edge]
            ["@noble/curves/secp256k1.js" :refer [secp256k1]]
            ["@noble/hashes/sha3.js" :refer [keccak_256]]))

(def now-sec (/ (js/Date.parse "2026-08-25T04:01:00.000Z") 1000))
(def domain "auth.kotobase.net")
(def uri "https://auth.kotobase.net/sign-in")
(def nonce "AbCdEf1234567890")
(def private-key (js/Uint8Array.from (clj->js (range 1 33))))
(def failures (atom []))

(defn check! [label ok?]
  (if ok?
    (js/console.log "ok  -" label)
    (do (js/console.error "FAIL-" label) (swap! failures conj label))))

(defn- bytes->hex [bytes]
  (apply str (map #(let [h (.toString % 16)] (if (= 1 (count h)) (str "0" h) h))
                  (array-seq bytes))))

(def public-key (secp256k1.getPublicKey private-key false))
(def address
  (edge/checksum-address
   (str "0x" (subs (bytes->hex (keccak_256 (.slice public-key 1))) 24))))

(def message
  (core/format-message
   {:scheme "https" :domain domain :address address
    :statement "Sign in without a transaction." :uri uri :version "1"
    :chain-id "1" :nonce nonce
    :issued-at "2026-08-25T04:00:00.000Z"
    :expiration-time "2026-08-25T04:05:00.000Z"
    :resources ["https://kotobase.net/"]}))

(def signature
  (let [recovered (secp256k1.sign (edge/eip191-digest message) private-key
                                   #js {:lowS true :prehash false
                                        :format "recovered"})
        out (js/Uint8Array. 65)]
    (.set out (.slice recovered 1) 0)
    (aset out 64 (+ 27 (aget recovered 0)))
    (str "0x" (bytes->hex out))))

(def principal (str "did:pkh:eip155:1:" (.toLowerCase address)))

(defn- decide [subject expected response]
  (async/authenticate!
   {:siwe (adapter/siwe-factor-verifier expected)}
   (m/request "request-1" subject {:required-level :single-factor})
   [(m/factor-request "siwe-1" :siwe {:subject subject})]
   [(merge {:authn.factor-response/request-id "siwe-1"} response)]))

(defn run []
  (let [policy {:domain domain :uri uri :nonce nonce :chain-ids #{"1"}
                :now-sec now-sec :max-age-sec 300 :clock-skew-sec 60
                :require-expiration? true}]
    (-> (js/Promise.all
         #js [(decide principal policy {:siwe/message message :siwe/signature signature})
              (decide nil policy {:siwe/message message :siwe/signature signature})
              (decide "did:pkh:eip155:1:0x0000000000000000000000000000000000000000"
                      policy {:siwe/message message :siwe/signature signature})
              (decide principal (assoc policy :nonce "WrongNonce123")
                      {:siwe/message message :siwe/signature signature})
              (decide principal policy {:siwe/message message :siwe/signature
                                         (str (subs signature 0 (dec (count signature)))
                                              (if (= "0" (subs signature (dec (count signature))))
                                                "1" "0"))})
              (decide principal policy {})])
        (.then
         (fn [[ok discovered wrong-sub wrong-nonce bad-signature missing]]
           (check! "a real EIP-191 wallet proof authenticates did:pkh"
                   (= :authenticated (:authn.decision/decision ok)))
           (check! "the chain-bound principal is the factor subject"
                   (= principal (-> ok :authn.decision/factors first :authn.factor/subject)))
           (check! "SIWE remains single-factor"
                   (= :single-factor (:authn.decision/level ok)))
           (check! "a subject-less first sign-in learns the wallet principal"
                   (= :authenticated (:authn.decision/decision discovered)))
           (check! "a valid proof cannot authenticate another subject"
                   (= :challenge (:authn.decision/decision wrong-sub)))
           (check! "nonce mismatch is refused"
                   (= :challenge (:authn.decision/decision wrong-nonce)))
           (check! "tampered signatures are refused"
                   (= :challenge (:authn.decision/decision bad-signature)))
           (check! "missing proofs fail closed without throwing"
                   (= :challenge (:authn.decision/decision missing)))))
        (.then (fn [_]
                 (if (seq @failures)
                   (do (js/console.error "FAILED:" (count @failures) (pr-str @failures))
                       (set! (.-exitCode js/process) 1))
                   (js/console.log "SIWE edge factor verifier smoke: all checks passed"))))
        (.catch (fn [error]
                  (js/console.error "threw:" error)
                  (set! (.-exitCode js/process) 1))))))

(run)
