(ns noise.hash.reference
  "SHA-256 through first-party `sha2.core` for `@noble/hashes` host substitution.

  BLAKE2s stays on `provider/noble` — handshake hot path; do not route it
  through pure `noise.blake2s` without measurement (ADR-2608301100)."
  (:require [sha2.core :as sha2]))

(defn- u8-vec [^js u8] (vec (js/Array.from u8)))

(defn- vec-u8 [v] (js/Uint8Array.from (clj->js v)))

(defn sha256
  "byte-vector → 32-byte digest via `org-nist-sha2`."
  [bs]
  (vec-u8 (sha2/sha256 (u8-vec bs))))
