(ns argon2.vectors
  "Known answers, and where each one comes from.

  Three independent implementations agree on every value below, which is why
  they are here rather than a round-trip suite: an Argon2 that agrees only
  with itself is worth nothing.

  `:rfc9106-*` are RFC 9106 §5.1–5.3 verbatim — the only complete Argon2
  vectors in the specification, covering all three variants with a secret and
  associated data supplied, which nothing else here exercises.

  `:pqh-*` come from `kotoba-lang/pqh`'s `test/kotoba/lang/pqh/vectors.edn`,
  whose docstring records them as verified byte-identical against
  `@noble/hashes`. They matter because they use the OWASP-recommended
  parameters a real password path would, which the RFC's 32 KiB vectors do
  not.

  All five were independently reproduced with BouncyCastle 1.78.1
  (`Argon2BytesGenerator`) before this implementation was written, so the
  oracle existed before the code did rather than being fitted to it."
  (:require [argon2.core :as a]))

(def rfc-password (vec (repeat 32 0x01)))
(def rfc-salt (vec (repeat 16 0x02)))
(def rfc-secret (vec (repeat 8 0x03)))
(def rfc-ad (vec (repeat 12 0x04)))

(def rfc-params
  {:password rfc-password :salt rfc-salt :secret rfc-secret
   :associated-data rfc-ad :parallelism 4 :memory-kib 32
   :iterations 3 :tag-length 32})

(def rfc
  [{:name "rfc9106-argon2d"  :type :argon2d
    :tag "512b391b6f1162975371d30919734294f868e3be3984f3c1a13a4db9fabe4acb"}
   {:name "rfc9106-argon2i"  :type :argon2i
    :tag "c814d9d1dc7f37aa13f0d77f2494bda1c8de6b016dd388d29952a4c4672b6ce8"}
   {:name "rfc9106-argon2id" :type :argon2id
    :tag "0d640df58d78766c08c037a34a8b53c9d01ef0452d75b65eb52520e96b01e659"}])

(def pqh
  [{:name "pqh-argon2id"
    :opts {:type :argon2id
           :password (a/unhex "636f727265637420686f727365206261747465727920737461706c65")
           :salt (a/unhex "433fd54e9abcbdd3707ad85157d1784b")
           :memory-kib 19456 :iterations 2 :parallelism 1 :tag-length 32}
    :tag "b7f32b137dec5bf12c2df0905d513d3bf1b9c7a3ae1c9244b6459a1e5174183c"}
   {:name "pqh-argon2id-2"
    :opts {:type :argon2id
           :password (a/unhex "707732")
           :salt (a/unhex "433fd54e9abcbdd3707ad85157d1784b")
           :memory-kib 8192 :iterations 3 :parallelism 1 :tag-length 32}
    :tag "6e1d4c73e0f353ca56965b9b07f142a5929b696795cb28846298b39dd65319eb"}])
