# triage

**LLM 分類 + golden-eval カーネル** — zero-dep, portable `.cljc`（JVM / CLJS / SCI）。
任意のアイテム列を固定ラベル集合へ分類し、golden セットで精度・**安全性**を計測する再利用カーネル。

kotoba-lang org にこれまで無かった「分類器を golden で測る」共通基盤。モデル呼び出しと
JSON parse は **host が注入**する（`koe` の telephony ports と同型の注入境界）。ライブラリ本体は
I/O もサードパーティ依存も持たない純関数だけ。manimani の triage（`triage/triage.bb`）から抽出。

```
host(Ollama/Anthropic/langchain) ──chat-fn/parse-fn 注入──▶ triage.classify/suggest
                                                                  │ [{:itemId :policy :confidence}]
golden cases ──▶ triage.eval/run ──▶ {:rows, :summary} ──▶ triage.metrics/report-str
```

## なぜ accuracy だけでは足りないか

単一スカラー `accuracy=100%` は「校正された分類器」と「golden への丸暗記」を区別できない。
本 lib は安全性指標を前面に出す:

- **auto-apply hazard** — *high-confidence で誤り* かつ safe ラベル（既定 `snooze`）以外。
  これは自動確定（Shift+A 等）が誤って適用してしまう最危険ケース。
- **zero-support** — golden に一度も現れない＝**未テスト**のラベル。
- **per-label recall / precision**、**confusion matrix**。

## API

```clojure
(require '[triage.classify :as classify]
         '[triage.eval     :as eval]
         '[triage.metrics  :as metrics])

;; 1) 分類（chat-fn / parse-fn は host 注入。config はドメイン側）
(def config {:system "あなたは…のアシスタントです…" :schema {…} :labels labels})
(classify/suggest config chat-fn parse-fn items)
;; => [{:itemId "x1" :policy "todo" :confidence "high" :reason "…"} …]

;; 2) golden 評価
(def labels ["reply_llm" "todo" "waiting" "done" "archive" "unsubscribe" "investigate" "snooze"])
(eval/run (fn [items] (classify/suggest config chat-fn parse-fn items)) cases labels)
;; => {:rows [...], :summary {:accuracy 1.0 :hazard [...] :zero-support [...] :per-label {...} :confusion {...}}}

;; 3) 人間可読レポート（既存 accuracy 出力の後ろに追記する想定）
(print (metrics/report-str rows labels))
```

`triage.classify` の純粋ヘルパ（`strip-fence` / `extract-json` / `build-prompt` / `select-known`）も
個別に使える。`extract-json` は `parse-fn` 注入で JVM(cheshire) / cljs(JSON.parse) どちらでも動く。

## test

```sh
kbb -M:test       # JVM
```

ゼロ依存・`format` 不使用・reader 条件分岐は `extract-json` の例外型のみ。bb/SCI でも動く。

## 由来

manimani triage アプリの `triage/triage.bb`（正本分類器）と `src/manimani/triage_metrics.cljc`
から抽出。manimani は本 lib を host 注入で consume し直す（ADR / co-scientist P0-0・C1）。
