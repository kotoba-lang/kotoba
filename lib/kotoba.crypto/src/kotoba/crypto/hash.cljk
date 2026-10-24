(ns kotoba.crypto.hash
  "hash -- addressed on its own.

  Split out of kotoba.lang.crypto on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:refer-clojure :exclude [hash])
  (:require [kotoba.crypto.default-digest-fn :refer [default-digest-fn]])
)

(defn hash
  "Hash `data` (byte seq) with `algo` (:sha256 default, :sha512). Returns a byte
  array. Uses the default JVM digest fn unless `:digest-fn` is supplied."
  ([data] (hash :sha256 data))
  ([algo data] (hash algo data default-digest-fn))
  ([algo data digest-fn]
   (digest-fn algo (vec data))))
