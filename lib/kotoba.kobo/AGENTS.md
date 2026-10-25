# AGENTS.md — kobo

`kobo` は Kotoba の **workbench**: editor / terminal / grant / receipt の
モデル（純 `.cljc`）、read-only の console、そして実行と配信を担う host 層
（ClojureScript / nbb）。terminal のモデル本体は
[`kuro`](https://github.com/kotoba-lang/kuro)。

## この repo で最初に読むもの

- `README.md` の「Not yet built」。**何が無いかを知らずに足すと重複する。**
- 設計の正本は superproject の
  `90-docs/adr/2606301000-kotoba-kobo-kuro-terminal-editor.edn`。

## 越えてはいけない線

### 1. UI は design system の外に出ない

`kobo.ui` は `kotoba-ui.core` と `appkit.core` **だけ**を require する
（`liquid-glass.*` / `shitsuke.*` を直接触らない）。生の hex・px の font-size・
font-family を app 側に書かない —— 色と型は token（`var(--hig-*)`）から取る。
layout は `kotoba-ui.shell` の scaffold から組む。

`test/kobo/ui_source_test.cljk` がこれをソーステキストに対して検査する。
**render 結果は誰が書いた CSS かを見ない**ので、design-quality のスコアが
100 でもこの規律の遵守は証明されない。両方要る。

端末 16 色も token に寄せる。任意の RGB を span に流すと、design system が
保証しているコントラストの外に出る（256色/truecolor は色を落として文字を残す
—— **読めない忠実さより、読める近似**）。

### 2. console の write surface は opt-in

`(ui/view wb {:write-surface? true})` を明示したときだけ command bar が出る。
既定は read-only（kotoba-lang の 23 repo が使う operator console 規約と同じ
用途を塞がないため）。

**「どこにも送れない入力欄は無い方がまし」**という判断で read-only にした経緯が
あるので、送り先が無い操作を足さない。逆に送り先ができたなら規約を見直してよい
（2026-08-04 に stdin/kill が入ったときそうした）。

### 3. `kobo.server` は 127.0.0.1 から動かさない

任意コマンドを起こす HTTP 面なので、bind アドレスを広げた瞬間に LAN に対する
遠隔実行になる。**`--host` フラグを作らない** ——「あとで 0.0.0.0 にできる」形は
いつか誰かがそうする。書き込み経路の `X-Kobo-Token` **ヘッダ**必須も外さない
（カスタムヘッダは preflight を強制するので CSRF 対策を兼ねる）。token を
URL に載せない（履歴に残る）。

これは**隔離ではない**。走らせたコマンドはこのマシンのディスクと network に
触れる。README と docstring のその記述を弱めない。

### 4. `:kobo/running` と `:kobo/receipts` を混ぜない

「まだ終わっていない」と「終わって exit 0」は別の事実。同じ列に積むと読み手が
取り違える。拒否（`:kobo/denials`）も同様に別で持つ —— 落とすと「receipt が
空」という 1 つの見た目が「拒否された」と「誰も打っていない」の両方を意味する。

### 5. deps は git 座標。`:local/root` を `:deps` に書かない

`:local/root` は consumer の gitlibs 基準で解決されるので、monorepo の外から
consume できなくなる。sibling checkout で作業したいときは `-M:local` で
override する。CI は git 経路で走り、**「隣で compile できる」ではなく
「外から consume できる」**を証明する。

例外は `:browser-render` alias（`kotoba-lang/browser` は dom-gpu ↔ cssom ↔
htmldom の `:local/root` 循環があり git 座標で表現できない）。**継承した制約**
なので、その旨を書いた上で別 alias / 別 path に隔離してある。

## テスト

```sh
kbb -M:test                   # モデル + console + design-quality gate（JVM）
npm install && npm run test:host  # host 配線と HTTP サーバ（nbb、実際に spawn する）
npm run test:browser-render       # console を kotoba-lang/browser で描く（monorepo のみ）
```

browser-render gate は「自分の道具で自分の道具が動く」ことの確認。
ここが落ちたら、UI がエンジンで描けなくなったということ。

## browser glue だけは生の JavaScript

`kobo.server` の `browser-glue`（fetch + EventSource + innerHTML 差し替え、
約 20 行）は、kobo に browser 向け cljs ビルドが無いための暫定。**非正典**
として扱う —— **ここにロジックを足さない**。分岐が要るようになったら、それが
cljs ビルドを入れるかどうかを決める合図。

## 変更を出すとき

superproject の pin 前進は
`kbb --backend sci --classpath ".:scripts/nbb_compat" scripts/west-pin-put.cljs kobo <sha>`。
手で west.yml を編集しない。
