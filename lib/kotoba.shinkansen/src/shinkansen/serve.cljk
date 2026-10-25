(ns shinkansen.serve
  "The node:http transport for `shinkansen.host` — and the dev loop
  (maturity axis F, which had a contract and no server).

  Bytes in → `host/handle` → bytes out. Two things live here that the pure
  host cannot own:

    the reload stream   GET /__shinkansen/reload is a text/event-stream;
                        every open client gets `reload` when the ctx is
                        swapped. `host/reload-script` (injected only when
                        :dev? is set) listens and calls location.reload().
    the watch           `fs.watch` over :watch dirs, debounced; on change
                        `rebuild-fn` runs and must answer {:ok true :ctx …}
                        or {:ok false :problems …}. A failed rebuild keeps
                        the LAST GOOD ctx serving and routes every GET to an
                        error document naming the problems (dev.cljc:
                        error-as-content, never a silent 500). The stream
                        fires either way, so the browser shows the error.

  Every save is a new snapshot — a new head to look at — which is why
  live-reload is the whole HMR story here (SPEC §2.5): there is no module
  to hot-swap, only a new document CID.

  Run programmatically: (start {:ctx … :port 0 :watch [\"src\"] :rebuild-fn f})
  → a promise of {:server :port :stop :swap!}."
  (:require [kotoba.lang.text :as str]
            [shinkansen.host :as host]
            ["node:http" :as http]
            ["node:fs" :as fs]))

(defn- read-body [^js req]
  (js/Promise.
   (fn [resolve _]
     (let [chunks (atom [])]
       (.on req "data" (fn [c] (swap! chunks conj c)))
       (.on req "end" (fn [] (resolve (.toString (js/Buffer.concat (clj->js @chunks)) "utf8"))))
       (.on req "error" (fn [_] (resolve "")))))))

(defn- parse-json [s]
  (when-not (str/blank? s)
    (try (js->clj (js/JSON.parse s) :keywordize-keys true)
         (catch :default _ ::invalid))))

(defn- headers->clj [^js req]
  (js->clj (.-headers req)))

(defn- get-headers
  "The headers a GET/HEAD document answer reads: If-None-Match, and nothing
   else (principal and grant are read on POST <invoke-path> only). Converting
   every header to Clojure cost ~8-11 us per request under kbb/sci."
  [^js req]
  (if-let [v (aget (.-headers req) "if-none-match")] {"if-none-match" v} {}))

(defn- write-response [^js res {:keys [status headers body]}]
  (.writeHead res status (clj->js headers))
  (.end res (str body)))

;; ── the station table ─────────────────────────────────────────────────────
;;
;; A document's ETag is the CID of its bytes, so once the host has answered a
;; URL the answer is a value: the bytes, the headers, the 304. The table
;; keeps that value per URL in the transport's own terms (a Buffer, a flat
;; header array) so a repeat request does no Clojure work beyond a Map
;; lookup — for :static. An :ssr entry re-runs its load-fn with the same
;; params and answers from the table only when the data is `=` to the data
;; the bytes were rendered from (host/response-plan); anything else — a
;; different value, a throwing load — goes to `host/handle`, which answers
;; and refreshes the entry. Swapping the ctx empties the table.

(def ^:const table-limit
  "Entries before the table is emptied and refilled (bounded memory under a
   crawl of distinct URLs; a hot set refills in one request per URL)."
  4096)

(defn- flat-headers [headers body-length]
  (let [a #js []]
    (doseq [[k v] headers] (.push a k (str v)))
    (.push a "content-length" (str body-length))
    a))

(def ^:private threw
  "What a station's `load` answers when the load throws: never `=` to data."
  #js {})

(defn- station [{:keys [response etag kind load-fn params data document]}]
  (let [body (js/Buffer.from (str (:body response)) "utf8")
        cid (subs etag 1 (dec (count etag)))]
    #js {:ssr (= kind :ssr)
         :etag etag
         :weak (str "W/" etag)
         :head (flat-headers (:headers response) (.-length body))
         :h304 #js ["etag" etag]
         :body body
         :threw threw
         ;; An :ssr station may answer only when the load, re-run with its
         ;; params, answers a value `=` to the data the bytes were rendered
         ;; from. The value is handed to the host when it is not (`pre`), so a
         ;; request runs its load once.
         :load (fn [] (try (load-fn params) (catch :default _ threw)))
         :same (fn [d] (= data d))
         :pre (fn [d] {:document document :params params :data d})
         ;; If-None-Match that is a list: the host's full comparison
         :listMatch (fn [inm] (host/not-modified? inm cid))}))

(def ^:private write-station
  "(st, req, res) → writes the station's answer: 304 when If-None-Match names
   its ETag, else 200 (no body for HEAD). A miss writes through this too, so
   the headers are converted to the transport's form once, when the station
   is built (clj->js of the response cost ~57 us per miss, 2026-09-23)."
  (js/Function.
   "st" "req" "res"
   (str "var inm = req.headers['if-none-match'];"
        "if (inm !== undefined && (inm === st.etag || inm === st.weak ||"
        "    ((inm.indexOf(',') >= 0 || inm.indexOf(' ') >= 0) && st.listMatch(inm)))) {"
        "  res.writeHead(304, st.h304); res.end(); return true; }"
        "res.writeHead(200, st.head);"
        "if (req.method === 'HEAD') res.end(); else res.end(st.body);"
        "return true;")))

(def ^:private answer-station
  "(table, req, res) → true when the table answered, false to fall through.

  The one piece of this namespace written in the host's language: a hit is
  a Map lookup, a header compare and a write — mechanism, no decision — and
  interpreted per request it cost ~11 us of the ~58 us a static response
  took (kbb/sci, bench/run.cljk cpu-us, 2026-09-23). The decisions stay in
  Clojure and are called from here: `load`/`same` (an :ssr station's load,
  `=`) and `listMatch` (an If-None-Match list, `host/not-modified?`). A stale
  :ssr station leaves the value its load answered on the request
  (`shinkansenPreload`) for the host."
  ((js/Function.
    "write"
    (str "return function (table, req, res) {"
         "var m = req.method;"
         "if (m !== 'GET' && m !== 'HEAD') return false;"
         "var st = table.get(req.url);"
         "if (st === undefined) return false;"
         "if (st.ssr) { var d = st.load();"
         "  if (d === st.threw) return false;"
         "  if (!st.same(d)) { req.shinkansenPreload = st.pre(d); return false; } }"
         "table.hits = (table.hits | 0) + 1;"
         "return write(st, req, res); };"))
   write-station))

(def ^:private listener
  "(table, fast, slow) → the node:http listener: the table first, then the
   Clojure handler. A plain JS closure so a hit never enters the interpreter."
  (js/Function. "table" "fast" "slow"
                "return function (req, res) { if (!fast(table, req, res)) slow(req, res); };"))

(defn- remember!
  "Keep the plan's station for `url`; answers the station (nil without a plan)."
  [^js table url resp]
  (when-let [plan (::host/plan resp)]
    (when (>= (.-size table) table-limit) (.clear table))
    (let [st (station plan)]
      (.set table url st)
      st)))

(defn- error-ctx
  "The ctx a failed rebuild serves: the last good tree, every leaf replaced
  by the error document, so the browser shows WHY."
  [ctx problems]
  (let [html (:html (host/error-document {:path "(rebuild)" :reason :rebuild-failed
                                          :detail (pr-str problems)}))]
    (assoc ctx :documents (into {} (for [[k _] (:documents ctx)] [k {:html html :mode :ssg :status 500}])))))

(defn start
  "Start serving. Returns a promise of
     {:server <http.Server> :port n :stop (fn []) :swap! (fn [ctx])}
  `:swap!` replaces the served ctx and fires the reload stream — the same
  thing the watch does, callable by a test or a build script."
  [{:keys [ctx port host watch rebuild-fn debounce-ms]
    :or {port 0 host "127.0.0.1" debounce-ms 80}}]
  (let [current (atom ctx)
        clients (atom #{})
        broadcast! (fn [msg]
                     (doseq [^js res @clients]
                       (try (.write res (str "data: " msg "\n\n")) (catch :default _ nil))))
        table (js/Map.)
        swap-ctx! (fn [new-ctx] (reset! current new-ctx) (.clear table) (broadcast! "reload") new-ctx)
        rebuild! (fn []
                   (when rebuild-fn
                     (let [r (try (rebuild-fn @current)
                                  (catch :default e {:ok false :problems [{:reason :rebuild-threw
                                                                           :error (str (ex-message e))}]}))]
                       (if (:ok r)
                         (swap-ctx! (assoc (:ctx r) :dev? true))
                         (swap-ctx! (error-ctx @current (:problems r)))))))
        timer (atom nil)
        on-change (fn [_ _]
                    (when-let [t @timer] (js/clearTimeout t))
                    (reset! timer (js/setTimeout rebuild! debounce-ms)))
        watchers (atom [])
        respond! (fn [^js req ^js res url resp]
                   ;; a document with a plan is written from its station: the
                   ;; same bytes and headers a hit writes, converted once
                   (if-let [st (remember! table url resp)]
                     (write-station st req res)
                     (write-response res resp)))
        threw (fn [^js res e]
                (write-response res {:status 500
                                     :headers {"content-type" "application/json"}
                                     :body (host/->json {:ok false :reason :handler-threw
                                                         :error (str (ex-message e))})}))
        slow (fn [^js req ^js res]
                  (let [url (.-url req)
                        method (.-method req)
                        get? (or (= "GET" method) (= "HEAD" method))]
                    (cond
                      (= url "/__shinkansen/reload")
                      (do (.writeHead res 200 #js {"content-type" "text/event-stream"
                                                   "cache-control" "no-cache"
                                                   "connection" "keep-alive"})
                          (.write res ": open\n\n")
                          (swap! clients conj res)
                          (.on req "close" (fn [] (swap! clients disj res))))

                      ;; GET/HEAD carry no body the host reads: answer now
                      get?
                      (try (respond! req res url
                                     (host/handle {:method method :url url
                                                   :headers (get-headers req) :body nil
                                                   ::host/preloaded (.-shinkansenPreload req)}
                                                  @current))
                           (catch :default e (threw res e)))

                      :else
                      (-> (read-body req)
                          (.then (fn [raw]
                                   (let [body (parse-json raw)]
                                     (if (= ::invalid body)
                                       (write-response res {:status 400
                                                            :headers {"content-type" "application/json"}
                                                            :body (host/->json {:ok false :reason :body-not-json})})
                                       (write-response res (host/handle {:method method
                                                                         :url url
                                                                         :headers (headers->clj req)
                                                                         :body body}
                                                                        @current))))))
                          (.catch (fn [e] (threw res e)))))))
        ;; a station the table may answer never reaches `slow`
        server (http/createServer (listener table answer-station slow))]
    (js/Promise.
     (fn [resolve reject]
       (.on server "error" reject)
       (.listen server port host
                (fn []
                  (doseq [dir (or watch [])]
                    (try (swap! watchers conj (fs/watch dir #js {:recursive true} on-change))
                         (catch :default e (js/console.error (str "watch refused for " dir ": " (ex-message e))))))
                  (resolve {:server server
                            :port (.-port (.address server))
                            :swap! swap-ctx!
                            :rebuild! rebuild!
                            ;; responses the station table answered (a test can
                            ;; tell a hit from a correct slow-path answer)
                            :table-hits (fn [] (or (.-hits table) 0))
                            :stop (fn []
                                    (doseq [^js w @watchers] (.close w))
                                    (doseq [^js c @clients] (try (.end c) (catch :default _ nil)))
                                    (.close server))})))))))
