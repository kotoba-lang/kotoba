(ns auth.otp
  "HOTP (RFC 4226) and TOTP (RFC 6238) one-time-password generation.

  The only host-specific part is the HMAC primitive — `javax.crypto.Mac` on the
  JVM, Node's `crypto` module on ClojureScript — isolated in `hmac-bytes`.
  Everything else (dynamic truncation, modulo, time-stepping) is pure .cljc and
  exercised against the RFC test vectors in auth.otp-test."
  (:require [auth.base32 :as base32]))

;; ───────────────────────── HMAC (host primitive) ─────────────────────────

(defn hmac-bytes
  "HMAC of `msg-ints` keyed by `key-ints`, both vectors of unsigned bytes
  (0–255). `algorithm` is :sha1 | :sha256 | :sha512. Returns a vector of
  unsigned bytes."
  [algorithm key-ints msg-ints]
  #?(:clj
     (let [nm  (case algorithm :sha1 "HmacSHA1" :sha256 "HmacSHA256" :sha512 "HmacSHA512")
           mac (javax.crypto.Mac/getInstance nm)]
       (.init mac (javax.crypto.spec.SecretKeySpec. (byte-array (map unchecked-byte key-ints)) nm))
       (mapv #(bit-and % 0xff) (.doFinal mac (byte-array (map unchecked-byte msg-ints)))))
     :cljs
     (let [crypto (js/require "crypto")
           nm     (case algorithm :sha1 "sha1" :sha256 "sha256" :sha512 "sha512")
           h      (.createHmac crypto nm (js/Buffer.from (clj->js key-ints)))]
       (.update h (js/Buffer.from (clj->js msg-ints)))
       (let [buf (.digest h)]
         (mapv #(aget buf %) (range (.-length buf)))))))

;; ───────────────────────── helpers (pure) ─────────────────────────

(defn counter-bytes
  "8-byte big-endian encoding of a counter (the HOTP moving factor).

  Public because a host whose HMAC is asynchronous cannot call `hotp`: it has
  to build the message itself, await its own primitive, and finish with
  `code-from-hmac`. See that function for why."
  [counter]
  (loop [i 7, c counter, acc [0 0 0 0 0 0 0 0]]
    (if (or (neg? i) (zero? c))
      acc
      (recur (dec i) (quot c 256) (assoc acc i (mod c 256))))))

(defn- pow10 [n] (reduce * 1 (repeat n 10)))

(defn- zero-pad [n width]
  (let [s (str n)]
    (str (apply str (repeat (max 0 (- width (count s))) "0")) s)))

;; ───────────────────────── HOTP / TOTP (pure) ─────────────────────────

(defn code-from-hmac
  "RFC 4226 §5.3 dynamic truncation: HMAC bytes -> the code string. Pure.

  Split out from `hotp` so a host whose HMAC primitive is ASYNCHRONOUS can
  still produce a code. Cloudflare Workers is the case that forced it: WebCrypto
  is the only crypto there (`crypto.subtle.sign` returns a Promise) and
  `hmac-bytes`'s :cljs branch reaches for Node's `crypto` module, which needs
  the `nodejs_compat` flag. A Worker that turns that flag on to compute a
  6-digit code gives up a build-time guarantee about its whole dependency
  surface for one HMAC — so instead it computes the HMAC with WebCrypto, awaits
  it, and calls this.

  Same split, and the same reason, as `authentication`'s IFactorVerifier /
  IAsyncFactorVerifier pair: verification is synchronous where the platform API
  is and Promise-returning where it is not."
  ([hs] (code-from-hmac hs nil))
  ([hs {:keys [digits] :or {digits 6}}]
   (let [offset (bit-and (peek hs) 0x0f)
         bin    (bit-or (bit-shift-left (bit-and (nth hs offset) 0x7f) 24)
                        (bit-shift-left (nth hs (+ offset 1)) 16)
                        (bit-shift-left (nth hs (+ offset 2)) 8)
                        (nth hs (+ offset 3)))]
     (zero-pad (mod bin (pow10 digits)) digits))))

(defn hotp
  "RFC 4226 HOTP. `secret-ints` is the raw shared secret (unsigned bytes),
  `counter` the moving factor. Options: :algorithm (default :sha1),
  :digits (default 6). Returns the zero-padded code string."
  ([secret-ints counter] (hotp secret-ints counter nil))
  ([secret-ints counter {:keys [algorithm digits] :or {algorithm :sha1 digits 6}}]
   (code-from-hmac (hmac-bytes algorithm secret-ints (counter-bytes counter))
                   {:digits digits})))

(defn counter-for
  "RFC 6238 time-step for a Unix time. Public for the same reason as
  `counter-bytes`: an async host builds the message itself.

  Also the unit a verifier's drift window is counted in — accept
  `(counter-for now)` plus or minus N steps, never plus or minus N seconds,
  or the window silently changes width as `now` moves within a step."
  ([unix-seconds] (counter-for unix-seconds nil))
  ([unix-seconds {:keys [period t0] :or {period 30 t0 0}}]
   (quot (- unix-seconds t0) period)))

(defn totp
  "RFC 6238 TOTP. `secret-ints` raw shared secret, `unix-seconds` current Unix
  time. Options: :algorithm (:sha1), :digits (6), :period (30s), :t0 (0)."
  ([secret-ints unix-seconds] (totp secret-ints unix-seconds nil))
  ([secret-ints unix-seconds {:keys [algorithm digits period t0]
                              :or {algorithm :sha1 digits 6 period 30 t0 0}}]
   (hotp secret-ints (counter-for unix-seconds {:period period :t0 t0})
         {:algorithm algorithm :digits digits})))

(defn- safe-period
  "A usable step length: a positive period, else the 30s default. Guards against
  a malformed/hand-edited vault entry (period 0 → divide-by-zero, or negative)."
  [period]
  (if (and (number? period) (pos? period)) period 30))

(defn- safe-digits
  "Clamp digit count to a sane range so `pow10` can't overflow a JVM long on an
  absurd value imported from a malformed otpauth URI."
  [digits]
  (if (number? digits) (max 1 (min 10 digits)) 6))

(defn remaining-seconds
  "Seconds left in the current TOTP step — drives the countdown in the UI."
  [unix-seconds period]
  (let [p (safe-period period)]
    (- p (mod unix-seconds p))))

;; ───────────────────────── account-level convenience ─────────────────────────

(defn account-code
  "Current code for a stored account map (see auth.db schema). For :hotp the
  caller is responsible for persisting the incremented counter. Defensive about
  period/digits so one malformed account can't crash a whole `code` listing."
  [{:account/keys [secret type algorithm digits period counter]} unix-seconds]
  (let [secret-ints (base32/decode secret)
        algo (if (contains? #{:sha1 :sha256 :sha512} algorithm) algorithm :sha1)
        opts {:algorithm algo :digits (safe-digits digits)}]
    (if (= type :hotp)
      (hotp secret-ints (or counter 0) opts)
      (totp secret-ints unix-seconds (assoc opts :period (safe-period period))))))
