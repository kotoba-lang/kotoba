# manimani-experience-ui

「見れば分かる。触れば応える。流れが見える。失敗しても戻れる。使うほど愛着が生まれる。」

`manimani-experience-ui` は、GitHub上の仕事を **Issue → Agent → PR → Actions → Receipt** と進める manimani のための、UI/UX設計規定です。Apple HIGとWCAGを基礎品質に使い、Nintendo Laboなどの公開された開発事例から学んだ「作る・遊ぶ・分かる」「操作そのものを楽しくする」という考えを、独自の **Kinetic Companion UI（随伴玩具UI）** に落とし込みます。

これはNintendoの公式ガイドラインではなく、同社の商標・キャラクター・画面表現を模倣するものでもありません。公開資料から抽出した一般原則を、manimani固有の文脈へ再構成しています。

## 読む順番

1. [Experience Guidelines](docs/guidelines.md) — 判断原則とレビュー基準
2. [Foundation UI](docs/foundation-ui.md) — 読める・押せる・戻れるための基礎UI
3. [Experience UI](docs/experience-ui.md) — まにまに君、運動、手応え、報酬
4. [GitHub journey](docs/github-journey.md) — Home / Inbox / Walk / Chatの動線
5. [Sources](docs/sources.md) — 公式資料と、そこからの推論
6. [Computational measurement](docs/measurement.md) — 数理モデル、実験、release gate
7. [Navigation and shell](docs/navigation-and-shell.md) — tab motion、Chat、Launch、Profile、Settings
8. [WebView agent boundary](adr/0002-webview-agent-loop-boundary.md) — Kotoba Shell、Codex CLI、loopの安全境界

実装で参照する正規データは [`design/tokens.edn`](design/tokens.edn)、[`design/motion.edn`](design/motion.edn)、[`design/metrics.edn`](design/metrics.edn)、[`design/color-analysis.edn`](design/color-analysis.edn)、並列agent topologyの [`design/agent-loops.edn`](design/agent-loops.edn) です。主要4画面は [`design/manimani-app.svg`](design/manimani-app.svg)、Launch / Profile / Settingsは [`design/manimani-system.svg`](design/manimani-system.svg)、並列agent体験は [`design/manimani-loom.svg`](design/manimani-loom.svg)、30 agentの高密度表示は [`design/manimani-loom-density.svg`](design/manimani-loom-density.svg)、個別agentとのコード会話は [`design/manimani-agent-chat.svg`](design/manimani-agent-chat.svg) です。小サイズの正規マスターは [`design/manimani-icon.svg`](design/manimani-icon.svg)、十牛図に基づく10状態は [`design/manimani-ten-ox-logos.svg`](design/manimani-ten-ox-logos.svg) です。変更理由は [`adr/0001-kinetic-companion-ui.md`](adr/0001-kinetic-companion-ui.md)、常時守る制約は [`rules/experience.rules.md`](rules/experience.rules.md) にあります。

## 二層モデル

| 層 | 目的 | 失敗してはいけないこと |
|---|---|---|
| Foundation UI | 情報を正確、安全、アクセシブルに操作する | private/public、blocker、実行状態、破壊操作を曖昧にする |
| Experience UI | 行為に手応え、発見、愛着を与える | キャラクターや演出が仕事の状態を隠す、遅らせる、誤認させる |

**配分の目安は Foundation 70% / Companion behavior 20% / Reward 10%。** 業務UIの明快さを保ちつつ、重要な瞬間にだけ遊びを濃くします。

## License

MIT. Nintendo、Nintendo Labo、Apple、GitHub等の名称・商標は各権利者に帰属します。

## WebView preview

The interactive implementation is CLJS + Reagent + shadow-cljs, with
component styles extracted by shadow-css.

```bash
npm install
npm run dev
# open http://localhost:8028
```

`npm run build` emits the release JavaScript and extracted CSS under `public/`.
