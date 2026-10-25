(ns lg-curpus2skill.server
  "XRPC/runs HTTP server for lg-curpus2skill — clj port of `lg/lg_curpus2skill/
  server.py` (FastAPI/uvicorn → org.httpkit.server, a babashka built-in;
  ADR-2606280030). Same endpoint surface:

    GET  /ok                    → {ok:true}
    GET  /health                → health graph result
    POST /runs                  → invoke a graph synchronously
    POST|GET /xrpc/{nsid}       → XRPC-compat shim (NSID → assistant_id)

  GRAPHS + the NSID→assistant map are ported verbatim. /runs and /xrpc return
  the Python `{output, elapsed_s}` envelope (or `{error, elapsed_s}` + HTTP 500
  on a node error). State is a clj map; the langgraph-clj graphs replace the
  Python LangGraph graphs. There is no postgres checkpointer (stateless
  request-response graphs, exactly as the Python).

  The Python FastAPI server (`lg/`) remains the DEPLOYED runtime and COEXISTS —
  this twin is additive (run alongside until a human cuts over). The pure
  dispatch fns (`runs`, `xrpc-post`, `xrpc-get`, `health`) are testable without a
  running socket."
  (:require [langgraph.graph :as g]
            [cheshire.core :as json]
            [kotoba.lang.text :as str]
            [lg-curpus2skill.graphs.health :as health]
            [lg-curpus2skill.graphs.extract-evidence :as extract-evidence]))

;; ── graph registry + NSID map (verbatim from server.py) ─────────────────────
(def GRAPHS
  {"health"          health/GRAPH
   "extractEvidence" extract-evidence/GRAPH})

(def NSID-TO-ASSISTANT
  {"com.etzhayyim.apps.curpus2skill.health"          "health"
   "com.etzhayyim.apps.curpus2skill.extractEvidence" "extractEvidence"})

;; ── helpers (parity with server.py) ─────────────────────────────────────────
(defn- safe-json
  "Mirrors `_safe_json`: pass JSON-able values through, else stringify."
  [obj]
  (try (json/generate-string obj) obj
       (catch Exception _ (str obj))))

(defn- elapsed-since [t0] (/ (Math/round (* 1000.0 (/ (- (System/nanoTime) t0) 1e9))) 1000.0))

(defn- invoke-graph
  "Run a graph with `{:input ...}` state; return the Python-shaped envelope:
  success → {:status 200 :body {:output ... :elapsed_s n}}
  node error → {:status 500 :body {:error ... :elapsed_s n}}."
  [graph input]
  (let [t0    (System/nanoTime)
        state (g/invoke graph {:input (or input {})})
        es    (elapsed-since t0)]
    (if-let [err (:error state)]
      {:status 500 :body {:error err :elapsed_s es}}
      {:status 200 :body {:output (safe-json (:result state)) :elapsed_s es}})))

;; ── pure dispatch (testable without a running server) ───────────────────────
(defn health
  "GET /health → the health graph result (Python parity)."
  []
  (let [state (g/invoke (GRAPHS "health") {:input {}})]
    {:status 200 :body (or (:result state) {:status "ok"})}))

(defn runs
  "POST /runs body → {:status :body}. body keys: assistant_id, input."
  [body]
  (let [assistant-id (get body "assistant_id" "health")
        graph        (get GRAPHS assistant-id)]
    (if (nil? graph)
      {:status 404 :body {:detail (str "graph '" assistant-id "' not found")}}
      (invoke-graph graph (get body "input" {})))))

(defn xrpc-post
  "POST /xrpc/{nsid} body → {:status :body}. NSID mapped to an assistant; body is
  the graph input (camelCase params match the handler)."
  [nsid body]
  (if-let [assistant-id (get NSID-TO-ASSISTANT nsid)]
    (if-let [graph (get GRAPHS assistant-id)]
      (invoke-graph graph (or body {}))
      {:status 404 :body {:detail (str "graph '" assistant-id "' not found")}})
    {:status 501 :body {:detail (str "NSID not mapped: " nsid)}}))

(defn xrpc-get
  "GET /xrpc/{nsid} query-params → {:status :body} (params are the graph input)."
  [nsid query-params]
  (if-let [assistant-id (get NSID-TO-ASSISTANT nsid)]
    (if-let [graph (get GRAPHS assistant-id)]
      (invoke-graph graph (or query-params {}))
      {:status 404 :body {:detail (str "graph '" assistant-id "' not found")}})
    {:status 501 :body {:detail (str "NSID not mapped: " nsid)}}))

;; ── http handler ────────────────────────────────────────────────────────────
(defn- json-resp [{:keys [status body]}]
  {:status status :headers {"Content-Type" "application/json"} :body (json/generate-string body)})

(defn- parse-body [req]
  (when-let [b (:body req)]
    (try (json/parse-string (slurp b)) (catch Exception _ nil))))

(defn- query->map [qs]
  (if (str/blank? qs)
    {}
    (into {} (for [pair (str/split qs #"&")
                   :let [[k v] (str/split pair #"=" 2)]
                   :when (seq k)]
               [k (or v "")]))))

(defn handler [req]
  (let [uri (:uri req) method (:request-method req)]
    (cond
      (and (= method :get) (= uri "/ok"))
      (json-resp {:status 200 :body {:ok true}})

      (and (= method :get) (= uri "/health"))
      (json-resp (health))

      (and (= method :post) (= uri "/runs"))
      (json-resp (runs (or (parse-body req) {})))

      (and (str/starts-with? uri "/xrpc/") (= method :post))
      (json-resp (xrpc-post (subs uri (count "/xrpc/")) (parse-body req)))

      (and (str/starts-with? uri "/xrpc/") (= method :get))
      (json-resp (xrpc-get (subs uri (count "/xrpc/")) (query->map (:query-string req))))

      :else
      (json-resp {:status 404 :body {:detail "not found"}}))))

(defn start!
  "Start through an explicitly supplied Ring server capability."
  [run-server & [{:keys [port] :or {port 2024}}]]
  (when-not (fn? run-server)
    (throw (ex-info "explicit HTTP server capability required"
                    {:capability :http-server})))
  (let [stop (run-server handler {:port port})]
    (println (str "lg-curpus2skill server up on :" port " graphs=" (pr-str (keys GRAPHS))))
    stop))

(defn -main [& _]
  (throw (ex-info "host adapter required; use the bb serve task"
                  {:capability :host-adapter})))
