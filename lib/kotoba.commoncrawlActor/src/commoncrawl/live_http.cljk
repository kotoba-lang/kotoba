(ns commoncrawl.live-http
  "The ONLY namespace in this repo that does real network/gzip IO.
  Deliberately plain `.cljs` (not `.cljc`) — nbb-only, per the repo-wide
  runtime priority (kotoba wasm > clojurewasm > cljs > nbb > jvm/bb) AND
  the ADR's explicit instruction that the CDX/WARC HTTP client part be
  written with nbb's fetch/http mechanism rather than a JVM-only client
  like `dossier.commoncrawl`'s `org.httpkit.client`.

  Every capability every OTHER ns in this repo takes as an injected
  argument (`commoncrawl.cdx`'s `fetch-fn`/`warc-fetch-fn`,
  `commoncrawl.llm`'s `complete-fn`, `commoncrawl.embeddings`'s
  `embed-fn`, `commoncrawl.kotobase`'s `http-fn`) has its REAL
  implementation here, and ONLY here — every other ns stays fully
  testable offline against canned fixtures because none of them ever
  import this one. `commoncrawl.sim` (offline demo) also never requires
  this ns; only a live tick-runner entry point does.

  Uses Node's synchronous `child_process.execFileSync` + `curl` for every
  HTTP call (same idiom `70-tools/bmc/src/gftd/cli.cljc`'s
  `llm-complete-fn` already uses in this monorepo) — this keeps every
  capability a PLAIN SYNCHRONOUS function, which is what
  `langgraph.graph`'s Pregel-style node execution requires (nodes are
  `state -> partial-state-map`, no Promise/async support), rather than
  fighting async fetch Promises inside a StateGraph node."
  (:require [kotoba.lang.text :as str]))

(def ^:private cp (js/require "child_process"))
(def ^:private zlib (js/require "zlib"))

;; ── generic curl wrapper ─────────────────────────────────────────────────

(defn- run-curl
  "args (vector of strings, no shell involved — execFileSync passes argv
  directly, so no quoting/injection concerns) -> the raw Buffer curl wrote
  to stdout, or nil on a curl invocation failure (non-zero exit / spawn
  error) — never throws, matching every other capability's 'transport
  failure -> nil' convention in this repo."
  [args & [{:keys [input timeout-ms] :or {timeout-ms 60000}}]]
  (try
    (.execFileSync cp "curl"
                   (clj->js args)
                   (clj->js (cond-> {:maxBuffer (* 64 1024 1024) :timeout timeout-ms}
                              input (assoc :input input))))
    (catch :default e
      ;; execFileSync throws on non-zero exit; curl's own stdout up to the
      ;; failure (if any) is on e.stdout — surface it as a low/failed status
      ;; rather than losing the response body entirely.
      (or (.-stdout e) nil))))

(defn- split-status
  "curl's `-w '\\n%{http_code}'`-suffixed stdout Buffer -> [body-buffer
  status-int]. A malformed/short response degrades status to 0 (never a
  fabricated 200)."
  [buf]
  (if-not buf
    [nil 0]
    (let [s (.toString buf "utf8")
          i (.lastIndexOf s "\n")]
      (if (neg? i)
        [s 0]
        (let [status (js/parseInt (subs s (inc i)) 10)]
          [(subs s 0 i) (if (js/isNaN status) 0 status)])))))

(defn- try-json-parse [s]
  (try (js->clj (js/JSON.parse s) :keywordize-keys true) (catch :default _ nil)))

(defn http-text!
  "method (:get/:post) + url + headers-map + body-map(optional, JSON-
  encoded) -> {:status :body}, `:body` ALWAYS the raw response string
  (never auto-JSON-parsed) — the seam `cdx-http-fn` needs, since a Common
  Crawl multi-capture response is newline-delimited JSON (many top-level
  JSON values), which is not itself valid single-document JSON and must be
  split line-by-line by the CALLER, not parsed whole here."
  [{:keys [method url headers body timeout-ms]}]
  (let [hdr-args (mapcat (fn [[k v]] ["-H" (str k ": " v)]) headers)
        method-str (str/upper (name (or method :get)))
        body-json (when body (js/JSON.stringify (clj->js body)))
        args (cond-> (into ["-sS" "-X" method-str url] hdr-args)
               body-json (into ["--data-binary" "@-"])
               true (into ["-w" "\n%{http_code}"]))
        [resp-text status] (split-status (run-curl args {:input body-json :timeout-ms (or timeout-ms 60000)}))]
    {:status status :body resp-text}))

(defn http-json!
  "Like `http-text!`, but `:body` is JSON-parsed when the WHOLE response is
  one parseable JSON document, else the raw response string (a non-JSON
  error page/HTML degrades to a string body rather than throwing — same
  idiom local-murakumo.worker's own proxies use). NOT used by
  `cdx-http-fn`/`collections-fn` — see `http-text!`'s docstring for why a
  whole-body JSON.parse is the wrong shape for Common Crawl's
  newline-delimited-JSON responses."
  [opts]
  (let [{:keys [status body]} (http-text! opts)]
    {:status status :body (or (try-json-parse body) body)}))

;; ── 1. Common Crawl CDX index ────────────────────────────────────────────

(def cdx-base "https://index.commoncrawl.org")

(defn- query-string [m]
  (str/join "&" (map (fn [[k v]] (str (js/encodeURIComponent (name k)) "=" (js/encodeURIComponent v))) m)))

(defn cdx-http-fn
  "Implements `commoncrawl.cdx`'s `fetch-fn` contract:
  `(fn [{:keys [path query]}] -> already-parsed-result)`.

  Real-API quirk (dossier.commoncrawl, ADR-2607182400, ported as a LESSON
  not code): a genuine no-match is HTTP 404 WITH a real JSON body
  (`{\"message\": \"No Captures found for: ...\"}`), not just a 200 — this
  fn parses the body on BOTH 200 and 404, exactly like
  dossier.commoncrawl's `live-http-fn`. A multi-match response is
  newline-delimited JSON (one capture record per line); each line is
  parsed separately. Any other status / a transport failure -> nil
  (genuinely unknown, never confused with a confirmed no-match)."
  [{:keys [path query]}]
  (try
    (let [url (str cdx-base path "?" (query-string query))
          {:keys [status body]} (http-text! {:method :get :url url})]
      (when (and (#{200 404} status) (string? body))
        (->> (str/split-lines body)
             (remove str/blank?)
             (mapv #(or (try-json-parse %) {:message %})))))
    (catch :default _ nil)))

(defn collections-fn
  "`(fn [] -> collections-vector | nil)` for `commoncrawl.cdx/latest-collection-id`."
  []
  (try
    (let [{:keys [status body]} (http-json! {:method :get :url (str cdx-base "/collinfo.json")})]
      (when (and (= 200 status) (vector? body)) body))
    (catch :default _ nil)))

;; ── 2. WARC range fetch + gunzip ─────────────────────────────────────────

(def data-base "https://data.commoncrawl.org")

(defn warc-fetch-fn
  "Implements `commoncrawl.cdx`'s `warc-fetch-fn` contract:
  `(fn [capture] -> decompressed-text | nil)`. Ranged GET of exactly the
  gzip member CDX pointed at (`bytes=offset-(offset+length-1)` against
  `data.commoncrawl.org/<filename>`), then `zlib.gunzipSync` — a genuine
  gzip decompression + real WARC/HTTP envelope, not a stub. Text decode is
  a plain UTF-8 decode (no charset-header sniffing — an honest, documented
  simplification; see `commoncrawl.extract`'s own docstring for the same
  posture on HTML parsing)."
  [{:keys [filename offset length]}]
  (try
    (let [offset (js/parseInt (str offset) 10)
          length (js/parseInt (str length) 10)
          range (str offset "-" (dec (+ offset length)))
          url (str data-base "/" filename)
          buf (run-curl ["-sS" "-r" range url] {:timeout-ms 30000})]
      (when buf
        (.toString (.gunzipSync zlib buf) "utf8")))
    (catch :default _ nil)))

;; ── 3. murakumo LLM extraction (murakumo-main alias) ─────────────────────
;; Follows the 70-tools/bmc/src/gftd/cli.cljc `llm-complete-fn` convention:
;; POST api.murakumo.cloud/v1/messages with model "murakumo-main" (the
;; fleet-main SSoT alias, ADR-2607173100 — the worker resolves it via KV,
;; so this ns never bakes in a concrete model id). Non-streaming (this
;; extraction prompt is short; the 100s-TTFB streaming workaround
;; gftd.cli documents is for long `thinking` generations, not this call).

(def messages-url "https://api.murakumo.cloud/v1/messages")
(def embeddings-url "https://api.murakumo.cloud/v1/embeddings")

(defn- murakumo-token
  "Bearer token for api.murakumo.cloud's /v1/messages + /v1/embeddings
  (both gated by the SAME `local-murakumo.worker/auth-ok?`). Resolution
  order: `COMMONCRAWL_MURAKUMO_TOKEN` env (explicit override) -> `kagi get
  MURAKUMO_CRITIC_TOKEN` via a `KAGI_BIN` env-provided path to the kagi
  binary (skill `secrets-location-map`: this kagi item mirrors
  local-murakumo's `ANTHROPIC_PROXY_TOKEN_2` secondary slot, gettable
  without 1Password's interactive-auth requirement) -> nil (an absent
  token makes every LLM/embeddings call fail closed with a clear 401,
  never silently skip auth)."
  []
  (or (.. js/process -env -COMMONCRAWL_MURAKUMO_TOKEN)
      (when-let [kagi-bin (.. js/process -env -KAGI_BIN)]
        (try
          (str/trim (.toString (.execFileSync cp kagi-bin #js ["get" "MURAKUMO_CRITIC_TOKEN"]) "utf8"))
          (catch :default _ nil)))))

(defn llm-complete-fn
  "-> `(fn [prompt] -> completion-string)`, the exact shape
  `commoncrawl.llm/advise` takes as `complete-fn`. Parses BOTH OpenAI
  (`choices[0].message.content`) and Anthropic (`content[].text`) response
  shapes, same dual-tolerance as `gftd.cli`'s own `llm-complete-fn`."
  []
  (let [token (murakumo-token)]
    (fn [prompt]
      (let [{:keys [status body]}
            (http-json! {:method :post :url messages-url
                        :headers (cond-> {"content-type" "application/json"}
                                   token (assoc "authorization" (str "Bearer " token)))
                        :body {:model "murakumo-main" :max_tokens 800 :stream false
                               :messages [{:role "user" :content prompt}]}
                        :timeout-ms 90000})]
        (if (map? body)
          (or (get-in body [:choices 0 :message :content])
              (some :text (:content body))
              (throw (ex-info (str "murakumo /v1/messages: unrecognized response shape (status " status ")")
                              {:status status :body body})))
          (throw (ex-info (str "murakumo /v1/messages failed, status " status) {:status status :body body})))))))

(defn embed-fn
  "-> `(fn [text] -> response-map | nil)`, the shape
  `commoncrawl.embeddings/embed` takes as `embed-fn`. Returns the raw
  parsed OpenAI-Embeddings-shaped response map for
  `commoncrawl.embeddings/parse-response` to interpret; nil on any
  transport/auth failure (never throws — the actor treats a missing
  embedding as 'ingest with no vector', not a hard failure)."
  []
  (let [token (murakumo-token)]
    (fn [text]
      (try
        (let [{:keys [status body]}
              (http-json! {:method :post :url embeddings-url
                          :headers (cond-> {"content-type" "application/json"}
                                     token (assoc "authorization" (str "Bearer " token)))
                          :body {:model "murakumo-embed" :input text}
                          :timeout-ms 60000})]
          (when (and (#{200} status) (map? body)) body))
        (catch :default _ nil)))))

;; ── 4. net-kotobase web.ingest / web.search ──────────────────────────────

(defn kotobase-http-fn
  "Implements `commoncrawl.kotobase`'s `http-fn` contract:
  `(fn [{:keys [url method headers body]}] -> {:status :body})`."
  [{:keys [url method headers body]}]
  (http-json! {:method (or method :post) :url url :headers headers :body body}))
