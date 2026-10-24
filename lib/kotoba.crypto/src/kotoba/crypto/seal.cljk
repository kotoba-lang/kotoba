(ns kotoba.crypto.seal
  "seal -- addressed on its own.

  Split out of kotoba.lang.crypto on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.crypto.aead :refer [AEAD decrypt encrypt]]
            [kotoba.crypto.envelope-metadata :refer [envelope-metadata]])
)

(defn seal
  "Encrypts with a registered AEAD provider (see `aead-provider`) and returns
  an envelope map carrying the ciphertext plus :envelope/* metadata:
  {:ciphertext bytes :tag bytes :envelope/algorithms .. :envelope/provider ..
   :envelope/epoch .. :envelope/kem? .. :envelope/hybrid? ..}.
  Algorithms default to the provider's :provider/algorithms; `opts` may set
  :algorithms, :epoch (default 0), :kem?, :hybrid? (default false)."
  ([registered key nonce plaintext aad]
   (seal registered key nonce plaintext aad {}))
  ([registered key nonce plaintext aad opts]
   (let [{:keys [aead provider]} registered
         algorithms (or (:algorithms opts) (:provider/algorithms provider))]
     (merge (encrypt aead key nonce plaintext aad)
            (envelope-metadata provider algorithms opts)))))
