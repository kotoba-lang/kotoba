(ns provider.entropy-transport
  "Production CSPRNG draw for `provider.entropy` (ADR 0151).

  Does NOT define a new capability. Builds `(fn [{:keys [n]}] -> reply)`
  for injection as `:draw`.

  ## Sources

  ### `mem-draw`
  Deterministic test double (delegates to `provider.entropy/mem-draw`).

  ### `os-draw`
  - **`:clj`** — `java.security.SecureRandom`
  - **`:cljs` / nbb / browser** — `crypto.getRandomValues` (Web Crypto /
    Node global crypto)

  No PRNG seeding from wall clock. No ambient Math/random."
  (:require [provider.entropy :as entropy])
  #?(:clj (:import (java.security SecureRandom))))

(defn mem-draw
  "Host-sealed deterministic draw — see `provider.entropy/mem-draw`."
  [seed-bytes]
  (entropy/mem-draw seed-bytes))

#?(:clj
   (defn os-draw
     "Build a SecureRandom draw transport (JVM).

     opts:
       :random  optional SecureRandom instance (tests)"
     ([] (os-draw {}))
     ([{:keys [random]}]
      (let [^SecureRandom rng (or random (SecureRandom.))]
        (fn [{:keys [n]}]
          (try
            (let [buf (byte-array (int n))]
              (.nextBytes rng buf)
              {:tag :bytes
               :bytes (mapv #(bit-and % 0xff) buf)})
            (catch Exception e
              {:tag :error
               :code :entropy/draw
               :message (or (.getMessage e) "SecureRandom failed")})))))))

#?(:cljs
   (defn- web-crypto
     "Return global crypto or nil."
     []
     (cond
       (exists? js/crypto) js/crypto
       (and (exists? js/globalThis) (.-crypto js/globalThis)) (.-crypto js/globalThis)
       (and (exists? js/require)
            (try (js/require "crypto") (catch :default _ nil)))
       (let [c (js/require "crypto")]
         (or (.-webcrypto c) c))
       :else nil)))

#?(:cljs
   (defn os-draw
     "Build a getRandomValues draw transport (cljs/nbb/browser).

     opts:
       :crypto  optional crypto object with getRandomValues (tests)"
     ([] (os-draw {}))
     ([{:keys [crypto]}]
      (let [c (or crypto (web-crypto))]
        (when-not (and c (fn? (.-getRandomValues c)))
          (throw (ex-info "entropy-transport/os-draw requires WebCrypto getRandomValues"
                          {:phase :entropy-transport})))
        (fn [{:keys [n]}]
          (try
            (let [buf (js/Uint8Array. n)]
              (.getRandomValues c buf)
              {:tag :bytes
               :bytes (mapv (fn [i] (aget buf i)) (range n))})
            (catch :default e
              {:tag :error
               :code :entropy/draw
               :message (or (.-message e) "getRandomValues failed")})))))))
