(ns oauth2.pkce
  "PKCE (RFC 7636) code verifier/challenge. SHA-256 and secure randomness
  are injected host capabilities — a `sha256-fn` (`[string] -> byte
  sequence`) and a `random-bytes-fn` (`[n] -> byte sequence`) — so this
  namespace stays zero third-party runtime deps, portable `.cljc`. The
  base64url codec is a small local implementation (no `java.util.Base64`),
  same portability bar as `kotoba-lang/multiformats`."
  (:require [kotoba.lang.text :as str]))

;; ─────────────────────────── base64url ───────────────────────────

(def ^:private b64url-alphabet
  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")

(defn base64url-encode
  "Encode a sequence of byte values (0-255) as unpadded base64url."
  [bytes]
  (let [bs (vec bytes)
        n (count bs)]
    (loop [i 0 out []]
      (if (>= i n)
        (apply str out)
        (let [b0 (bit-and (nth bs i) 0xff)
              b1 (when (< (inc i) n) (bit-and (nth bs (inc i)) 0xff))
              b2 (when (< (+ i 2) n) (bit-and (nth bs (+ i 2)) 0xff))
              triple (bit-or (bit-shift-left b0 16)
                              (bit-shift-left (or b1 0) 8)
                              (or b2 0))
              c0 (nth b64url-alphabet (bit-and (bit-shift-right triple 18) 0x3f))
              c1 (nth b64url-alphabet (bit-and (bit-shift-right triple 12) 0x3f))
              c2 (nth b64url-alphabet (bit-and (bit-shift-right triple 6) 0x3f))
              c3 (nth b64url-alphabet (bit-and triple 0x3f))]
          (recur (+ i 3)
                 (conj out
                       (cond
                         (nil? b1) (str c0 c1)
                         (nil? b2) (str c0 c1 c2)
                         :else (str c0 c1 c2 c3)))))))))

(defn base64url-decode
  "Decode an unpadded (or padded) base64url string to a vector of byte
  values (0-255)."
  [s]
  (let [clean (str/replace s #"=+$" "")
        idx (fn [ch] (str/index-of b64url-alphabet ch))
        chars (vec clean)
        n (count chars)]
    (vec
     (loop [i 0 out []]
       (if (>= i n)
         out
         (let [c0 (idx (nth chars i))
               c1 (when (< (inc i) n) (idx (nth chars (inc i))))
               c2 (when (< (+ i 2) n) (idx (nth chars (+ i 2))))
               c3 (when (< (+ i 3) n) (idx (nth chars (+ i 3))))
               n-chars (- n i)
               triple (bit-or (bit-shift-left c0 18)
                               (bit-shift-left (or c1 0) 12)
                               (bit-shift-left (or c2 0) 6)
                               (or c3 0))
               b0 (bit-and (bit-shift-right triple 16) 0xff)
               b1 (bit-and (bit-shift-right triple 8) 0xff)
               b2 (bit-and triple 0xff)]
           (recur (+ i 4)
                  (into out
                        (cond
                          (>= n-chars 4) [b0 b1 b2]
                          (= n-chars 3) [b0 b1]
                          (= n-chars 2) [b0]
                          :else [])))))))))

;; ──────────────────────────────── PKCE ────────────────────────────────

(defn generate-code-verifier
  "Generate an RFC 7636 §4.1 code verifier: 32 random bytes, base64url
  encoded (43 chars — within the required [43,128] length). `random-bytes-fn`
  is an injected `[n] -> byte sequence` secure-randomness capability."
  [random-bytes-fn]
  (base64url-encode (random-bytes-fn 32)))

(defn code-challenge
  "RFC 7636 §4.2 S256 code challenge for `verifier`: base64url(sha256(verifier)).
  `sha256-fn` is an injected `[string] -> byte sequence` digest capability.
  Returns `{:code-challenge ... :code-challenge-method \"S256\"}`, ready to
  splice into `oauth2.core/authorization-url`."
  [verifier sha256-fn]
  {:code-challenge (base64url-encode (sha256-fn verifier))
   :code-challenge-method "S256"})
