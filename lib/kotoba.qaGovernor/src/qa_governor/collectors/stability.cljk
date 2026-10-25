(ns qa-governor.collectors.stability
  "kotoba-lang/qa-governor — deterministic (non-LLM) stability check
  (ADR-2607031100). Regression guard for a real bug found while building
  ghosthacker-flow.terminal: `future`/`agent`/`send`/`send-off` use
  clojure.lang.Agent's non-daemon thread pool, so a `-main` that uses them
  without calling `shutdown-agents` hangs the JVM process after its logic
  finishes. This flags any `-main`-bearing source that risks that exact
  class of hang, plus (optionally) whether the test run finished within a
  time budget as a coarse hang signal.

  Limitation (honest): text-pattern scanning, not a real control-flow
  analysis — it can't tell whether shutdown-agents is reachable from every
  code path, only whether it appears anywhere in the file.")

(def ^:private hang-risk-pattern #"\(future\b|\(agent\b|\bsend-off\b|\bsend\b")
(def ^:private shutdown-pattern #"shutdown-agents")

(defn check-agent-hang-risk
  "-mainを含む1ファイル分のソース文字列を見て、future/agent系を使うのに
   shutdown-agentsが無ければ危険(:at-risk? true)とみなす。"
  [source]
  (let [uses-agents? (boolean (re-find hang-risk-pattern source))
        has-shutdown? (boolean (re-find shutdown-pattern source))]
    {:at-risk? (and uses-agents? (not has-shutdown?))
     :uses-agents? uses-agents?
     :has-shutdown? has-shutdown?}))

(def ^:private test-timeout-budget-ms
  "この時間を超えてtestが終わらない場合、ハング気味とみなして減点する
   （完全なハング検出はホスト側でtimeoutをかける必要がある。ここでは
   ホストが計測したelapsed msを受け取って判定するだけ）。"
  120000)

(defn stability-entry
  "main-sources: `defn -main`を含むソースファイルの内容(文字列)のcoll。
   elapsed-test-ms: テスト実行にかかった時間(ms、任意)。"
  [{:keys [main-sources elapsed-test-ms]}]
  (let [checks (map check-agent-hang-risk main-sources)
        at-risk-count (count (filter :at-risk? checks))
        any-at-risk? (pos? at-risk-count)
        within-budget? (or (nil? elapsed-test-ms) (< elapsed-test-ms test-timeout-budget-ms))
        score (cond
                any-at-risk? 0
                (not within-budget?) 30
                :else 100)]
    {:category :stability
     :score score
     :evidence (str (count checks) " -main source(s) scanned for agent/future without shutdown-agents"
                     (when any-at-risk? (str " — " at-risk-count " AT RISK"))
                     (when elapsed-test-ms (str "; test run took " elapsed-test-ms "ms"
                                                 (when-not within-budget? " (exceeds budget)"))))}))
