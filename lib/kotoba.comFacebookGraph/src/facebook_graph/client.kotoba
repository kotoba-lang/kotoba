(ns facebook-graph.client
  "Portable core for talking to the Meta Marketing API (Graph API, Marketing
  surface) -- one auth/HTTP boundary for every facebook-graph.* namespace in
  this library. Covers Facebook, Instagram, Messenger and Audience Network
  placements, which share one Marketing API domain (graph.facebook.com).

  This is the `kotoba-lang/com-facebook-graph` provider repo named in
  cloud-itonami's ADR-0023 (media-network domain adapters). A prior
  implementation of this provider existed only as an uncommitted Python
  virtualenv under this same path (recovered evidence: compiled .pyc/
  .pytest_cache files with no .py source, no git history, no GitHub repo --
  see the `advertising-strategy-itonami.md` sales/ads index for the
  investigation). This rewrite follows the actual kotoba-lang convention
  used by sibling vendor-API clients (`com-cloudflare`): portable `.cljc`,
  pure query/response handling, real HTTP behind an injectable `:http-fn` so
  every namespace is testable with a stub, never only against a live
  account.

  Query construction and response parsing are pure .cljc. The actual HTTP
  call is JVM-only by default (java.net.http) but always takes an
  injectable `:http-fn` -- the same `{:url :method :headers :body} ->
  {:status :body}` convention as cloudflare.client/jvm-http-fn."
  (:require [kotoba.lang.text :as str]
            #?(:clj [json.data-json :as json])))

(def default-api-version "v25.0")

(defn api-base [{:keys [api-version] :or {api-version default-api-version}}]
  (str "https://graph.facebook.com/" api-version))

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
                     :delete (-> builder .DELETE .build)
                     (throw (ex-info "Unsupported HTTP method" {:method method})))
           resp (.send (java.net.http.HttpClient/newHttpClient) request
                      (java.net.http.HttpResponse$BodyHandlers/ofString))]
       {:status (.statusCode resp) :body (.body resp)})))))

#?(:clj
(defn access-token
  "FACEBOOK_ACCESS_TOKEN from the environment, or throw. Callers can always
  override via an explicit :token in opts instead of relying on env. Never
  written to a resource file -- ADR-0023's registration/auth section
  requires credentials to stay out of committed EDN/JSON."
  []
  (or (System/getenv "FACEBOOK_ACCESS_TOKEN")
      (throw (ex-info "FACEBOOK_ACCESS_TOKEN is required" {})))))

#?(:clj
(defn- auth-headers [token]
  {"Authorization" (str "Bearer " token)
   "Content-Type" "application/json"}))

#?(:clj
(defn- query-string [params]
  (when (seq params)
    (str "?" (str/join "&" (map (fn [[k v]] (str (name k) "=" v)) params))))))

#?(:clj
(defn call!
  "Call a Marketing API endpoint. `path` is relative to the versioned API
  base (e.g. \"/act_123/campaigns\" or \"/122345\"). Returns the parsed JSON
  response on a transport-level 2xx WITHOUT a Graph API :error envelope;
  throws (preserving the provider-native :code/:error_subcode/:fbtrace_id)
  on a transport-level non-2xx status OR a Graph-API-level {:error ...}
  body -- Graph API sometimes returns errors with a 200 transport status, so
  checking only the HTTP status is not sufficient, matching
  cloudflare.client/rest!'s fail-closed default."
  ([path] (call! path {}))
  ([path {:keys [method body http-fn token query]
          :or {method :get http-fn (jvm-http-fn)}
          :as opts}]
   (let [resp (http-fn (cond-> {:url (str (api-base opts) path (query-string query))
                                :method method
                                :headers (auth-headers (or token (access-token)))}
                        body (assoc :body (json/write-str body))))
         parsed (try (json/read-str (:body resp) :key-fn keyword)
                     (catch Exception _ {:raw (:body resp)}))]
     (when (or (>= (:status resp) 300) (:error parsed))
       (throw (ex-info "Meta Marketing API request failed"
                       {:status (:status resp) :path path :error (:error parsed)})))
     parsed))))
