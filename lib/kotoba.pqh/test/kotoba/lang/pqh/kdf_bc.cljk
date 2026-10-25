(ns kotoba.lang.pqh.kdf-bc
  "JVM BouncyCastle host impl of kotoba.lang.pqh.kdf/IKdf -- the raw Argon2id
   (RFC 9106) primitive.

   Lives under test/ (not src/) so the lib core stays vendor-free per
   ADR-2607012200: the pure core declares the IKdf seam, the host supplies a
   vetted impl. Consumers bring an equivalent impl on their own classpath.

   Correctly JVM-only .clj (not .cljc): directly imports org.bouncycastle.*
   to implement the raw primitive. BouncyCastle is a :test-scoped dep
   (deps.edn `:test` alias `org.bouncycastle/bcprov-jdk18on`, not `:deps`),
   so this is a test fixture, not a production seam impl -- a real cljs
   host impl would use @noble/hashes instead (see kdf.cljc)."
  (:require [kotoba.lang.pqh.kdf :as kdf])
  (:import (org.bouncycastle.crypto.generators Argon2BytesGenerator)
           (org.bouncycastle.crypto.params Argon2Parameters Argon2Parameters$Builder)))

(defn bc-kdf
  "Returns an IKdf backed by BouncyCastle's Argon2id (RFC 9106)."
  []
  (reify kdf/IKdf
    (-argon2id [_ password salt m-kib t p dk-len]
      (let [bc-params (-> (Argon2Parameters$Builder. Argon2Parameters/ARGON2_id)
                          (.withSalt ^bytes salt)
                          (.withParallelism (int p))
                          (.withMemoryAsKB (int m-kib))
                          (.withIterations (int t))
                          (.withVersion Argon2Parameters/ARGON2_VERSION_13)
                          (.build))
            gen (doto (Argon2BytesGenerator.) (.init bc-params))
            out (byte-array dk-len)]
        (.generateBytes gen ^bytes password out)
        out))))
