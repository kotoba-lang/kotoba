# JUN-133 item 3 周辺 — file: リンク未解決の根因（2026-10-20 実測）

> **注記（2026-10-20 同日、owner 決定）**: TS SDK は prune 済み
> （kotoba + amu selfhost に一本化）。本文書は SDK 撤去前の観測記録として
> 残す（file: リンクの深さ前提の教訓は他の linked パッケージにも有効）。

## 症状

worktree で `npm install --ignore-scripts` 後も `@kotoba-lang/xrpc` /
`@kotoba-lang/did-etzhayyim` / `@kotoba-lang/sdk` が解決できず、vitest の
8 ファイルがロードできなかった（「Failed to load url @kotoba-lang/xrpc/...」）。

## 根因（実測で確定）

package.json の `file:../../../xrpc` は **npm が `node_modules/@kotoba-lang/xrpc`
のシンボリックリンクを相対パス `../../../../../xrpc` で張る**。この相対は
「repo が `<org>/<repo>/<sub>` の深さに居る」（例:
`github/kotoba-lang/kotodama-host/sdk/kotodama-host-sdk`）ときにのみ、
`github/kotoba-lang/xrpc` に正しく解決する。

worktree は `github/wt/hermes/<task>/...` と**深さが違う**ため、同じ相対が
`wt/hermes/xrpc` を指し、存在せずリンク切れになる
（`readlink -f node_modules/@kotoba-lang/xrpc` → `/Users/junkawasaki/github/wt/hermes/xrpc`）。

## 吸収（worktree 運用の慣行）

worktree を `wt/hermes/<task>/` に作る運用では、**`wt/hermes/` に sibling
シムリンクを張って深さ差を吸収**する:

```sh
ln -sfn /Users/junkawasaki/github/kotoba-lang/xrpc          /Users/junkawasaki/github/wt/hermes/xrpc
ln -sfn /Users/junkawasaki/github/kotoba-lang/sdk           /Users/junkawasaki/github/wt/hermes/sdk
ln -sfn /Users/junkawasaki/github/kotoba-lang/did-etzhayyim /Users/junkawasaki/github/wt/hermes/did-etzhayyim
```

## 吸収後の実測

- ロード失敗 8 ファイル → **4 ファイル**に減少。
- **Tests 313 passed / 2 failed (315)**（吸収前: 195 passed / 0 failed —
  ロードできていた分だけ。全対象は 315 件）。
- 残る 4: drainer-encryption / drainer-lifecycle（ファイルロード失敗 —
  別の未解決依存の可能性）、xrpc-client の legacy nsid スキップ、
  xrpc-handler の end-to-end（挙動差 = 次スライス）。

## 本質的解決（残る選択肢）

1. linked パッケージを registry 配布に切り替え（file: を廃止）。
2. worktree 作成手順に sibling シムリンクを組み込み（本「吸収」を慣行化）。
3. package.json の file: を絶対パス化（環境固定 — 非推奨）。

## 追記（2026-10-20 同日、実測）— sibling シムリンクの「陳腐化」

drainer-encryption / drainer-lifecycle のロード失敗は、sibling シムリンクの
**指し先が古い checkout だった**ことが原因だった（`@kotoba-lang/sdk` の
main checkout は PR #3（dist 同梱）より前の commit に居て、`main:
./dist/index.js` が存在せず "Failed to resolve entry"）。

吸収の補強: sibling シムリンクは **main に追随した worktree** を指す。

```sh
git -C /Users/junkawasaki/github/kotoba-lang/sdk fetch https://github.com/kotoba-lang/sdk.git main
git -C /Users/junkawasaki/github/kotoba-lang/sdk worktree add /Users/junkawasaki/github/wt/hermes/_sdk-main FETCH_HEAD
ln -sfn /Users/junkawasaki/github/wt/hermes/_sdk-main /Users/junkawasaki/github/wt/hermes/sdk
```

これで **Test Files 28/28、Tests 324/324 全通過**（本プログラムで初の
フルグリーン）。xrpc / did-etzhayyim も同様に main 追随 worktree を指すのが
望ましい（現状は main checkout のままで通っている）。
