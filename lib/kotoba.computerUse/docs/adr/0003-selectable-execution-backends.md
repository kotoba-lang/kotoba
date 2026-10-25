# ADR-0003: selectable execution backends + multi-bot residents

- Status: Accepted (2026-08-29)
- 関連: ADR-0001（IComputer host-capability boundary）, ADR-0010（Datomic
  action log）, com-junkawasaki `manifest/cua-bots.edn`,
  `scripts/cua-bots-tick.cljs` / `scripts/cua-bots-loop.cljs`

## 課題

`computeruse.macos` は「オペレータのデスクトップそのもの」を 1 つだけ持って
いた。screenshot は全画面、click は cliclick、keystroke は System Events。
これは 1 人が 1 台の前に座って agent を回す形には合っているが、常駐 bot
には 3 つの点で足りない。

1. **フォーカスを奪う。** このワークステーションでは多数の Claude Code
   セッションが並行してターミナルのペインで走っており、focus を取り合って
   いる。合成キーストロークは「今 focus を持っているペイン」に入るので、
   別セッションのプロンプトに打ち込む事故が実際に起きる（workspace の既知
   ハザード）。常駐 bot がこれを毎時やるのは論外である。
2. **実行場所が 1 つしかない。** window だけを見たい／別マシンで見たい／
   そもそも画面が要らない（決定論の gate を回すだけ）——どれも「computer
   use」の同じ問いの別の答えなのに、選ぶ口が無かった。
3. **昇格の経路が無い。** 「いまは cheap な非視覚 gate、将来は実 touch
   drag」という bot は、実装を書き換えないと昇格できなかった。

## 決定

### 1. backend contract を IComputer の *下* に 1 枚入れる

`computeruse.backend/IBackend` — `observe!` / `act!` / `probe!` の 3 つだけ。

- `observe!` → `{:png-path … :captured-at … :backend …}`、非視覚 backend は
  `{:exit … :observation … :raw …}`、失敗は refusal map。
- `act!` → **deny-by-default**。その backend が持たない action kind は
  `{:refused true :reason <pinned literal>}` を返す。**黙って何もしない
  経路を作らない。**
- `probe!` → `{:available? true|false|:unmeasured :why … :measured-at …}`。
  **測っていないものを false と言わない**（`:unmeasured` は
  「available? false」とは別の事実）。

IComputer（ADR-0001）は消さない。あれは Anthropic の computer-use action
語彙を langgraph の tool として出すための面で、こちらは「画面はどこにあるか」
の面である。`computeruse.bots/backend->computer` が前者を後者の上に載せる。

### 2. registry は 10 個で固定し、資格は *測った日付付きで* 書く

`resources/computeruse/backends.edn`:

```
:macos-local :window-scoped :agent-space :fleet-node :macos-vm
:linux-container :cf-browser :cf-sandbox :saas-sandbox :host-object
```

各 entry は description・**isolation（オペレータの focus/cursor を奪うか）**・
capability ごと（observe/act/probe）の `:qualification` を持つ。status は
`:qualified` / `:refused` / `:unavailable` / `:pending` / `:unmeasured` の
5 つで、**どれも `:measured-at` を必須にした**（テストが強制する）。

これは workspace の capability-kit の作法をそのまま持ってきたものである:
**測らなかったものを楽観的に書かない。** `:pending` と `:unavailable` は
具体的な `:unblock` 条件を必ず持つ（これもテストが強制する）。

実装があるのは 4 つ（`:macos-local` `:window-scoped` `:host-object`
`:fleet-node`）。残る 6 つは `PendingBackend` に解決し、observe/act は
`:backend/not-implemented` を返し、probe は `:unmeasured` を返す。
**選べるが、選んでも嘘をつかない。**

### 3. `:window-scoped` が既定の「安全な desktop backend」

`screencapture -l <CGWindowID>` は **window を focus せずに撮る**（実測
2026-08-29: 撮影後も frontmost は Terminal のまま）。act は
**app-scripting（AppleScript/AX）だけ**で、`:pointer` `:key` `:type` は
恒久的に `:backend/unsupported-action-kind` で拒否する——合成グローバル
入力は焦点を持つ窓に入るので、並行セッションのペインを撃つ。

#### ⚠ action kind を拒否するだけでは、その能力を排除できていなかった（実測 2026-08-29）

**実 session でこの穴を踏んだ。** model は `:script` の中にこう書いた:

```applescript
tell application "Google Chrome" to activate
tell application "System Events" to key code 116   -- Page Down
```

gate はこれを **4 step 連続で許可した**——kind が `:script` だったからである。
つまり `:pointer` / `:key` / `:type` を kind 名で拒否しても、**同じ合成入力が
残った 1 つの kind の中身として通っていた**。このワークステーションでは、その
key code は並行 agent のターミナルペインに入りえた。

対策として `:script` の**内容**を検査する（`script-hazard`）: System Events の
`keystroke` / `key code` / `key down|up` / `click at`、および
`do shell script` / `run script` を含む script は
`:backend/synthetic-input-in-script` で拒否し、**osascript に到達させない**。

これは AppleScript という間接参照のある言語に対する denylist なので**証明では
なく床**である。構造的な保証は「kind を拒否していること」の側にあり、この検査は
その 1 つ残った kind の明白な穴を塞ぐもの。`activate`（入力を合成せずに focus を
奪う）は許可するが、act result に `:activated-app? true` を載せて receipt に残す。

**教訓を一般化すると: 能力を action kind の名前で排除することは、その能力を
排除することではない。** 残った kind が任意のスクリプトを取るなら、そこを通る。

CGWindowID の取得経路は実測で選んだ: pyobjc Quartz は不在、JXA の
`ObjC.deepUnwrap(CGWindowListCopyWindowInfo(...))` は `undefined` を返す。
**動いたのは小さな Swift ヘルパ**（初回 swiftc 8.8s、以降キャッシュ）。

### 4. 「撮れた」と「黒い矩形が撮れた」を区別する

capture が成功した場合と、真っ黒な画像が返った場合は、どちらも exit 0 に
なる。`image-stats` が sips で 32px BMP に落として画素バイトの stddev を
測り、閾値未満なら `:blank? true` にして session は `:could-not-measure`
で終わる。**実測: 実内容のある窓 94.4 / 塗り潰し 0。**
これが無いと bot は黒い画面を「観測できた」と報告する。

### 5. multi-bot resident layer（`computeruse.bots`）

名簿 entry は fail-closed で検証する（cloud-itonami の
`grok_bot_runtime/normalize-config` と同じ作法）。**backend id の実在は
registry に問い合わせる**——ここに id の写しを持つと registry が伸びた日に
嘘をつき始める。

1 session = 1 bot = observe → interpret → **gate** → act のループ。
**gate はすべての `act!` の前に決定論で走る**:

| reason | いつ |
|---|---|
| `:gate/step-ceiling-reached` | step ≥ `:bot/max-steps` |
| `:gate/budget-exhausted` | tokens ≥ `:bot/budget-tokens` |
| `:gate/malformed-action` | action map でない / 未知の kind |
| `:gate/action-kind-not-allowed` | `:bot/allowed-actions` に無い |
| `:gate/frame-dimensions-unknown` | frame が寸法を報告していない |
| `:gate/coordinate-outside-frame` | 座標が frame の外 |

順序は契約の一部（ceiling は action ではなく session の話なので先）。
**拒否は reason literal つきで receipt に記録され、model には history と
して返る。黙って落とさない。** 負テストは literal を pin する——「失敗した」
だけを assert するテストは、別の理由で落ちた実行を成功として数える
（ADR-2608136000 が名指しした形）。

`:gate/frame-dimensions-unknown` は「測れなかったものを permissive に
しない」ための項目である。寸法を報告しない backend が、報告しないという
理由で無制限の click を得てはならない。

### 6. outcome は 3 値で、3 値のまま exit code になる

`:done` → 0 / `:failed` → 1 / `:could-not-measure` → 2。

**畳まない。** 観測できなかった session（window が無い / frame が黒い /
model adapter が死んでいる）は「目標を達成できなかった」とは別の事実で、
これを 1 に畳むと、走らなかった検査が走って落ちた検査と同じ値を返す。

### 7. model adapter は「text in / text out + 任意の画像パス」1 本

`computeruse.model-adapters` の adapter は
`(fn [{:keys [prompt image-path]}] → {:text :tokens :adapter} | {:error})`。

langchain の `ChatModel` protocol を**使わない**のは、常駐 CLI が nbb で
bare checkout から動く必要があるからである（langgraph / langchain は
tools.deps の git 依存で、nbb は解決できない）。`computeruse.agent` と
`computeruse.openai-model` は JVM の tool-calling ループのためにそのまま
残り、`bots/backend->computer` が両者を繋ぐ——**registry は 1 つ**で、
「画面がどこにあるか」の概念が 2 つに割れないようにする。

prompt には**その frame がどのアプリの窓か**を書く。実測 2026-08-29:
これが無い版では、model が Chrome の窓を見ながら 8 step 連続で Safari を
scripting した——**すべて gate を通った正当な action で、宛先だけが違った**。
画素にアプリ名は写っていない。

**残り step 数と「step 切れ = FAILED」も書く。** 実測: 書かない版では、
既に描画済みのページを前にして 8 step すべてを navigate と scroll に使い、
一度も結論しなかった。

実測（2026-08-29）で 2 つとも **画像を実際に読むこと**を証明した（受け
取ったこと、ではなく）:

| adapter | 証拠 | 所要 |
|---|---|---|
| `:claude-cli` | スクリーンショットの中にしか無い「パンの保存方法についての日本語の会話」を描写した | 9.3s |
| `:murakumo` | ChatGPT ウィンドウの capture に対し「ChatGPT デスクトップアプリのウィンドウ」と答えた | 64s |

どちらの答えも prompt にもファイル名にも含まれていない。既定は速い方
（`:claude-cli`）。

murakumo は alias `murakumo-main` で解決する（workspace の規則どおり
env override → alias → endpoint-only fallback）。**具体的な model id は
どこにも焼かない。** ⚠ 実測: alias entry が自分で宣言している endpoint
（`infer.murakumo.cloud/v1/chat/completions`）は同日 text/vision とも
**HTTP 404** を返し、動いたのは `api.murakumo.cloud/v1/chat/completions`
だった。resolver は宣言 endpoint を先に試し、答えなければ fallback し、
**どちらが答えたかを receipt に記録する**。

### 8. JSON は自前で読む

`computeruse.json`（~80 行、pure）。nbb では `js/JSON` が、JVM では
`clojure.data.json` が使えるが、**両ホストで別のパーサを使うと、両ホストで
別の挙動をする**。依存ゼロで 1 つにした。malformed input は throw する——
**parse 失敗が空応答と同じ顔をしてはならない。**

## 実測した資格（2026-08-29）

| backend | observe | act | probe |
|---|---|---|---|
| `:macos-local` | qualified | **refused**（`:backend/foreground-not-allowed`、deny-by-default） | qualified |
| `:window-scoped` | **qualified** | qualified（`:script` のみ。他 3 kind は恒久拒否） | qualified |
| `:host-object` | **qualified** | refused（`:backend/act-unsupported`） | qualified |
| `:fleet-node` | **unavailable** | unavailable | qualified |
| 他 6 つ | pending | pending | pending |

`:fleet-node` は judah / simeon / zebulun の **3 台とも** ssh 到達可能で
`/usr/sbin/screencapture` も在るが、ssh セッションに window server が無い
ため `could not create image from display` で exit 1 になる。**ノードには
何もインストールしていない。** `probe!` は毎回これを測って報告する。

## 実 session 2 本（2026-08-29、着地前に実行）

**`:host-object` / `isekai-touch-qa`** — exit **0**、`:done`、29s、999 tokens、
step 0（act 無し）。network-isekai の決定論 gate
（`kbb --backend sci scripts/run-task.cljk jintori-touch`）を実際に回し、その verdict を
observation として model が結論した:

> "jintori scene verified responding with touch stick input handling:
> 7/7 tests passed, compilation successful, axis-based input detection working"

**`:window-scoped` / `uiux-bots-page-qa`** — exit **1**、`:failed`、7 step、
10,822 tokens、8 frame。Chrome の窓を focus せずに 8 枚撮り、model が
`{:done true :success false}` で自分から終えた:

> "Grok runtime and Workstation loops sections are visible and rendering
> live data with current timestamps (not stale). No empty sections or
> error displays observed in visible content. Hyakka section not visible
> in current viewport — unable to confirm its status due to step/method
> limitations."

**これは失敗ではなく、正しい 3 値の答えである** —— 3 セクションのうち 2 つを
確認し、3 つ目を確認できなかったと申告した session は `:done` ではない。
そして「観測できなかった」（exit 2）でもない。

同 session の **step 1 で guard が実際に発火した**: model が
`keystroke "l" using command down` … `key code 36` を書き、
`:backend-refused? true` で **osascript に届かなかった**。負テストだけでなく
本番でも両方向を見せている。

## 現在地の穴（正直に）

- **`:script` の内容検査は denylist である。** `run script` と
  `do shell script` は塞いだが、AppleScript は間接参照を作れる言語なので、
  これを「合成入力は不可能」と読まない。allowlist（アプリの scripting
  dictionary の verb だけを許す）にするのが本筋で、それは未実装。
- **`:window-scoped` の bot は自分の窓を開けない。** probe が target window
  の実在を要求するので、Chrome が最小化されている／別 Space に在ると
  session が始まる前に `:could-not-measure`（exit 2）で終わる。これは嘘は
  ついていないが、自己修復できない。塞ぐなら「観測前に 1 回だけ gate 済み
  `:script` を許す」形になる。
- **`backend->computer`（langgraph bridge）は JVM のユニットテストまで**で、
  実 model を通した E2E はしていない。常駐 CLI はこの経路を使わない。
- **6 backend が pending。** それぞれの `:unblock` は registry にある。
  一番近いのは `:linux-container`（このマシンに docker 29.4.0/OrbStack が
  実在する。足りないのは image と capture 経路）。
- **token 会計は adapter ごとに意味が違う。** `:claude-cli` は
  input+output だけを数える（cache_read は Claude Code 自身の system
  prompt のもので、空の呼び出しでも 35k あり、どんな budget も一瞬で
  使い切る）。生の usage map は receipt の `:raw` に残す。
