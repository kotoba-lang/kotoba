(ns chie.methods.digest
  "chie 智慧 — Murakumo-only digest narration of the opening-priority readout
  (ADR-2606171200 + ADR-2605215000). Two paths, one invariant:

    - `template-digest` — deterministic, offline narration (the R0/R1 default and the
      fail-open fallback). Pure, replay-safe; this is what the heartbeat emits.
    - `narrate` — LIVE narration via the Murakumo fleet ONLY (LiteLLM loopback /
      EVO-X2 LAN / per-node Ollama), gated by CHIE_MURAKUMO_LIVE=1. Any other endpoint
      throws (murakumo-only-violation? — ADR-2605215000). Live failure falls back to the
      template (fail-open). HTTP is injectable; this namespace loads on any host.

  The digest is NARRATION, never a verdict: it describes the aggregate opening readout
  (who most needs OPENING, by axis) — it does NOT grade capability or forecast (G1/G4)."
  (:require [kotoba.lang.text :as str]
            [chie.methods.analyze :as analyze]))

;; ADR-2605215000: the Murakumo fleet endpoints — NOTHING else is representable.
(def murakumo-allowed-hosts
  #{"127.0.0.1:4000" "localhost:4000"
    "192.168.1.70:8077" "192.168.1.70:11434"
    "127.0.0.1:11434" "localhost:11434"})

(def default-endpoint "http://127.0.0.1:4000/v1/chat/completions")
(def default-model "gemma3:4b")
(def live-env "CHIE_MURAKUMO_LIVE")

(defn murakumo-only-violation [msg endpoint]
  (ex-info msg {:chie/murakumo-only-violation true :endpoint endpoint}))

(defn murakumo-only-violation? [e]
  (boolean (:chie/murakumo-only-violation (ex-data e))))

(defn- host-of [endpoint]
  (when-let [[_ netloc] (re-find #"^[A-Za-z][A-Za-z0-9+.\-]*://([^/?#]*)" (str endpoint))]
    (str/lower netloc)))

(defn assert-murakumo
  "Refuse any endpoint whose host:port is not in the Murakumo fleet allowlist."
  [endpoint]
  (let [h (host-of endpoint)]
    (when-not (contains? murakumo-allowed-hosts h)
      (throw (murakumo-only-violation
              (str "non-Murakumo inference endpoint refused: " endpoint
                   " (ADR-2605215000 — Murakumo fleet is the sole inference SSoT)")
              endpoint)))
    endpoint))

(defn- fmt3 [v] (format "%.3f" (double v)))

(defn template-digest
  "Deterministic aggregate narration of the opening readout. Pure — no I/O.
  `c` is a coverage map (chie.methods.coverage-report/coverage), `res` an analyze result."
  [nodes res c]
  (let [top (analyze/rank (:opening res) nodes 3)
        reach (analyze/rank (:reach res) nodes 1)
        axis-line (->> analyze/axes
                       (map (fn [axis]
                              (let [d (into {} (keep (fn [[nid m]]
                                                       (when-let [v (get m axis)] [nid v]))
                                                     (:concentration res)))
                                    t (first (analyze/rank d nodes 1))]
                                (when t (str (name axis) "→" (get-in nodes [(first t) ":organism/label"] (first t)))))))
                       (remove nil?)
                       (str/join " · "))]
    (str "chie digest — " (:n-nodes c) " nodes / " (:n-edges c) " 縁 ("
         (:open c) " open / " (:closed c) " closed). "
         "Closed concentration most in need of OPENING: "
         (str/join ", " (map (fn [[_ label v]] (str label " (" (fmt3 v) ")")) top)) ". "
         (when (seq reach)
           (let [[_ rlabel rv] (first reach)]
             (str "Top 取-reach (supplier/funder lock-in): " rlabel " (" (fmt3 rv) "). ")))
         "Per-axis lead: " axis-line ". "
         "Routing: OPENING (open-weights / open-compute / anti-monopoly) — observation, not a winner-rank.")))

(defn narrate
  "Return a digest string. Live Murakumo narration when CHIE_MURAKUMO_LIVE=1 and an
  injected :http-post is supplied; otherwise (and on any live failure) the template.
  Always Murakumo-only: a non-fleet endpoint throws before any call."
  ([nodes res c] (narrate nodes res c {}))
  ([nodes res c {:keys [live? endpoint http-post]
                 :or {endpoint default-endpoint}}]
   (let [live? (if (some? live?) live? #?(:clj (= "1" (System/getenv live-env)) :default false))
         template (template-digest nodes res c)]
     (if (and live? http-post)
       (try
         (assert-murakumo endpoint)
         (let [prompt (str "Summarise this AI-ecosystem opening readout in 2 sentences, "
                           "aggregate-only, no winner-ranking, no forecast:\n" template)
               resp (http-post endpoint {:model default-model :prompt prompt})]
           (or (some-> resp str str/trim not-empty) template))
         (catch #?(:clj Exception :cljs :default) e
           (if (murakumo-only-violation? e) (throw e) template)))  ;; fail-open, but never to a bad endpoint
       template))))
