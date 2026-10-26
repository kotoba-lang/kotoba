(ns kotoba.capability.random.bytes.provider
  "JVM reference host provider for actor:host field \"random_bytes\".

  ABI: (ptr, len) -> bytes-written|-1 — pure surface here is
  `(fill! byte-array) -> same array` using SecureRandom.
  Memory-backed injection remains the embedder's job."
  (:import [java.security SecureRandom]))

(def ^:private rng (delay (SecureRandom.)))

(defn fill!
  "Fill a byte array with CSPRNG bytes; returns the same array."
  [^bytes dest]
  (.nextBytes ^SecureRandom @rng dest)
  dest)

(defn random-bytes
  "Allocate and fill `n` cryptographically secure random bytes."
  [n]
  (let [bs (byte-array (int n))]
    (fill! bs)))

(defn host-export
  []
  {:module "kotoba"
   :field "random_bytes"
   :params [:i32 :i32]
   :result :i32
   :fn random-bytes})
