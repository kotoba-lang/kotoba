# jp-go-digital-design-system

[デジタル庁デザインシステム（DADS）の HTML コンポーネント例](https://github.com/digital-go-jp/design-system-example-components-html)
（MIT License, © 2025 デジタル庁）を **cljc hiccup** で提供するライブラリ。
ADR-2607141915（com-junkawasaki/root）。

- markup / class 名（`dads-*`）は上流の HTML 例に忠実。CSS は
  `resources/jp_go_dds/dds.css` に vendor（先頭コメントに上流 commit と MIT 表記。
  `kbb --backend sci scripts/vendor.cljk <上流 clone>` で再生成 — 手編集禁止）。
- **既定は light 固定**（上流に dark palette は無い）。`page` に `:dark? true`
  を渡すと `jp-go-dds.dark` の反転層が入り、`prefers-color-scheme` と
  `[data-theme]` の両方に対応する。**上流の dark ではなく、こちらの拡張**
  （下記「dark」節）。
- 上流に無い layout 補助（container / section / grid / stack / card / hero）は
  `dds-ext-*` prefix + `core/ext-css` で明確に区別（上流 class と混ぜない）。
- 既定で**外部リクエストゼロ**（Noto Sans JP の Google Fonts 読み込みは
  `:google-fonts? true` の opt-in）。

## 収録コンポーネント（上流の全 40 に wrapper、2026-09-16）

`jp-go-dds.core` の hiccup wrapper（上流 example HTML に class ごと忠実）:

button / heading / accordion / input-text / textarea / checkbox / radio /
form-field(form-control-label) / select / table / chip-label / divider /
notification-banner / language-selector / **blockquote / breadcrumb /
calendar（静的な月 grid）/ carousel-single / date-picker（separated）/
description-list / disclosure / drawer / emergency-banner / file-upload
（静的）/ hamburger-menu-button / horizontal-menu / image / link / list /
menu-list / menu-list-box / modal-dialog / page-navigation /
progress-indicator / resource-list / search-box / step-navigation / tab /
toc / utility-link** — 2026-09-16 までは 14 だけで、残り 26 は CSS が
vendor されているだけで API が無かった。

上流 41 エントリのうち **40 が正式コンポーネント**(各 `c/c.css` を持つ)で、
`card` だけがパターン(example CSS のみ)。**40 件すべてを vendor 済み**。
上流の script がアプリケーション 1 本ぶんあるもの（calendar の月送り、
carousel の slide machine、file-upload の検証・drop）は静的な形だけを出し、
docstring にそう書いてある — 動くふりはしない。

## behavior 層 — `jp-go-dds.behavior`（shadcn に対する Radix、2026-09-16）

DADS 上流は CSS + example HTML で、開閉・focus・矢印キーの挙動は上流の
component ごとの script が担う。この workspace ではそれが pattern ごとに
書き直されていた（shell の account menu、switch）。`jp-go-dds.behavior/script`
は **1 本の依存ゼロ・冪等な runtime** で、markup の marker
（`data-behavior=dialog|menu|tabs|disclosure|radiogroup|toast|combobox`）で
効く。class 名には触らない — shinkansen.audit が `data-chrome` を読むのと
同じ流儀。`behavior/css` が層の rule（popup は `position:absolute` +
`z-index:var(--hig-z-float)`、toast は fixed + `--hig-z-toast`）を token 契約で
持つ。host は script を 1 ファイルとして配る（`script-src 'self'`）。

- **dialog**: `<dialog>` の `showModal()` が focus trap、Escape と focus return
  は platform。足すのは invoker 属性（`command` / `commandfor`）の polyfill と
  `data-dialog-open/-close`、backdrop click の方針（既定は何もしない）。
- **menu**: `[data-menu-opener][aria-expanded]` + `[data-menu-popup][data-chrome=float]`。
  click / ArrowDown で開き、Escape で閉じて opener に戻り、外側 click / focus で
  閉じ、Arrow / Home / End / typeahead で移動。
- **tabs**: `[role=tablist] > [role=tab]` + `[role=tabpanel]`。automatic activation、
  roving tabindex、`aria-orientation` に従う矢印。
- **disclosure**: `aria-expanded` + `aria-controls` を持つ control が対象を出し入れ
  （`<details>` は native のまま）。
- **radiogroup**: `[role=radio]` を矢印で移動**かつ選択**（click する。何が起きるかは
  host の click handler）。
- **toast**: live region + `jpGoDds.behavior.toast({text, actionLabel, onAction, timeout, tone})`。
- **combobox**: `input[role=combobox]` + `[role=listbox]`。入力で filter、矢印で
  `aria-activedescendant`、Enter で選択（hidden input と `change` に落ちる）。

実ブラウザ検査: `test/behavior_browser_test.cljk`（390 / 1280、80 assertion）。

## token 面の追加（2026-09-16）

`--hig-*` bridge は **128 個**を運ぶ（71 → 128）。足したのは、text 11 style の
`font-weight` / `font-family`、`display1-3`、palette の teal / mint / indigo /
brown / gray2-6（DADS 最寄りの primitive）、そして `--hig-motion-*`（press /
reveal / panel）・`--hig-z-*`（raised / sticky / float / modal / toast）・
`--hig-breakpoint-*`（xs / sm / md）。同じ数字は `tokens/motion` /
`tokens/layers` / `tokens/breakpoints` のデータとしても読め、`tokens_test`
が両者の一致を pin する。実測の出所: app.itonami.cloud が HIG 層込みで
117 個を宣言し、kotoba.cloud（この bridge）が 71 個 — 差の 46 個がこれ。

## CSS の配り方 —— `dds.css` と `css-for`

この design system の CSS は各ページの `<style>` に **inline** される(外部リクエスト
ゼロが設計方針)。40 component を全部束ねると global 込みで約 172KB になり、
core だけの 72KB から **+100KB**。cloud-itonami だけで 713 ページあるので、
使わない component まで常時配ると全ページが太る。

そこで 2 段構えにしている:

| 用途 | 使うもの | 大きさ |
|---|---|---|
| 既定(core 14 component) | `resources/jp_go_dds/dds.css` | 約 72KB |
| 追加で 1〜2 個だけ要る | `dds.css` + `(jp-go-dds.css/css-for [:date-picker])` | +数 KB |
| 素の markup を広く塗る | `dds.css` + `jp-go-dds.skin/skin-css` | +4KB |
| 全部(ドキュメント用途) | `(jp-go-dds.css/all-css)` | 約 185KB |

`css-for` は **core に既に入っている component を黙って落とす**(同じ custom
property の二重定義を避けるため)。`resources/jp_go_dds/components/<name>.css` に
1 ファイルずつ置いてあるので、nbb など resource が使えない実行系からは
`jp-go-dds.css/component-path` でパスだけ取って呼び出し側で読む。

**core 14**(= `dds.css` に束ねてある): button / heading / accordion / input-text /
textarea / checkbox / form-control-label / table / chip-label / divider /
notification-banner / select / link / list

**per-component で追加できる 26**: blockquote / breadcrumb / calendar / carousel /
date-picker / description-list / disclosure / drawer / emergency-banner /
file-upload / hamburger-menu-button / horizontal-menu / image /
language-selector / menu-list / menu-list-box / modal-dialog / page-navigation /
progress-indicator / radio / resource-list / search-box / step-navigation /
tab / toc / utility-link

`notification-banner` は `:type` に `:success` / `:error` / `:warning` /
`:info-1` / `:info-2` を取り、icon path は上流 `src/components/
notification-banner/{success,error,warning,info-1}.html` をそのまま写している
（`fill="Canvas"` も上流どおり）。**上流との差分が1点だけある**: 上流の例は常に
閉じるボタンを持つが、閉じる挙動は JS 依存なので既定では出さない（静的 SSR
ページに動かないボタンを置かないため）。上流どおりの markup が要る場合は
`:closable? true`（+ `:close-id`）を渡す。

## token 面 — `jp-go-dds.tokens`（共通化の接ぎ目）

このワークスペースの view / SVG / audit は **`--hig-*` token 契約**を共通言語に
している（`shitsuke.hig` が発行元、ADR-2607122200）。DADS が発行するのは
`--color-key-*` / `--color-neutral-*` / `--color-primitive-*` なので、**skin を
DADS に替えると token 契約に忠実に書かれた資産ほど色を失う**。

`jp-go-dds.tokens/skin-css` はその橋渡し（`--hig-*` を DADS primitive の上に
再定義する `:root` 宣言 1 本）＋ design-quality audit の 3 補正
（`color-scheme` 宣言 / tap target 44px / safe-area）をまとめたもの。
**DADS 自身の変数も `dads-*` class も一切上書きしない**ので、skin を kotoba-ui へ
戻すときはこの CSS を出さないだけでよい。

```clojure
(require '[jp-go-dds.tokens :as tokens])
(page/->page {:title "..." :css dds-css :app-css (str tokens/skin-css my-css)} ...)
```

`tokens/hig-var` は `var(--hig-*)` を書くヘルパ、`tokens/bridged?` は
「その token がこの skin で生き残るか」をアプリのテストから assert するための述語。
橋渡しの右辺が vendor 済み CSS に実在することは
`jp-go-dds.tokens-test/every-bridged-primitive-exists-in-vendored-css` が強制する
（存在しない変数を参照しても CSS はエラーを出さず、その宣言だけが黙って無効に
なるため — SVG が不可視になる形でしか表面化しない）。

**dark は表現できない**（上流に dark palette が無い）。dark が要るアプリは
DADS ではなく kotoba-ui skin を選ぶ、が正しい分岐。

### 橋渡しの決定核は `.kotoba`（`kotoba/bridge_document.kotoba`）

token 正規化・breakout guard・除外・content identity は **Kotoba の
`:document` 値**として書いてあり、`jp-go-dds.tokens` はその oracle。
移行計画 W6 の per-slice 手順（ADR-2607279200 / ADR-2607270100 §10）に従い、
**consumer API は一切変えていない** —— アプリは今までどおり
`jp-go-dds.tokens/skin-css` を使う。

gate は `test/jp_go_dds/kotoba_document_parity_test.cljk`（JVM のみ。
`kotoba-lang/compiler` は `:test` alias の**テスト専用**依存で、
ライブラリ本体は実行時に依存しない）:

- 71 件の bridge 全体が `tokens/bridge-css` と**バイト一致**すること
- `brand-tokens` 除外が `tokens/bridge-css-except` と一致すること
- `:color-tint` / `"color-tint"` / `"--hig-color-tint"` が 1 つの
  custom property に落ちること（keyword を素の `str` に通して
  `--hig-:color-tint` を作った実測バグの再発防止）
- `{` `}` `;` `/*` を含む値が **fail closed** すること。Kotoba に `throw` は
  無い（意図的な安全制約であって backend の欠落ではない）ので、guest は
  失敗を `[:result :string :string]` の値として返す
- `document-sha256` が token 契約の content identity になること

実測した制約が 1 つある。**恒久の設計ではない**:

1. **bridge は 1 つの document 値に入らない。** `document-container-item-limit`
   は 32、`document-node-limit` は 256（kotoba-kir `value.cljc`）。71 件は
   どちらも超えるので、最大 32 件の chunk に切って `join-decls` で繋ぐ。
   chunk 境界が出力に現れないことは gate が別に assert する。

`string=?` / `string-contains?` は amu `1e21a1f` で `:bool` になった。
`:bool` 宣言の関数はそれらをそのまま返せ、`and` / `or` / `not` で合成できる。
（`<` / `=` は HIR では `:bool` でも KIR execute が 0/1 word のままなので、
`:bool` を返すときは wrap を残す。）

### dark ramp の鏡映も `.kotoba`（`kotoba/dark_mirror.kotoba`）

`jp-go-dds.dark` は docstring で規則を 1 本だけ宣言している ——
`ramp の i 番目 → 同じ ramp の (n-1-i) 番目`。数値で `1000 - N` を計算せず
**index で鏡映する**ことが、ramp ごとの例外表を消している（代償は中間 grey が
数単位ずれること）。この判断を `.kotoba` が持ち、gate は
**vendored `dds.css` に実在する 12 本の ramp すべて**（各 12〜13 段）で
`dark/mirror` と突き合わせる。`light-name` は 156 件の literal 全件。

`mirror-index` を `(- n i)` に壊すと 0 failures が 15 failures になることを確認済み。

### palette は宣言データ（`resources/jp_go_dds/palette.edn`）

正規表現でテキストから構造を復元する処理は Kotoba へ移せない。**移行ではなく
設計変更を先にやる**のが規則なので、走査を **vendor 時に 1 回だけ**走らせて
結果を EDN にした:

```bash
kbb --backend sci --classpath "src:../css/src:../html/src" scripts/palette.cljk
```

`scripts/vendor.cljk` はこれを最後に必ず呼ぶ（再 vendor して EDN を作り忘れると
dark が**前の上流の palette を描き続ける**）。生成物なので手編集禁止。
中身は `:literals`(156) / `:ramps`(12) / `:all`(177) と source の sha256。

**導出は 1 つだけ** —— `palette.cljs` は自前の parser を持たず
`jp-go-dds.dark` の公開関数を呼ぶだけ。committed な EDN が現在の走査と
一致することは gate が検査する。

### dark / light / snapshot の宣言も `.kotoba`（`kotoba/dark_declarations.kotoba`）

宣言データの上でなら、dark の**判断**の側は純関数になる:

| set | 値 |
|---|---|
| snapshot | `--dds-light-X: <light の実値>` |
| dark | `--color-X: var(--dds-light-<X の鏡映>)` |
| light | `--color-X: var(--dds-light-X)` |

退避が要るのは反転が対合だから —— `--color-red-800: var(--color-red-400)` と
その相方を同じ要素に書くと **CSS custom property の循環**になり両方無効になる。
だから両側とも `--dds-light-*` の複製だけを参照する。

一様な規則の**唯一の例外は white / black**（ramp の段ではなく、ramp を測る端）。
scrim（`rgba(0, 0, 0, α)`）は base だけ反転し、α は上流の宣言から取る。

gate は vendored sheet の **12 ramp すべてで dark / light / snapshot の 3 セット
とも `jp-go-dds.dark` と一致**すること、白黒の例外、scrim 12 件が
`rgba(0, 0, 0, ` で始まること（再 vendor で空白が変わると暗い地に黒い scrim が
残るため）。`mirror-index` を壊すと落ちることを確認済み。

### component の判断も `.kotoba`（`kotoba/button.kotoba`）

component が決めているのは markup（1 要素 + テキスト 1 つ）ではなく**属性**:

1. **既定値** — `:type` は `:solid-fill`、`:size` は `"md"`。`(button "OK")` が
   素の button ではなく本物の DADS button になるのはこれ。
2. **要素の選択** — `:href` があれば `<a>`、無ければ `type="button"` /
   `"submit"` を持ち `disabled` を取りうる `<button>`。`<a>` に `disabled` は
   無いので、2 分岐は上位集合の共有ではなく本当に別物。
3. **優先順位** — `:attrs` は任意属性（`data-*` / `aria-*` / `hx-*`）を通すが、
   `class` / `data-type` / `data-size` は**後から**当たり上書きできない。
   これが component の同一性で、上書きできてしまうと consumer は selectable
   hook を得るために DADS button の CSS を app 側へ複製することになる。

gate は 16 通りの opts 行列（両要素・全オプション・passthrough 衝突を含む）で
`jp-go-dds.core/button` と属性文字列・タグ名を突き合わせる。実測: `owned?` の
`class` 判定を潰すと 0 → **2 failures**、既定 size を `"lg"` にすると
0 → **17 failures**。

属性は**固定順**で出す（sort ではなく）。順序も contract の一部で、
これがあるから比較できる。

### 残りの component も `.kotoba`（`kotoba/components.kotoba`）

button と同じ形で 7 つの判断を持つ:

| component | 判断 |
|---|---|
| heading | level → tag、level → 上流の `data-size`（表であって式ではない。1..6 の外は `"20"`） |
| chip-label | 既定 2 つ |
| input-text | 既定 size、`type` は `"text"`、**`:size` は `data-size` に消費され属性としては出さない**（`size="md"` は HTML では文字幅ヒントで DADS の意図と違う） |
| textarea | 既定 rows |
| checkbox / radio | 既定 size、どの属性が出るか |
| form-field | **`__requirement` と `__status` の区別** |

最後の 1 つは既定値ではない。必須/任意マーカーは `data-required` を持つ
`__requirement` で、`__status` は「入力済み」等を表すグレーの塗りバッジ。
必須マーカーに `__status` を使うのは様式の選択ではなく**誤り**で、
`.cljc` の docstring が「実測でこれをやっていた」と記録している。
**一度実際に間違えた判断は、テストが届く場所に置く価値がある。**

`select` と `notification-banner` は下の別モジュール —— 判断が option リストと
icon 表の上にあり、平坦な属性マップとは形が違うため。

gate は各 component の hiccup を**判断を持つノードまで walk** して属性を
突き合わせる（`(second h)` は属性マップであって子ではないので、入れ子
component への index 演算は間違えやすい。tag 名で引く）。実測: heading の
表の 1 段を変えると 0 → **1 failure**、`__requirement` を `__status` に
すり替えると 0 → **2 failures**。

### `select` の option 状態と banner の icon 表（`kotoba/select_banner.kotoba`）

判断が**リストと表**の上にあるので別モジュール。

**どの option に `selected` が付くか**が、この repo で唯一**実害を出した判断**:

1. 値が空の option は placeholder —— `disabled` かつ `selected`（送信で生き残っては困る prompt）
2. 現在値に一致する option が `selected` —— **テキストとして比較**する。options は数値も keyword も持つので `18` は `"18"` に一致しなければならない
3. **現在値が無ければ何も selected にならない** —— ブラウザが先頭を表示する

3 番目が刺さります。ページは正しく見え、フォームは先頭を送信し、誰も気付かない ——
実測 2026-07-30、`cloud-itonami/inkan` が 18.0mm のつもりで **12.0mm** の印影を描画。
既定値が要るなら呼び出し側が渡すしかなく、このモジュールにそれは作れませんが、
**規則をテストが届く形にする**ことはできます。

なお**数値→テキストの変換は host 境界**で起きます（Kotoba に任意値の `str` は無い）。
gate は `.cljc` 側から `18` と `"18"` の両方を流して境界が保たれることを見ます。

### `select` と `button` は passthrough の向きが逆（実測 2026-08-10）

`button` は `:attrs` を**先に** merge して自分の class/data-* を後に置くので
ライブラリが勝ちます。`select` は逆で、**`:attrs` が `class` / `data-size` を
上書きできます** —— `(select {:attrs {:class "MINE"}} …)` は `class="MINE"` を出し、
DADS のスタイルが丸ごと外れます。button の docstring が「component の同一性を
壊させないため」と書いている、その規則の反対です。

移植は**出荷されている挙動をそのまま再現**しています。あるべき挙動を encode した
parity gate は、実際の挙動について何も証明しないからです。食い違いは gate で
明示的に assert してあるので失われません。**どちらが正しいかを決めるのは
migration ではなく shipped API の変更**なので、ここではしていません。

### `table` の header semantics（`kotoba/table.kotoba`）

table の固定された markup ではなく、セルが持つ意味を移した:

- `:headers` の各セルは `th.dads-table__col-header[scope=col]`
- `:row-header?` のときだけ、各 body row の 0 番セルは
  `th.dads-table__row-header[scope=row]`
- 残りは属性の無い `td`

`scope` は見た目ではなく accessibility relationship なので、tag と属性を同じ
規則から出す。これにより、見た目だけ通る `td scope=row` や、関係を持たない `th`
への drift を gate が拾う。2 行 × 3 セルを含む matrix で `.cljc` の hiccup と
全セルを突き合わせる。実測: row-header の index を 0 → 1 に壊すと
0 → **12 failures**。

### 残っている `.cljc`

`resolve-dark`（コントラスト検査用の別名解決）と `all-declarations` は
走査結果の上での**グラフ探索**なので、次の候補は別の形になる。
`tokens/root-css` を `.kotoba` にする案は成立しない —— 入力の `dds.css` が
72,114 バイトで `string-value-byte-limit` 65,536 を超える（`:root` ブロック
だけなら 8,617 バイトで収まる）。

## 使い方

```clojure
(require '[jp-go-dds.core :as dds]
         '[jp-go-dds.page :as page])

(page/->page {:title "..." :css (slurp "resources/jp_go_dds/dds.css")} ; css は呼び出し側が読む(純関数維持)
  (dds/container
    (dds/heading 1 "見出し")
    (dds/button "申し込む" {:type :solid-fill :size "lg"})
    (dds/accordion "よくある質問" [:p "回答"] {})))
```

第一消費者: `gftdcojp/ai-gftd-itad`（itad.gftd.ai の LP — kotoba-ui からの
opt-out はオーナー指示 + 行政手続き系サービスとしての信頼感のため。
ADR-2607141915 に理由を明記）。

## dark (`jp-go-dds.dark`) —— 上流には無い。これは拡張

```clojure
(page/->page {:title "..." :css dds-css :dark? true} …)
```

`:dark? true` だけで CSS・`color-scheme`・`theme-color` が揃う。knob を 1 つに
してあるのは、CSS と meta を別フラグにすると「dark の地に light のブラウザ
chrome」というページが必ず生まれるため。

### 色を作らず、ramp を逆から辿る

デジタル庁デザインシステムに dark palette は無い。しかし**無いのは palette で
あって色ではない** —— 上流は 10 色相 + key を 13 段、neutral grey を 12 段
持っており、どの ramp も単調に暗くなる。dark を「同じ ramp を逆から辿ること」と
定義すれば、新しい色を一つも発明せずに dark が出る。規則は 1 本:

    ramp の i 番目 → 同じ ramp の (n-1-i) 番目

index で鏡映するので、grey の `420` `536` のような半端な段にも例外表が要らない
（数値で `N → 1000-N` を計算すると `50 → 950` が存在しない）。

**反転は primitive 層で行う。** `--color-key-*` も `--color-semantic-*` も
`tokens/hig->dads` の `--hig-*` 契約も primitive を指しているので、primitive を
反転すれば **semantic の dark 版も `--hig-*` の dark bridge も component CSS の
書き換えも一切要らない**。`dads-*` の markup はそのまま dark になる。

唯一の例外が `white ↔ black` で、鏡映すると地が純黒になり面がそれ以上下に
行けなくなるため、地は grey の最暗段に落とす。上流から導けないこちらの判断。

### 実測 contrast（`kbb -M:test` が毎回検算する）

地 `#1a1a1a` に対して:

| token | dark 値 | contrast |
|---|---|---|
| `--color-neutral-solid-gray-800`（本文） | `#e6e6e6` | 13.94:1 |
| `--color-neutral-solid-gray-700` | `#cccccc` | 10.84:1 |
| `--color-neutral-solid-gray-600` | `#b3b3b3` | 8.30:1 |
| `--color-neutral-solid-gray-536` | `#999999` | 6.11:1 |
| `--color-key-900`（primary action） | `#9db7f9` | 8.76:1 |
| `--color-semantic-error-1` | `#ff7171` | 6.51:1 |
| `--color-semantic-success-1` | `#259d63` | 5.04:1 |
| `--color-semantic-warning-orange-1` | `#fb5b01` | 5.47:1 |
| `--color-semantic-warning-yellow-1` | `#ebb700` | 9.37:1 |
| solid-fill button（地 key / 字 white） | — | 8.76:1 |
| **反転しない場合の key blue `#0017c1`** | — | **1.57:1** |

最後の行が dark を設計する理由そのもの。デジタル庁の key blue は暗地の上で
2:1 も出ないので、反転しないと primary action が読めない。

この表は説明ではなく**検査**で、`dark_test` が WCAG の相対輝度から毎回計算して
閾値に当てる。上流の再 vendor で palette が動いたらここが落ちる —— 色の劣化は
落ちるテストにしないと誰も気付かない。

### 実装上の落とし穴、2 つとも塞いである

- **循環参照**: 鏡映は対合なので `red-800: var(--red-400)` と
  `red-400: var(--red-800)` を同じ要素に書くと両方 invalid になり色が全部消える。
  light の実値を vendored CSS から**抽出**して `--dds-light-*` に退避し、dark は
  それだけを参照する（抽出であって書き写しではないので、再 vendor に追従する。
  `dark.cljc` に色の literal は 1 つも無く、テストがそれを固定している）。
- **`@media` は specificity を上げない**: `@media (prefers-color-scheme: dark)`
  の中の `:root` は外の素の `:root` と同じ強さなので、後から出る
  `tokens/a11y-css` の `:root { color-scheme: light }` に順序だけで負け、
  **auto-dark が黙って無効化される**。dark 側を `:root:root`、`[data-theme]` 側を
  `:root:root[data-theme=…]` にして、明示指定 > auto > 素の `:root` を
  順序に依存せず固定してある。

## テスト

```bash
kbb --backend sci --classpath "src:test:../html/src:../css/src:../text/src" test/run_tests.cljk
kbb --backend sci --classpath "src:test:../html/src:../css/src:../text/src" test/behavior_browser_test.cljk   # 実ブラウザ
kbb -X:test   # JVM compat（kbb の engine は git dep を解決しないので 2026-09-16 時点では走らない — parity gate は JVM が要る）
```

## 互換スキン (`jp-go-dds.skin`)

既存の素朴な markup を **書き換えずに** DADS の見た目へ寄せるためのスキン。
cloud-itonami の operator console(各 repo の `render_html.clj` が実 actor 実行から
生成)や一部の product LP は、意味的な HTML と小さな class 語彙
(`.ok` / `.warn` / `.err` / `.critical` / `.muted` / `.card` / `.badge` / `.banner`
/ `.bar` / `.cta-*` …)だけで書かれていて、1 repo ずつ形が違う。構造を組み直すと
セクション欠落の危険があるので、**markup は触らず `<style>` の中身だけ**を
`dds.css` + `skin-css` に差し替える。

```clojure
(require '[jp-go-dds.skin :as skin])
(str vendored-dds-css "\n" skin/skin-css)   ; skin は dds.css の後ろ
```

`skin-rules` も EDN(`[selector decls]` のベクタ列)。raw hex は書かず、判定色は
DADS の semantic token(`--color-semantic-success-2` / `-warning-yellow-2` /
`-error-1`)に載せている。

## kotoba-uiux 規約との関係

このモノレポの標準 UI スタックは kotoba-ui（ADR-2607122200）。本ライブラリは
「デジタル庁デザインシステムに合わせたい日本の公共・行政文脈サービス」向けの
**明示的な opt-out 先**であり、採用する repo は理由を ADR に書くこと。

## Shared theme toggle

`jp-go-dds.theme-toggle` is the common lambda yin-yang control used by Kotoba and Kotobase. It is a component namespace in this design-system repository, not a separate repository.

```clojure
(require '[jp-go-dds.theme-toggle :as theme])
;; page options: :dark? true, :app-css theme/css, :head [[:script theme/script]]
;; header content: theme/control
```

The script runs before paint, follows OS appearance until explicitly selected, and stores the selection per origin. Keep one control per page. Native button keyboard behavior, switch state, reduced motion and Japanese/English labels are included. Without JavaScript the button stays hidden and the page follows the OS.

### Compact language selection

`language-selector` shows the current native language name and adds search when
there are more than six choices. Options may provide `:aliases` (for example an
English language name), and hosts may localize `:search-label` and `:empty-label`.
Load `jp-go-dds.behavior/language-selector-script` once. JVM `css-for` includes
its layout when requesting `:language-selector`; resource-reading hosts must
append `jp-go-dds.behavior/language-selector-css` after the component sheets.
Search matches native names, aliases and codes without accent sensitivity.
Escape returns focus to the opener; arrows select visible choices. The popup
is scrollable and is positioned within the viewport when opened.
