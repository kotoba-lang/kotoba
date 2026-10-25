(ns authentication.adapters.siwe-edge
  "EIP-4361 Sign-In with Ethereum as an authentication factor at edge hosts.

  `siwe.edge` owns the strict message parser and EIP-191/secp256k1 recovery.
  This adapter owns the authentication policy around that crypto result:
  relying-party domain/URI, server nonce, accepted EIP-155 chains, temporal
  bounds, and an optional already-known subject.

  A successful proof authenticates the chain-bound principal
  `did:pkh:eip155:<chain-id>:<address>`. It is single-factor, never
  phishing-resistant: a wallet signature has no authenticator-enforced RP
  origin binding comparable to WebAuthn.

  The host remains responsible for issuing an unpredictable nonce and
  atomically consuming it. This adapter verifies the nonce inside the signed
  message; it deliberately does not pretend an in-memory set is durable replay
  protection for a distributed service."
  (:require [authentication.model :as m]
            [authentication.ports :as p]
            [siwe.edge :as siwe]))

(defn verify-claims
  "Verify a wallet response under relying-party `expected` policy.

  The response is `{:siwe/message <EIP-4361 text>
                    :siwe/signature <0x r||s||v>}`.
  `expected` is passed to `siwe.edge/verify` and should normally bind at least
  `:domain`, `:uri`, `:nonce`, `:chain-ids`, and a clock. `:expect-subject`
  additionally binds the recovered did:pkh when the caller already knows who
  is re-authenticating. Returns a non-throwing authentication claim map."
  [{:siwe/keys [message signature]} {:keys [expect-subject] :as expected}]
  (if-not (and (string? message) (string? signature))
    {:ok? false :error :missing-siwe-proof}
    (let [verified (siwe/verify message signature (dissoc expected :expect-subject))
          principal (:principal verified)]
      (cond
        (not (:valid? verified))
        {:ok? false :subject principal :error (:problem verified)}

        (and expect-subject (not= expect-subject principal))
        {:ok? false :subject principal :error :subject-mismatch}

        :else
        {:ok? true
         :subject principal
         :evidence-ref principal
         :assurance :single-factor
         :at (get-in verified [:message :expiration-time])
         :address (:address verified)
         :chain-id (:chain-id verified)}))))

(defn siwe-factor-verifier
  "An `IAsyncFactorVerifier` for an EIP-4361 wallet proof.

  `expected` has the `siwe.edge/verify` policy keys. When a factor request has
  a subject and `:expect-subject` was not explicitly supplied, that subject is
  required by default. The returned protocol remains async so it composes with
  WebCrypto-backed factors even though noble's EOA recovery is synchronous."
  ([] (siwe-factor-verifier {}))
  ([expected]
   (reify p/IAsyncFactorVerifier
     (verify-factor-async! [_ factor-request response]
       (let [subject (:authn.factor-request/subject factor-request)
             expected (cond-> expected
                        (and subject (not (contains? expected :expect-subject)))
                        (assoc :expect-subject subject))
             claims (verify-claims response expected)]
         (js/Promise.resolve
          (m/factor (:authn.factor-request/id factor-request)
                    :siwe
                    (true? (:ok? claims))
                    {:subject (or (:subject claims) subject)
                     :evidence-ref (:evidence-ref claims)
                     :assurance (:assurance claims)
                     :at (:at claims)})))))))
