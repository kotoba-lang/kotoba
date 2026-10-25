(ns chacha20.core
  "[RFC 8439](https://www.rfc-editor.org/rfc/rfc8439) ChaCha20 — the stream
  cipher and its block function, in portable `.cljc`."
  (:require [chacha20.word :as w]))

(def ^:private constants
  "\"expand 32-byte k\" as four little-endian words. The specification fixes
  them; they are not a parameter and not a nothing-up-my-sleeve choice to
  re-derive."
  [0x61707865 0x3320646e 0x79622d32 0x6b206574])

(defn- quarter-round
  "RFC 8439 §2.1. Returns the four updated words."
  [a b c d]
  (let [a (w/add a b) d (w/rotl (w/xor d a) 16)
        c (w/add c d) b (w/rotl (w/xor b c) 12)
        a (w/add a b) d (w/rotl (w/xor d a) 8)
        c (w/add c d) b (w/rotl (w/xor b c) 7)]
    [a b c d]))

(defn- qr!
  "Apply a quarter round to four positions of a 16-word state vector."
  [s i j k l]
  (let [[a b c d] (quarter-round (nth s i) (nth s j) (nth s k) (nth s l))]
    (-> s (assoc i a) (assoc j b) (assoc k c) (assoc l d))))

(defn- double-round
  "RFC 8439 §2.3.1: four column rounds, then four diagonal rounds. The
  diagonal pattern is the whole reason ChaCha mixes across the state rather
  than within four independent columns."
  [s]
  (-> s
      (qr! 0 4 8 12) (qr! 1 5 9 13) (qr! 2 6 10 14) (qr! 3 7 11 15)
      (qr! 0 5 10 15) (qr! 1 6 11 12) (qr! 2 7 8 13) (qr! 3 4 9 14)))

(defn state
  "The 16-word initial state, RFC 8439 §2.3: constants, eight key words, the
  counter, three nonce words."
  [key counter nonce]
  (into (into (vec constants)
              (mapv #(w/le32 key (* 4 %)) (range 8)))
        (into [(w/u32 counter)]
              (mapv #(w/le32 nonce (* 4 %)) (range 3)))))

(defn- hchacha-state
  "HChaCha20 initial state: constants, eight key words, four nonce words (no
  counter). Used by XChaCha extended-nonce construction."
  [key nonce16]
  (into (into (vec constants)
              (mapv #(w/le32 key (* 4 %)) (range 8)))
        (mapv #(w/le32 nonce16 (* 4 %)) (range 4))))

(defn hchacha-subkey
  "HChaCha20(key[32], nonce16[16]) -> 32-byte subkey. Pure permutation with no
  feedforward addition (unlike `block`)."
  [key nonce16]
  (let [key (vec key) nonce16 (vec nonce16)]
    (cond
      (not= 32 (count key)) {:status :error :reason :bad-key-length :length (count key)}
      (not= 16 (count nonce16)) {:status :error :reason :bad-nonce-length :length (count nonce16)}
      :else
      (let [s (nth (iterate double-round (hchacha-state key nonce16)) 10)
            out-idx [0 1 2 3 12 13 14 15]]
        {:status :ok
         :bytes (vec (mapcat (fn [i] (w/word->le (nth s i))) out-idx))}))))

(defn hchacha-subkey!
  [key nonce16]
  (let [r (hchacha-subkey key nonce16)]
    (if (= :ok (:status r)) (:bytes r)
        (throw (ex-info (str "hchacha: " (name (:reason r))) r)))))

(defn block
  "One 64-byte keystream block."
  [key counter nonce]
  (let [s0 (state key counter nonce)
        s (nth (iterate double-round s0) 10)]
    (vec (mapcat (fn [i] (w/word->le (w/add (nth s i) (nth s0 i)))) (range 16)))))

(defn encrypt
  "XOR `data` with the keystream, RFC 8439 §2.4.

  `counter` is the first block counter: **1** for the AEAD's payload and 0
  when the block function is being used to derive a key. Encryption and
  decryption are the same operation, which is why there is one function."
  [key counter nonce data]
  (let [data (vec data)]
    (cond
      (not= 32 (count key)) {:status :error :reason :bad-key-length :length (count key)}
      (not= 12 (count nonce)) {:status :error :reason :bad-nonce-length :length (count nonce)}
      :else
      {:status :ok
       :bytes (vec (mapcat (fn [i]
                             (let [ks (block key (+ counter i) nonce)
                                   chunk (subvec data (* 64 i)
                                                 (min (count data) (* 64 (inc i))))]
                               (map bit-xor chunk ks)))
                           (range (quot (+ (count data) 63) 64))))})))

(defn encrypt!
  [key counter nonce data]
  (let [r (encrypt key counter nonce data)]
    (if (= :ok (:status r))
      (:bytes r)
      (throw (ex-info (str "chacha20: " (name (:reason r))) r)))))
