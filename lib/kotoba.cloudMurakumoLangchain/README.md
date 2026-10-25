# murakumo-langchain — langchain-clj/langgraph-clj × Murakumo fleet gemma4

[langchain-clj](https://github.com/com-junkawasaki/langchain-clj) /
[langgraph-clj](https://github.com/com-junkawasaki/langgraph-clj) を
Murakumo Mac mini fleet (10 ノード) の **gemma4 QAT** で動かす統合層。

両ライブラリの設計 (zero-dep / 全 .cljc / I/O は注入ホスト能力) を
そのまま踏襲する 3 層:

```
src/murakumo/
  model.cljc   Ollama ネイティブ /api/chat の ChatModel アダプタ (zero-dep, I/O 注入)
  fleet.cljc   10 ノード roster + ラウンドロビン ChatModel (zero-dep)
  host.clj     babashka ホスト能力 (babashka.http-client + cheshire) + (gemma) 便宜関数
examples/
  demo.clj     LCEL chain / StateGraph+checkpointer / ReAct agent — fleet live 検証済
```

`model.cljc` / `fleet.cljc` は WASM premise を守っているので、bb 以外の
ホスト (SCI / cljs / kotoba-clj) でも `:http-fn` / `:json-*` を差し替えれば
そのまま動く。ADR-2605215000 (Murakumo-only inference) 準拠。

## 使い方

```sh
cd 70-tools/clj/murakumo-langchain
kbb -m demo          # 3 デモを fleet に対して live 実行
```

```clojure
(require '[murakumo.host :as host]
         '[langchain.model :as model]
         '[langchain.message :as msg])

;; fleet 全体ラウンドロビン (既定 gemma4:e4b-it-qat)
(def llm (host/gemma))
(model/-generate llm [(msg/user "こんにちは")] {})

;; 12b / 単一ノード / オプション
(host/gemma {:model "gemma4:12b-it-qat"})
(host/gemma-node "http://100.101.27.85:11434" {:options {:num_ctx 32768}})
```

ReAct agent (gemma4 は Ollama native tool-calling 対応):

```clojure
(require '[langgraph.prebuilt :as prebuilt] '[langgraph.graph :as g])
(def agent (prebuilt/create-react-agent
            {:model (host/gemma {:model "gemma4:12b-it-qat"})
             :tools [my-tool]
             :system "After a tool result arrives, answer in one sentence."}))
(g/invoke agent {:messages [(msg/user "…")]})
```

## ハマりどころ (実測)

- **OpenAI 互換エンドポイントは `options`/`num_ctx` を黙って無視する** —
  必ずネイティブ `/api/chat` を使う (このアダプタはそうしている)。
- **gemma4 QAT は reasoning モデル** — `:think false` 既定。有効化すると
  思考トレースが ctx を消費する。
- **12b はノードあたり 1 並列** (M4 16GB)。e4b は 2 並列可。
- **e4b は tool 結果後の最終応答が空になることがある** — tool-calling
  ループの最終応答が要る用途は 12b を使う。
- fleet roster の SSoT は `50-infra/murakumo/fleet.edn` (tailscale IP は
  `fleet.cljc` に転記)。
