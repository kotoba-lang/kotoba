# ADR 0004: ブラウザ / WebGPU 実行経路

- Status: Accepted
- Date: 2026-06-24
- 関連: 0001 (StyleIR), 0002 (renderer)

## 背景

Gemma 4 vision はブラウザで **WebGPU** を使うのが最速 (API キー不要・データ非
送信)。だが Node 経路は (a) ラスタライズに native `@resvg/resvg-js` を使い、
(b) CLI が `node:fs` を読む。これらはブラウザで動かない。抽出/描画/svgraph 出力
自体は isomorphic (fflate + fast-xml-parser) なので、ブラウザ専用の薄い層だけ
分離すればよい。

## 決定

- **ラスタライザを差し替え可能にする**。`pipeline` の各推論関数は
  `opts.rasterize?` を受け取り、既定は Node の `@resvg/resvg-js`、ブラウザは
  `rasterizeSvgBrowser` (OffscreenCanvas/Image, DOM 型非依存) を注入する。
- **ブラウザ入口 `src/browser.ts`** を用意し、Node 専用 (cli, @resvg) を含めない。
  `analyzeDeck(bytes)` 一発で、抽出 → 実スライドを canvas で raster →
  **WebGPU + q4f16** の Gemma vision → デッキトーン集約まで行う。
  device/dtype の既定を `webgpu`/`q4f16` にする (Node 既定は `cpu`/`q4`)。
- `package.json` の `exports` に `./browser` サブパスを公開。

## 代替案

- **全経路を 1 エントリに**: bundler が native `@resvg` を解決しようとして壊れる。
  ラスタライザ注入で分離する方が安全。
- **rasterize を完全に動的 import に**: pipeline は静的 import だが native の
  `@resvg` は関数内で動的 import するため、ブラウザ bundle に native は載らない
  (呼ばれもしない)。現状の静的 import で十分。

## 帰結

- ブラウザでは `@com-junkawasaki/office-style/browser` の `analyzeDeck` を呼ぶ。
- ブラウザ入口は Node でも import 時に例外を出さない (canvas は関数内でのみ参照)。
- 実機 (WebGPU) E2E 検証は今後 (最小 Vite/Worker harness)。Node 経路の vision は
  実機検証済み (CPU/q4, 3.8GB モデル)。
