# ADR-0001: comfyui-clj — portable Clojure, Datomic-API-first node-graph engine

- Status: Accepted (2026-06-12)
- 関連: langchain-clj ADR-0001, langgraph-clj ADR-0001, kawasakijun ADR-0010 (EDN事実層 + Datalogビュー)

## 課題

ComfyUI 相当のノードグラフ実行エンジンを、

1. **Clojure WASM で動く前提**(SCI / CLJS / GraalVM / kotoba-clj いずれのホストでも)、
2. **Datomic API 前提**(キャッシュ・実行履歴を EAV ファクトとして保持、ADR-0010 と同型)

で実装したい。本家 ComfyUI は Python + サーバ + GPU 推論が一体だが、
本質は**エンジン**にある: ノード型レジストリ、リンクで結ばれたワークフロー、
content-addressed キャッシュ付きトポロジカル実行、プロンプトキュー。

## 決定

### 1. エンジンと推論を分離 — 重い処理はホスト能力注入

拡散モデル・画像コーデック等の重い処理は実装しない。ノード型の `:fn` は
構築時にホスト能力を closure で受け取る(langchain-clj の
`:http-fn` 注入と同じパターン、`std/host-fn-node`)。エンジン自体は
依存 langchain-clj のみ(それ自体依存ゼロ)・全 .cljc・スレッドなし。

### 2. 本家 ComfyUI との対応

| upstream (ComfyUI) | comfyui-clj |
|---|---|
| `NODE_CLASS_MAPPINGS` / custom node | `comfyui.node` registry / node pack (plain map) |
| `INPUT_TYPES` / `RETURN_TYPES` / `FUNCTION` / `CATEGORY` / `OUTPUT_NODE` | `:inputs` / `:outputs` / `:fn` / `:category` / `:output-node?` |
| API format prompt JSON `{id: {class_type, inputs: {x: [id, idx]}}}` | 同形の EDN map (`comfyui.workflow`) |
| グラフ検証 (型・必須入力・サイクル) | `workflow/validate` |
| 実行エンジン (topo 実行・変更ノードのみ再実行) | `comfyui.exec` — content-addressed cache key |
| `/object_info` | `node/object-info` |
| `/prompt` + `/queue` + `/history` | `comfyui.queue` (enqueue! / run-next! / history) |
| (サーバ・WebSocket UI) | 非スコープ — ホスト側の責務 |

### 3. キャッシュと実行履歴は datom (ADR-0010 L1)

- **cache key** = `(pr-str [class_type 解決済み入力])` の canonical 文字列。
  リンク入力は上流ノードの key + output index で再帰的に内容アドレス化。
  ホストのハッシュ関数に依存しない(JVM/CLJS で `hash` が異なる問題を回避)。
- **`exec/datomic-cache`** — ノード出力を `:cache/key`(unique identity)の
  ファクトとして永続化。executor インスタンスを跨いでキャッシュが生きる。
- **run 履歴** — `execute` ごとに run entity + ノードごとの exec entity
  (`:exec/node :exec/key :exec/cached :exec/output`)。
  「run 7 でどのノードがなぜ再実行されたか」は Datalog クエリ。
- ストアは `langchain.db`(Datomic 互換ミニ実装)。本物の Datomic Local /
  DataScript は `langchain.db/api` と同シェイプの関数マップで差し替え。

### 4. langchain-clj ノードパック

`comfyui.nodes.langchain` — ChatModel / langchain tool をノード型に
ブリッジ。ComfyUI スタイルのグラフで LLM パイプラインが組める。

```
browser-use-clj      computer-use-clj          ← エージェント層
        └────────┬────────┘
          langgraph-clj          comfyui-clj   ← このリポジトリ (オーケストレーション層)
                └───────┬───────────┘
                  langchain-clj                ← 基盤層
```

### 5. ライセンス

本家 ComfyUI 準拠で **GPL-3.0**(コードはクリーンルーム実装だが、
ワークスペースの「本家準拠」方針に従う)。

## 非スコープ (v0.1)

- HTTP サーバ・WebSocket・UI(ホスト側で `queue`/`exec` を呼ぶ)
- 実画像・拡散モデルノード(host-fn-node でホストが提供)
- lazy evaluation / partial output streaming / VRAM 管理相当
