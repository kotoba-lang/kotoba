(ns oauth2.core
  "OAuth 2.0 (RFC 6749) authorization-code flow as data — request/response
  shapes, no network I/O. This is the raw RFC 6749 substrate: building the
  authorization URL, parsing the redirect callback, shaping a token request
  body, and normalizing a token response. HTTP transport itself is the
  caller's job (inject whatever `:http-fn` your host already uses, the same
  seam `kotoba-lang/godaddy-dns` uses) — this namespace never makes a
  network call. `.cljc`, zero third-party runtime deps."
  (:require [kotoba.lang.text :as str]))

;; ───────────────────────────── encoding ─────────────────────────────

(def ^:private hex-digits "0123456789ABCDEF")

(defn- ->hex2
  "Byte value (0-255) to a 2-digit uppercase hex string, no platform hex
  formatter — portable across clj/cljs."
  [n]
  (str (nth hex-digits (bit-and (bit-shift-right n 4) 0xf))
       (nth hex-digits (bit-and n 0xf))))

(defn- unreserved-char? [ch]
  (let [c (int ch)]
    (or (<= (int \a) c (int \z))
        (<= (int \A) c (int \Z))
        (<= (int \0) c (int \9))
        (#{(int \-) (int \_) (int \.) (int \~)} c))))

(defn- char->utf8-byte-ints [ch]
  #?(:clj (map #(bit-and (int %) 0xff) (.getBytes (str ch) "UTF-8"))
     :cljs (map #(.charCodeAt ^js % 0)
                (js/unescape (js/encodeURIComponent (str ch))))))

(defn- percent-encode
  "RFC 3986 percent-encode a string, leaving unreserved chars
  (A-Z a-z 0-9 - _ . ~) untouched."
  [s]
  (apply str
         (mapcat (fn [ch]
                   (if (unreserved-char? ch)
                     [ch]
                     (map #(str "%" (->hex2 %)) (char->utf8-byte-ints ch))))
                 (str s))))

(defn- query-encode [s] (percent-encode s))

(defn- form-encode
  "application/x-www-form-urlencoded value: like percent-encode but a
  literal space encodes as '+'."
  [s]
  (str/replace (percent-encode s) "%20" "+"))

(defn- ->query-string [params]
  (str/join "&"
            (for [[k v] params
                  :when (some? v)]
              (str (query-encode (name k)) "=" (query-encode (str v))))))

(defn ->form-body
  "A param map to an application/x-www-form-urlencoded string."
  [params]
  (str/join "&"
            (for [[k v] params
                  :when (some? v)]
              (str (form-encode (name k)) "=" (form-encode (str v))))))

;; ─────────────────────────── authorization ───────────────────────────

(defn authorization-url
  "Build the full RFC 6749 §4.1.1 authorization request URL.

  `authorize-endpoint` is the authorization server's base URL; the rest
  become query params. `response-type` defaults to \"code\". Include
  `code-challenge`/`code-challenge-method` for PKCE (RFC 7636) — see
  `oauth2.pkce`."
  [{:keys [authorize-endpoint client-id redirect-uri scope state
           response-type code-challenge code-challenge-method]
    :or {response-type "code"}}]
  (str authorize-endpoint
       "?" (->query-string
            {:response_type response-type
             :client_id client-id
             :redirect_uri redirect-uri
             :scope scope
             :state state
             :code_challenge code-challenge
             :code_challenge_method code-challenge-method})))

(defn parse-authorization-response
  "Given the decoded redirect query params (a map, string or keyword keys),
  return `{:code ... :state ...}` on success, or `{:error ...
  :error-description ...}` per RFC 6749 §4.1.2.1 when the authorization
  server reports a failure."
  [query-params]
  (let [get* (fn [k] (or (get query-params k) (get query-params (name k))))
        error (get* :error)]
    (if error
      {:error error
       :error-description (get* :error_description)}
      {:code (get* :code)
       :state (get* :state)})))

;; ────────────────────────────── token ────────────────────────────────

(def ^:private grant-param-fns
  {"authorization_code"
   (fn [{:keys [code redirect-uri client-id client-secret code-verifier]}]
     {:grant_type "authorization_code"
      :code code
      :redirect_uri redirect-uri
      :client_id client-id
      :client_secret client-secret
      :code_verifier code-verifier})
   "refresh_token"
   (fn [{:keys [refresh-token client-id client-secret scope]}]
     {:grant_type "refresh_token"
      :refresh_token refresh-token
      :client_id client-id
      :client_secret client-secret
      :scope scope})
   "client_credentials"
   (fn [{:keys [client-id client-secret scope]}]
     {:grant_type "client_credentials"
      :client_id client-id
      :client_secret client-secret
      :scope scope})})

(defn token-request-body
  "Return the RFC 6749 §4.1.3/§6/§4.4.2 param map for the given
  `:grant-type` (\"authorization_code\", \"refresh_token\", or
  \"client_credentials\"). `nil`-valued params are dropped by
  `->form-body`/`->query-string`, not the caller's concern. Throws
  `ex-info` on an unrecognized grant type."
  [{:keys [grant-type] :as params}]
  (if-let [f (get grant-param-fns grant-type)]
    (f params)
    (throw (ex-info (str "oauth2: unknown grant_type " (pr-str grant-type))
                     {:grant-type grant-type}))))

(defn parse-token-response
  "Normalize a decoded (already JSON-parsed) token response map into
  `{:access-token :token-type :expires-in :refresh-token :scope}`. Throws
  `ex-info` carrying the RFC 6749 §5.2 error fields when the response is
  an error response (`:error` present)."
  [{:keys [error error_description error_uri
           access_token token_type expires_in refresh_token scope]
    :as resp}]
  (if error
    (throw (ex-info (str "oauth2: token endpoint error " error)
                     {:error error
                      :error-description error_description
                      :error-uri error_uri}))
    {:access-token access_token
     :token-type token_type
     :expires-in expires_in
     :refresh-token refresh_token
     :scope scope}))
