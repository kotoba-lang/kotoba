(ns biscuit.keys
  "A deterministic signature stand-in.

  Not Ed25519. This library injects `sign-fn`/`verify-fn` and owns no crypto,
  so what the suite can honestly check is the **chain shape**: that a block is
  validated against the key its predecessor named, that splicing fails, that
  editing a block fails. Those hold for any signature scheme, and a real
  Ed25519 binding is a deployment concern (`kotoba-lang/ed25519`).

  What this stand-in must NOT do is be forgeable in a way that hides a chain
  defect, so it binds the payload and the key together and nothing else."
  (:require [kotoba.lang.text :as str]))

(defn keypair [seed] {:private (str "priv:" seed) :public (str "pub:" seed)})

(defn sign-fn [private-key payload]
  (str "sig(" (str/replace (str private-key) "priv:" "") "|" (hash payload) ")"))

(defn verify-fn [public-key payload signature]
  (= signature (str "sig(" (str/replace (str public-key) "pub:" "") "|" (hash payload) ")")))
