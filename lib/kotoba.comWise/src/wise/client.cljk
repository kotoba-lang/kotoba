(ns wise.client
  "Portable core for talking to the Wise (formerly TransferWise) Platform
  API -- one auth/HTTP boundary for every wise.* namespace in this library.

  Query construction and response parsing are pure .cljc. The actual HTTP
  call is JVM-only by default (java.net.http) but always takes an
  injectable `:http-fn` -- the same `{:url :method :headers :body} ->
  {:status :body}` convention as gmail.client/cloudflare.client
  (kotoba-lang/com-gmail, kotoba-lang/com-cloudflare) -- so every namespace
  here is testable with a stub, never only against a live account.

  Auth is a bearer API token (a personal/service token, or an OAuth2 access
  token for a Wise Partner integration). Obtaining that token is out of
  scope for this library -- callers pass one, the same way cloudflare.client
  expects a pre-obtained CLOUDFLARE_API_TOKEN."
  (:require [kotoba.lang.text :as str]
            #?(:clj [json.data-json :as json])))

(def api-base "https://api.wise.com")
(def sandbox-api-base "https://api.sandbox.transferwise.tech")

#?(:clj
(defn jvm-http-fn
  "Real java.net.http transport. {:url :method :headers :body} ->
  {:status :body}, same convention as cloudflare.client/jvm-http-fn."
  ([] (jvm-http-fn {}))
  ([{:keys [timeout-seconds] :or {timeout-seconds 30}}]
   (fn [{:keys [url method headers body]}]
     (let [builder (-> (java.net.http.HttpRequest/newBuilder (java.net.URI/create url))
                       (.timeout (java.time.Duration/ofSeconds timeout-seconds))
                       (as-> b (reduce-kv (fn [b k v] (.header b k v)) b headers)))
           request (case method
                     :post (-> builder
                              (.POST (java.net.http.HttpRequest$BodyPublishers/ofString (or body "")))
                              .build)
                     :get (-> builder .GET .build)
                     (throw (ex-info "Unsupported HTTP method" {:method method})))
           resp (.send (java.net.http.HttpClient/newHttpClient) request
                      (java.net.http.HttpResponse$BodyHandlers/ofString))]
       {:status (.statusCode resp) :body (.body resp)})))))

#?(:clj
(defn api-token
  "WISE_API_TOKEN from the environment, or throw. Callers can always
  override via an explicit :token in opts instead of relying on env."
  []
  (or (System/getenv "WISE_API_TOKEN")
      (throw (ex-info "WISE_API_TOKEN is required" {})))))

#?(:clj
(defn- auth-headers [token]
  {"Authorization" (str "Bearer " token)
   "Content-Type" "application/json"}))

#?(:clj
(defn request!
  "Call a Wise API endpoint. `path` is relative to `:api-base` (default
  `wise.client/api-base`; pass `:api-base wise.client/sandbox-api-base` in
  opts to hit the sandbox instead), e.g. \"/v1/profiles\" or
  (str \"/v1/transfers/\" transfer-id). `opts` accepts :method (default
  :get), :body (a map, JSON-encoded), :query (a map of query params),
  :http-fn, :token, :api-base. Returns the parsed JSON body, or nil for an
  empty body. Throws on a transport-level non-2xx status."
  ([path] (request! path {}))
  ([path {:keys [method body http-fn token query api-base]
          :or {method :get http-fn (jvm-http-fn) api-base api-base}}]
   (let [query-string (when (seq query)
                        (str "?" (str/join "&" (map (fn [[k v]] (str (name k) "=" v)) query))))
         resp (http-fn (cond-> {:url (str api-base path query-string)
                                :method method
                                :headers (auth-headers (or token (api-token)))}
                        body (assoc :body (json/write-str body))))]
     (when-not (< (:status resp) 300)
       (throw (ex-info "Wise API request failed"
                       {:status (:status resp) :path path :body (:body resp)})))
     (when (seq (:body resp))
       (json/read-str (:body resp) :key-fn keyword))))))
