# office-style ドキュメント

`@com-junkawasaki/office-style` — pptx からスライドのトーン・マナー・スタイルを
抽出し単一の **StyleIR** に正規化する。

## 目次

- [アーキテクチャ](./architecture.md) — データフロー / モジュール構成 / 設計原則
- [StyleIR スキーマ](./ir-schema.md) — `style-ir/1` の全フィールドと svgraph 対応
- [実装状況 (STATUS)](./STATUS.md) — 機能マトリクス / 検証結果 / 今後
- ランディングページ: [`index.html`](./index.html)

## ADR (Architecture Decision Records)

- [0001 — StyleIR (2 層 IR)](./adr/0001-style-ir.md)
- [0002 — スライドレンダラと slide-master 継承](./adr/0002-slide-renderer.md)
- [0003 — svgraph 相互運用 (2 出力シェイプ)](./adr/0003-svgraph-interop.md)
- [0004 — ブラウザ / WebGPU 経路](./adr/0004-browser-webgpu.md)

## クイックリンク

- 使い方 / CLI / API: ルートの [`../README.md`](../README.md)
- 型の正本: [`../src/types.ts`](../src/types.ts)
- 検証: `npm test` / `npm run verify:svgraph` / `npm run verify:real`
