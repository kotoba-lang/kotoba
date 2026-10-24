(ns fleet.cli
  "The plumbing every fleet entrypoint had its own copy of: argv parsing, a
  child-process wrapper, and an HTTP call.

  Extracted because four scripts had drifted into four slightly different
  versions of each — one `sh` swallowed stderr, another inherited it; one HTTP
  helper reported a failed curl as status 599 and another let the exception
  escape. Divergence in the plumbing is how a fleet ends up with a component
  that reports success differently from its neighbour.

  `sandbox_agent.cljs` deliberately keeps its own copies: it is scp'd to a node
  and run standalone, so it must not require anything."
  (:require ["node:child_process" :as cp]
            [kotoba.lang.text :as str]))

;; ── args ────────────────────────────────────────────────────────────────────

(def argv (vec (.-argv js/process)))

(defn opt
  "Value of `--flag`, or `default`. Scans the whole argv, so it does not care
  where nbb's own flags sit."
  [flag default]
  (or (second (drop-while #(not= flag %) argv)) default))

(defn flag? [f] (boolean (some #{f} argv)))

(defn req
  "Value of `--flag` or die — for arguments with no sane default."
  [flag]
  (or (opt flag nil)
      (throw (ex-info (str flag " is required") {:flag flag}))))

;; ── processes ───────────────────────────────────────────────────────────────

(defn sh
  "Run `cmd` with `args` (no shell). Returns stdout. Throws on non-zero exit,
  with stderr in the message — a silent failure in a fleet step is worse than a
  loud one."
  [cmd args & [opts]]
  (try
    (cp/execFileSync cmd (clj->js (vec args))
                     (clj->js (merge {:encoding "utf8" :maxBuffer (* 64 1024 1024)} opts)))
    (catch :default e
      (throw (ex-info (str cmd " failed: "
                           (str/trim (str (or (some-> (.-stderr e) str) (.-message e)))))
                      {:cmd cmd :args (vec args) :status (.-status e)})))))

(defn sh-status
  "Like `sh` but never throws: {:exit n :out s}."
  [cmd args & [opts]]
  (try {:exit 0 :out (sh cmd args opts)}
       (catch :default e {:exit (or (:status (ex-data e)) 1) :out (ex-message e)})))

;; ── http ────────────────────────────────────────────────────────────────────

(defn http
  "One HTTP call via curl. {:status n :body s} — a transport failure is status
  0 with the error in :body, never an exception, so callers branch on status
  instead of mixing two failure channels."
  [{:keys [url method headers body timeout-sec] :or {method :get timeout-sec 60}}]
  (let [hdr (mapcat (fn [[k v]] ["-H" (str (name k) ": " v)]) headers)
        args (concat ["-sS" "--max-time" (str timeout-sec) "-w" "\n%{http_code}"
                      "-X" (str/upper (name method)) url]
                     hdr
                     (when body ["--data-binary" body]))
        {:keys [exit out]} (sh-status "curl" (vec args))]
    (if (zero? exit)
      (let [lines (str/split-lines out)]
        {:status (js/parseInt (last lines)) :body (str/join "\n" (butlast lines))})
      {:status 0 :body out})))

(defn json-http
  "`http` with a parsed body. {:status n :json m :body s}."
  [req]
  (let [{:keys [status body]} (http (update req :headers merge {"accept" "application/json"}))]
    {:status status :body body
     :json (try (js->clj (js/JSON.parse body) :keywordize-keys true)
                (catch :default _ nil))}))

;; ── output ──────────────────────────────────────────────────────────────────

(defn say [& xs] (println (str/join " " (map str xs))))
(defn warn [& xs]
  (binding [*print-fn* *print-err-fn*] (println (str/join " " (map str xs)))))
