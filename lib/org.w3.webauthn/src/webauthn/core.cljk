(ns webauthn.core
  "W3C WebAuthn relying-party ceremony data as EDN — builds the options
  objects the browser's `navigator.credentials` API needs, and validates
  the relying-party-checkable parts of the response. Real crypto (COSE
  key parsing, CBOR attestation-object decoding, signature verification)
  is host-injected; this stays zero-dep and portable.

  `bytes` throughout this namespace means a plain seq/vector of ints in
  [0 255] — not a platform byte array — so the same code runs unchanged
  on the JVM, ClojureScript, and SCI."
  (:require [kotoba.lang.text :as str]))

(def ^:private alphabet
  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")

(def ^:private char->val
  (into {} (map-indexed (fn [i c] [c i]) alphabet)))

(defn base64url-encode
  "Encode a seq of byte ints (0-255) to an unpadded base64url string."
  [bytes]
  (let [bytes (vec bytes)
        n (count bytes)]
    (loop [i 0 chunks []]
      (if (>= i n)
        (str/join chunks)
        (let [b0 (nth bytes i)
              b1 (when (< (inc i) n) (nth bytes (inc i)))
              b2 (when (< (+ i 2) n) (nth bytes (+ i 2)))
              triple (bit-or (bit-shift-left b0 16)
                             (bit-shift-left (or b1 0) 8)
                             (or b2 0))
              c0 (nth alphabet (bit-and (bit-shift-right triple 18) 0x3F))
              c1 (nth alphabet (bit-and (bit-shift-right triple 12) 0x3F))
              c2 (nth alphabet (bit-and (bit-shift-right triple 6) 0x3F))
              c3 (nth alphabet (bit-and triple 0x3F))
              chunk (cond
                      (nil? b1) (str c0 c1)
                      (nil? b2) (str c0 c1 c2)
                      :else (str c0 c1 c2 c3))]
          (recur (+ i 3) (conj chunks chunk)))))))

(defn base64url-decode
  "Decode an unpadded (or padded) base64url string to a vector of byte ints."
  [s]
  (let [s (str/replace s "=" "")
        n (count s)]
    (loop [i 0 out []]
      (if (>= i n)
        out
        (let [c0 (get char->val (nth s i))
              c1 (when (< (inc i) n) (get char->val (nth s (inc i))))
              c2 (when (< (+ i 2) n) (get char->val (nth s (+ i 2))))
              c3 (when (< (+ i 3) n) (get char->val (nth s (+ i 3))))
              sextet (bit-or (bit-shift-left c0 18)
                             (bit-shift-left (or c1 0) 12)
                             (bit-shift-left (or c2 0) 6)
                             (or c3 0))
              b0 (bit-and (bit-shift-right sextet 16) 0xFF)
              b1 (bit-and (bit-shift-right sextet 8) 0xFF)
              b2 (bit-and sextet 0xFF)
              bytes (cond
                      (nil? c2) [b0]
                      (nil? c3) [b0 b1]
                      :else [b0 b1 b2])]
          (recur (+ i 4) (into out bytes)))))))

(defn creation-options
  "Build a PublicKeyCredentialCreationOptions-shaped EDN map (kebab-case
  field names mirroring the spec) for navigator.credentials.create()."
  [{:keys [rp-id rp-name user-id user-name user-display-name challenge
           timeout attestation authenticator-selection pub-key-cred-params]
    :or {timeout 60000
         attestation "none"
         pub-key-cred-params [{:alg -7 :type "public-key"}
                               {:alg -257 :type "public-key"}]}}]
  {:rp {:id rp-id :name rp-name}
   :user {:id user-id :name user-name :display-name user-display-name}
   :challenge (base64url-encode challenge)
   :pub-key-cred-params pub-key-cred-params
   :timeout timeout
   :attestation attestation
   :authenticator-selection authenticator-selection})

(defn request-options
  "Build a PublicKeyCredentialRequestOptions-shaped EDN map for
  navigator.credentials.get()."
  [{:keys [rp-id challenge timeout allow-credentials user-verification]
    :or {timeout 60000 user-verification "preferred"}}]
  {:rp-id rp-id
   :challenge (base64url-encode challenge)
   :timeout timeout
   :allow-credentials allow-credentials
   :user-verification user-verification})

(defn verify-client-data
  "Relying-party checks on an already JSON-decoded clientDataJSON map
  (WebAuthn §7.1/§7.2). Never throws; returns {:valid? bool :errors [...]}."
  [decoded-client-data {:keys [expected-type expected-challenge expected-origin]}]
  (let [{:keys [type challenge origin]} decoded-client-data
        errors (cond-> []
                 (not= type expected-type) (conj :type-mismatch)
                 (not= (base64url-decode challenge) (vec expected-challenge)) (conj :challenge-mismatch)
                 (not= origin expected-origin) (conj :origin-mismatch))]
    {:valid? (empty? errors) :errors errors}))

(defn verify-signature-counter
  "Per §6.1.3: true if new-counter is 0 (authenticators without a
  counter) or strictly greater than previous-counter; false otherwise —
  a same-or-lower nonzero counter signals possible cloning."
  [previous-counter new-counter]
  (or (zero? new-counter) (> new-counter previous-counter)))
