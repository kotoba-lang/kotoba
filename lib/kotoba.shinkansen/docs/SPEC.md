# shinkansen — 仕様

**shinkansen は、view・state・agent 向け tool 面のすべてを CID で address する、
Kotoba stack 用 content-addressed web framework である。** 名前が可変な場所に
アプリの要素は 1 つも置かない — link は CID、state 遷移は CID、agent が UI を
取るのも browser と同じ address である。

Status: R0（2026-09-13、ADR-2609131808 accepted）。2026-09-16 設計見直し（§1.5–1.8、`shinkansen.invoke`）。

---

## 1. 設計原理

### 1.1 identity は CID、Location は設定

ADR-2609092600 の app 4 面を framework の primitive としてそのまま使う:

    identity  ipfs://{cid}                       不変。app が記録する唯一のアドレス
    naming    DNSLink / IPNS                     可変な版
    bytes     https://{cid}.ipfs.yataverse.com   Location 1（オーナー指示 2026-09-14。`{cid}.ipfs.kotobase.net` は退役、522）
    entry     https://{name}.itonami.app/        Location 2

- **HTML の link は CID そのもの**: `href="https://{cid}.ipfs.yataverse.com/"` が
  1 等公民（ADR-2609131630 の mirror zone が 2026-09-14 に bytes plane そのものになった）。
  **書き込み経路（2026-09-17 に測って直した）**: bytes plane は R2 `kotobase-graph-database-production` の
  `ipld/{cid}` を最初に読む（net-kotobase/ipfs wrangler.jsonc）ので、**R2 に書けば `{cid}.ipfs.yataverse.com` は
  即解決する** —— app-kotoba-cloud `npm run publish:receipts` がこれ（HEAD で既存 skip → `wrangler r2 object put`
  → plane から読み戻してバイト比較）。archive の `PUT kotobase.net/ipfs/{cid}` は zone の Redirect Rule 4 本
  （2026-09-14 16:03 JST 作成）が Worker `930ce2d0` の除外を無視して全 path・全 method を kotoba.cloud へ
  飛ばしていたため 308 で死んでいた。同日 owner が rule を patch（document は `graph.kotoba.cloud/` へ、
  `/.well-known/ /api/ /xrpc/ /pins /mcp /health /ipfs/ /ipns/` と非 GET は除外）→ `PUT /ipfs/x` は 401
  （= 届いて auth を求める）に戻った。plane は raw を `application/octet-stream` で返す（CID 検証済み bytes の
  面。render は entry host の仕事）。
- **`:document` は自己完結の 1 ファイル**。CDN から asset を取りに行く document は
  CID を名乗れない — `shinkansen.publish/manifest` は外部 asset 参照を
  **理由付きで拒否**する（どの URL が違反かを `:external` で返す）。
  CID gateway への link（`{cid}.ipfs.*` / `{cid}.ipns.*` / path 形
  `ipfs.yataverse.com/ipfs/{cid}`、legacy の `ipfs.kotobase.net/ipfs/{cid}` は 301 で同じ所へ）は
  content 自身なので違反ではない。

### 1.2 Unison 的 content addressing

state も content である。`shinkansen.state/chain-entry` は re-frame の
`db + event → db` の**結果の db 値**を EDN テキストにして hash し、CID を取る:

    {:db       <新しい db 値>
     :db-cid   "bafkrei…"          その content address
     :prev     <前の entry の CID>  head では nil
     :event    <dispatch された event、verbatim>
     :height   3}

- **同じ db 値に至る別の経路は同じ CID に着地する**（`same-db-value-same-cid`
  test が pin）。これが「diff を patch する」代わりに「state 全体を address する」
  Unison 的モデル。
- **chain は検証可能**: `walk-chain` が各 entry の `:db-cid` を自分の `:text` から
  再計算して照合する。1 つでも壊れていれば `:failed-at` に height を出して fail closed。
- **hash 関数は注入**（`cid-fn`）。workspace の content-address lib（本番）と
  guest の `:hash/sha256` capability（kbb）の両方で同じ chain が作れる。

### 1.3 js / event は host の権限（framework は触らない）

- guest（`.kotoba`、amu compile）は **inert document を返すだけ**。shitsuke の
  `reframe_core.kotoba`（db+event→db、effects を host へ）と同じ境界。
- event の実装は既に host 側にある: dom-gpu の `:dom/add-event-listener` op
  （multi-listener、hit-test + bubbling、browser_events.cljk の click/key-down）。
- kbb wire-ids に DOM capability を**足さない**。js 操作は host の権限であり、
  guest が ambient authority を持つことは ADR-2608650000 が恒久に禁止している。

### 1.4 agent は tool call で来る

`shinkansen.mcp` が MCP（stdio JSON-RPC）面を出す。LLM agent は screen ではなく
tool で lake を読み、UI document を取り、dispatch を投げる:

| tool | 先 | 用途 |
|---|---|---|
| `lake_list` | GET /api/v1/lake/blocks | cursor page で最近の block 一覧（CID・size・gateway URL） |
| `lake_head` | GET /api/v1/lake/head | 現在の IPNI advertisement tip |
| `lake_fetch` | GET /ipfs/{cid} | 1 block の取得（meta または text） |
| `lake_dispatch` | （app 側） | `artifact` CID の state chain への event dispatch。**§1.6 の envelope の transport** —— principal と grant は tool 引数ではなく session（server 起動時に束ねる ctx）から来る |

失敗は throw しない: `{:ok false :error <理由>}` を返す。CIDv0（`Qm…`）は
`lake_fetch` が理由を名指して拒否する。

### 1.5 5 つの軸は直交する —— DID / CID / origin / grant / effect（2026-09-16 設計見直し）

オーナーとの設計対話（docs./apps./console. の origin 分離 → DID + Biscuit → CID first、
2026-09-16）から framework の primitive を整理し直した。1 つの request が立てる問いは 5 つで、
それぞれ**別の機構**が答える。どれも他の代用にならない:

    who    principal   DID            誰が求めているか
    what   artifact    CID            正確にどの計算か（identity、§1.1）
    where  origin      Web origin     どこに隔離されているか（Location、§1.1）
    may    grant       Biscuit        何をしてよいと**委譲された**か（上限であって authority ではない）
    do     effect      effect request 実際に起こそうとしている外界への作用

見直し前の shinkansen は what / where を持ち、who / may を持たず、do を名付けていなかった。
`actions/dispatch` は宣言と shape を検査するだけで、`lake_dispatch` は event 以外を受け取らない ——
**binding に届いたことが authority だった。** これは capability-semantics
（`kotoba-lang/lang/capability-semantics.edn`）の `:plain-resource-is-not-authority` と
`:missing-grant :deny` を framework 自身が破っている形。

決定:

- **origin は containment であって proof ではない。** `{cid}.ipfs.yataverse.com` は document ごとに
  別 origin（storage / SW / DOM が隔離される）、`{name}.itonami.app` は人が入る名前。どちらの
  hostname も identity ではなく authority でもない。**authorizer への入力に origin / path / host は
  含めない**（`invoke_test/the-authorizer-sees-the-effect-and-nothing-about-where-the-call-came-from`
  が受け取る key 集合を `#{:principal :artifact :grant :effect}` に pin）。
- **grant は上限、authority は authorizer の決定。** framework は Biscuit を parse しない・署名を
  検証しない・policy を持たない。それは `kotoba-lang/authority`（束）と `org-biscuitsec` の
  `biscuit.kotoba-logic/authorize`（五源 join: amu ∧ vm ∧ grant ∧ policy ∧ runtime）の仕事で、host が
  `authorize-fn` として束ねる。framework が持つのは **seam と fail-closed**: authorizer が無ければ
  `:no-authorizer`、答えが decision の形（`:ok` を持つ map）でなければ
  `:authorizer-answer-not-a-decision`、否なら `:denied` + authorizer の理由。**nil は allow に
  pun しない**（kotoba-lang/authority README の「missing policy が public database になった」形）。
- **shinkansen 自身が行う effect は 1 つ —— chain append。** `:action` は
  `{:effect :chain/append :resource "kotoba://app/<cid>/chain" :event […]}` を求め、`:query` は
  `:app/query`、`:event` は `:app/assert`（`kotoba://app/<cid>/events/<source>`）。resource は
  `kotoba://` scope なので authority の segment 束が新 scheme 無しで covers? を答える。guest の
  re-frame effects（`:fx`）は従来どおり host の権限（§1.3、ADR D4 不変）。
- **chain entry は who と on-whose-decision を記録し、grant は記録しない。** entry に `:principal`
  と `:receipt`（authorizer の答えから `:grant` / `:token` を除いたもの）が載る。bearer を public な
  CAR に載せない（capability-semantics `:raw-bearer-in-public-car :forbidden`）。
  ⚠ 既知の限界（見直し前から）: chain の検証は各 entry の `:db-cid` = hash(`:text`) だけで、
  `:prev` / `:event` / `:principal` は hash に含まれない。entry 単位の改竄耐性は authorizer の
  receipt（署名付き）側の仕事であり、この framework の chain は state identity の chain。

### 1.6 invocation は 1 つの形 —— query / action / event、URL は transport（`shinkansen.invoke`）

見直し前は同じことに 3 つの語彙があった: `shinkansen.actions` は intent を event と呼び、
`shinkansen.load` は query を load と呼び、MCP tool と（文書にあって未実装の）`POST /dispatch` は
それぞれ自分の body で dispatch を encode していた。protocol semantic は 1 つの envelope:

    {:artifact  "bafk…"                        CID（必須）
     :principal "did:key:z6Mk…"                DID（wire 上は任意。要るかは authorizer が決める）
     :grant     <opaque>                       提示された委譲（wire 上は Biscuit）。framework には不透明
     :input     {:kind :query  :params {…}}          ask   — 値を答える
                {:kind :action :event  [id …]}       intend — re-frame event を chain へ
                {:kind :event  :source s :frame f}   happened — 外界の事実を app へ assert}

| kind | 対応する既存 seam | effect | 答え |
|---|---|---|---|
| `:query` | `load/run-load`、`render :ssr` | `:app/query` | station（data CID / document CID） |
| `:action` | `actions/dispatch` → `state/chain-entry` | `:chain/append` | 新 db 値と CID、chain entry |
| `:event` | host が適用（`streamRun` の frame、webhook） | `:app/assert` | 適用結果（host） |

- 順序は **check-envelope → effect-request → authorize → 既存の純粋 seam**。各段が理由を名指して
  止まる（`:cidv0-refused` / `:unknown-kind` / `:action-needs-event` / `:principal-not-a-did` …）。
  defect のある envelope は authorizer に届かない（`invoke_test` が呼出回数 0 を pin）。
- **kind は動詞を跨がない**: `invoke/dispatch` に `:query` を渡せば `:not-an-action`、`invoke/query` に
  `:action` を渡せば `:not-a-query`。query は append しないし event は intent ではない。
- **re-frame の語彙は変えない。** shitsuke の guest が言う「event」は本 SPEC の `:action` の中身
  （`:input :event`）で、guest の「effect」（`:fx`）は host へ出る作用。chain entry の `:event` は
  従来どおり re-frame event を指す。名前を変えるのではなく、envelope の `:kind` が層を言う。
- **transport は adapter**: `invoke/from-mcp`（`lake_dispatch` 引数 + session identity → envelope。
  引数に紛れた `principal` / `grant` は**無視される**）、`invoke/from-route`（解決した route → `:query`
  envelope。path は envelope に乗らない）。HTTP の `POST <api>/invoke` は同じ body を運ぶ host の
  binding で、URL は semantic ではない。browser runtime（§2.3b）の `shinkansen.dispatch(id, params)` は
  host handler を呼ぶ**ローカル**の action であり、chain へ届けるのは host handler が envelope を組んで
  送る責任 —— `{cid}.ipfs.*` origin から API は cross-origin なので **grant は header / body で明示的に
  運び、ambient cookie を authority にしない**。

### 1.7 path は参照、URL は view —— 「Google に合わせない」

`routes/resolve-path` は **name → artifact** の resolver であり、その答えは document でもあり
`:invocation {:artifact <leaf> :input {:kind :query :params …}}` でもある（同じ ok 結果に両方載る）。
同じ CID は N 個の name / N 個の origin から届いてよく、どの URL もその identity ではない:

    resolve(origin, path) → CID          URL = render(origin, CID, context)

- **canonical は CID。** `https://apps.example/<cid>` も `ipfs://<cid>` も `kotoba run <cid>` も
  同じ計算の projection。framework は URL を canonical として記録しない（§1.1「app が記録する唯一の
  アドレスは identity」の言い直し）。
- **`:ssr` は query。** route の params が入力、render fn が artifact の答え、答えは content ——
  `cid-fn` を渡せば `:document-cid` が付く（`render_test/ssr-answer-is-a-station-when-hashed`）。
  `:ssr` が出来ないのは CID を**描く前に**知ること。だから `:ssr` に `:data-cid` を予め宣言するのは
  引き続き `:ssr-with-data-cid` で拒否する（identity は計算されるもので、約束するものではない）。
- **path に持たせる役割は 3 つだけ**: human alias / resolver 入力 / UI navigation state。identity・
  authority・execution semantics は持たせない。`/apps/foo/edit` の `edit` は capability ではなく
  表示。`:links-resolve` / `:locale-path-links` の audit 軸は projection の整合性検査であって、URL を
  identity と認めるものではない。
- **検索エンジン向けの hypertext（`docs.kotoba.cloud/...`）は上の層。** 下の層（CID / DID / grant /
  invocation / effect）を歪めない。二層で、上が下に従属する。

### 1.8 origin 分離の代価 —— preference は name origin の性質

「別の家」の隔離は security には利くが、**preference にはそのまま効く**: `{cid}.ipfs.*` の
document は 1 つずつ別 origin なので、theme の `localStorage["kotoba-theme"]`（§2.3c）も locale の
cookie `shinkansen_locale`（§2.3）も **document ごとに別**になり、CID を跨いで持ち越されない。
これは bug ではなく origin 分離の定義そのもの。従って:

- **theme / locale の記憶は entry（name）origin の性質**（`{name}.itonami.app`）。bytes origin
  （`{cid}.ipfs.*`）で開いた document の既定は theme = `system`（storage 無し = system、§2.3c の
  契約どおり）、locale = Accept-Language（cookie 無し = negotiate の第 2 優先）。
- **cookie の既定は host-only。** `locale/defaults` の `:cookie-attrs` に `:domain` は無い（`Domain=` を
  省いた cookie は host-only）。**parent-domain cookie を置いてよいのは preference（locale / theme の記憶）だけ**
  —— 分離が守るのは authority であって好みではなく、product は name-origin family（docs. / blog. / console.）
  を 1 つの選択で覆うために `:domain` を選べる（§2.3、app-kotoba-cloud の実測）。credential / session /
  grant を `Domain=` で家族全体に配ることは framework のどの seam も許さない（grant は header で運ぶ、§1.6）。
  `Path=` は security boundary ではない。
- **wildcard trust を書かない**: CSP や CORS の allow list に `*.kotobase.net` を入れると 1 つの
  subdomain takeover が全 document に及ぶ。`:csp-allows-assets` 軸（§2.4）は document 自身の asset を
  許すかを見る軸であり、wildcard を推奨する軸ではない。

---

## 2. モジュール

    src/shinkansen/state.cljk    db 値 → CID chain（純粋、hash fn 注入、persistence は caller）
    src/shinkansen/publish.cljk  publish manifest（自己完結検査 + scripts/publish-document.cljk の argv）
    src/shinkansen/mcp.cljk      MCP tool 宣言 + dispatch（純粋、handler 注入）
    src/shinkansen/locale.cljk   locale negotiation 契約（cookie ベース、path 非依存、純粋）
    src/shinkansen/viewport.cljk multi-screen-size 契約（viewport meta + xs band、静的 audit）
    src/shinkansen/audit.cljk    UI/UX document 契約 = 決定論的 fitness function（22 軸、理由付き finding）
    src/shinkansen/coscientist.cljk Generate→Reflect→Rank(Elo)→Evolve→Meta の kaizen loop（judge = audit）
    src/shinkansen/interaction.cljk browser 側の契約（data-action / data-params、run stream、hydrate、theme、locale）+ 1 本の runtime
    src/shinkansen/theme.cljk    light / dark / system の契約（storage、属性、head-script、theme/set）
    src/shinkansen/invoke.cljk   invocation envelope（query / action / event）+ authority seam（authorize-fn 注入、無ければ拒否）+ MCP / route adapter
    src/shinkansen/routes.cljk   name → artifact の resolver（ok 結果に :invocation を同梱）
    src/shinkansen/actions.cljk  post-authorization の宣言検査 + chain entry（binding は invoke 経由でここに来る）
    src/shinkansen/load.cljk     query の答え = data station（EDN text の CID）
    src/shinkansen/render.cljk   :ssg / :ssr / :isr。:ssr は query、cid-fn で :document-cid
    src/shinkansen/host.cljk     reference host（request → response の純関数: name → bytes、POST /invoke、named status）
    src/shinkansen/serve.cljk    node:http transport + dev loop（watch / rebuild / reload stream / error-as-500）
    src/shinkansen/maturity.cljk Next / SvelteKit / shadcn / Radix との比較を data で（declared vs driven、test で ns 実在を pin）
    src/shinkansen/form.cljk     schema（data）→ validate（coerce + field ごとの理由）→ field-attrs（aria-invalid / describedby）
    src/shinkansen/live.cljk     live regions（§2.7）: frame algebra（snapshot / delta / heartbeat / error、`reconcile` 純粋）+ keyed DOM patcher の runtime + `:live-stable` の helper
    examples/reference_app.cljk  本物の CID・本物の Biscuit authorizer を束ねた todo app（`npm run host`）
    test/                        168 tests / 667 assertions, 0 fail 0 error（nbb via kbb）

### 2.1 publish の 2 面契約

実体の publish は root の `scripts/publish-document.cljk`（archive = kotobase.net
`PUT /ipfs/{cid}` → B2、origin = R2 `ipld/{cid}`）。shinkansen はその**前段**:
自己完結検査 → manifest → argv。**1 面だけに書いた publish は web 面で 502 になる**
（archive のみの書き込みは bytes 面で 200・web 面で 502 — 過去の誤診の実測）。

### 2.2 MCP の protocol 契約

- `initialize` → `{protocolVersion, capabilities: {tools}, serverInfo}`（server 名 `shinkansen`）
- `tools/list` → 4 tool の declaration（`base-url` は注入、test は任意 host に向けられる）
- `tools/call` → handler dispatch。handler 無し tool は
  `{:ok false :error "tool not implemented"}` — **宣言済みで実装無しは見える**（silent skip しない）
- `lake_dispatch` は `artifact` + `event` を必須引数とし、handler には `invoke/from-mcp` が組んだ
  envelope が 1 つ渡る。principal / grant は ctx（session）から折り込まれ、引数の同名 key は無視される
  （`mcp_test/lake-dispatch-hands-the-handler-one-envelope-with-the-session-identity`）。tool schema に
  `grant` は無い（`lake-dispatch-declares-the-artifact-required`）。
- 未知 method → JSON-RPC error `-32601`
- **declaration と dispatch 表の同型 test** が「tools/list に載っているのに呼べない」
  tool の発生を落ちるようにしている

### 2.3 locale negotiation は HOST/edge の権限（document は path を fork しない）

オーナー決定（app-kotoba.cloud の実測に基づく）: URL path による locale 選択
（`/ja/about`）は dead link と IA 断片化を生む（22 locale × path 複製）。shinkansen
の framework default は **1 route = 1 language-agnostic document、locale は
cookie（Accept-Language フォールバック付き）で negotiate、言語切替は client 側で
cookie を書く**。

- `negotiate` — 優先順位: **`:explicit`**（`?lang=` や legacy locale path、読者が今使った switch）>
  cookie > Accept-Language q 値 > **`:hint`**（環境の示唆: Cloudflare cf.country → locale）> :default。
  **`:normalize`** は app の alias 表（zh → :zh-Hans、he-IL → :he）で、explicit / cookie / header の
  各 tag に当たる。どの段も `:normalize` の答えが :supported に無ければ **fail-closed で無視**
  （stale/forged cookie も細工した `?lang=` も host が出してない locale に固定できない）。結果は
  `:source`（:explicit / :cookie / :accept-language / :hint / :default）を記録する。q=0 の tag は
  「受け入れない」（RFC 9110）として捨てる（2026-09-16 まで 1.0 に昇格していた）。
  3 つの seam は cloud-kotoba/app-kotoba-cloud が自前の locale.cljk で再導出していたもの（2026-09-16
  実測）—— framework 側に置いて app が require する。
- `set-cookie-header` — Set-Cookie 属性は**この 1 箇所**で serial 化。各 app が
  serialization を再導出するのを禁止。**値は app のもの**: 既定は host-only（`:domain` 無し）だが、
  locale は preference であって authority ではないので、docs. / blog. / console. を跨ぐ product は
  `:domain` に registrable parent を置いてよい（app-kotoba-cloud、オーナー実測 2026-09-16: host-only では
  host を跨ぐたびに言語が反転した）。host を跨いでよいのは preference だけで credential は決して跨がない
  （§1.8）。
- `substitute` — build 時生成 document の SSR seam。shitsuke の i18n table
  （sign_in_i18n 型: source 文字列 → request 時に localize）と対になる。未知の
  文字列は source のまま通す（翻訳欠落は空白ではなく source で見える — 内容は
  fail-open、locale **選択**は fail-closed）。
- `document-variants` — content-addressing 側: 1 route → N locale document、
  それぞれ別 CID（publish/manifest と同じ自己完結検査を通る）。**identity は
  per-locale-CID のまま、name/route は locale 非依存、negotiate は edge/host が
  cookie で行う** — `/ja/` 型の path fork は作らない。

locale negotiation は document ではなく HOST/edge に属する。shinkansen はその
純粋契約だけを提供する（render はしない、cookie を読む IO もしない）。

### 2.3b browser 側の interaction は framework の契約（`shinkansen.interaction`、2026-09-16）

実測: cloud-itonami-app の `interaction.js` は 14,352 行で、共通 component の `script`
（cloud-kotoba-dds shell / chat / bot）とも重複して、hook で要素を探す・要素ごとに listener を
付ける・list を container に描く・`data: <json>` の run stream を読む・mount を hydrate する、を
それぞれ手で書いている。framework が持つのは**契約**と**runtime 1 本**、host が持つのは
「action が何をするか」「stream の event が何を意味するか」「mount に何を描くか」。

1. **action**: control は `data-action="<event-id>"`（+ 任意の `data-params` JSON）を名乗る。
   runtime は click / submit の delegated listener を 1 本だけ持ち、host が `shinkansen.on(id, fn)`
   で登録した handler を `(params, element, event)` で呼ぶ。id は `shinkansen.actions` が宣言する
   event id と同じ語彙（`:cart/add` ↔ `"cart/add"`）。hiccup 側は `interaction/action-attrs`。
2. **run stream**: `shinkansen.streamRun(source, {onEvent, onClose, onError}, init)` は run body を
   行単位で読み、JSON frame ごとに `onEvent` を呼ぶ。wire は 2 形を 1 つの reader で受ける ——
   Hermes 形 SSE（`data: <json>`、`[DONE]` と comment 行は skip）と newline-delimited JSON（行そのものが
   object）。前者は JVM-free Hermes gateway、後者は Bot loop の `/api/bots/:id/messages/stream` が
   話す（2026-09-16 実測、cloud-itonami-app）。`source` は URL か `(init) => Promise<Response>` ——
   認証・CSRF retry は host、読むのは framework。非 2xx は body を読まずに
   `onError({status, response})` へ渡す（host が自分の error body を読める）。`{abort(reason)}` を返す。
   実行検査は `scripts/runtime-node-check.cljk`（runtime 文字列を Node で走らせ両 wire の frame 到達を
   数える。`SCANNED\tn`）。
3. **hydrate**: `shinkansen.hydrate(name, fn)` は `[data-hydrate="<name>"]` の未 hydrate な要素に
   `fn` を当てて印を付ける。mount は server が描き、browser は埋めるだけ。

js / event は host の権限（§1.3）のまま —— framework は DOM capability を足さない。runtime は
文字列で、host が自分の file として配るか 1 度 inline する。

### 2.3b′ 翻訳は rendered document への substitution（`locale/substitute :exact?`、2026-09-16）

オーナー指示「翻訳対応して」。cloud-itonami-app の document は text node 550 / attribute 107 /
inline script literal 1,297 の日本語を持つ。`substitute` の plain mode は部分一致（「送信」が
「送信中」の中で「Send中」になる）なので、**`:exact? true`** を足した: source は text node 全体
（`>src<`、前後空白は保つ）・attribute 値（`="src"`）・script literal（`'src'` / `"src"`）の
いずれか**丸ごと**にだけ当たり、長い source から先に置換する。regex 文字は quote、target の `$1`
は literal、script literal 内の引用符は escape。訳の無い node は source のまま残る（空にしない）。
表は rendered document から抽出した `{ja en}` の EDN。template literal（`` `…${x}…` ``）は
対象外 —— それは残数として測る。

### 2.3c theme と locale は framework の選択（`shinkansen.theme` / `shinkansen.locale` の browser 側、2026-09-16）

オーナー指示「言語切り替え, dark, light, system theme switcher も統合」。同日の実測: theme の
選択は jp-go-dds.theme-toggle（2 状態 λ、key `kotoba-theme`、`<html data-theme>`）、
cloud-itonami-app の `data-appearance` toggle（独自 key、独自 `:root:has()` scope、server が
外した appearance を JS がまだ回す）、OS 追従だけの page、の 3 通りが並存していた。契約は 1 つ:

- **theme**: mode は `light | dark | system`。storage `kotoba-theme` に `light|dark`、**無い = system**。
  `<html data-theme="light|dark">`、system は属性を**外す**（CSS が決して当てない値を入れると黙って
  light になる）。CSS は `jp-go-dds.dark/dark-css`（`:root:root[data-theme]` が media block に勝つ）。
  `theme/head-script` を `<head>` に置いて paint 前に適用、runtime の `shinkansen.theme`
  （`get / effective / set / onChange`）が属性・storage・switcher を同期し、OS の変更にも
  `shinkansen:theme` event で追従する。action は `theme/set {mode}`。
- **locale**: action は `locale/set {locale}`。runtime の `shinkansen.locale.set` が §2.3 の
  negotiation cookie（`defaults` の属性から**導出**、Secure は https のときだけ）を書き、control の
  `href` へ移動するか reload する —— document は host/edge が再 negotiate し、client で描き直さない。
- 両 action は **framework-actions** として全 declaration に merge され、`:actions-declared` 軸は
  宣言無しでも declared と数える。host は `shinkansen.on` で上書きできる。
- **runtime で組み立てる文字列**（template literal）は render 時の `substitute` に映らない —— source に
  1 つの literal として存在しないから。`shinkansen.locale.format(pattern, params)`（cljc は
  `locale/format-message`）で `format('{name} に頼む', {name})` と書けば pattern は普通の quoted literal
  になり、`:exact?` 表がそれを訳し、runtime が穴を埋める。`{key}` は params の値、無い key は
  **そのまま残る**（見える穴。黙って空にしない）、nil は空、数値は `Intl.NumberFormat(<html lang>)`。
  `shinkansen.locale.lang()` は `<html lang>`。

### 2.5 reference host —— 契約を「宣言」から「駆動」へ（`shinkansen.host` / `shinkansen.serve`、2026-09-16）

実測（2026-09-16、cloud-kotoba / net-kotobase / cloud-itonami-app / cloud-kotoba-dds の require 形を数えた）:
19 namespace のうち消費者があるのは 5（interaction 10 / theme 6 / audit 6 / viewport 3 / coscientist 1）、
routes / load / render / actions / invoke / adapter / dev / state / bridge / publish / mcp の 11 は **0**。
契約と test は在るが一度も host に呼ばれていない —— 宣言のみ。reference host はそれを framework 自身の
host で駆動する（product consumer ではない。`maturity.cljc` は `:driven-by-host` と `:driven-by-product` を
区別する）。

`shinkansen.host/handle` は **request data → response data** の純関数、`shinkansen.serve` は node:http の
transport + dev loop:

    GET  <name>         routes/resolve-path → artifact → load（query station）→ render（:ssg verbatim /
                        :ssr = query / :isr = window）→ layouts を外側へ合成 → bytes。
                        ETag = CID、`Cache-Control: no-cache`（name は可変。`{cid}.ipfs.*` が不変 origin）、
                        `Link: <ipfs://cid>; rel=canonical`（identity の在処）、If-None-Match → 304
    POST /invoke        body → envelope（`:kind` と event id の文字列は interaction 語彙で keyword 化）、
                        principal は `principal-fn(headers)`、grant は `grant-fn(headers)`（既定は
                        `Authorization: Bearer <opaque>` の文字列。**何であるかは authorize-fn の仕事**、host は
                        読まない）→ invoke/dispatch | query | authorize(:event) → chain（host の永続化）→ JSON
    status              400 envelope の欠陥 / 403 seam の拒否（`:no-authorizer` を含む —— authorizer の無い host は
                        error ではなく拒否）/ 404 `:no-match` + deepest / 405 / 422 `:undeclared-event` /
                        `:validation-failed` / 500 `:document-not-registered`（tree が名指す leaf が documents に
                        無い = 設定ミスであって missing page ではない）・`:render-failed`・`:load-failed`。
                        error は viewport を持つ document（dev/error-document の規則は本番でも同じ）
    dev                 `:dev?` で reload listener を `</body>` 前に注入（**dev bytes ≠ published bytes**）。
                        `GET /__shinkansen/reload` は text/event-stream、ctx の swap で `reload`。`fs.watch` +
                        debounce → `rebuild-fn` → `{:ok true :ctx}` なら swap、`{:ok false :problems}` なら
                        **最後の良い tree のまま全 leaf を error document（500）に差し替えて理由を見せる**。
                        HMR は無い —— hot-swap する module が無く、新しい document CID が在るだけ

reference app（`examples/reference_app.cljk`、`npm run host`）は本物を束ねる: cid-fn = content-address
（sha2-256 → raw CIDv1、publish 経路と同じ lib。ETag は本物の CID）、authorize-fn = §3.1 の binding
（Ed25519 Biscuit → `biscuit.kotoba/authorize`、kind を 1 つに閉じる）、grant wire = `Bearer <base64 EDN token
model>`（**この app の wire**であって framework の wire ではない）。`/`（:ssg、interaction runtime を inline した
form）、`/todos`（:ssr）、`/todos/:id`（:ssr + path param）、`POST /invoke`。root 鍵は demo 用の固定 seed ——
本番は `auth.kotoba.cloud/v1/biscuit/token` で発行し root 秘密鍵を配らない。

**product binding（kotoba.cloud、2026-09-16）**: bytes を asset binding が配る Worker は `host/handle` に
document を渡せない。そのために公開した seam が `host/document-headers`（ETag = CID / Link / no-cache）、
`host/not-modified?`（receipt だけで 304）、`routes/paths->tree`（flat な emit → tree）。app 側の
`content-identity` ns が render で receipts を書き、Worker の `route-static` が name を tree で解決して
同じ header を答える。`POST /v1/invoke` は `host/handle-invoke` に app の grant-fn（`Authorization: Biscuit`）
と authorize-fn（wire verify → `->grant` → lattice、kind → `kotoba://can/data:read|write`、artifact = receipt
set）を渡す。workerd で 14 check（ETag、304 null body、no-grant、test root の token は signature で拒否）。

実装で見つかった床割れ: `actions/dispatch` の `(resolve 'shinkansen.state/db-text)` は nbb では他 ns が
state を load していないと **nil** を返す。suite では state-test が load するので緑、走る host では
`null.call`（host-node-check の初回で発見）。`require` に置き換えた。**suite の緑は「駆動された」ではない**。

### 2.6 forms —— schema と field-error の契約（`shinkansen.form`、2026-09-16）

shadcn 側の react-hook-form + zod に当たるもの。schema は data（`{:fields {:email {:type :string
:required true :max 120 :pattern … :message "…"} …}}`）、`validate` は form が post した文字列を型に
coerce し、**落ちた field と rule を全部**名指す（`{:errors {:email [:pattern] :agree [:required]}
:messages {…}}`）。markup 側は `field-attrs` が control に `aria-invalid="true"` + `aria-describedby`
（`<id>-error`）を出し、jp-go-dds `form-field :error` が同じ id で error text を描く —— error は control の
そばに在り、消える toast ではない。`actions` の declaration は `:validate` に fn の代わりに **schema map** を
受け、拒否に `:errors` / `:messages` を付ける（同じ schema が chain と form の両方を gate する）。

`:behaviors-delivered`（§2.4）の契約表は jp-go-dds.behavior 0.2.0 の **12 kind** を知る（2026-09-16 に
popover / tooltip / select / slider / table が加わった。宣言があるのに契約表に無ければ「no such behaviour」に
なるので、behavior 層と audit は同じ日に動く）。

### 2.7 live regions —— 開いている間に変わるデータの契約（`shinkansen.live`、2026-09-17）

**実測（console.kotoba.cloud/requests/、2026-09-17、Chrome の performance API）**: document の
DOMContentLoaded 390 ms に対し `GET /v1/requests` は初回 4,978 ms、2 回目 **17,863 ms**、応答 195 KB
（500 行）。authority の Durable Object は 2,977 本の job 記録（各 prompt + 応答で数 MB）を毎回
decode して 300 byte の行を作っていた。その walk の間、同じ object を通る `/v1/billing/status`
（3,552 ms）/ `/v1/research/status`（4,900 ms）も待たされる —— **一覧が console 全体を遅くしていた**。
browser 側は 15 秒ごとに全件を取り直し、`replaceChildren` で table を作り直し、`<select>` の option も
組み直す（scroll・選択・開いた list が消える —— 「更新のたびに崩れる」）。document は data が来るまで
tile も table も `hidden` で、来た瞬間に page が伸びる（「すぐにコンテンツが表示されない」）。

これは 3 つの契約の欠落であり、`shinkansen.live` はその 3 つを持つ。**js / event は host の権限
（§1.3）のまま**: framework が持つのは frame の algebra と runtime 1 本、host が持つのは行の描き方
（`create` / `patch`）と行の意味。

1. **wire は frame、frame は差分。** 1 つの reader（§2.3b `streamRun`、または fetch）で 4 種を受ける:

       {:kind :snapshot  :cursor c :rows [...]}                  集合全体（最初の 1 回）
       {:kind :delta     :cursor c :upsert [...] :remove [ids]}  cursor 以降に変わったもの
       {:kind :heartbeat :cursor c}                              変化なし
       {:kind :error     :reason "…"}                            名指しの拒否

   cursor は server の単調時計（ms）。client は `?since=<cursor>` で再開し、transport が poll でも SSE でも
   frame は同じ。**毎 tick 全件を送り直すのは anti-pattern `:full-refetch`**（`live/anti-patterns`）。
   frame の algebra は `live/reconcile`（pure）—— browser runtime と同じ規則を Clojure で持つので、server は
   inline する最初の frame を作れ、test は frame 列の帰結を DOM 無しで pin できる。

2. **server は projection から答える。記録を歩かない。** 行は byte、記録は MB。store は記録の隣に行の
   index entry（記録が変わるたびに更新）を持ち、一覧は index を **1 回の bounded な操作**で読む。
   予算は契約の一部: endpoint は O(rows) で答え、O(records × record size) は
   `:walk-the-records` として設計 review で落とす。

3. **DOM は keyed patch。region を作り直さない。** `shinkansen.live(mount, opts)` は `opts.key` で行を
   keyed に持ち、key ごとに node を **1 度だけ** `create`、行が変わったときだけ `patch`（text node
   のみ）、順序どおりに `insertBefore`、消えた key を remove —— それ以外に触らない。node が生き残るので
   focus・選択・scroll が生き残る。`<select>` は option 集合が変わったときだけ組み直す（`live.options`、
   選択値は保つ）。region は data が来る**前に**高さを確保する（`live-attrs` → inline `min-block-size`
   / `aspect-ratio`）ので、最初の frame は page を伸ばさず空間を埋める。最初の frame は edge が
   document に inline できる（`snapshot-script`、`[data-live-snapshot]` の JSON）—— 最初の paint に行が在る
   （§2.3 の `:edge` load の live 版）。runtime は inline があればそこから始め、無ければ fetch する。
   `document.hidden` の間は何も fetch せず **`paused`（reason `hidden`）を告げる** —— 見えない document の
   indicator が「読み込んでいます…」のまま止まっていた（2026-09-17 実測: automation の background tab）。
   `visibilitychange` で見えた瞬間に cursor 付きで接続する（次の wake-up を待たない）。401 は `signed-out`
   で止まる。失敗は backoff（最大 8×interval。stream の close は pending の backoff を上書きしない）。

**audit 軸 `:live-stable`（§2.4）**: `[data-live]` を宣言した document は、(a) 各 region が空間を確保して
いる、(b) `shinkansen.live` を定義した script が配られている、の 2 つを静的に約束する。宣言が無ければ
`:not-applicable`、参照 script が供給されなければ `:unmeasured`（pass と同じ値は返さない）。runtime の
振る舞い（同じ node が frame をまたいで生きること、順序、削除、option の再構築が集合の変化時だけである
こと、hidden の間は fetch せず shown で即接続すること）は `scripts/runtime-node-check.cljk` が DOM double で
実行して数える（`SCANNED	14`）。

**consumer の形（kotoba.cloud の Requests / Dashboard）**: authority は job 記録の隣に
`idx:<createdAt>:<jobId>` の行 projection を持ち、`/jobs/list` は index を `limit`+`reverse` で 1 回読む
（`since` があれば `updatedAt > since` の行だけ）。edge の `GET /v1/requests?since=` は delta frame、
`GET /v1/requests/stream` は同じ frame を SSE で流す。document は `live-attrs` で tile / table / chart の
高さを確保し、edge は signed-in の request に最初の snapshot を inline する。browser は
`shinkansen.live` に行の `create` / `patch` を渡すだけになる。

### 2.4 UI/UX document 契約は fitness function である（`shinkansen.audit` + `shinkansen.coscientist`）

オーナー指示（2026-09-15、`kotoba.cloud/account` の実測「uiux 品質があまり高くない」）:
framework の改善は co-scientist の approach で進める —— **測れない品質は劇場**
（keiei-arbor ADR-2606141500 / isekai.ux ADR-0007 / 90-docs/design-quality と同系）。

`shinkansen.audit/score-document` は emitted HTML 1 枚を 13 軸で採点し、各 miss を
**理由付きで名指し**する。軸はすべて live page で実測した失敗から起こした
（2026-09-15 の `/account`: 20.5 / 100、12 finding）:

| 軸 | 実測した失敗 |
|---|---|
| `:assets-resolve` | `/js/session.js` が本番で 404 —— document は届くが hydrate せず、全 cell が永遠に「読み込んでいます…」 |
| `:unique-ids` | `account-refresh`×4 / `account-org-create`×2 —— 2 個目以降は listener の付かない死んだ button |
| `:idle-pending` | idle document に 12 個の loading cell —— readiness ではなく捏造された progress |
| `:nav-one-home` | sidebar の `/account`×3、`data-current`×3 |
| `:nav-before-content` | phone band で 13 link（1,148px）の nav が本文の前に来る |
| `:skip-link` / `:plain-labels` / `:idle-disabled` / `:repeated-actions` / `:note-density` / `:locale-path-links` / `:fixed-anchor` | 同 page で各 1 件以上 |

- **2026-09-15 第 2 周（オーナー実測「/docs/ 下層で layout が崩れる・ページが見つからない」）で足した 3 軸**:
  `:links-resolve`（same-origin の `<a href>` は公開 document か宣言 route に解決する —
  sidebar が `/docs/` を link しながら `/docs/index.html` を emit していなかった = framework
  自身が書いた 404）、`:csp-allows-assets`（host の CSP が document 自身の stylesheet /
  script を許す — `style-src 'unsafe-inline'` の下で外部 CSS に移した瞬間、全頁が
  無スタイルで届きながら bytes の audit は 100 だった）、`:pre-overflow`（`<pre>` を持つ
  document に `overflow-x:auto` — phone で code が行の途中で切れる）。ctx に `:documents` /
  `:routes` / `:csp`（文字列、または CSP を配らないことの明示 `:none`）を渡す。
- **2026-09-15 第 4 周（オーナー実測「右上のヘッダーがスクロールする」「左下のメニューが
  単に広がる」）で足した 1 軸**: `:chrome-layers` — document が**宣言した** chrome はその層を保つ。
  `data-chrome=top` を付けた要素（console の top bar）には `position:sticky|fixed` + block anchor
  の rule が、`data-chrome=float` を付けた要素（popover menu）には `position:absolute|fixed` +
  `z-index` の rule が、その marker を名指しで当たっていること。marker が契約であって class 名
  ではない（cloud-kotoba-dds.shell が両方の marker を emit する）。menu は hidden のまま測る
  —— 開く前に層の rule が無ければならない。宣言の無い document は測るものが無く 1.0。
- **2026-09-15 第 5 周（オーナー実測「code area が見ずらい」）で足した 1 軸**: `:code-language` —
  可視の `<pre>` は自分の言語を名乗る（`<pre data-lang>` か、子 `<code class="language-x">`。
  cloud-kotoba-dds.code/block が両方を emit する）。名乗らない block は 1 色の壁で、token 化も
  読み上げもできない。`<pre hidden>`（script が埋める JSON dump）は data であって block ではなく
  数えない。score は名乗った block の割合、finding は件数と直し方。`:pre-overflow` はそのまま
  「scroll か wrap できること」を測り続ける。
- **2026-09-16（オーナー指示「interaction などを共通化」）で足した 1 軸**: `:actions-declared` —
  document の control が名乗る `data-action` id は、`shinkansen.actions` の宣言（ctx `:actions`）に
  在る event である。browser と agent の dispatch 語彙は 1 つなので、宣言に無い id を名乗る
  control は surface が `:undeclared-event` で拒否する死んだ control。control が 1 つも無い
  document は **`:not-applicable`**（score でも unmeasured でもなく平均から外れる —— 1.0 を
  配ると control の無い静的頁が全部持ち上がる。実測: account-like fixture 39.6 → 40.8）。
  宣言無しで control が在る document は `:unmeasured`。
- **2026-09-16（オーナー実測「docs.kotoba.cloud/graph/ の uiux が崩れている」）で足した 1 軸**:
  `:classes-styled` — document が要素に付けた class 名は、その document が運ぶ CSS（inline
  `<style>` か、ctx `:stylesheets` で渡された same-origin stylesheet）の selector に当たっている。
  上の marker 軸は document が**宣言した**もの（`data-chrome` / `data-action` / `data-lang`）しか
  見ないので、shipped されない stylesheet 向けに書かれた markup は何も宣言せず何も落とさない ——
  実測: `/docs/graph/` は marketing header / footer の markup を emit しながら token bridge しか
  inline せず、54 class 中 27 に rule が無く、header は生リンクの羅列・skip link は出っぱなしのまま
  audit は 98.3。selector だけを見る（`url(x.png)` の `.png` や宣言の `.5rem` は rule ではない）。
  許容は **5 分の 1、ただし最低 1 つ**（rule の無い hook class は健全な頁にも在る。実測 3 / 58、
  10 / 122）。超過分は線形に落ち、5 分の 3 で 0。class を 1 つも持たない document は
  `:not-applicable`、stylesheet が渡されていなければ `:unmeasured`。finding は名前を sorted で
  最大 12 個 + 件数、直し方は「shared shell（site-layout / docs-page）を通すか、書いた CSS を
  inline する」。
- **2026-09-16（オーナー指示「Radix 相当の behavior 層」）で足した 1 軸**: `:behaviors-delivered` —
  document が `data-behavior=…`（jp-go-dds.behavior: dialog / menu / tabs / disclosure /
  radiogroup / toast / combobox）を宣言したら、その marker を select する script が**運ばれて**
  いて（inline か、ctx `:scripts` で渡された same-origin script）、かつ subtree が契約の markup
  （menu なら `[data-menu-opener][aria-expanded][aria-controls]` と
  `[data-menu-popup][data-chrome=float]`、tabs なら tablist / tab[aria-selected] / tabpanel、
  combobox なら `[role=combobox]` の aria 3 点と `[role=listbox]`、dialog は `<dialog>` +
  aria-labelledby、toast は role=status + aria-live、radiogroup は role=radiogroup +
  radio[aria-checked]、disclosure は aria-expanded + aria-controls）を持つこと。runtime 無しの
  markup（deploy が script を忘れた /account の形）も、markup が足りない runtime も、class は
  1 つも変わらないまま死んだ control になる —— どちらも finding で名指す。marker の無い
  document は `:not-applicable`、参照した script が渡されていなければ `:unmeasured`。
  score は「守られた宣言 / 宣言」。契約表は `shinkansen.audit/behavior-contract`（data）。
- **1 本の emit tree を複数 host が分け合うとき**、document ごとの `:ctx` を shared ctx に
  merge する（docs host の page は自分の surface の `:documents` に対して link を解決する）。
- **測れない軸は pass にしない**: asset set を渡さないと `:assets-resolve` は
  `:unmeasured` に載り平均から除外される（0 でも 1 でもない）。0 枚の audit は
  `:empty? true` で overall 0。
- 可視性は構造で判定する（`hidden` 属性、閉じた `<details>` の summary 以外）。
  idle 系の軸は browser が既定で隠すものを数えない。
- `shinkansen.coscientist/kaizen-cycle` は finding ごとに hypothesis を 1 本
  （owner = :consumer / :deploy / :framework、effort）、Elo round-robin（K=32、
  headroom 主導・決定論的）で rank、low-risk consumer + 全 deploy 行を batch に
  evolve、iteration 文書を出す。**unmeasured が 1 つでもあれば converged にしない。**
  `delta` が before/after の軸別の測定 —— roadmap は予測、delta が証明。
- consumer 側の使い方: emitted document 群 + 公開 asset set を渡して audit し、
  床（`--min`）を gate にする。deploy 直前に asset set 込みで 1 度走らせること
  （`:assets-resolve` が deploy 起因の outage を止める唯一の場所）。

---

## 3. 検証

```bash
kbb -M:test        # 163 tests / 618 assertions, 0 failures, 0 errors
```

⚠ `test_runner` の `-main` に**列挙されていない** test ns は require されても走らない。
217c338 の `viewport-test` はこの形で 1 度も走っておらず、走らせると
`no-xs-band-fails` が落ちた（`:no-xs-band` の比較が逆: 最小 band が 480px **未満**
のときに flag していた。2026-09-15 修正）。ns を足すときは require と doseq の両方。

- `same-db-value-same-cid` — 異なる event 経路で同じ db 値 → 同一 CID
- `corrupted-entry-fails-closed` — 改竄 entry は理由を名指して拒否
- `mid-chain-corruption-names-its-height` — 壊れた位置（height）を報告
- `document-with-external-asset-is-refused-by-name` — 外部 asset は URL 付きで拒否
- `gateway-references-are-not-external` — CID gateway link は違反でない
- `lake-fetch-refuses-non-cid-fail-closed` — CIDv0 は handler に届く前に拒否
- `declared-tools-match-dispatch-table` — tools/list と dispatch の表が同型
- `account-like-document-names-every-failure` — /account の実測失敗 12 種を 1 文書に再現し、各軸の finding 文言を pin
- `unmeasured-assets-are-not-a-pass` — asset set 無しは `:unmeasured`（score nil、平均から除外）
- `converged-only-when-clean-and-fully-measured` — unmeasured / 0 枚では converged にならない
- `no-authorizer-is-a-refusal-not-a-pass` — authorize-fn 無し → `:no-authorizer`、guest step は 0 回
- `an-answer-that-is-not-a-decision-is-a-refusal` — authorizer が nil / `:ok` 無し map → `:authorizer-answer-not-a-decision`
- `denied-names-the-authorizer-reason-and-appends-nothing` — 否 → `:denied` + authorizer の理由、step 0 回
- `allowed-appends-and-records-who-and-on-whose-decision-never-the-grant` — entry に `:principal` / `:receipt`、結果のどこにも `:grant` は無い
- `the-authorizer-sees-the-effect-and-nothing-about-where-the-call-came-from` — authorizer の入力 key は `#{:principal :artifact :grant :effect}` のみ
- `envelope-defects-are-named-before-the-authorizer-is-asked` — 9 種の defect を理由付きで拒否し、authorizer 呼出 0 回。境界側: 3 kind の正しい envelope は届く（3 回）
- `mcp-identity-comes-from-the-session-not-the-arguments` — 引数に紛れた principal / grant は無視
- `a-resolved-route-is-a-query-envelope-not-an-execution` — path は envelope に乗らない

壊して確かめた（2026-09-16）: `invoke/authorize` の「authorize-fn 無し」を allow に書き換えると
`no-authorizer-is-a-refusal-not-a-pass` と `a-query-goes-through-the-same-seam-and-answers-a-station`
が落ちる（exit 1、4 failures）。無改変で exit 0。

### 3.1 本物の authorizer での動作検証（`scripts/verify-invoke-authority.cljk`、2026-09-16）

unit test の authorize-fn は fake。**seam が本物に繋がることは別に測る**:

```bash
npm run verify:authority   # 兄弟 repo（org-biscuitsec / authority / text）が west pin に在ること
# = kbb --backend sci --classpath src:../org-biscuitsec/src:../org-biscuitsec/test:../authority/src:../text/src scripts/verify-invoke-authority.cljk
```

束ねたもの: Ed25519（node:crypto、org-biscuitsec 自身の real-crypto suite と同じ binding `biscuit.ed25519`）で
root 発行 → 保持者が **offline で app A の chain だけに attenuate** → `biscuit.token/verify`（root **公開**鍵）→
`biscuit.kotoba/authorize`（authority.chain の束、`:kinds` は **effect が名指す 1 kind に閉じる**）→
`invoke/dispatch` / `invoke/query` → 本物の `actions` → `state/chain-entry` → `state/walk-chain`。
MCP 層は `mcp/handle-request`（stdio loop が 1 行ごとに呼ぶ関数）を in-process で通す。

出力は `CASE<TAB>name<TAB>OK|FAIL<TAB>expected<TAB>got<TAB>guest-steps n`、末尾 `SCANNED<TAB>16<TAB>FAILED<TAB>0`。
exit 0 は n>0 かつ FAILED=0 のときだけ、1 は FAIL、2 は setup 不能（「測れなかった」は pass と別の値）。

| case | 期待（理由 literal を pin） |
|---|---|
| authorizer 無し | `:no-authorizer`、guest step 0 |
| grant 無し | `:no-grant-presented` |
| A に narrow した token で A に append | ok、entry に `:principal` / `:receipt {:reason :pass/granted :depth 2}`、結果のどこにも `:grant` 無し、`walk-chain` valid |
| 同じ token で **B** に append | `:denied` / `:out-of-scope`（束の答え） |
| root の wildcard token で B | ok（wildcard は本物、境界の両側） |
| query-only token で append | `:pass/no-grant`（kind を閉じたから） |
| `before` 過去の token | `:expired-or-no-trusted-time` |
| splice（block 0 の next key を差し替え、attacker 鍵で追記） | `:signature-mismatch`（暗号学的に、index 0） |
| 許可済みだが未宣言 event | `:undeclared-event`（宣言 gate は authority の後も立つ） |
| query grant で A を query | ok、data station |
| query grant で B | `:out-of-scope` |
| MCP: session の grant で append | ok、principal が記録される |
| MCP: 引数に wide token を紛れ込ませて B | `:out-of-scope`（session の narrow token が勝つ） |
| MCP: session に grant 無し | `:no-grant-presented` |

壊して確かめた: ① seam が authorizer の否を無視するよう書き換え → 8 FAIL、exit 1。② binding の `:kinds` を
3 kind 全部に開く → query-only token は**別の理由**（scope 束の `:out-of-scope`）で止まり、pin した
`:pass/no-grant` と食い違って 1 FAIL —— 理由 literal を pin していなければこの退行は緑のまま通った
（8 問 #6 の実例）。無改変で exit 0、SCANNED 16。

測っていないこと: stdio **process** に app を attach した経路（`stdio.cljc` は R0 のまま）、protobuf wire を
跨いだ Biscuit（`biscuit.wire` は経路上に無く、token model を data で渡している）。

### 3.2 reference host を走らせて測る（`scripts/host-node-check.cljk`、2026-09-16）

```bash
npm run verify:host    # serve を port 0 で起動し fetch で 17 case、SCANNED 17 / FAILED 0
npm run host           # 手で触る: http://127.0.0.1:8787/、console に dev token と curl 例
```

17 case: 200 + 本物の CID ETag + canonical Link + no-cache / dev bytes に reload listener / If-None-Match → 304 /
未知 name → 404 `:no-match` / `/todos` ssr height 0 / grant 無し → 403 `no-grant-presented` / app の token → 200 +
db-cid + `"grant"` key 無し / `/todos` が todo と height 1 と **新しい CID** / `/todos/:id` / 未宣言 → 422 /
別 app の token → 403 `out-of-scope` / CIDv0 → 400 / 読めない grant → 403 `grant-unreadable`（app 自身の理由）/
`:query` → data station / GET /invoke → 405 / reload stream が rebuild で `data: reload` / 失敗した rebuild が
500 + `rebuild-failed` + 問題文。

### 3.3 live e2e（`scripts/live-identity-e2e.cljk`、`npm run verify:live`、2026-09-17）

本番の name host に対して session 無しで測る: receipts（apex の 1 組が全 host の正）→ `/` の bytes を hash して
ETag の CID と一致（**weak 形 `W/"cid"` を許す** —— Cloudflare は圧縮時に strong ETag を weak にし、
browser は受け取った形で `If-None-Match` を返す。`host/not-modified?` は `W/` を剥いで比較する。これは
live e2e が見つけた: strong 比較だけでは browser に 304 が一度も出ない）→ Link rel=canonical → no-cache →
If-None-Match strong / weak の両方で 304 → asset は identity を名乗らない。seam は **api.kotoba.cloud** で
1 回（grant 無し → 403 `no-grant-presented`、読めない → `grant-unreadable`。docs. は documents-only の host で
`/v1/invoke` は 404 —— 設計どおり、e2e の前提が違っていた）。さらに **canonical resolves**（bytes plane `{cid}.ipfs.yataverse.com` が同じ bytes を返す）。
2026-09-17 午前、release 441beec4: `SCANNED 20 / FAILED 2` —— canonical resolves が両 host で 404（書き込み
経路が無かった、§1.1）。同日 `publish:receipts` を回した 1 回目（09:45 の build、567 document、509 published /
58 already / 0 FAIL）は**それでも赤だった** —— 回している間に別 release（favicon を全 host に）が出て 567 個全部の
CID が変わっていた。main tip（e9e12f36）で `npm run render` し直すと receipt は live と 567/567 一致（render は
再現可能）、その build で 2 回目を回した後: **順方向 SCANNED 567 / PUBLISHED 267 / ALREADY 300 / FAILED 0、逆方向 244 / 323 / 0（合わせて 511 PUT、56 は 1 回目と同じ bytes）** → `verify:live` **SCANNED 20 / FAILED 0 / UNREACHABLE 0（canonical resolves は両 host とも 200、served CID = ETag）**。届かない host は
2（pass ではない）。**測れたこと**: 1 release が全 document を変えると CLI 経由の publish は 1 document ≈ 6–10 s
（wrangler 起動が支配的）で 1 時間級 —— retrievability を release step のままにすると、次の release までに
終わらないことがある。deploy chain（Worker 側の R2 binding か drain worker）に寄せるのが次段。

**production allow path**（2026-09-17、owner の Chrome の passkey session、console.kotoba.cloud 同 origin）:
`POST /v1/database/session/tenants {name}` → tenant → `POST …/token {tenantId dbName permissions [data:read]}` →
auth.kotoba.cloud が Biscuit を発行（15 分）→ `POST /v1/invoke` `Authorization: Biscuit <token>` → **200 /
`receipt.reason granted` / `holder` = session の active DID / `requested kotoba://can/data:read`**、別 artifact →
403。同じ e2e が 2 つの床割れを見つけた: tenants の転送が常に `/v1/biscuit/token` を向いていた（list が本番で
一度も出ていなかった、app PR 322）、query の station が空だった（Worker は index を渡し load-fn は raw を
読んでいた、app PR 327）。**unit が緑でも生成物を走らせるまで分からない**（8 問 #8）。

**実ブラウザ**（Chrome、2026-09-16）: `/` の form に token と text を入れて add → interaction runtime の delegated
submit → `fetch('/invoke')` Bearer → `{"ok":true,… "height":1,"receipt":{"reason":"pass/granted"}}` が `<pre>` に
出て navigation は起きず、`/todos` が「height 1 / buy milk from the browser」を描いた。⚠ extension の ref click は
native submit を起こさず（座標 click は起こす）—— 自動化で form を押すときは座標で。
⚠ 発見: `lang/capability-semantics.edn` の閉じた `:kinds` に `:chain/append` / `:app/query` / `:app/assert` は
**無い**。semantics の集合をそのまま `:kinds` に渡す production authorizer は 3 つとも `:unknown-kind :deny` で
拒否する —— 方向は正しい（fail-closed）が、登録は言語側の決定（§6 の次段 2 に含める）。

---

## 4. 依存と非依存

**使う**: shitsuke（view/state の .kotoba guest 群、変更しない）、
content-address / io-ipld / io-multiformats（hash・CID）、
`scripts/publish-document.cljk`（2 面publish の実体）、
kotoba-server `word mcp`（MCP stdio の形）、
`kotoba-lang/authority` + `org-biscuitsec`（authorize-fn の実体。framework は seam だけ）。

**使わない（恒久）**: Svelte/React（ADR-2608260900）、guest からの js 操作、
DOM capability wire の新設、mutable naming に載せる document（IPNS/DNSLink は
naming 面であって document の identity ではない）。

## 5. 他 framework との対応

shinkansen は一つの層であり、単独では web にならない。上下の層と何を所有し・
何を所有しないかの対応表 (上位 = 表現、下位 = 基盤):

| 層 | 所有する | 所有しない |
|---|---|---|
| **jp-go-dds** (orgs/kotoba-lang/jp-go-dds) | design tokens / base parts (page/->page, dds.css) | app shell pattern, document publish, CID |
| **cloud-kotoba-dds** (orgs/kotoba-lang/cloud-kotoba-dds) | app shell / patterns: shell, account-entry, navigation (docs/design.md レイヤー表) | CID / MCP (発行面は持たない) |
| **app-kotoba-cloud site.cljk kc-*** (orgs/kotoba-lang/app-kotoba-cloud) | その shell の現行 SSR 実装。`site-layout` が chrome (header/nav/footer) の唯一の定義 | CID publish (静的 Worker Static Assets のみ) |
| **shinkansen** (この repo) | content-addressed document publish (CID = identity) + state chain + MCP lake tools — 上記 shell が作った document を**配送する** 計画面 | routing / IA / visual shell (kc-* と site-layout が正。shinkansen は再定義しない) |

方向は一方向: jp-go-dds ← cloud-kotoba-dds ← app-kotoba-cloud → shinkansen。
app-kotoba-cloud の site-layout が chrome の SSOT である限り、shinkansen 側で
visual shell を複製しないこと (ADR-2609092600 :document の自己完結原則は
「asset を document に同梱する」ことであり「shell を再実装する」ことではない)。

## 6. 次の一段（未実施、実測の順）
1. **yataverse lake index への着地**: worktree
   `net-kotobase-ipfs-yataverse-index` に着手済みの top page / `/api/v1/lake/*`
   を shinkansen publish 経由に置き換え
2. **authorize-fn の実体を production に束ねる**: §3.1 の binding（verify → `biscuit.kotoba/authorize`、
   kind を 1 つに閉じる）を host に置き、`lake_dispatch` の R0 refusal を本物の decision に置き換える。
   session の principal は CACAO（人）/ DID（agent）から、grant は `auth.kotoba.cloud/v1/biscuit/token`
   から。`:chain/append` / `:app/query` / `:app/assert` を `lang/capability-semantics.edn` の `:kinds` に
   登録する（無ければ `:unknown-kind :deny`）。**framework 側に Biscuit parser を置かない。**
3. ~~product が reference host を通る~~ → **着地（2026-09-16、kotoba.cloud）**: app-kotoba-cloud の render が
   全 document を `adapter/adapt`（publish gate → CID receipt）に通し `/.well-known/shinkansen/receipts.json` を
   出す。Worker は `routes/paths->tree` で name → document を解決し、`host/document-headers` /
   `host/not-modified?` で **ETag = CID / Link rel=canonical ipfs:// / 304 を receipt だけで**答える。
   `POST /v1/invoke` が seam を authn の Biscuit wire + pinned root 公開鍵 + `biscuit.authority/->grant` +
   `authority.chain` に束ねる（data:read の token が receipt set を query できる。chain は無いので action は
   422）。残り: layouts と render は app 自身の site.cljk のまま（tree は名付けるだけ）、bytes は Static Assets。
4. **chain entry の receipt 署名**: §1.5 の既知の限界（`:prev` / `:event` / `:principal` が hash 外）を
   authorizer の署名付き receipt で閉じるか、entry 全体を hash するかを実測して決める。
5. ~~guest bridge~~（`bridge.cljc` 着地済み）、~~MCP stdio loop~~（`stdio.cljc` 着地済み）、
   ~~west pin~~（登録済み、pin は各 PR で前進）
