# ADR-0001: computer-use-clj — portable Clojure, Datomic-API-first computer-use agent

- Status: Accepted (2026-06-12)
- 関連: langchain-clj / langgraph-clj / browser-use-clj ADR-0001, kawasakijun ADR-0010

## 課題

Anthropic computer use 相当のデスクトップ操作エージェントを、

1. **Clojure WASM で動く前提**(実デスクトップはホスト能力として注入)、
2. **Datomic API 前提**(操作履歴を EAV ファクトとして保持)

で実装したい。本家リファレンス(anthropic-quickstarts
computer-use-demo)は Python + Docker/VNC 一体だが、本質は
**「computer tool の action 語彙 + screenshot→act のサンプリングループ」**にある。

## 決定

### 1. デスクトップはホスト能力 (IComputer protocol)

`computeruse.computer/IComputer`(screenshot/key!/type!/mouse-move!/
click!/scroll!/cursor-position)。実装はホストが注入: ワークステーション
なら xdotool/screencapture、サンドボックスなら VNC、デスクトップ自動化
MCP でも良い。screenshot の戻り値は不問(mock は文字列レンダリング、
実ホストは Anthropic image content blocks)— tool 結果へ素通しされる。
テストは `mock-computer`(仮想スクリーン: ウィンドウ矩形・クリックで
フォーカス・フォーカス先へタイピング・決定的レンダリング・操作 :log)。

### 2. 本家 computer use との対応

| upstream | computer-use-clj |
|---|---|
| computer tool の action 語彙 (screenshot/key/type/mouse_move/left_click/…/scroll/cursor_position) | `computeruse.tool`(同語彙の input_schema + `dispatch`) |
| `computer_20250124` server-defined tool type | 明示 input_schema の custom tool として定義(API 互換)。server type を使いたいホストは wire format を自前送信し `dispatch` だけ利用 |
| sampling loop (until no tool_use) | `computeruse.agent` — langgraph StateGraph(`:agent ⇄ :tools`、`done` tool 終端、`:recursion-limit`) |
| Docker/VNC コンテナ | 非スコープ — ホスト側の責務 |

### 3. 操作履歴は datom (ADR-0010 L1)

`:history-conn` を渡すと全アクションが session entity + caction entity
(`:caction/action :caction/input :caction/result`)として記録される。
「セッション s1 の全クリック」「ctrl+s を押した全セッション」は
Datalog クエリ。チェックポイントは langgraph-clj の
`:compile-opts {:checkpointer …}` を透過。

### 4. 積層

deps は langgraph-clj のみ(langchain-clj が transitive)。
browser-use-clj と対になる sibling ライブラリ。

### 5. Human-in-the-loop 承認

外部アカウント作成・規約同意などの不可逆操作は、共有リポジトリ
`kotoba-lang/hil` の `IHumanApproval` を通す。`computeruse.hil` が
`request_human_approval` tool として agent graph に追加し、macOS では
`display dialog` の `Approve` / `Reject` を使う。`Reject` が既定で、
通常は入力欄を表示しない。`input-label` は非機密の短い入力に限り、
credential 名を含むラベルは共有契約で拒否する。

実機 macOS adapter は `:expected-frontmost-app` を指定できる。NGC の例は
Chrome を明示的に foreground にしてから操作し、別アプリが前面なら即時に
停止する。これにより、agent 起動元の Terminal や別 desktop への誤操作を
防ぐ。

## 非スコープ (v0.1)

- 実デスクトップドライバ・サンドボックス(Docker/VNC 相当)— ホスト注入
- left_click_drag(v0.1 では mouse_move + click で代替)・hold_key・wait
- bash / text editor ツール(必要なら langchain tool として並べる)
