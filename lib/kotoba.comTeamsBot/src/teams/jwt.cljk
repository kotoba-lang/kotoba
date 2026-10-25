(ns teams.jwt
  "Pure JWT structural parsing + claims validation — portable `.cljc`, no
  crypto (RS256 signature verification needs Web Crypto + a fetched JWKS,
  see `teams.jwt-verify`, `.cljs`-only). Splitting the pure/testable half
  from the crypto/async half mirrors this workspace's other webhook-verify
  splits (`meta-webhook.signature`/`async-signature`,
  `line-messaging.signature`/`async-signature`) — this one just needs an
  extra pure layer because a JWT (unlike a plain HMAC) carries structured
  claims worth validating on their own."
  (:require [kotoba.lang.text :as str]))

(defn- base64url->base64 [s]
  (let [s   (-> s (str/replace "-" "+") (str/replace "_" "/"))
        pad (mod (- 4 (mod (count s) 4)) 4)]
    (str s (apply str (repeat pad "=")))))

(defn- b64-decode-str
  "base64url-encoded UTF-8 string -> decoded string."
  [s]
  #?(:clj (String. (.decode (java.util.Base64/getDecoder) (base64url->base64 s)) "UTF-8")
     :cljs (let [binary (js/atob (base64url->base64 s))
                 bytes  (js/Uint8Array. (.-length binary))]
             (dotimes [i (.-length binary)]
               (aset bytes i (.charCodeAt binary i)))
             (.decode (js/TextDecoder.) bytes))))

(defn split-jwt
  "\"header.payload.signature\" -> {:header-b64 :payload-b64 :signature-b64}
  or nil if not a 3-part JWT (a caller receiving anything else should
  reject the request outright, not attempt further parsing)."
  [token]
  (let [parts (str/split (str token) #"\.")]
    (when (= 3 (count parts))
      {:header-b64    (nth parts 0)
       :payload-b64   (nth parts 1)
       :signature-b64 (nth parts 2)})))

(defn decode-segment
  "One JWT segment (base64url-encoded JSON) -> parsed EDN map via the
  caller's `json-read` (kept injectable rather than hardcoding a JSON
  library, same DI discipline as every HTTP client in this workspace)."
  [json-read segment-b64]
  (json-read (b64-decode-str segment-b64)))

(defn valid-claims?
  "Checks `iss`/`aud`/`exp`/`nbf` -- NOT the signature (`teams.jwt-verify`
  does that separately). `now-epoch-sec` is injected for testability (a
  caller passes the real current time; a test passes a fixed value).
  `expected-issuer` is Bot Framework's own token issuer
  (`https://api.botframework.com`); `expected-audience` is your bot's
  Microsoft App Id (the same one used for `teams.client`'s OAuth2 token
  acquisition)."
  [{:keys [iss aud exp nbf]} {:keys [expected-issuer expected-audience now-epoch-sec]}]
  (boolean
   (and (= iss expected-issuer)
        (= aud expected-audience)
        (number? exp) (< now-epoch-sec exp)
        (or (nil? nbf) (>= now-epoch-sec nbf)))))
