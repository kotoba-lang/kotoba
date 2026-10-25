# ADR-0001: langgraph-clj — portable Clojure, Datomic-API-first LLM orchestration

- Status: Accepted (2026-06-11, v0.2 で langchain-clj を切り出し)
- 関連: langchain-clj ADR-0001, kawasakijun ADR-0010 (Life Graph — EDN事実層 + Datalogビュー), ADR-0002 (Pregel DAG)

## 課題

LangGraph 相当のエージェントオーケストレーションを、

1. **Clojure WASM で動く前提**(SCI / CLJS / GraalVM / kotoba-clj いずれのホストでも)で、
2. **Datomic API 前提**(状態・履歴・チェックポイントを EAV ファクトとして保持、ADR-0010 と同型)

で実装したい。Python の langgraph はランタイム・依存ともに重く、状態は pickle されたバイナリで、ワークスペースの「1事実1表現 / Datalog ビュー」原則に反する。

## 決定

### 1. 本家と同じ積層: langchain-clj の上に langgraph-clj

```
browser-use-clj      computer-use-clj          ← エージェント層 (このリポジトリに git 依存)
        └────────┬────────┘
          langgraph-clj          comfyui-clj   ← このリポジトリ (オーケストレーション層)
   (graph/checkpoint/prebuilt/viz)
                └───────┬───────────┘
                  langchain-clj                ← 基盤層
  (runnable / message / prompt / model / tool / parser / memory / db)
```

v0.1 で同居していた LangChain 層(`langgraph.{runnable,message,prompt,
model,tool,parser,memory,db}`)は v0.2 で
[langchain-clj](https://github.com/kotoba-lang/langchain)
(`langchain.*`)へ切り出した。依存は langchain-clj のみ(それ自体は依存ゼロ)。

### 2. 全コード .cljc・ホスト能力は注入

- JVM interop なし、スレッドなし、core.async なし、wall clock / 乱数なし。
- I/O(HTTP・JSON)はホスト能力として注入(langchain.model 参照)。
- 並行性は持たない。Pregel superstep 内のノード実行は逐次(意味論として並列)。

### 3. チェックポイントはすべて datom (ADR-0010 L1)

**チェックポイント** = superstep ごとの entity
(`:checkpoint/thread :checkpoint/step :checkpoint/state …`)。
resume / human-in-the-loop / time travel は Datalog クエリで落ちてくる。
ストアは `langchain.db`(Datomic 互換ミニ実装)で、本物の Datomic Local /
DataScript は `langchain.db/api` と同シェイプの関数マップで差し替え。

### 3.1 長期耐久 loop は外側 supervisor の責務

`langgraph-clj` の graph 実行は有界である。Claude Code 型の長時間 agent を作る
場合でも、graph 内に無期限 loop / sleep / worker 管理を入れない。代わりに
host/kotoba code runtime が durable outer loop を持つ:

1. lease を取得する
2. 最新 checkpoint と loop budget を読む
3. `run*` を `:recursion-limit` 付きで 1 tick 実行する
4. checkpoint / event / budget / governor decision を datom に保存する
5. continue / sleep / interrupt / stop を決める

この分離により、`.cljc` の portability と Datalog replayability を保ったまま、
プロセス再起動・stale lease 回収・長期予算管理を実現する。

### 4. LangGraph との対応

| upstream (langgraph) | langgraph-clj |
|---|---|
| `StateGraph` / `add_node` / `add_edge` / `add_conditional_edges` | `langgraph.graph` 同名関数 |
| channel reducer (`Annotated[list, add]`) | `{:channels {:messages {:reducer into :default []}}}` |
| Pregel superstep / recursion_limit | `run-loop` (`:recursion-limit`, default 25) |
| checkpointer / thread_id / time travel | `langgraph.checkpoint` (mem / Datomic) |
| `interrupt_before/after` + `update_state` | `:interrupt-before/after` + `update-state!` |
| `create_react_agent` | `langgraph.prebuilt/create-react-agent` |
| `get_graph().draw_mermaid()` | `langgraph.viz/mermaid` |

LCEL / prompt / model / tool / parser / memory の対応表は langchain-clj
ADR-0001 を参照。

### 5. チェックポイントストア — datomic vs kg.ingest

2 種類の kotoba バックエンドが選択可能:

| バックエンド | namespace | 書き込み | 読み取り | 適用先 |
|---|---|---|---|---|
| `kotoba-checkpointer` | `langgraph.kotoba-checkpoint` | `datomic.transact` | `datomic.q` / `datomic.pull` | ローカル kotoba-server (operator JWT) |
| `kg-checkpointer` | `langgraph.kg-checkpoint` | `kg.ingest` | `datomic.q` (kotobase-kg-v1) | kotobase.net (Bearer JWT 可) |

`kg-checkpointer` は CF Worker がブロックする `datomic.transact` を回避し、
スキーマ設定も不要。チェックポイントは `kotobase-kg-v1` 共有グラフに
`kg/claim/*` 述語として書き込まれ、`datomic.q` で読み返す。

**EDN クレームスキーマ (`kg.ingest` entity)**:
```edn
{:id     "<thread>/<step>"               ; 例: "thread-A/1"
 :kind   "langgraph/checkpoint"
 :claims [{:pred "thread"   :value "<thread-id>"}
          {:pred "step"     :value "<step-as-string>"}   ; "0", "1", ...
          {:pred "state"    :value (pr-str state-map)}   ; EDN 文字列化した状態
          {:pred "frontier" :value (pr-str frontier-vec)}
          {:pred "status"   :value (pr-str status-kw)}]} ; ":running" / ":done"
```

Datomic 属性 `:kg/claim/thread` / `:kg/claim/step` / `:kg/claim/state` /
`:kg/claim/frontier` / `:kg/claim/status` で Datalog クエリ可。

## 非スコープ (v0.2)

- Send API / subgraph(次版候補)
- 真の並列 superstep・トークン単位ストリーミング(チャンク列としての `stream` のみ)
- Datalog rules (%)・`d/history`(必要なら本物の Datomic を差す)
- host 側 durable supervisor 本体(lease / sleep / worker lifecycle / process restart)

## 帰結

- 同一コードが JVM / SCI / CLJS / WASM で動く。テストは JVM (`kbb -M:test`) で実行。
- エージェントの全実行履歴がワークスペースの事実層(ADR-0010)と同じ表現になり、
  m365-archive 等の既存 datom と join できる。
