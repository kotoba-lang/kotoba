# ADR 0004: DADS 由来の component maturity（button variant/size・focus ring・field・banner・forced-colors）

- **Status**: accepted — landed on `main` 2026-08-05, tests green (80 tests / 916 assertions)
- **Date**: 2026-08-05
- **Deciders**: Jun Kawasaki
- **Context tags**: ui, accessibility, wcag, forms, cljc, dads
- **Related**: `docs/adr/0001-liquid-glass-ui.md`, `docs/adr/0002-css-core-migration-and-ink-token.md`,
  `docs/adr/0003-motion-and-dynamic-effects.md`,
  [`kotoba-lang/jp-go-digital-design-system`](https://github.com/kotoba-lang/jp-go-digital-design-system)
  (ADR-2607141915, com-junkawasaki/root)

## 背景

ADR 0001–0003 で material（tokens / css.core EDN rules / motion）は揃い、
component も 29 個ある。しかし **material の成熟度と、component contract の
成熟度が乖離していた** —— 見た目は仕上がっているのに、control としての
振る舞いが荒い。実測した gap:

| gap | 実際の状態 |
|---|---|
| keyboard focus | sheet 全体で `:focus-visible` rule は **toggle track の 1 本だけ**。button / tab / menu-item / list-row / chip / disclosure-summary / slider / select は focus 時に**何も描かない**（WCAG 2.4.7 level A） |
| button の寸法 | 1 サイズのみ。小さくするには consumer が `min-height` を override するしかなく、そのたびに 44px tap target が黙って壊れる |
| button の階層 | primary / secondary / tertiary の区別が無い |
| link button | `<a>` 形が無い |
| form label | control は 6 種類あるのに **label / support / error を関連付ける手段が 1 つも無い**。consumer が手で `<label>` を書き、`aria-describedby` は大抵付いていない（accessible に*見える*だけの markup） |
| inline status | `alert`（中央 modal）はあるが、flow に留まる非ブロッキングの通知が無い |
| touch の hover | `:hover` に guard が無く、tap 後に浮いたまま張り付く |
| forced-colors | 対応ゼロ。この material は forced-colors が剥がすもの（`box-shadow` = 縁と rim の全部）と見えないもの（`backdrop-filter`）でできており、残るのは `mix-blend-mode` の specular 霞だけ |

これらは「デザインの好み」ではなく、**政府デザインシステムなら既に答えを
出している類の問題**である。このワークスペースには
`kotoba-lang/jp-go-digital-design-system`（デジタル庁デザインシステム DADS の
cljc port、MIT / © デジタル庁）が既にあり、その `dads-button` /
`form-control-label` / `notification-banner` が上記の大半に答えを持っていた。

## Decision / 決定

**liquid-glass-ui の material は一切変えずに、DADS の contract を移植する。**

- **既定は完全に無音**。`:variant :outline` と `:size :md`（既定）は modifier
  class も rule も出さない —— `panel` の `:regular`/`:raised` と同じ「既定の
  variant は沈黙する」契約。この規則によって、これ以前に書かれた button は
  **byte 単位で同一に描画される**（test で固定）。
- **DADS の flat fill をそのまま持ち込まない**。`--solid-fill` は不透明な
  swatch で material を置換するのではなく、**同じ material を accent で
  tint する** —— primary action も背後を屈折させ続ける。`--text` は逆に
  surface を完全に落とす（glass panel の中の tertiary action に 2 枚目の
  glass を重ねない）。
- **数値は DADS のものをそのまま使う**（focus ring 4px/2px/2px、
  semantic color、44px hit expander）。「glass だから柔らかくする」という理由で
  accessibility の強度を下げない。retune は token 経由で consumer ができる。

移植したもの:

1. **button の `:variant` × `:size`**（DADS `data-type` / `data-size`）。
   `:sm`(36px) / `:xs`(28px) は **transparent な `::after` で 44px の touch
   target を保つ** —— DADS の技法をそのまま。base rule の `overflow: hidden`
   は clip した `::after` に pointer event を通さないので、この 2 サイズだけ
   `overflow: visible` にする。
2. **`:href`**（`<a>` 形）。shitsuke の hiccup を**再タグ付け**して作るので
   class/`data-act`/`title` の source は 1 つのまま。disabled な link は
   `href` を**出さない**（属性ではなくこれが activate 不能・focus 不能に
   する実体）+ `role="link"` + `aria-disabled`。
3. **`:attrs` passthrough**（component 側の attrs が勝つ。`list-row` と同契約）。
4. **`:disabled` と `[aria-disabled="true"]` の両綴り**を style が covers。
5. **two-tone focus ring**（`:liquid-glass/focus` token）。黒 outline + 黄 halo。
   任意の背景に浮く material では単色リングは背景と一致した瞬間に消えるため、
   **dark scheme でも敢えて反転させない**（両方明色になり保証が壊れる）。
   halo は surface 自身の elevation + rim の**前に**積む —— `box-shadow` は
   compose ではなく replace なので、素朴に書くと focus した瞬間に glass の縁が
   消える（最も強い視覚的アンカーを必要とする利用者に対して）。
6. **`field` / `field-control-attrs`**（DADS `form-control-label`）。id から
   `-support` / `-error` を導出し `aria-describedby` / `aria-invalid` /
   `aria-required` を返す。`field` が control の hiccup を書き換える方式は
   採らない —— control は native element を入れ子にしているので（`text-field`
   は `[:div [:input] specular]`）、木を歩いて「どれが control か」を当てる
   実装になり、外した時に**黙って壊れる**。DADS も同じ理由で caller に
   配線させている。
7. **`banner`**（DADS `notification-banner`）。status 色は背景 wash ではなく
   **左端 4px の帯**に乗せる（wash は legible にするために不透明である必要が
   あり、それはこの material が唯一やってはいけないこと）。`:error`/`:warning`
   は `role="alert"`、他は `role="status"`。icon は DADS の path を複製せず
   自前の stroke glyph（上流は `fill="Canvas"` の knockout で不透明背景を前提に
   しており、この material には成立しない。stroke + `currentColor` なら
   forced-colors でも生き残る）。
8. **`@media (hover: hover)`**。これに伴い cascade 順が load-bearing になり、
   `press-rules` を `button-rules` から分離した（`:active` が hover block の
   前にあると、mouse で押している間 hover が勝って press morph が見えない）。
   `component-css` は base → hover → press → focus の順で emit する。
9. **`@media (forced-colors: active)`**。backdrop と specular を落とし、
   surface を system palette に渡し、**disabled の `opacity: .45` を
   `GrayText` に置換**する（opacity は forced palette の一部ではないので、
   opacity で暗くした control は暗いまま recolor され、読めなくなる）。

## Consequences

- token group が 2 つ増えた（`:liquid-glass/focus` / `:liquid-glass/status`）。
  `:liquid-glass/ink` に `:on-accent` を追加。`.kotoba` form-A port
  （`kotoba/tokens_core.kotoba`、ADR-2607270100 §10）は surface/radius/accent/
  lens/ink/motion の representative sample を対象とする proving slice であり、
  新 group は**未 port**。parity gate は cljc 側の map から case を生成する
  ので緑のまま通る。
- `component-rules` は base → hover → press → focus の連結を返す（データ view）。
  `base-rules-data` / `hover-rules` / `press-rules` / `focus-rules` を public に
  したので、自前で render する consumer も順序を保てる。**`component-rules` を
  直接 render すると hover の media guard は失われる**（docstring に明記）。
- component 数 29 → 31（`field` / `banner`）+ 公開 helper 1（`field-control-attrs`）。

## 測定について（正直に）

**deterministic な design-quality audit（`kotoba-lang/design-quality`）は、
この変更の前も後も showcase を 100.00 / converged と採点した。**

これは改善が無かったのではなく、**この audit がこの class の欠陥を見られない**
ことを意味する。`:focus-visible` 軸は page source 中の文字列 `:focus-visible`
に対する regex であり、toggle 1 本でその軸は満点になっていた。`:tap-targets`
軸も `min-height: 44px` が sheet のどこかにあれば通る。

同じ罠を自分の test でも踏んだ: 最初に書いた
`every-interactive-surface-has-a-focus-ring-test` は rendered sheet を grep して
おり、**button の focus rule を削除する mutation を通してしまった** ——
同じ selector が forced-colors block にも現れるため。データ（`focus-rules`）に
対する assertion に書き直して mutation で落ちることを確認した。

`hover-is-gated-behind-a-hover-capable-pointer-test` も同様に、base block に
`:hover` rule を注入する mutation で落ちることを確認済み。

**未実施**: ブラウザでの実描画確認。この環境の sandbox 下で local static
server がファイルを配れず（3 回試行して 404）、深追いしないと判断した。
markup と CSS data は 80 tests / 916 assertions と上記 mutation で担保して
いるが、視覚的な回帰確認は行っていない。

もう 1 件、mutation ではなく生成 CSS の目視で見つけた実バグ:
`press-rules` を `button-rules` から分離した際、`--text` variant の
`::before` reset が**新旧両方の場所に残って重複出力**されていた。
`no-exactly-duplicated-rule-test`（同一 selector + 同一 decls の完全重複を
弾く data assertion）を追加して塞いだ。

## Landed

| 何 | どこ |
|---|---|
| 実装 commit | `c2e7d31` |
| PR | [kotoba-lang/liquid-glass-ui#15](https://github.com/kotoba-lang/liquid-glass-ui/pull/15)（merged 2026-08-05） |
| `main` tip | `f46ad6f` |
| superproject の pin 前進 | `com-junkawasaki/root` `1c33407`（`kbb --backend sci scripts/west-pin-put.cljk` によるサーバ側 single-entry commit） |

pin 前進では最初にローカル branch 経由を試み、**base が 10 commit 古かったため
`cloud-itonami-app` / `cssom` / `torihiki` の pin を退行させるところを
`west-pin-verify-guard` が正しくブロックした**。AGENTS.md が「API single-entry が
唯一の正経路」と定めている理由の実例なので記録しておく。superseded になった
ローカル commit は `.git/stash-archive-2026-08-05/` に patch として退避済み。

## この repo の位置づけ（2026-08-05 時点、正直に）

**同じ日にオーナーが `jp-go-dds` をこの workspace の base design system と決め、
`kotoba-ui` / `liquid-glass-ui` は legacy になった**（skill `kotoba-uiux`。実測で
jp-go-dds 依存 170 repo に対し kotoba-ui 依存 12 repo）。**新規 UI をこの stack で
始めない。**

その上でこの ADR の作業は無駄ではない: 残る ~12 repo（`kotoba-lang/app-*`、
`cloud-itonami/kaisya`、`lawfirm`、`gftdcojp/apex`）は今もこの skin を使っており、
塞いだのは WCAG 2.4.7 level A の欠落・壊れた tap target・関連付けられていない
form label という**実害のある欠陥**である。加えて contract を DADS 側に寄せた分、
将来それらの repo が jp-go-dds へ移る際の差分は小さくなる。

**ただし、これ以上この repo に投資する理由にはならない。** 追加の component を
足すより、consumer を jp-go-dds へ移す方が正しい。

## 残っている作業

1. **fleet-db への吸収**（`fleet reconcile`）。pin 前進は west.yml に載ったが、
   fleet-db（Phase 1.5 の上流正本）へは未吸収。GitHub Actions 撤去
   （ADR-2607300900）以降これは手作業で、しかも**このセッションの変更だけでなく
   workspace 全体の drift を吸収する**操作なので、変更される全 pin の
   fast-forward 確認とセットでないと危険（AGENTS.md に退行を焼き込んだ実例あり）。
   ここでは意図的に実行していない。
2. **ブラウザでの実描画確認**（上記）。`docs/index.html` は再生成済み。
3. **`.kotoba` port**: `kotoba/tokens_core.kotoba` に新 token group
   （`:focus` / `:status`、`:ink :on-accent`）は未 port。parity gate は cljc 側の
   map から case を生成するため緑のまま通るので、これは gate の穴ではなく
   proving slice の範囲外という位置づけ。
