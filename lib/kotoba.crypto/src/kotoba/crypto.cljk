(ns kotoba.crypto
  "Assembled from one repo per definition.

  This namespace holds no implementation. It re-exports the definitions
  that each live in their own repo, so a call site can require one name
  and a library can require only the definitions it actually uses.

  AN IMPLEMENTATION BUILT AGAINST kotoba.lang.crypto IS NOT ACCEPTED HERE.
  kotoba.lang.crypto still declares IAEAD, and a protocol split into its own
  repo is a DIFFERENT protocol from the one the source namespace declares
  (ADR-2609091900). Measured 2026-09-09 on kotoba.lang.fs: a filesystem
  reified against the source protocol answers through the source namespace
  and fails through this one -- No implementation of method: :exists?.
  Build the implementation against the repo that declares the protocol here,
  or call through kotoba.lang.crypto.

  NOT re-exported here, on purpose: IAEAD. A protocol's identity is what extend-type and reify dispatch on,
  and a copy would make an implementation silently extend nothing, so the
  protocol name stays in the one repo that declares it. Requiring that repo
  is a compile error away; a copy would not be.

  Value vars are not re-exported either: default-digest-fn. `(def x other/x)` copies, which is harmless for a function and makes
  with-redefs through this namespace a SILENT no-op for a value -- measured
  on kotoba.lang.edn, where three assertions passed against nothing at all.
  Require the repo that defines the value.
"
  (:refer-clojure :exclude [hash])
  (:require [kotoba.crypto.aead :as iaead-ns]
            [kotoba.crypto.aead-provider :as aead-provider-ns]
            [kotoba.crypto.envelope-metadata :as envelope-metadata-ns]
            [kotoba.crypto.hash :as hash-ns]
            [kotoba.crypto.hkdf :as hkdf-ns]
            [kotoba.crypto.hmac :as hmac-ns]
            [kotoba.crypto.mock-aead :as mock-aead-ns]
            [kotoba.crypto.seal :as seal-ns]
            [kotoba.crypto.unseal :as unseal-ns]
            [kotoba.crypto.validate-provider :as validate-provider-ns]))

(def aead-provider "See kotoba.crypto.aead-provider/aead-provider." aead-provider-ns/aead-provider)
(def decrypt "See kotoba.crypto.aead/decrypt." iaead-ns/decrypt)
(def encrypt "See kotoba.crypto.aead/encrypt." iaead-ns/encrypt)
(def envelope-metadata "See kotoba.crypto.envelope-metadata/envelope-metadata." envelope-metadata-ns/envelope-metadata)
(def hash "See kotoba.crypto.hash/hash." hash-ns/hash)
(def hkdf "See kotoba.crypto.hkdf/hkdf." hkdf-ns/hkdf)
(def hmac "See kotoba.crypto.hmac/hmac." hmac-ns/hmac)
(def mock-aead "See kotoba.crypto.mock-aead/mock-aead." mock-aead-ns/mock-aead)
(def seal "See kotoba.crypto.seal/seal." seal-ns/seal)
(def unseal "See kotoba.crypto.unseal/unseal." unseal-ns/unseal)
(def validate-provider "See kotoba.crypto.validate-provider/validate-provider." validate-provider-ns/validate-provider)
