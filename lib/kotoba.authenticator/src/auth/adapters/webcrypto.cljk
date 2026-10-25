(ns auth.adapters.webcrypto
  "TOTP where the only crypto is WebCrypto: Cloudflare Workers, service
  workers, browsers, Deno.

  `auth.otp/hmac-bytes` reaches for `javax.crypto.Mac` on the JVM and Node's
  `crypto` module on ClojureScript. A Worker has neither unless it turns on
  `nodejs_compat`, and turning that flag on to compute a six-digit code trades
  a build-time guarantee about the whole dependency surface for one HMAC.
  WebCrypto is there — but `crypto.subtle.sign` returns a Promise, and `hotp`
  is synchronous.

  So this namespace does the HMAC asynchronously and finishes with the pure
  half `auth.otp` publishes. The truncation, the modulo and the time-stepping
  are the same code the RFC vectors exercise; only the primitive differs.

  ClojureScript only."
  (:require [auth.otp :as otp]
            [auth.verify :as verify]))

(defn- ->u8 [byte-seq] (js/Uint8Array.from (clj->js (vec byte-seq))))

(defn- hmac-key!
  "Import once per verification rather than once per counter. A window of 3
  counters is 3 signatures over the same key, and re-importing for each is
  work with no purpose."
  [secret-bytes algorithm]
  (js/crypto.subtle.importKey
   "raw" (->u8 secret-bytes)
   #js {:name "HMAC" :hash (case algorithm :sha256 "SHA-256" :sha512 "SHA-512" "SHA-1")}
   false #js ["sign"]))

(defn- sign! [key msg-bytes]
  (-> (js/crypto.subtle.sign "HMAC" key (->u8 msg-bytes))
      (.then (fn [buf] (vec (array-seq (js/Uint8Array. buf)))))))

(defn codes-for-counters!
  "Promise of `{counter -> code}` for every counter given.

  The shape `auth.verify/verdict` consumes. Returning the whole window rather
  than testing one code at a time is deliberate: the comparison then happens
  in one pure function over values, so the accept/reject decision can be
  tested without a clock, a key, or a Promise."
  ([secret-bytes counters] (codes-for-counters! secret-bytes counters nil))
  ([secret-bytes counters {:keys [algorithm digits] :or {algorithm :sha1 digits 6}}]
   (-> (hmac-key! secret-bytes algorithm)
       (.then (fn [key]
                (js/Promise.all
                 (clj->js (map (fn [c]
                                 (-> (sign! key (otp/counter-bytes c))
                                     (.then (fn [hs]
                                              #js [c (otp/code-from-hmac hs {:digits digits})]))))
                               counters)))))
       (.then (fn [pairs]
                (into {} (map (fn [p] [(aget p 0) (aget p 1)]) (array-seq pairs))))))))

(defn verify!
  "The whole check: window, codes, verdict.

  `{:secret-bytes :presented :unix-seconds :last-used :window :period :digits}`
  -> Promise of `auth.verify/verdict`'s result.

  `:last-used` is the highest counter already accepted for this secret and is
  what makes a code single-use inside its own step. Passing `nil` there means
  'no replay check', which is correct only during enrolment — where there is
  nothing yet to replay — and wrong everywhere else."
  [{:keys [secret-bytes presented unix-seconds last-used window period digits]
    :or {window verify/default-window period 30 digits 6}}]
  (let [counter (otp/counter-for unix-seconds {:period period})
        counters (verify/window-counters counter window)]
    (-> (codes-for-counters! secret-bytes counters {:digits digits})
        (.then (fn [codes]
                 (verify/verdict {:presented presented
                                  :codes codes
                                  :last-used last-used
                                  :digits digits}))))))
