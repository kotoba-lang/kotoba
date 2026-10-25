(ns kotodama.verify.encrypted-lm-head
  "Executable proof receipt for ciphertext-only candidate LM-head inference."
  (:require [kotodama.inference.encrypted :as encrypted]
            [paillier.core :as phe]))

(def hidden [0.25 -0.5 1.0 0.75 -0.25 0.5 -0.75 0.125])
(def weights [[0.10 0.20 -0.30 0.40 0.05 -0.10 0.25 0.30]
              [-0.40 0.30 0.20 0.10 -0.20 0.15 0.05 -0.25]
              [0.50 -0.25 0.125 -0.75 0.30 0.10 -0.05 0.20]
              [-0.15 0.05 0.35 -0.10 0.40 -0.30 0.20 0.25]])
(def bias [0.05 -0.10 0.20 0.0])
(def token-ids [11 42 103 2048])
(def activation-scale 1000)
(def weight-scale 1000)

(defn- timed [f]
  (let [start (System/nanoTime)
        value (f)]
    {:value value
     :milliseconds (/ (- (System/nanoTime) start) 1.0e6)}))

(defn- max-error [left right]
  (reduce max (map #(Math/abs (- (double %1) (double %2))) left right)))

(defn -main [& _]
  (let [keygen (timed phe/generate-keypair)
        {:keys [public-key private-key]} (:value keygen)
        client (timed #(encrypted/prepare-lm-head-request
                        public-key hidden
                        {:activation-scale activation-scale
                         :hidden-bound 1.0}))
        request (:value client)
        second-request (encrypted/prepare-lm-head-request
                        public-key hidden
                        {:activation-scale activation-scale
                         :hidden-bound 1.0})
        server (timed #(encrypted/evaluate-lm-head
                        request weights bias
                        {:weight-scale weight-scale
                         :token-ids token-ids}))
        response (:value server)
        decrypt (timed #(encrypted/decrypt-lm-head-response private-key response))
        result (:value decrypt)
        quantized (encrypted/quantized-lm-head
                   hidden weights bias activation-scale weight-scale)
        plaintext (encrypted/plaintext-lm-head hidden weights bias)
        exact? (= (:integer-logits quantized)
                  (:kotodama/integer-logits result))
        randomized? (not= (get-in request
                                  [:kotodama.encrypted/hidden :ciphertexts])
                          (get-in second-request
                                  [:kotodama.encrypted/hidden :ciphertexts]))
        request-boundary? (= #{:shape :ciphertexts}
                             (set (keys (:kotodama.encrypted/hidden request))))
        response-boundary? (= #{:shape :ciphertexts :output-bounds}
                              (set (keys (:kotodama.encrypted/logits response))))]
    (when-not (and exact? randomized? request-boundary? response-boundary?)
      (throw (ex-info "encrypted LM-head proof failed"
                      {:exact? exact?
                       :randomized? randomized?
                       :request-boundary? request-boundary?
                       :response-boundary? response-boundary?})))
    (prn {:kotodama/encrypted-lm-head :ok
          :primitive-library :kotoba-lang/paillier
          :primitive-namespace 'paillier.core
          :primitive-wire-version :paillier-phe-v1
          :cryptographic-scope :paillier-linear-phe
          :not-proved [:full-transformer :nonlinear-layers :fhe]
          :key-bits (:bits public-key)
          :hidden-size (count hidden)
          :candidate-count (count weights)
          :ciphertexts-randomized? randomized?
          :request-contains-only-public-contract-and-ciphertexts? request-boundary?
          :response-contains-only-ciphertexts? response-boundary?
          :integer-logits-exact? exact?
          :plaintext-logits plaintext
          :decrypted-logits (:kotodama/logits result)
          :max-quantization-error (max-error plaintext (:kotodama/logits result))
          :selected-token-id (:kotodama/selected-token-id result)
          :timing-ms {:keygen (:milliseconds keygen)
                      :client-encrypt (:milliseconds client)
                      :server-encrypted-matvec (:milliseconds server)
                      :client-decrypt (:milliseconds decrypt)}})))
