(ns ipns.core
  "EDN-first helpers for libp2p-key IPNS names — the 'k51...' CIDv1
  (identity-multihash over the libp2p PublicKey protobuf) derived from an
  Ed25519 public key. Portable .cljc, no BigInteger (same manual digit-array
  style as kotoba-lang/did's base58btc), so it runs identically on JVM and
  ClojureScript.

  An actor's graph IS its key: holding the Ed25519 private key is authority
  over the graph named by `pubkey->name` — no registrar, no owner hand-off,
  no shared token (see kotoba-lang/kekkai `cacao.clj` and kotoba-lang/kagi
  `identity.clj`, the two JVM actor-identity call sites this library
  replaces the copy-pasted derivation in)."
  (:require [kotoba.lang.text :as str]))

(def ^:private b36-alphabet "0123456789abcdefghijklmnopqrstuvwxyz")

(def ^:private b36-idx
  (into {} (map-indexed (fn [i c] [c i]) b36-alphabet)))

(defn- ->byte-seq
  "Normalize a byte-array or int seq to a seq of 0..255 ints, so callers can
  pass either JVM `byte[]` (signed) or plain Clojure int vectors."
  [data]
  (map #(bit-and (int %) 0xff) (seq data)))

(defn base36
  "Encode byte ints (or a byte-array) to lowercase base36, prefixing one '0'
  digit per leading zero input byte (multibase convention, same shape as
  did.core/base58btc)."
  [data]
  (let [in (->byte-seq data)
        digits (reduce
                (fn [digits b]
                  (let [[digits carry]
                        (reduce (fn [[ds carry] d]
                                  (let [v (+ (* d 256) carry)]
                                    [(conj ds (rem v 36)) (quot v 36)]))
                                [[] b] digits)]
                    (loop [digits digits carry carry]
                      (if (pos? carry)
                        (recur (conj digits (rem carry 36)) (quot carry 36))
                        digits))))
                [] in)
        nzeros (count (take-while zero? in))]
    (str (apply str (repeat nzeros \0))
         (apply str (map #(nth b36-alphabet %) (rseq digits))))))

(defn base36-decode
  "Decode lowercase base36 to a byte int vector. Inverse of `base36`."
  [s]
  (let [bytes (reduce
               (fn [bs c]
                 (let [idx (or (b36-idx c)
                               (throw (ex-info "bad base36 character" {:char c})))
                       [bs carry]
                       (reduce (fn [[acc carry] d]
                                 (let [v (+ (* d 36) carry)]
                                   [(conj acc (rem v 256)) (quot v 256)]))
                               [[] idx] bs)]
                   (loop [bs bs carry carry]
                     (if (pos? carry)
                       (recur (conj bs (rem carry 256)) (quot carry 256))
                       bs))))
               [] (seq s))
        nzeros (count (take-while #(= \0 %) s))]
    (vec (concat (repeat nzeros 0) (rseq bytes)))))

(defn pubkey->name
  "Ed25519 raw public key (32 bytes: int-seq or byte-array) -> the actor's
  key-derived libp2p-key IPNS name ('k51...'): a CIDv1 wrapping an identity
  multihash of the libp2p PublicKey protobuf. Holding the private key IS
  authority over this name."
  [pub]
  (let [raw (->byte-seq pub)]
    (when-not (= 32 (count raw))
      (throw (ex-info "Ed25519 public key must be 32 bytes" {:got (count raw)})))
    (let [pb  (concat [0x08 0x01 0x12 0x20] raw)     ; libp2p PublicKey proto: key_type=Ed25519(1), len=32
          mh  (concat [0x00 (count pb)] pb)          ; identity multihash (code 0x00), single-byte len (<128)
          cid (concat [0x01 0x72] mh)]               ; CIDv1 (version 0x01), codec libp2p-key (0x72)
      (str "k" (base36 cid)))))

(defn name->pubkey
  "Inverse of `pubkey->name`: decode a 'k51...' IPNS name back to the raw
  32-byte Ed25519 public key (int vector). Throws if the name isn't a
  CIDv1/libp2p-key/identity-multihash wrapping a 32-byte Ed25519 protobuf key."
  [name]
  (when-not (str/starts-with? name "k")
    (throw (ex-info "expected a base36 'k'-prefixed IPNS name" {:name name})))
  (let [cid (base36-decode (subs name 1))]
    (when-not (and (>= (count cid) 2) (= 0x01 (first cid)) (= 0x72 (second cid)))
      (throw (ex-info "expected CIDv1 libp2p-key (0x01 0x72)" {:name name})))
    (let [mh (drop 2 cid)]
      (when-not (and (>= (count mh) 2) (= 0x00 (first mh)))
        (throw (ex-info "expected identity multihash (0x00)" {:name name})))
      (let [len (second mh)
            pb  (vec (take len (drop 2 mh)))]
        (when-not (and (= len (count pb)) (= len 36)
                       (= 0x08 (nth pb 0)) (= 0x01 (nth pb 1))
                       (= 0x12 (nth pb 2)) (= 0x20 (nth pb 3)))
          (throw (ex-info "expected libp2p Ed25519 PublicKey protobuf" {:name name})))
        (vec (drop 4 pb))))))

(defn name->pubkey*
  "`name->pubkey`, fail-closed: `nil` for anything that is not a well-formed
  Ed25519 libp2p-key name, instead of throwing.

  Exists so a VERIFIER can be written without a surrounding try/catch. A
  verifier that throws on a malformed name is a verifier whose caller has to
  remember to catch, and the one it forgets is the adversarial input."
  [name]
  (try (name->pubkey name)
       (catch #?(:clj Exception :cljs :default) _ nil)))

(defn name-matches-pubkey?
  "Does `name` name exactly `pub`?

  **This is the check that makes `pubkey->name`'s claim true.** This library
  says an actor's graph IS its key -- holding the private key is authority
  over the name, no registrar. That property only holds if every verifier
  resolves the authoritative key FROM THE NAME. A verifier that instead
  trusts a key the record carries alongside the name is verifying that
  somebody signed something, which any keypair can satisfy: an attacker
  generates their own, signs a record naming someone else's `k51...`, and it
  passes. `ipns.record/validate` already does the right thing (it derives the
  pubkey with `name->pubkey` and verifies against that); this predicate is
  the same discipline for the record shapes that carry an explicit key.

  `pub` may be a byte-array, an int seq, or a `js/Uint8Array`, matching
  `pubkey->name`'s own input contract. Fail-closed: `false` for a malformed
  name, a `nil` key, or a key of the wrong length -- never a throw."
  [name pub]
  (boolean
   (when (and (string? name) (some? pub))
     (when-let [expected (name->pubkey* name)]
       (= expected (vec (->byte-seq pub)))))))
