(ns kotoba.crypto.aead-provider
  "aead-provider -- addressed on its own.

  Split out of kotoba.lang.crypto on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.crypto.aead :refer [AEAD decrypt encrypt]]
            [kotoba.crypto.validate-provider :refer [validate-provider]])
)

(defn aead-provider
  "Registers a host-injected AEAD cipher with its provider metadata (the
  injection boundary). Validates the provider record at registration —
  hosts cannot inject a cipher without declaring :provider/id and
  :provider/fips-validated. Returns {:aead .. :provider ..}."
  [aead provider]
  (when-not (satisfies? AEAD aead)
    (throw (ex-info "crypto: AEAD implementation required" {:aead aead})))
  {:aead aead :provider (validate-provider provider)})
