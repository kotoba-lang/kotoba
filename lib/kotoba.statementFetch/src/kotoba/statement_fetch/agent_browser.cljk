(ns kotoba.statement-fetch.agent-browser
  "nbb host driver: executes a `kotoba.statement-fetch` plan against the
  `agent-browser` CLI.

  All impurity lives here. The plan itself — including every argv — is
  computed by the pure `.cljc` core, so what this namespace does is limited
  to process spawning, polling, and reporting.

  The driver cannot type a credential: `:handoff` steps compile to no argv at
  all, and the core refuses to compile a flow that carries one."
  (:require [kotoba.lang.text :as str]
            [kotoba.statement-fetch :as sf]
            ["node:child_process" :as cp]
            ["node:fs" :as fs]))

;; ---------------------------------------------------------------------------
;; Locating the CLI
;; ---------------------------------------------------------------------------

(def ^:private candidate-paths
  ["/opt/homebrew/lib/node_modules/agent-browser/bin/agent-browser.js"
   "/usr/local/lib/node_modules/agent-browser/bin/agent-browser.js"])

(defn resolve-cli
  "Locates a runnable `agent-browser`.

  Prefers the globally installed package entry point over the `agent-browser`
  shim on PATH. Observed 2026-07-25: npm's `/opt/homebrew/bin/agent-browser`
  symlink pointed into a deleted scratch worktree, so the shim was dangling
  while the package itself was healthy. Resolving the package directly makes
  the driver immune to that."
  []
  (or (first (filter #(fs/existsSync %) candidate-paths))
      (let [r (cp/spawnSync "which" #js ["agent-browser"] #js {:encoding "utf8"})
            p (some-> (.-stdout r) str/trim not-empty)]
        (when (and p (fs/existsSync p)) p))
      (throw (ex-info "agent-browser not found (npm i -g agent-browser)" {}))))

;; ---------------------------------------------------------------------------
;; Running
;; ---------------------------------------------------------------------------

(defn run-argv
  "Runs one agent-browser invocation. Returns {:ok? :out :err :argv}."
  [{:keys [cli session-flags timeout-ms]} argv]
  (let [full (vec (concat [cli] session-flags argv))
        r    (cp/spawnSync "node" (clj->js full)
                           #js {:encoding "utf8" :timeout (or timeout-ms 120000)})]
    {:ok?  (zero? (or (.-status r) 1))
     :out  (str/trim (or (.-stdout r) ""))
     :err  (str/trim (or (.-stderr r) ""))
     :argv full}))

(defn- sleep!
  "Synchronous sleep. Keeps the polling loop straight-line; nothing else in
  this driver is concurrent."
  [ms]
  (let [sab (js/SharedArrayBuffer. 4)]
    (js/Atomics.wait (js/Int32Array. sab) 0 0 ms)))

(defn page-text
  "Visible text of the whole page. `get text` requires an explicit selector —
  omitting it is a usage error, not an implicit whole-page read."
  [ctx]
  (:out (run-argv ctx ["get" "text" "body"])))

;; ---------------------------------------------------------------------------
;; Human authentication handoff
;; ---------------------------------------------------------------------------

(defn await-login
  "Opens the institution's login page and waits for a human to authenticate.

  Polls the page for the flow's `:handoff/done-when` marker. Returns
  {:ok? true} once it appears, {:ok? false :reason :timeout} otherwise.

  This is the whole of the driver's involvement in authentication. It does
  not read, store, autofill, or transmit any credential — the operator
  authenticates in the browser through their own password manager."
  [ctx login {:keys [poll-ms deadline-ms]
              :or   {poll-ms 5000 deadline-ms 600000}}]
  (let [marker (get-in login [:handoff/done-when :expect/text])]
    (run-argv ctx ["open" (:handoff/url login)])
    (println)
    (println "  ── 認証ハンドオフ ─────────────────────────────────")
    (println "  " (:handoff/reason login))
    (println "   URL:" (:handoff/url login))
    (when-let [fs* (:handoff/fields login)]
      (println "   入力欄:" (str/join " / " fs*)))
    (println "   ブラウザ上でログインしてください。完了を検知したら自動で続行します。")
    (println "   検知条件: ページに「" marker "」が現れること")
    (println "  ───────────────────────────────────────────────────")
    (println)
    (loop [waited 0]
      (cond
        (str/includes? (page-text ctx) marker)
        (do (println "   ✓ 認証を検知しました。続行します。") {:ok? true})

        (>= waited deadline-ms)
        {:ok? false :reason :timeout :waited-ms waited}

        :else
        (do (sleep! poll-ms)
            (when (zero? (mod (+ waited poll-ms) 60000))
              (println (str "   … 待機中 " (quot (+ waited poll-ms) 60000) "分")))
            (recur (+ waited poll-ms)))))))

;; ---------------------------------------------------------------------------
;; Plan execution
;; ---------------------------------------------------------------------------

(defn run-plan
  "Executes a compiled plan. Returns {:ok? :results [...]}.

  Stops at the first failing step: a banking flow that has drifted from its
  recorded selectors must not keep clicking."
  [plan {:keys [session profile timeout-ms] :as opts}]
  (let [ctx {:cli           (resolve-cli)
             :session-flags (sf/session-argv {:session (or session "statement-fetch")
                                              :profile profile})
             :timeout-ms    timeout-ms}
        login (await-login ctx (:plan/login plan) opts)]
    (if-not (:ok? login)
      {:ok? false :stage :login :result login}
      (loop [[step & more] (:plan/steps plan), acc []]
        (if-not step
          {:ok? true :results acc}
          (let [r (run-argv ctx (:step/argv step))
                acc (conj acc (assoc r :step/type (:step/type step)))]
            (println (str "   " (if (:ok? r) "✓" "✗") " "
                          (name (:step/type step)) " "
                          (str/join " " (rest (:step/argv step)))))
            (if (:ok? r)
              (recur more acc)
              {:ok? false :stage :steps :results acc
               :failed (assoc step :result r)})))))))

(defn discover
  "Snapshots the current page so unverified selectors in a flow definition can
  be replaced with real ones. Run this after authenticating, then edit the
  institution EDN."
  [{:keys [session profile]}]
  (let [ctx {:cli (resolve-cli)
             :session-flags (sf/session-argv {:session (or session "statement-fetch")
                                              :profile profile})}]
    {:url  (:out (run-argv ctx ["get" "url"]))
     :snap (:out (run-argv ctx ["snapshot" "-i" "-c"]))}))
