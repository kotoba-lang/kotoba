(ns kagami.did
  "did:key encode/decode for ed25519 (Phase 2, ADR-2607160005).
  did:key:z6Mk... = multibase base58btc of (0xed 0x01 + raw 32-byte pubkey).
  Pure cljc; bignum arithmetic via js/BigInt (:cljs) / BigInteger (:clj)."
  (:require [kotoba.lang.text :as str]))

(def ^:private alphabet "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")

(defn hex->bytes [h]
  (mapv #(#?(:clj Integer/parseInt :cljs js/parseInt) (subs h % (+ % 2)) 16)
        (range 0 (count h) 2)))

(defn bytes->hex [bs]
  (apply str (map #(let [s #?(:clj (Integer/toString (int %) 16) :cljs (.toString % 16))]
                     (if (= 1 (count s)) (str "0" s) s))
                  bs)))

;; generic bignum ops over the host's big integer type
(defn- big [x] #?(:cljs (js/BigInt x) :clj (biginteger x)))
(defn- big-zero? [n] #?(:cljs (= n (js/BigInt 0)) :clj (zero? (.signum ^java.math.BigInteger n))))
(defn- big-add-mul [acc m x] #?(:cljs (+ (* acc (big m)) (big x))
                                :clj (.add (.multiply ^java.math.BigInteger acc (big m)) (big x))))
(defn- big-divmod [n d]
  #?(:cljs (let [q (/ n (big d))] [q (js/Number (- n (* q (big d))))])
     :clj (let [[q r] (.divideAndRemainder ^java.math.BigInteger n (big d))]
            [q (.intValue ^java.math.BigInteger r)])))

(defn- bytes->base58 [bs]
  (let [n (reduce (fn [acc b] (big-add-mul acc 256 b)) (big 0) bs)
        zeros (count (take-while zero? bs))]
    (loop [n n out ""]
      (if (big-zero? n)
        (str (apply str (repeat zeros "1")) out)
        (let [[q r] (big-divmod n 58)]
          (recur q (str (nth alphabet r) out)))))))

(defn- base58->bytes [s n-bytes]
  (let [n (reduce (fn [acc c] (big-add-mul acc 58 (str/index-of alphabet c)))
                  (big 0) s)]
    (loop [n n out ()]
      (if (>= (count out) n-bytes)
        (vec out)
        (let [[q r] (big-divmod n 256)]
          (recur q (conj out r)))))))

(defn pubkey-hex->did
  "raw ed25519 pubkey hex (64 chars) -> did:key:z6Mk..."
  [pubkey-hex]
  (str "did:key:z" (bytes->base58 (into [0xed 0x01] (hex->bytes pubkey-hex)))))

(defn did->pubkey-hex
  "did:key:z... -> raw pubkey hex. Throws on non-ed25519 or malformed."
  [did]
  (when-not (str/starts-with? did "did:key:z")
    (throw (ex-info "not a did:key" {:did did})))
  (let [bs (base58->bytes (subs did (count "did:key:z")) 34)]
    (when-not (= [0xed 0x01] (subvec bs 0 2))
      (throw (ex-info "not an ed25519 did:key" {:did did})))
    (bytes->hex (subvec bs 2))))
