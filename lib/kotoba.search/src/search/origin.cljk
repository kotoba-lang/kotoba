(ns search.origin
  "Google-like contract for https://search.kotobase.net.

  One box in; ranked `{title, url, snippet, score}` out. The Worker is a
  reader of an inverted index, not a Datalog engine.

  Retrieve = posting AND (`search.postings`). Rank = field weights
  (`search.model`) on the hit set only — never score the corpus. Production
  scale ranking is `kotobase-shard-index` (BM25, impact-ordered); inject it
  as `:retrieve`. This file is the HTTP/envelope oracle the origin must
  match (ADR-2608170600).

  Forbidden: hydrate-then-scan, Datalog over tokens, GraphSync selectors."
  (:require [kotoba.lang.text :as str]
            [search.model :as model]
            [search.postings :as postings]))

(def origin "https://search.kotobase.net")

(def xrpc-path "/xrpc/ai.gftd.apps.kotobase.search.query")

(def default-k 10)
(def max-k 50)

(defn context-from-docs
  "In-memory origin context. Rebuildable: throw the index away and call
  again from the same docs (or from datoms via `search.postings/from-datoms`)."
  [docs]
  (let [docs (vec docs)
        by-id (into {} (map (fn [d]
                              [(or (:search/id d) (:id d)) d]))
                    docs)]
    {:engine :postings
     :docs docs
     :docs-by-id by-id
     :index (postings/build docs)}))

(defn- url-decode [s]
  (-> (str s)
      (str/replace "+" " ")
      (str/replace "%20" " ")))

(defn parse-query-string
  [qs]
  (if (str/blank? qs)
    {}
    (into {}
          (keep (fn [pair]
                  (when-not (str/blank? pair)
                    (let [[k v] (str/split pair #"=" 2)]
                      [(keyword (url-decode k)) (url-decode (or v ""))]))))
          (str/split qs #"&"))))

(defn request-params
  [req]
  (or (:params req)
      (when (map? (:body req)) (:body req))
      (parse-query-string (:query-string req))))

(defn- parse-k [raw]
  (let [n (cond
            (number? raw) (long raw)
            (and (string? raw) (re-matches #"[0-9]+" raw))
            #?(:clj (Long/parseLong raw)
               :cljs (js/parseInt raw 10))
            :else default-k)]
    (max 1 (min max-k n))))

(defn snippet
  "Window around the first query term, else a prefix. Display only — not
  a second index."
  [text terms]
  (let [s (str (or text ""))
        lower (str/lower s)
        idx (some (fn [t]
                    (let [i (str/index-of lower (str/lower (str t)))]
                      (when i i)))
                  terms)
        start (if idx (max 0 (- idx 40)) 0)
        end (min (count s) (+ start 160))
        cut (subs s start end)]
    (str (when (pos? start) "…")
         cut
         (when (< end (count s)) "…"))))

(defn doc-url
  [doc]
  (or (:search/url doc)
      (:url doc)
      (str "https://kotobase.net/doc/" (or (:search/id doc) (:id doc)))))

(defn google-hit
  [doc score terms]
  {:title (or (:search/title doc) (:title doc) (str (:search/id doc)))
   :url (doc-url doc)
   :snippet (snippet (or (:search/body doc) (:body doc) "") terms)
   :score score
   :doc-id (or (:search/id doc) (:id doc))})

(defn rank-ids
  "Score only retrieved ids. O(|hits|), not O(corpus)."
  [docs-by-id ids q]
  (let [terms (model/tokenize q)
        weights model/default-weights]
    (->> ids
         (keep (fn [id]
                 (when-let [doc (get docs-by-id id)]
                   (let [score (model/score-doc weights terms doc)]
                     (when (pos? score)
                       (assoc doc :search/score score))))))
         (sort-by (juxt (comp - :search/score) #(or (:search/id %) (:id %))))
         vec)))

(defn retrieve
  "Default engine: posting AND. A Worker with a shard-index store replaces
  this by supplying `:retrieve` on the context."
  [ctx q]
  (or (when-let [f (:retrieve ctx)] (f ctx q))
      (postings/query (:index ctx) q)))

(defn landing-html
  "Single search box. No dialect textarea, no SPARQL, no graph picker."
  ([] (landing-html ""))
  ([q]
   (str "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>search.kotobase.net</title>"
        "<style>"
        "html,body{margin:0;min-height:100%;font:16px/1.4 ui-sans-serif,system-ui,sans-serif;"
        "background:#fff;color:#202124}"
        "main{max-width:560px;margin:18vh auto 0;padding:0 16px}"
        "h1{font-weight:400;font-size:22px;letter-spacing:-0.02em;margin:0 0 24px;text-align:center}"
        "form{display:flex;gap:8px}"
        "input[name=q]{flex:1;height:44px;border:1px solid #dfe1e5;border-radius:24px;"
        "padding:0 20px;font-size:16px;outline:none}"
        "input[name=q]:focus{border-color:#4285f4}"
        "button{height:44px;padding:0 18px;border:0;border-radius:4px;"
        "background:#f8f9fa;color:#3c4043;cursor:pointer}"
        "#hits{margin-top:32px}"
        "article{margin:0 0 22px}"
        "a{color:#1a0dab;font-size:18px;text-decoration:none}"
        "cite{display:block;color:#006621;font-style:normal;font-size:13px}"
        "p{margin:4px 0 0;color:#4d5156}"
        "</style></head><body><main>"
        "<h1>search.kotobase.net</h1>"
        "<form action=\"/\" method=\"get\" role=\"search\">"
        "<input type=\"search\" name=\"q\" value=\"" (str/replace (str q) "\"" "&quot;") "\" autofocus autocomplete=\"off\">"
        "<button type=\"submit\">Search</button></form>"
        "<div id=\"hits\"></div>"
        "<script>"
        "(function(){var p=new URLSearchParams(location.search);var q=p.get('q');"
        "if(!q)return;var h=document.getElementById('hits');"
        "fetch('/search?q='+encodeURIComponent(q)+'&k=10',{headers:{Accept:'application/json'}})"
        ".then(function(r){return r.json()}).then(function(b){"
        "if(!b.hits||!b.hits.length){h.textContent=b.reason||'no results';return;}"
        "h.innerHTML=b.hits.map(function(x){"
        "return '<article><cite>'+x.url+'</cite><a href=\"'+x.url+'\">'+x.title+"
        "'</a><p>'+(x.snippet||'')+'</p></article>';}).join('');"
        "});})();"
        "</script></main></body></html>")))

(defn- envelope
  [ctx q k retrieved ranked]
  {:ok (= :ok (:reason retrieved))
   :q q
   :k k
   :origin origin
   :engine (or (:engine ctx) :postings)
   :reason (:reason retrieved)
   :hits (mapv #(google-hit % (:search/score %) (:terms retrieved))
               (take k ranked))
   :stats {:docs (:docs retrieved)
           :terms (:terms retrieved)
           :posting-entries-read (:posting-entries-read retrieved)
           :hit-count (count ranked)}})

(defn- search-response
  [ctx req]
  (let [params (request-params req)
        q (str (or (:q params) (:query params) ""))
        k (parse-k (:k params))
        retrieved (retrieve ctx q)
        ranked (if (= :ok (:reason retrieved))
                 (rank-ids (:docs-by-id ctx) (:hits retrieved) q)
                 [])]
    {:status 200
     :headers {"content-type" "application/json; charset=utf-8"}
     :body (envelope ctx q k retrieved ranked)}))

(defn handle
  "Ring-shaped request → response. Body of `/search` is a map (JSON later).

  GET `/` is the one-box page. GET `/search` and the XRPC path are the
  ranked JSON envelope."
  [ctx req]
  (if (= :hydrate-then-scan (:strategy ctx))
    {:status 501
     :headers {"content-type" "application/json; charset=utf-8"}
     :body {:ok false :reason :forbidden-strategy :origin origin}}
    (let [method (keyword (str/lower (name (or (:request-method req)
                                                    (:method req)
                                                    :get))))
          path (or (:uri req) (:path req) "/")]
      (cond
        (and (#{:get :head} method) (= path "/"))
        {:status 200
         :headers {"content-type" "text/html; charset=utf-8"}
         :body (landing-html (str (or (:q (request-params req)) "")))}

        (and (#{:get :post} method)
             (or (= path "/search")
                 (= path xrpc-path)))
        (search-response ctx req)

        :else
        {:status 404
         :headers {"content-type" "application/json; charset=utf-8"}
         :body {:ok false :reason :not-found :origin origin}}))))
